"""Offline local-network prototype for a passenger stop request queue."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import json
import hmac
import secrets
import threading
import time
import uuid
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
STAGES = [
    "Ngara",
    "Roysambu",
    "Githurai",
    "Kahawa Wendani",
    "Kahawa Sukari",
    "KU",
    "Bypass",
    "Kihunguro",
    "Ruiru",
    "K-Road",
    "Juja",
    "Thika",
]
requests = []
lock = threading.Lock()
last_change = 0
started = time.time()
last_seen = {"passenger": None, "driver": None}
CONFIG_FILE = ROOT / "vehicle_config.json"
DEFAULT_CONFIG = {"vehicle_id": "MAT-001", "sacco": "Unassigned", "monthly_fee": 10, "currency": "USD", "billing_status": "Due", "fleet_url": "", "fleet_token": ""}
try:
    config = {**DEFAULT_CONFIG, **json.loads(CONFIG_FILE.read_text(encoding="utf-8"))}
except (OSError, ValueError):
    config = DEFAULT_CONFIG.copy()
if not config.get("admin_key"):
    config["admin_key"] = secrets.token_urlsafe(24)
    CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")
sync_status = {"last_success": None, "error": ""}


def fleet_sync_loop():
    while True:
        with lock:
            current = config.copy()
            requested = {item["stage"] for item in requests}
            pending = sum(1 for stage in STAGES if stage in requested)
            screens = {name: bool(last_seen[name] and time.time() - last_seen[name] < 30) for name in last_seen}
            running_for = int(time.time() - started)
        if current.get("fleet_url") and current.get("fleet_token"):
            try:
                url = current["fleet_url"].rstrip("/") + "/api/checkin"
                payload = json.dumps({"passenger_screen": screens["passenger"], "driver_screen": screens["driver"],
                                      "pending_stops": pending, "uptime_seconds": running_for}).encode()
                req = urllib.request.Request(url, data=payload, headers={"Authorization": "Bearer " + current["fleet_token"],
                                                                         "Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=8) as response:
                    if response.status == 200:
                        sync_status.update({"last_success": time.time(), "error": ""})
                    else:
                        sync_status["error"] = f"Fleet server returned {response.status}"
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                sync_status["error"] = str(exc)[:160]
        time.sleep(60)


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self._send(200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/state":
            screen = urlparse(self.path).query
            screen = screen.split("=", 1)[1] if screen.startswith("screen=") else ""
            with lock:
                if screen in last_seen:
                    last_seen[screen] = time.time()
                requested = {item["stage"] for item in requests}
                unique = [stage for stage in STAGES if stage in requested]
                single = [stage for stage in unique if sum(1 for item in requests if item["stage"] == stage) == 1]
                safe_config = {key: value for key, value in config.items() if key not in ("admin_key", "fleet_token")}
                safe_config["fleet_sync_configured"] = bool(config.get("fleet_url") and config.get("fleet_token"))
                state = {"stages": STAGES, "queue": unique, "single": single, "updated": last_change,
                         "screens": last_seen.copy(), "config": safe_config, "uptime": int(time.time() - started),
                         "fleet_sync": sync_status.copy()}
            self._send(200, json.dumps(state))
        else:
            self._send(404, "Not found")

    def do_POST(self):
        global last_change
        path = urlparse(self.path).path
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        except (ValueError, json.JSONDecodeError):
            self._send(400, json.dumps({"error": "Invalid request"})); return
        with lock:
            if path == "/api/select":
                stage = payload.get("stage")
                if stage not in STAGES:
                    self._send(400, json.dumps({"error": "Unknown stage"})); return
                item = {"id": uuid.uuid4().hex, "stage": stage, "created": time.time()}
                requests.append(item)
                last_change = time.time()
                result = {"id": item["id"], "stage": stage}
            elif path == "/api/undo":
                item_id = payload.get("id")
                latest = requests[-1] if requests else None
                if latest and latest["id"] == item_id and time.time() - latest["created"] <= 10:
                    requests.pop()
                    last_change = time.time()
                    result = {"ok": True}
                else:
                    self._send(409, json.dumps({"error": "This request can no longer be undone"})); return
            elif path == "/api/serve":
                stage = payload.get("stage")
                if stage not in STAGES:
                    self._send(400, json.dumps({"error": "Unknown stage"})); return
                requests[:] = [item for item in requests if item["stage"] != stage]
                last_change = time.time()
                result = {"ok": True}
            elif path == "/api/skip":
                stage = payload.get("stage")
                matches = [item for item in requests if item["stage"] == stage]
                if len(matches) != 1:
                    self._send(409, json.dumps({"error": "This stop has more than one request"})); return
                requests.remove(matches[0])
                last_change = time.time()
                result = {"ok": True}
            elif path == "/api/admin/config":
                supplied = self.headers.get("Authorization", "").removeprefix("Bearer ")
                if not hmac.compare_digest(supplied, config["admin_key"]):
                    self._send(401, json.dumps({"error": "Enter the local admin key shown in the server window"})); return
                vehicle_id = str(payload.get("vehicle_id", "")).strip()[:32]
                sacco = str(payload.get("sacco", "")).strip()[:64]
                billing_status = payload.get("billing_status")
                if not vehicle_id or not sacco or billing_status not in ("Paid", "Due"):
                    self._send(400, json.dumps({"error": "Enter a vehicle ID, SACCO, and billing status"})); return
                config.update({"vehicle_id": vehicle_id, "sacco": sacco, "billing_status": billing_status,
                               "monthly_fee": 10, "currency": "USD",
                               "fleet_url": str(payload.get("fleet_url", "")).strip().rstrip("/")[:256]})
                new_token = str(payload.get("fleet_token", "")).strip()[:160]
                if new_token:
                    config["fleet_token"] = new_token
                CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")
                result = {"ok": True, "config": config.copy()}
            else:
                self._send(404, json.dumps({"error": "Not found"})); return
        self._send(200, json.dumps(result))

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8080
    threading.Thread(target=fleet_sync_loop, daemon=True).start()
    print(f"Offline stop queue running on port {port}; fleet sync runs every 60 seconds when configured.")
    print(f"Local admin key: {config['admin_key']}")
    print("Open http://<this-device-LAN-IP>:8080/?screen=passenger or ?screen=driver")
    ThreadingHTTPServer((host, port), Handler).serve_forever()

