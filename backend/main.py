import os
import asyncio
import json
from contextlib import asynccontextmanager, suppress

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from feed import poll_all_feeds
from static_gtfs import load_static_gtfs, check_and_reload_if_needed, fetch_current_md5
from store import store
from routers import alerts, stops, vehicles

load_dotenv()

FEED_POLL_INTERVAL = int(os.getenv("FEED_POLL_INTERVAL", 60))
MD5_CHECK_INTERVAL = int(os.getenv("MD5_CHECK_INTERVAL", 300))

connected_clients: set[WebSocket] = set()
background_tasks: set[asyncio.Task] = set()


def _serialize_vehicles() -> list[dict]:
	return [
		{
			"vehicle_id": vehicle.vehicle_id,
			"trip_id": vehicle.trip_id,
			"route_id": vehicle.route_id,
			"route_short_name": vehicle.route_short_name,
			"lat": vehicle.lat,
			"lng": vehicle.lng,
			"bearing": vehicle.bearing,
			"current_stop_sequence": vehicle.current_stop_sequence,
			"timestamp": vehicle.timestamp,
		}
		for vehicle in store.vehicles.values()
	]


async def broadcast(data: dict) -> None:
	message = json.dumps(data)
	stale_clients: set[WebSocket] = set()

	for websocket in list(connected_clients):
		try:
			await websocket.send_text(message)
		except Exception:
			stale_clients.add(websocket)

	connected_clients.difference_update(stale_clients)


async def feed_poll_loop() -> None:
	while True:
		await poll_all_feeds()
		await broadcast({"type": "vehicles", "data": _serialize_vehicles()})
		await asyncio.sleep(FEED_POLL_INTERVAL)


async def md5_check_loop() -> None:
	while True:
		await check_and_reload_if_needed()
		await asyncio.sleep(MD5_CHECK_INTERVAL)


def _track_task(task: asyncio.Task) -> None:
	background_tasks.add(task)
	task.add_done_callback(background_tasks.discard)


@asynccontextmanager
async def lifespan(app: FastAPI):
	store.current_static_md5 = await fetch_current_md5()
	await load_static_gtfs()
	await poll_all_feeds()

	feed_task = asyncio.create_task(feed_poll_loop())
	md5_task = asyncio.create_task(md5_check_loop())
	_track_task(feed_task)
	_track_task(md5_task)

	try:
		yield
	finally:
		for task in list(background_tasks):
			task.cancel()

		for task in list(background_tasks):
			with suppress(asyncio.CancelledError):
				await task

		background_tasks.clear()
		connected_clients.clear()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_methods=["*"],
	allow_headers=["*"],
)

app.include_router(stops.router)
app.include_router(vehicles.router)
app.include_router(alerts.router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
	await websocket.accept()
	connected_clients.add(websocket)

	try:
		await websocket.send_text(json.dumps({"type": "vehicles", "data": _serialize_vehicles()}))

		while True:
			await websocket.receive_text()
	except WebSocketDisconnect:
		pass
	finally:
		connected_clients.discard(websocket)