# Rome Bus Tracker
=================

Lightweight backend to combine GTFS static data and GTFS-RT feeds for displaying arriving buses at stops in Rome.

Features
--------
- Load full static GTFS (stops, routes, trips, stop_times) and keep it updated when the GTFS zip changes
- Poll GTFS-RT feeds (vehicle positions, trip updates, service alerts) and broadcast live updates
- Endpoints to search stops, find nearby stops, and list arriving buses (real-time + scheduled)

Quickstart
----------
Prerequisites
- Python 3.10+ (virtualenv recommended)
- A `.env` file with feed URLs (see Env configuration below)

Install

```bash
cd Rome-Bus-Tracker
python -m venv backend/venv
source backend/venv/bin/activate
pip install -r backend/requirements.txt
```

Environment variables
---------------------
Create a `.env` file in the project root with values for at least the GTFS-RT and static GTFS URLs:

- `VEHICLE_POSITIONS_URL` — GTFS-RT vehicle positions feed
- `TRIP_UPDATES_URL` — GTFS-RT trip updates feed
- `SERVICE_ALERTS_URL` — GTFS-RT service alerts feed
- `STATIC_GTFS_URL` — full static GTFS zip URL
- `STATIC_GTFS_MD5_URL` — URL returning the MD5 (or etag/text) for the GTFS zip (used to check updates)
- `OUTDIR` — (optional) directory for inspect/samples output (default `backend/data`)
- `FEED_POLL_INTERVAL` — seconds between RT feed polls (default `60`)
- `MD5_CHECK_INTERVAL` — seconds between static GTFS MD5 checks (default `300`)

Running the server (development)
--------------------------------
Start with uvicorn from repo root:

```bash
# run with autoreload; serve FastAPI app defined in backend/main.py
uvicorn backend.main:app --reload --port 8000
```

Key API endpoints
-----------------
- `GET /stops?q=...` — search stops by name (max 20 results)
- `GET /stops/nearest?lat=<lat>&lng=<lng>` — nearest stop to coordinates
- `GET /stops/nearby?lat=<lat>&lng=<lng>&radius=<meters>` — all stops within radius (default 1000m)
- `GET /stops/{stop_id}` — stop metadata
- `GET /stops/{stop_id}/arriving-buses` — returns `realtime_buses` and `scheduled_buses` for the stop
- `GET /stops/{stop_id}/incoming` — legacy endpoint returning realtime buses only

Example: show arriving buses at a stop

```bash
curl http://localhost:8000/stops/73211/arriving-buses
```

What the API returns
--------------------
- `realtime_buses`: vehicles present in the GTFS-RT vehicle positions feed. Each entry contains:
	- `vehicle_id`, `route_short_name`, `stops_remaining`, `current_stop_name`, `minutes_until_arrival`, `arrival_time`, `lat`, `lng`, `is_realtime: true`
- `scheduled_buses`: upcoming scheduled trips (from trip_updates when available, otherwise falling back to static `stop_times.txt`) with `minutes_until_arrival` and `is_realtime: false`
- `alerts`: active service alerts affecting the stop

Debugging & local testing
-------------------------
- Use `backend/inspect_feeds.py` to fetch and sample feeds (it writes JSON samples to `backend/data`).
- Use `backend/debug_stop.py` to inspect what trips and updates are available for a stop.

Notes & behavior
----------------
- The app polls GTFS-RT feeds every `FEED_POLL_INTERVAL` seconds (default 60s).
- The app checks the static GTFS MD5 every `MD5_CHECK_INTERVAL` seconds (default 300s) and reloads static GTFS only when changed.
- If `trip_updates` parsing fails, the server falls back to static GTFS `stop_times.txt` for scheduled times where possible.

Extending the project
---------------------
- Add a small frontend to visualize stops and buses on a map (use `realtime_buses` for live positions)
- Improve trip_update parsing and validation to handle different provider message shapes
- Add caching, rate-limiting, and basic auth for production

Files of interest
-----------------
- `backend/main.py` — FastAPI app and background polling loops
- `backend/feed.py` — fetch + decode GTFS-RT
- `backend/static_gtfs.py` — download + parse static GTFS zip and build indices
- `backend/matcher.py` — core logic to compute stops remaining, nearest stops, scheduled/realtime merging
- `backend/store.py` — in-memory application store
- `backend/inspect_feeds.py` — standalone script to sample feeds for debugging
- `backend/debug_stop.py` — helper to debug a specific stop

License
-------
See `LICENSE` in the repository root.
