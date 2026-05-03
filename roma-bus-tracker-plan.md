# Roma Bus Tracker — Full Build Plan

## Table of Contents
1. [Prerequisites & System Setup](#1-prerequisites--system-setup)
2. [Project Structure](#2-project-structure)
3. [Backend Setup](#3-backend-setup)
4. [Backend Files — Detail](#4-backend-files--detail)
5. [Frontend Setup](#5-frontend-setup)
6. [Frontend Files — Detail](#6-frontend-files--detail)
7. [Data Models Reference](#7-data-models-reference)
8. [API Reference](#8-api-reference)
9. [Running the Project](#9-running-the-project)
10. [Build for Production](#10-build-for-production)

---

## 1. Prerequisites & System Setup

> **WSL note:** All backend and frontend dev work runs inside WSL (Ubuntu). Android Studio and Expo Go run on Windows. The two communicate over the network — this section covers the setup for both sides.

### 1.0 WSL Setup (if not done yet)

Open PowerShell as Administrator and run:
```powershell
wsl --install
```
This installs WSL 2 with Ubuntu by default. Reboot when prompted. After reboot, open Ubuntu from the Start menu and set your username/password.

Verify WSL 2 is active:
```powershell
wsl --list --verbose
# should show VERSION 2
```

### 1.1 Python (inside WSL)

Ubuntu 22.04+ ships with Python 3.10. Install 3.11 explicitly:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
```

Verify:
```bash
python3.11 --version
```

### 1.2 Node.js (inside WSL)

Use `nvm` so you can switch Node versions without `sudo`:
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
```

Close and reopen your WSL terminal (or run `source ~/.bashrc`), then:
```bash
nvm install 20
nvm use 20
nvm alias default 20
node --version   # v20.x.x
npm --version
```

### 1.3 Expo CLI and EAS CLI (inside WSL)

```bash
npm install -g expo-cli
npm install -g eas-cli
```

Verify:
```bash
expo --version
eas --version
```

### 1.4 Git (inside WSL)

```bash
sudo apt install -y git
git --version
```

Configure your identity:
```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

### 1.5 Android Studio (on Windows, NOT inside WSL)

Android Studio must run on Windows — the Android emulator requires hardware virtualization that doesn't pass through WSL.

1. Download from https://developer.android.com/studio and install on Windows.
2. On first launch: complete the Setup Wizard, let it download the Android SDK.
3. Go to `SDK Manager → SDK Tools` — make sure `Android Emulator` and `Android SDK Platform-Tools` are checked.
4. Go to `Device Manager → Create Device` — pick a phone (e.g. Pixel 7), download a system image (API 34), finish.
5. Add `adb` to your Windows PATH: `C:\Users\<you>\AppData\Local\Android\Sdk\platform-tools`

**Connecting WSL to the Windows Android emulator:**

The emulator runs on Windows but Expo runs in WSL. You need to forward ADB over TCP:

In a Windows PowerShell (not WSL):
```powershell
adb kill-server
adb -a nodaemon server start
```

Then in WSL, add this to your `~/.bashrc` or `~/.zshrc`:
```bash
export ADB_SERVER_SOCKET=tcp:$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):5037
```

Reload: `source ~/.bashrc`

Now `adb devices` in WSL should list your running emulator.

### 1.6 Expo Go App (on your physical phone)

Install **Expo Go** from the App Store (iPhone) or Google Play (Android). This lets you test on a real device instantly by scanning a QR code — no build required.

Your phone and your Windows machine must be on the **same Wi-Fi network**. The Expo dev server runs in WSL but is exposed on Windows's IP (see Section 9 for the tunnel setup).

### 1.7 iOS Simulator

iOS simulators require macOS + Xcode. **This is not possible on WSL/Windows.** Your options:
- Test iOS using Expo Go on a physical iPhone
- Use EAS Build (cloud build) to get an `.ipa` and install it via TestFlight
- If you have a Mac available, run `npx expo start` there and connect to the same backend

---

## 2. Project Structure

Create the root folder and the two sub-projects:
```bash
mkdir roma-bus-tracker
cd roma-bus-tracker
mkdir backend
```

Final directory layout (you will create these files as you follow this plan):

```
roma-bus-tracker/
├── backend/
│   ├── venv/                    ← Python virtual environment (auto-created)
│   ├── main.py                  ← FastAPI app entry point
│   ├── feed.py                  ← GTFS-RT feed fetching & decoding
│   ├── static_gtfs.py           ← Static GTFS loading & indexing
│   ├── matcher.py               ← Business logic (ETAs, stops remaining)
│   ├── store.py                 ← In-memory state shared across modules
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── stops.py             ← /stops endpoints
│   │   ├── vehicles.py          ← /vehicles endpoints
│   │   └── alerts.py            ← /alerts endpoints
│   ├── requirements.txt
│   └── .env
└── frontend/                    ← Created by Expo CLI (see section 5)
    ├── app/
    │   ├── _layout.jsx
    │   ├── (tabs)/
    │   │   ├── _layout.jsx
    │   │   ├── map.jsx
    │   │   └── search.jsx
    │   └── stop/
    │       └── [id].jsx
    ├── components/
    │   ├── MapView/
    │   │   ├── index.native.jsx
    │   │   └── index.web.jsx
    │   ├── BusMarker.jsx
    │   ├── StopMarker.jsx
    │   ├── IncomingBusList.jsx
    │   └── AlertBanner.jsx
    ├── hooks/
    │   ├── useVehicles.js
    │   ├── useStop.js
    │   └── useAlerts.js
    ├── lib/
    │   └── api.js               ← Axios/fetch wrappers for REST calls
    ├── constants/
    │   └── config.js            ← Backend URL, map settings
    ├── package.json
    └── app.json
```

---

## 3. Backend Setup

### 3.1 Create and activate virtual environment

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows
```

You should see `(venv)` in your terminal prompt.

### 3.2 Create requirements.txt

Create the file `backend/requirements.txt` with this content:

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
httpx==0.27.0
gtfs-realtime-bindings==1.0.0
protobuf==4.25.3
python-dotenv==1.0.1
aiofiles==23.2.1
```

Install all packages:
```bash
pip install -r requirements.txt
```

### 3.3 Create .env file

Create `backend/.env`:
```
VEHICLE_POSITIONS_URL=https://romamobilita.it/sites/default/files/rome_rtgtfs_vehicle_positions_feed.pb
TRIP_UPDATES_URL=https://romamobilita.it/sites/default/files/rome_rtgtfs_trip_updates_feed.pb
SERVICE_ALERTS_URL=https://romamobilita.it/sites/default/files/rome_rtgtfs_service_alerts_feed.pb
STATIC_GTFS_URL=https://romamobilita.it/sites/default/files/rome_static_gtfs.zip
STATIC_GTFS_MD5_URL=https://romamobilita.it/sites/default/files/rome_static_gtfs.zip.md5
FEED_POLL_INTERVAL=60
MD5_CHECK_INTERVAL=300
```

---

## 4. Backend Files — Detail

### 4.1 `backend/store.py`

**Purpose:** Single shared in-memory state object that all modules read and write. Avoids circular imports and makes the live data accessible everywhere.

**Contents:**

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Vehicle:
    vehicle_id: str
    trip_id: Optional[str]
    route_id: Optional[str]
    route_short_name: Optional[str]   # resolved from static GTFS
    lat: float
    lng: float
    bearing: Optional[float]
    current_stop_sequence: Optional[int]
    timestamp: int                     # unix epoch seconds

@dataclass
class StopTimeUpdate:
    stop_id: str
    stop_sequence: int
    arrival_time: Optional[int]        # unix epoch, None if not predicted
    departure_time: Optional[int]

@dataclass
class TripUpdate:
    trip_id: str
    route_id: Optional[str]
    vehicle_id: Optional[str]
    stop_time_updates: list[StopTimeUpdate] = field(default_factory=list)

@dataclass
class ServiceAlert:
    alert_id: str
    header: str
    description: str
    affected_route_ids: list[str] = field(default_factory=list)
    affected_stop_ids: list[str] = field(default_factory=list)

@dataclass
class Stop:
    stop_id: str
    stop_name: str
    lat: float
    lng: float

@dataclass
class AppStore:
    # Live data (updated every 60s)
    vehicles: dict[str, Vehicle] = field(default_factory=dict)
    # key: trip_id
    trip_updates: dict[str, TripUpdate] = field(default_factory=dict)
    service_alerts: list[ServiceAlert] = field(default_factory=list)

    # Static GTFS data (updated on MD5 change)
    stops: dict[str, Stop] = field(default_factory=dict)
    # key: route_id, value: short name string e.g. "64"
    routes: dict[str, str] = field(default_factory=dict)
    # key: trip_id, value: route_id
    trips: dict[str, str] = field(default_factory=dict)
    # key: stop_id, value: list of (trip_id, stop_sequence) tuples
    stop_to_trips: dict[str, list[tuple[str, int]]] = field(default_factory=dict)
    # key: trip_id, value: ordered list of (stop_id, stop_sequence) tuples
    trip_to_stops: dict[str, list[tuple[str, int]]] = field(default_factory=dict)
    # set of service_ids active today
    active_service_ids: set[str] = field(default_factory=set)
    # set of trip_ids running today (pre-computed from active_service_ids)
    active_trip_ids: set[str] = field(default_factory=set)

    current_static_md5: str = ""

# Global singleton — import this in all other modules
store = AppStore()
```

---

### 4.2 `backend/static_gtfs.py`

**Purpose:** Downloads the static GTFS zip, parses the CSV files inside it, and populates the `store` with stops, routes, trips, stop_times, and active services. Called once at startup and again whenever the MD5 changes.

**Function breakdown:**

```python
import zipfile, io, csv, hashlib, datetime
import httpx
from store import store
import os
from dotenv import load_dotenv

load_dotenv()

STATIC_GTFS_URL = os.getenv("STATIC_GTFS_URL")
STATIC_GTFS_MD5_URL = os.getenv("STATIC_GTFS_MD5_URL")
```

**`async def fetch_current_md5() -> str`**
- Makes a GET request to `STATIC_GTFS_MD5_URL`
- Returns the raw text content (the MD5 hash string)
- Used to cheaply check if static data has changed

**`async def download_gtfs_zip() -> bytes`**
- Makes a GET request to `STATIC_GTFS_URL`
- Returns raw bytes of the zip file
- Called only when MD5 has changed

**`def parse_stops(zip_ref: zipfile.ZipFile) -> dict[str, Stop]`**
- Opens `stops.txt` from the zip
- Reads CSV: `stop_id, stop_name, stop_lat, stop_lon`
- Returns dict keyed by `stop_id`

**`def parse_routes(zip_ref: zipfile.ZipFile) -> dict[str, str]`**
- Opens `routes.txt` from the zip
- Reads CSV: `route_id, route_short_name`
- Returns `{route_id: route_short_name}` — e.g. `{"100": "64", "200": "40"}`

**`def parse_trips(zip_ref: zipfile.ZipFile) -> tuple[dict[str, str], dict[str, str]]`**
- Opens `trips.txt` from the zip
- Reads CSV: `trip_id, route_id, service_id`
- Returns two dicts:
  - `{trip_id: route_id}` — to look up a trip's route
  - `{trip_id: service_id}` — to filter active trips

**`def parse_calendar(zip_ref: zipfile.ZipFile) -> set[str]`**
- Opens `calendar.txt` from the zip
- Reads CSV: `service_id, monday, tuesday, ..., start_date, end_date`
- Gets today's weekday name
- Returns set of `service_id` values where today's column = "1" and today is within start/end date range
- Also handles `calendar_dates.txt` overrides (exception_type 1=added, 2=removed)

**`def parse_stop_times(zip_ref: zipfile.ZipFile) -> tuple[dict, dict]`**
- Opens `stop_times.txt` from the zip — this is the largest file, potentially millions of rows
- Reads CSV: `trip_id, stop_id, stop_sequence, arrival_time, departure_time`
- Builds and returns two dicts:
  - `stop_to_trips`: `{stop_id: [(trip_id, stop_sequence), ...]}` — for "which trips serve this stop"
  - `trip_to_stops`: `{trip_id: [(stop_id, stop_sequence), ...]}` — ordered by stop_sequence, for "stops remaining"
- Note: `arrival_time` in GTFS can be > 24:00:00 for overnight trips — parse carefully

**`async def load_static_gtfs()`**
- Calls `download_gtfs_zip()`
- Opens the zip in memory with `zipfile.ZipFile(io.BytesIO(data))`
- Calls all parse functions above
- Computes `active_trip_ids`: the intersection of trips whose `service_id` is in `active_service_ids`
- Writes everything into `store` fields
- Logs how many stops, routes, trips, stop_times were loaded

**`async def check_and_reload_if_needed()`**
- Calls `fetch_current_md5()`
- Compares to `store.current_static_md5`
- If different: calls `load_static_gtfs()`, updates `store.current_static_md5`
- If same: does nothing (cheap path, runs every 5 minutes)

---

### 4.3 `backend/feed.py`

**Purpose:** Downloads and decodes the three GTFS-RT `.pb` binary feeds. Updates `store.vehicles`, `store.trip_updates`, and `store.service_alerts`.

```python
import httpx, os
from dotenv import load_dotenv
from google.transit import gtfs_realtime_pb2
from store import store, Vehicle, TripUpdate, StopTimeUpdate, ServiceAlert

load_dotenv()

VEHICLE_POSITIONS_URL = os.getenv("VEHICLE_POSITIONS_URL")
TRIP_UPDATES_URL = os.getenv("TRIP_UPDATES_URL")
SERVICE_ALERTS_URL = os.getenv("SERVICE_ALERTS_URL")
```

**`async def fetch_pb(url: str) -> bytes`**
- Makes a GET request to the given URL with `httpx.AsyncClient`
- Sets a 30-second timeout
- Returns raw bytes
- Raises an exception (caught by callers) on HTTP error

**`def decode_vehicle_positions(raw: bytes) -> dict[str, Vehicle]`**
- Creates a `gtfs_realtime_pb2.FeedMessage` and calls `ParseFromString(raw)`
- Iterates over `feed.entity`
- For each entity where `entity.HasField("vehicle")`:
  - Extracts `vehicle.vehicle.id`, `vehicle.trip.trip_id`, `vehicle.trip.route_id`
  - Extracts `vehicle.position.latitude`, `vehicle.position.longitude`, `vehicle.position.bearing`
  - Extracts `vehicle.current_stop_sequence`, `vehicle.timestamp`
  - Looks up `route_short_name` from `store.routes` using `route_id`
  - Creates a `Vehicle` dataclass instance
- Returns dict keyed by `vehicle_id`

**`def decode_trip_updates(raw: bytes) -> dict[str, TripUpdate]`**
- Parses `FeedMessage` the same way
- For each entity where `entity.HasField("trip_update")`:
  - Extracts `trip_update.trip.trip_id`, `trip_update.trip.route_id`
  - Extracts `trip_update.vehicle.id` if present
  - Iterates `trip_update.stop_time_update` list:
    - For each: extracts `stop_id`, `stop_sequence`
    - Extracts `arrival.time` and `departure.time` (both are unix timestamps)
    - Creates `StopTimeUpdate` dataclass
  - Creates `TripUpdate` dataclass with the list of stop time updates
- Returns dict keyed by `trip_id`

**`def decode_service_alerts(raw: bytes) -> list[ServiceAlert]`**
- Parses `FeedMessage`
- For each entity where `entity.HasField("alert")`:
  - Extracts `alert.header_text.translation[0].text` (pick language "it" or first available)
  - Extracts `alert.description_text.translation[0].text`
  - Iterates `alert.informed_entity`:
    - Collects `route_id` values into `affected_route_ids`
    - Collects `stop_id` values into `affected_stop_ids`
  - Creates `ServiceAlert` dataclass
- Returns list of alerts

**`async def poll_vehicle_positions()`**
- Calls `fetch_pb(VEHICLE_POSITIONS_URL)`
- Calls `decode_vehicle_positions(raw)`
- Writes result to `store.vehicles`

**`async def poll_trip_updates()`**
- Calls `fetch_pb(TRIP_UPDATES_URL)`
- Calls `decode_trip_updates(raw)`
- Writes result to `store.trip_updates`

**`async def poll_service_alerts()`**
- Calls `fetch_pb(SERVICE_ALERTS_URL)`
- Calls `decode_service_alerts(raw)`
- Writes result to `store.service_alerts`

**`async def poll_all_feeds()`**
- Calls all three poll functions above (can be done concurrently with `asyncio.gather`)
- Called by the background task in `main.py` every 60 seconds

---

### 4.4 `backend/matcher.py`

**Purpose:** Business logic layer. Answers the app's main questions using the data in `store`.

```python
import time, math
from store import store
```

**`def haversine(lat1, lng1, lat2, lng2) -> float`**
- Computes the great-circle distance in meters between two lat/lng points
- Standard haversine formula
- Used to find the nearest stop or vehicle to a location

**`def get_incoming_buses(stop_id: str) -> list[dict]`**
- Looks up `store.stop_to_trips[stop_id]` to get all `(trip_id, stop_sequence_at_target)` tuples
- Filters to trips in `store.active_trip_ids` only
- For each trip_id:
  - Looks up `store.trip_updates.get(trip_id)` for a live `TripUpdate`
  - If found: finds the `StopTimeUpdate` for this `stop_id` in the update list
    - If `arrival_time` is in the future (> `time.time()`): include this bus
    - Compute `stops_remaining`: count of `stop_time_updates` entries before this stop that haven't been passed yet
  - If no live trip update: skip (bus not currently tracked, or static-only operator)
- For each matched live trip:
  - Find the vehicle in `store.vehicles` that has this `trip_id`
  - Build result dict: `{vehicle_id, route_short_name, arrival_time, stops_remaining, lat, lng}`
- Sort by `arrival_time` ascending
- Return the list

**`def get_stops_remaining(trip_id: str, target_stop_id: str) -> int | None`**
- Gets `TripUpdate` from `store.trip_updates.get(trip_id)`
- If not found: returns `None`
- Finds the `StopTimeUpdate` entry where `stop_id == target_stop_id`
- Finds the vehicle's `current_stop_sequence` from `store.vehicles` (matched by `trip_id`)
- Returns `target_stop_sequence - current_stop_sequence`
- If result is negative (vehicle already passed): returns 0

**`def get_nearest_stop(lat: float, lng: float) -> dict | None`**
- Iterates all stops in `store.stops`
- Computes haversine distance for each
- Returns the stop with minimum distance, plus the distance in meters

**`def get_nearest_vehicles(lat: float, lng: float, limit: int = 5) -> list[dict]`**
- Iterates all vehicles in `store.vehicles`
- Computes haversine distance for each
- Returns the `limit` closest vehicles sorted by distance
- Includes route name, distance, ETA if available

**`def get_alerts_for_stop(stop_id: str) -> list[dict]`**
- Filters `store.service_alerts` to those where `stop_id in alert.affected_stop_ids`
- Returns list of alert dicts

**`def get_alerts_for_route(route_id: str) -> list[dict]`**
- Filters `store.service_alerts` to those where `route_id in alert.affected_route_ids`
- Returns list of alert dicts

---

### 4.5 `backend/routers/stops.py`

**Purpose:** HTTP endpoints for stop search and stop detail queries.

```python
from fastapi import APIRouter, HTTPException, Query
from store import store
from matcher import get_incoming_buses, get_nearest_stop, get_alerts_for_stop

router = APIRouter(prefix="/stops", tags=["stops"])
```

**`GET /stops?q={query}`**
- Query param `q`: search string (e.g. "termini", "colosseo")
- Iterates `store.stops.values()`
- Filters: `q.lower() in stop.stop_name.lower()`
- Returns list of `{stop_id, stop_name, lat, lng}` — limit to 20 results

**`GET /stops/nearest?lat={lat}&lng={lng}`**
- Calls `get_nearest_stop(lat, lng)`
- Returns nearest stop with distance in meters

**`GET /stops/{stop_id}`**
- Looks up `store.stops.get(stop_id)`
- Returns `404` if not found
- Returns `{stop_id, stop_name, lat, lng}`

**`GET /stops/{stop_id}/incoming`**
- Calls `get_incoming_buses(stop_id)`
- Calls `get_alerts_for_stop(stop_id)`
- Returns `{buses: [...], alerts: [...]}`
- Each bus entry: `{vehicle_id, route_short_name, arrival_time, stops_remaining, lat, lng}`

---

### 4.6 `backend/routers/vehicles.py`

**Purpose:** HTTP endpoints for vehicle queries.

```python
from fastapi import APIRouter
from store import store
from matcher import get_nearest_vehicles

router = APIRouter(prefix="/vehicles", tags=["vehicles"])
```

**`GET /vehicles`**
- Returns all vehicles currently in `store.vehicles` as a list
- Each entry: `{vehicle_id, route_short_name, lat, lng, bearing, trip_id}`

**`GET /vehicles/{vehicle_id}`**
- Looks up `store.vehicles.get(vehicle_id)`
- Returns `404` if not found
- Returns full vehicle detail including trip_id and current_stop_sequence

**`GET /vehicles/nearest?lat={lat}&lng={lng}&limit={n}`**
- Calls `get_nearest_vehicles(lat, lng, limit)`
- Returns list of nearest vehicles with distance

---

### 4.7 `backend/routers/alerts.py`

**Purpose:** HTTP endpoints for service alerts.

```python
from fastapi import APIRouter
from store import store
from matcher import get_alerts_for_route

router = APIRouter(prefix="/alerts", tags=["alerts"])
```

**`GET /alerts`**
- Returns all current `store.service_alerts` as a list

**`GET /alerts/route/{route_id}`**
- Calls `get_alerts_for_route(route_id)`
- Returns filtered list for that route

---

### 4.8 `backend/main.py`

**Purpose:** FastAPI application entry point. Wires everything together: background polling tasks, WebSocket endpoint, HTTP router registration, startup/shutdown lifecycle.

```python
import asyncio, json
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

from routers import stops, vehicles, alerts
from feed import poll_all_feeds
from static_gtfs import load_static_gtfs, check_and_reload_if_needed
from store import store

load_dotenv()

FEED_POLL_INTERVAL = int(os.getenv("FEED_POLL_INTERVAL", 60))
MD5_CHECK_INTERVAL = int(os.getenv("MD5_CHECK_INTERVAL", 300))
```

**`connected_clients: set[WebSocket]`**
- Module-level set that holds all currently connected WebSocket clients
- Used by `broadcast()` to push updates to all clients simultaneously

**`async def broadcast(data: dict)`**
- Serializes `data` to JSON string
- Iterates `connected_clients`
- Calls `ws.send_text(json_str)` for each
- On `WebSocketDisconnect` or any exception: removes the client from the set
- Must handle exceptions per-client so one bad connection doesn't block others

**`async def feed_poll_loop()`**
- Infinite loop: `while True: await poll_all_feeds(); await asyncio.sleep(FEED_POLL_INTERVAL)`
- After each poll: calls `broadcast({"type": "vehicles", "data": vehicles_as_dicts})`
- Vehicles as dicts: converts `store.vehicles` to a JSON-serializable list

**`async def md5_check_loop()`**
- Infinite loop: `while True: await check_and_reload_if_needed(); await asyncio.sleep(MD5_CHECK_INTERVAL)`

**`@asynccontextmanager async def lifespan(app: FastAPI)`**
- Called once at startup and once at shutdown
- Startup block:
  1. Calls `await load_static_gtfs()` — blocks until static data is ready
  2. Calls `await poll_all_feeds()` — gets first live data immediately
  3. Starts `feed_poll_loop()` as a background task with `asyncio.create_task()`
  4. Starts `md5_check_loop()` as a background task
- Shutdown block: cancels background tasks

**`app = FastAPI(lifespan=lifespan)`**

**CORS middleware setup:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten this in production
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Router registration:**
```python
app.include_router(stops.router)
app.include_router(vehicles.router)
app.include_router(alerts.router)
```

**`@app.websocket("/ws") async def websocket_endpoint(websocket: WebSocket)`**
- Calls `await websocket.accept()`
- Adds websocket to `connected_clients`
- Immediately sends the current vehicle state so the client doesn't wait up to 60s for first data
- Enters `while True` loop calling `await websocket.receive_text()` to keep the connection alive
- On `WebSocketDisconnect`: removes from `connected_clients` and returns

---

## 5. Frontend Setup

### 5.1 Create the Expo app

From the `roma-bus-tracker` root directory:
```bash
npx create-expo-app frontend --template blank
cd frontend
```

### 5.2 Install dependencies

```bash
npx expo install expo-router react-native-safe-area-context react-native-screens expo-linking expo-constants expo-status-bar
npx expo install @tanstack/react-query axios
npx expo install @maplibre/maplibre-react-native
npx expo install maplibre-gl
npx expo install expo-location
```

For web support:
```bash
npx expo install react-dom react-native-web @expo/metro-runtime
```

### 5.3 Update app.json

In `frontend/app.json`, set the following fields:
```json
{
  "expo": {
    "name": "Roma Bus Tracker",
    "slug": "roma-bus-tracker",
    "scheme": "romabuses",
    "platforms": ["ios", "android", "web"],
    "web": {
      "bundler": "metro"
    }
  }
}
```

### 5.4 Configure Expo Router

In `frontend/package.json`, add to the `"main"` field:
```json
"main": "expo-router/entry"
```

---

## 6. Frontend Files — Detail

### 6.1 `frontend/constants/config.js`

**Purpose:** Central place for backend URLs. Change the IP here when testing on a physical device (use your local machine's IP, not `localhost`, since the phone and computer share the same network).

```js
export const API_BASE_URL = "http://192.168.x.x:8000"  // change to your machine's IP
export const WS_URL = "ws://192.168.x.x:8000/ws"

export const MAP_CONFIG = {
  initialLat: 41.9028,
  initialLng: 12.4964,
  initialZoom: 13,
  tileUrl: "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
}
```

---

### 6.2 `frontend/lib/api.js`

**Purpose:** Thin wrappers around `fetch` for each REST endpoint. Keeps URL logic out of components.

**`export async function searchStops(query)`**
- Calls `GET /stops?q={query}`
- Returns parsed JSON array of stop objects

**`export async function getNearestStop(lat, lng)`**
- Calls `GET /stops/nearest?lat={lat}&lng={lng}`
- Returns nearest stop object with `distance_meters`

**`export async function getStop(stopId)`**
- Calls `GET /stops/{stopId}`
- Returns stop object

**`export async function getIncomingBuses(stopId)`**
- Calls `GET /stops/{stopId}/incoming`
- Returns `{buses, alerts}`

**`export async function getAlerts()`**
- Calls `GET /alerts`
- Returns list of alert objects

---

### 6.3 `frontend/hooks/useVehicles.js`

**Purpose:** WebSocket hook. Maintains a live map of vehicles keyed by `vehicle_id`. Components that import this hook always have up-to-date positions without polling.

```js
import { useEffect, useRef, useState } from "react"
import { WS_URL } from "../constants/config"
```

**`export function useVehicles()`**
- `const [vehicles, setVehicles] = useState(new Map())`
  - Map from `vehicle_id` (string) to vehicle object
- `const wsRef = useRef(null)`
  - Holds the WebSocket instance across re-renders
- `const reconnectTimeout = useRef(null)`
  - Holds timeout ID for reconnection delay

**`function connect()`** (defined inside the hook)
- Creates `new WebSocket(WS_URL)`
- `ws.onopen`: logs connection, clears any reconnect timeout
- `ws.onmessage`: parses JSON, expects `{type: "vehicles", data: [...]}`
  - Builds new Map from the data array using `vehicle_id` as key
  - Calls `setVehicles(newMap)`
- `ws.onclose`: schedules reconnect after 5 seconds via `setTimeout`
- `ws.onerror`: logs error (onclose will handle reconnect)
- Stores the WebSocket in `wsRef.current`

- `useEffect`: calls `connect()` on mount, returns cleanup function that closes the socket and clears reconnect timeout

- Returns `vehicles` (the Map)

---

### 6.4 `frontend/hooks/useStop.js`

**Purpose:** Fetches and refreshes stop detail + incoming buses for a given stop ID.

```js
import { useState, useEffect } from "react"
import { getStop, getIncomingBuses } from "../lib/api"
```

**`export function useStop(stopId)`**
- `const [stop, setStop] = useState(null)`
- `const [incoming, setIncoming] = useState([])`
- `const [alerts, setAlerts] = useState([])`
- `const [loading, setLoading] = useState(true)`
- `const [error, setError] = useState(null)`

**`async function load()`** (defined inside the hook)
- Calls `getStop(stopId)` and `getIncomingBuses(stopId)` in parallel using `Promise.all`
- Updates all state variables
- Sets `loading = false`

- `useEffect`: calls `load()` immediately, then sets up a `setInterval` to call it every 30 seconds (re-fetch incoming buses periodically)
- Cleans up the interval on unmount or when `stopId` changes

- Returns `{ stop, incoming, alerts, loading, error }`

---

### 6.5 `frontend/hooks/useAlerts.js`

**Purpose:** Fetches all current service alerts once when the app mounts.

**`export function useAlerts()`**
- `const [alerts, setAlerts] = useState([])`
- `useEffect`: calls `getAlerts()` on mount, sets `alerts`
- Returns `alerts`

---

### 6.6 `frontend/components/MapView/index.native.jsx`

**Purpose:** MapLibre React Native map for iOS and Android. Renders bus markers and stop markers.

```jsx
import MapLibreGL from "@maplibre/maplibre-react-native"
```

**Props:**
- `vehicles`: Map of vehicle objects (from `useVehicles`)
- `stops`: array of stop objects to show (kept small — only visible area or searched stops)
- `onStopPress(stopId)`: callback when user taps a stop marker
- `mapRef`: forwarded ref so parent can call `flyTo()` without re-render

**Key implementation notes:**
- Use `MapLibreGL.MapView` with `ref={mapRef}`
- Use `MapLibreGL.Camera` with a `ref` — do NOT update `centerCoordinate` from state or the map will re-center on every render. Only call `cameraRef.current.flyTo(...)` imperatively.
- Render bus markers as `MapLibreGL.PointAnnotation` components, each keyed by `vehicle_id`
- For rotation, apply `style={{ transform: [{ rotate: `${bearing}deg` }] }}` to the marker icon image
- Render stop markers as `MapLibreGL.PointAnnotation` separately
- Wrap marker tap handlers with `onSelected` prop

**`function BusIcon({ bearing, routeName })`** (local to this file)
- Returns a small View with a colored circle + route name text
- Applies rotation transform using `bearing`

---

### 6.7 `frontend/components/MapView/index.web.jsx`

**Purpose:** MapLibre GL JS map for the web version. Same props interface as the native version.

```jsx
import { useEffect, useRef } from "react"
import maplibregl from "maplibre-gl"
import "maplibre-gl/dist/maplibre-gl.css"
```

**Implementation approach:**
- Use a `div` container with `useRef`
- Initialize `new maplibregl.Map(...)` inside `useEffect` on mount — store in `mapRef`
- For vehicles: maintain a `Map<vehicle_id, maplibregl.Marker>` in a ref
  - On each update: call `marker.setLngLat([lng, lat])` on existing markers
  - For new vehicles: create `new maplibregl.Marker(element).setLngLat().addTo(map)`
  - For removed vehicles: call `marker.remove()` and delete from the ref map
  - This is the key to no-reset: you never call `map.setCenter()` — only update individual markers
- For stop markers: same pattern with a separate ref map

**`function createBusElement(routeName, bearing)`** (local helper)
- Creates a DOM element (a div) styled as a bus icon with rotation
- Returns the element for use as a custom `maplibregl.Marker`

---

### 6.8 `frontend/components/BusMarker.jsx`

**Purpose:** Shared data model for how a bus is displayed. Contains the icon style logic used by both map implementations.

- Exports `BUS_COLORS`: object mapping route name prefixes to colors (e.g. all "n" prefix = night bus = dark blue)
- Exports `getRouteColor(routeShortName)`: returns a color string
- On native: used in `BusIcon` inside the native MapView
- On web: used in `createBusElement` inside the web MapView

---

### 6.9 `frontend/components/IncomingBusList.jsx`

**Purpose:** Shows the list of buses coming to a stop with ETA and stops remaining.

**Props:**
- `buses`: array of bus objects `{vehicle_id, route_short_name, arrival_time, stops_remaining}`

**Rendering:**
- Each row shows: route name badge (colored), "arrives in X min" (computed from `arrival_time - Date.now()/1000`), "N stops away"
- If `arrival_time` is within 1 minute: show "arriving now" instead
- If list is empty: show "No live buses tracked for this stop"

---

### 6.10 `frontend/components/AlertBanner.jsx`

**Purpose:** Shows service disruption warnings for a stop or route.

**Props:**
- `alerts`: array of alert objects `{header, description}`

**Rendering:**
- Renders a yellow/orange banner for each alert
- Shows `header` text prominently, `description` in smaller text below
- Dismissible per alert with a close button (use local state to track dismissed IDs)

---

### 6.11 `frontend/app/_layout.jsx`

**Purpose:** Root layout for Expo Router. Sets up the query client and tab navigation.

```jsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Stack } from "expo-router"

const queryClient = new QueryClient()

export default function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <Stack>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="stop/[id]" options={{ title: "Stop Detail" }} />
      </Stack>
    </QueryClientProvider>
  )
}
```

---

### 6.12 `frontend/app/(tabs)/_layout.jsx`

**Purpose:** Bottom tab bar with two tabs: Map and Search.

```jsx
import { Tabs } from "expo-router"

export default function TabLayout() {
  return (
    <Tabs>
      <Tabs.Screen name="map" options={{ title: "Map", tabBarIcon: ... }} />
      <Tabs.Screen name="search" options={{ title: "Search", tabBarIcon: ... }} />
    </Tabs>
  )
}
```

---

### 6.13 `frontend/app/(tabs)/map.jsx`

**Purpose:** Main map screen. Shows all live buses as markers. Tapping a stop marker opens the stop detail screen.

```jsx
import { useVehicles } from "../../hooks/useVehicles"
import MapView from "../../components/MapView"
import { useRouter } from "expo-router"
```

**Implementation:**
- `const vehicles = useVehicles()` — subscribes to live WebSocket updates
- `const router = useRouter()`
- `const mapRef = useRef(null)` — passed to MapView so it can be controlled imperatively
- Renders `<MapView vehicles={vehicles} onStopPress={(id) => router.push(`/stop/${id}`)} mapRef={mapRef} />`
- Optionally: a floating "locate me" button that calls `mapRef.current.flyTo(userLocation)` using `expo-location`

---

### 6.14 `frontend/app/(tabs)/search.jsx`

**Purpose:** Search for a stop by name. Shows results in a list. Tapping a result navigates to the stop detail screen.

```jsx
import { useState } from "react"
import { View, TextInput, FlatList, TouchableOpacity, Text } from "react-native"
import { searchStops } from "../../lib/api"
import { useRouter } from "expo-router"
```

**State:**
- `query`: string from TextInput
- `results`: array of stop objects
- `loading`: boolean

**Behavior:**
- `onChangeText`: updates `query`, debounces 300ms, calls `searchStops(query)` when `query.length >= 2`
- Each result row shows `stop_name`
- Tapping a row: `router.push(`/stop/${stop.stop_id}`)`

---

### 6.15 `frontend/app/stop/[id].jsx`

**Purpose:** Stop detail screen. Shows stop name, incoming buses with ETAs, stops remaining, and service alerts.

```jsx
import { useLocalSearchParams } from "expo-router"
import { useStop } from "../../hooks/useStop"
import IncomingBusList from "../../components/IncomingBusList"
import AlertBanner from "../../components/AlertBanner"
```

**Implementation:**
- `const { id } = useLocalSearchParams()`
- `const { stop, incoming, alerts, loading } = useStop(id)`
- If `loading`: show a spinner
- Renders:
  1. Stop name as heading
  2. `<AlertBanner alerts={alerts} />` (hidden if alerts is empty)
  3. `<IncomingBusList buses={incoming} />`
  4. A small map thumbnail centered on the stop (optional — embed a smaller MapView showing just this stop and nearby buses)

---

## 7. Data Models Reference

### Vehicle (from WebSocket)
```json
{
  "vehicle_id": "atac_123",
  "trip_id": "98765",
  "route_id": "100",
  "route_short_name": "64",
  "lat": 41.9028,
  "lng": 12.4964,
  "bearing": 270.0,
  "current_stop_sequence": 12,
  "timestamp": 1746300000
}
```

### Incoming Bus (from `/stops/{id}/incoming`)
```json
{
  "vehicle_id": "atac_123",
  "route_short_name": "64",
  "arrival_time": 1746300420,
  "stops_remaining": 3,
  "lat": 41.9100,
  "lng": 12.4800
}
```

### Stop
```json
{
  "stop_id": "70311",
  "stop_name": "Termini (MA)",
  "lat": 41.9010,
  "lng": 12.5010
}
```

### Service Alert
```json
{
  "alert_id": "alert_001",
  "header": "Line 40 deviation",
  "description": "Via Cavour detour until 15 May due to roadworks",
  "affected_route_ids": ["200"],
  "affected_stop_ids": ["70311", "70312"]
}
```

---

## 8. API Reference

| Method | Path | Description |
|---|---|---|
| WS | `/ws` | Live vehicle positions stream |
| GET | `/stops?q=` | Search stops by name |
| GET | `/stops/nearest?lat=&lng=` | Nearest stop to coordinates |
| GET | `/stops/{id}` | Stop detail |
| GET | `/stops/{id}/incoming` | Incoming buses + alerts for stop |
| GET | `/vehicles` | All live vehicles |
| GET | `/vehicles/{id}` | Single vehicle detail |
| GET | `/vehicles/nearest?lat=&lng=&limit=` | Nearest vehicles to coordinates |
| GET | `/alerts` | All service alerts |
| GET | `/alerts/route/{route_id}` | Alerts for a specific route |

---

## 9. Running the Project

### Start the backend

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

`--host 0.0.0.0` makes it accessible from your phone on the same Wi-Fi network.
`--reload` auto-restarts on file changes during development.

You should see in the logs:
- "Loading static GTFS..." then how many stops/routes/trips were loaded
- "Polling vehicle positions..." every 60 seconds
- "Client connected" when the app connects

### Start the frontend

```bash
cd frontend
npx expo start --tunnel
```

The `--tunnel` flag is required on WSL. Without it, the QR code contains a WSL-internal IP that your phone and the Windows emulator cannot reach. The tunnel (via `ngrok` under the hood) gives you a public URL that works everywhere.

If you haven't used `--tunnel` before, Expo will prompt you to install `@expo/ngrok`:
```bash
npm install -g @expo/ngrok
```

Then re-run `npx expo start --tunnel`.

This opens the Expo dev menu. Press:
- `a` — open Android emulator (must be already running on Windows, with ADB bridge set up per Section 1.5)
- `w` — open in web browser (opens in your Windows browser automatically)
- Scan the QR code with Expo Go on your phone

> **iOS simulator** is not available on WSL. Use Expo Go on a physical iPhone instead.

### Update the backend URL

Because the backend runs inside WSL, you need your **Windows host IP** (not the WSL IP) so that your phone and emulator can reach it.

Find the Windows host IP from inside WSL:
```bash
cat /etc/resolv.conf | grep nameserver | awk '{print $2}'
```

This prints something like `172.28.80.1`. Use this IP in `frontend/constants/config.js`.

Alternatively, find your machine's LAN IP from Windows (run in PowerShell):
```powershell
ipconfig
# look for "IPv4 Address" under your Wi-Fi adapter, e.g. 192.168.1.50
```

Use the LAN IP if testing from a physical phone on the same Wi-Fi. Use the WSL nameserver IP if testing from the Windows Android emulator.

Update `frontend/constants/config.js`:
```js
export const API_BASE_URL = "http://172.28.80.1:8000"  // your Windows host IP
export const WS_URL = "ws://172.28.80.1:8000/ws"
```

**Also open port 8000 in WSL's firewall** so Windows can reach it. From WSL:
```bash
# This is usually not needed — WSL 2 routes automatically — but if connections are refused:
sudo ufw allow 8000
```

---

## 10. Build for Production

### Backend

Deploy FastAPI to any server that runs Python. Recommended options:
- **Railway.app** — push to GitHub, it detects Python, add a `Procfile`:
  ```
  web: uvicorn main:app --host 0.0.0.0 --port $PORT
  ```
- **Render.com** — similar, free tier available
- **VPS (DigitalOcean, Linode)** — use `gunicorn` with `uvicorn` workers behind `nginx`

### Frontend — Web

```bash
cd frontend
npx expo export --platform web
```
Outputs to `dist/`. Deploy to **Vercel**, **Netlify**, or any static host. Update `constants/config.js` to point to your deployed backend URL.

### Frontend — iOS + Android

EAS Build compiles your app in the cloud — you do not need Android Studio or Xcode locally. All commands run inside WSL.

You need a free [Expo account](https://expo.dev):
```bash
eas login
eas build:configure
```

Build Android APK (for testing without Play Store):
```bash
eas build --platform android --profile preview
```

This uploads your code to Expo's build servers and returns a download link for the `.apk`. Install it on your Android device or emulator.

Build for production:
```bash
eas build --platform android   # requires Google Play Developer account to submit
eas build --platform ios       # requires Apple Developer account ($99/year)
```

Submit to stores (after a successful build):
```bash
eas submit --platform android
eas submit --platform ios
```

> **iOS note:** You cannot build a local iOS binary from WSL. EAS Build is the only path. If you need fast iOS iteration, connect to a Mac running the same backend and run `npx expo start` there.
