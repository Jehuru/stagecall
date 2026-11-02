"""Central StageCall fleet dashboard prototype (Python standard library only)."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(ROOT))).expanduser()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATA_FILE = DATA_DIR / "fleet_data.json"
LOCK = threading.Lock()
ADMIN_KEY = os.environ.get("STAGECALL_ADMIN_KEY")
if not ADMIN_KEY and os.environ.get("PORT"):
    raise RuntimeError("STAGECALL_ADMIN_KEY must be configured for hosted deployments")
if not ADMIN_KEY:
    ADMIN_KEY = secrets.token_urlsafe(24)
    print("Temporary admin key (set STAGECALL_ADMIN_KEY to keep a stable key):")
    print(ADMIN_KEY)
try:
    records = json.loads(DATA_FILE.read_text(encoding="utf-8"))
except (OSError, ValueError):
    records = {}


def save_records():
    temporary_file = DATA_FILE.with_suffix(".tmp")
    temporary_file.write_text(json.dumps(records, indent=2), encoding="utf-8")
    os.replace(temporary_file, DATA_FILE)


class Handler(BaseHTTPRequestHandler):
    def send_body(self, status, body, content_type="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))

    def is_admin(self):
        supplied = self.headers.get("Authorization", "").removeprefix("Bearer ")
        return hmac.compare_digest(supplied, ADMIN_KEY)

    def authorized_vehicle(self):
        supplied = self.headers.get("Authorization", "").removeprefix("Bearer ")
        supplied_hash = hashlib.sha256(supplied.encode()).hexdigest()
        for record in records.values():
            if hmac.compare_digest(supplied_hash, record["token_hash"]):
                return record
        return None

    def public_record(self, record):
        return {key: value for key, value in record.items() if key != "token_hash"}

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/healthz":
            self.send_body(200, json.dumps({"ok": True}))
        elif path == "/":
            self.send_body(200, (ROOT / "fleet.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/vehicles":
            if not self.is_admin():
                self.send_body(401, json.dumps({"error": "Admin key required"})); return
            with LOCK:
                payload = [self.public_record(record) for record in records.values()]
            self.send_body(200, json.dumps(payload))
        else:
            self.send_body(404, "Not found")

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self.read_json()
        except (ValueError, json.JSONDecodeError):
            self.send_body(400, json.dumps({"error": "Invalid JSON"})); return

        if path == "/api/checkin":
            with LOCK:
                record = self.authorized_vehicle()
                if not record:
                    self.send_body(401, json.dumps({"error": "Unknown vehicle token"})); return
                record["last_seen"] = time.time()
                record["screens"] = {"passenger": bool(payload.get("passenger_screen")),
                                      "driver": bool(payload.get("driver_screen"))}
                record["pending_stops"] = max(0, min(999, int(payload.get("pending_stops", 0))))
                record["uptime_seconds"] = max(0, int(payload.get("uptime_seconds", 0)))
                save_records()
            self.send_body(200, json.dumps({"ok": True})); return

        if not self.is_admin():
            self.send_body(401, json.dumps({"error": "Admin key required"})); return
        with LOCK:
            if path == "/api/register":
                vehicle_id = str(payload.get("vehicle_id", "")).strip()[:32]
                sacco = str(payload.get("sacco", "")).strip()[:64]
                if not vehicle_id or not sacco:
                    self.send_body(400, json.dumps({"error": "Vehicle ID and SACCO are required"})); return
                if vehicle_id in records:
                    self.send_body(409, json.dumps({"error": "That vehicle ID is already registered"})); return
                token = secrets.token_urlsafe(32)
                record = {"vehicle_id": vehicle_id, "sacco": sacco, "monthly_fee": 10, "currency": "USD",
                          "billing_status": "Due", "last_seen": None, "screens": {"passenger": False, "driver": False},
                          "pending_stops": 0, "uptime_seconds": 0,
                          "token_hash": hashlib.sha256(token.encode()).hexdigest()}
                records[vehicle_id] = record
                save_records()
                self.send_body(201, json.dumps({"vehicle_id": vehicle_id, "token": token})); return
            if path == "/api/billing":
                vehicle_id = str(payload.get("vehicle_id", ""))
                status = payload.get("billing_status")
                if vehicle_id not in records or status not in ("Paid", "Due"):
                    self.send_body(400, json.dumps({"error": "Unknown vehicle or invalid billing status"})); return
                records[vehicle_id]["billing_status"] = status
                save_records()
                self.send_body(200, json.dumps({"ok": True})); return
        self.send_body(404, json.dumps({"error": "Not found"}))

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", os.environ.get("STAGECALL_PORT", "8090")))
    print(f"StageCall fleet dashboard listening on port {port}.")
    print("For internet use, publish behind HTTPS and keep the admin key and vehicle tokens private.")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()

