# StageCall prototype

An offline, local-network prototype for passenger stop requests. The passenger display lists route stages; the driver display shows a queue of requested stages without counts.

## Run it

1. Install Python 3 on the device that will act as the vehicle's local server.
2. Connect the server device and both display devices to the same local Wi-Fi network. This network does not need internet access. A small router or a phone hotspot can provide the local network.
3. From this folder, run `python server.py`.
4. Find the server device's local IP address, then open these URLs on the screens:
   - Passenger screen: `http://SERVER-IP:8080/?screen=passenger`
   - Driver screen: `http://SERVER-IP:8080/?screen=driver`
   - Vehicle admin screen: `http://SERVER-IP:8080/?screen=admin`

Keep the server running while the vehicle uses the prototype. If Windows Firewall prompts, allow Python on the private local network so the other screens can connect.

## Current behavior

- Passenger taps add requests immediately.
- The driver sees each requested stage once, in the configured route order.
- A passenger can undo their most recent selection for 10 seconds, provided nobody has made a later selection.
- The conductor can mark a stage served. A stage with only one outstanding request can also be marked “No longer needed”; when multiple passengers requested it, it stays in the queue.
- Refreshing either screen does not lose the queue; the server holds it in memory until it is stopped.

The route stages in `server.py` are configured from Nairobi CBD toward Thika: Ngara, Roysambu, Githurai, Kahawa Wendani, Kahawa Sukari, KU, Bypass, Kihunguro, Ruiru, K-Road, Juja, and Thika.

The vehicle admin screen records an ID, SACCO, and a manual billing status at $10 USD/month. It also accepts a central fleet service URL and vehicle sync token. Vehicle details are saved in `vehicle_config.json`; stop requests and screen check-in times remain in memory. A local admin key is printed by `server.py` on startup and is required to change vehicle settings. Secret values are excluded from the passenger/driver state API.

## Central fleet dashboard prototype

`fleet_server.py` is the separate central service. It holds multiple vehicle registrations in `fleet_data.json`, displays last check-in time and screen status, and lets the admin mark the monthly maintenance charge paid or due. Each vehicle checks in once per minute when it has internet. Stop requests continue working on the local vehicle network if the internet is unavailable.

For a same-Wi-Fi demonstration, run `python fleet_server.py` on a computer and open `http://localhost:8090`. The console prints a temporary central admin key. Register each vehicle, copy its one-time token, then enter the dashboard URL and token in the vehicle's local admin screen. The vehicle's ID and SACCO should match the registration. For a local same-computer demo, the dashboard URL can be `http://localhost:8090`; if the bus server is on another device, use the central computer's LAN IP instead. The vehicle server prints a local admin key when it starts; enter that key when saving its settings.

To keep the central admin key stable when restarting the service in PowerShell, set it before launch: `$env:STAGECALL_ADMIN_KEY = "your-long-random-secret"`.

For real remote monitoring across mobile networks, the central service must be hosted at a stable public address with HTTPS. The included Python service is a prototype and does not provide HTTPS, user accounts, automated invoices, or payment processing. Do not expose it directly to the public internet; use a properly secured HTTPS host before deploying to paying SACCOs. The admin key and vehicle tokens grant access and should be kept private.

