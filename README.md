# StageCall prototype

An offline, local-network prototype for passenger stop requests. The passenger display lists route stages; the driver display shows a queue of requested stages without counts.

## Current behavior

- Passenger taps add requests immediately.
- The driver sees each requested stage once, in the configured route order.
- A passenger can undo their most recent selection for 10 seconds, provided nobody has made a later selection.
- The conductor can mark a stage served. A stage with only one outstanding request can also be marked “No longer needed”; when multiple passengers requested it, it stays in the queue.
- Refreshing either screen does not lose the queue; the server holds it in memory until it is stopped.

The vehicle admin screen records an ID, SACCO, and a manual billing status at USD/month. It also accepts a central fleet service URL and vehicle sync token.
