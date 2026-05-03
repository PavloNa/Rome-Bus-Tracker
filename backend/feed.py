import asyncio
import os
import time

import httpx
from dotenv import load_dotenv
from google.transit import gtfs_realtime_pb2
from store import store, Vehicle, TripUpdate, StopTimeUpdate, ServiceAlert

load_dotenv()

VEHICLE_POSITIONS_URL = os.getenv("VEHICLE_POSITIONS_URL")
TRIP_UPDATES_URL = os.getenv("TRIP_UPDATES_URL")
SERVICE_ALERTS_URL = os.getenv("SERVICE_ALERTS_URL")

async def fetch_pb(url: str) -> bytes:
    if not url:
        raise RuntimeError(f"{url} is not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        return resp.content

def decode_vehicle_positions(raw: bytes) -> dict[str, Vehicle]:
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(raw)

    vehicles = {}
    for entity in feed.entity:
        if not entity.HasField("vehicle"):
            continue

        v = entity.vehicle
        route_id = v.trip.route_id if v.HasField("trip") else None
        vehicles[v.vehicle.id] = Vehicle(
            vehicle_id=v.vehicle.id,
            trip_id=v.trip.trip_id if v.HasField("trip") else None,
            route_id=route_id,
            route_short_name=store.routes.get(route_id) if route_id else None,
            lat=v.position.latitude,
            lng=v.position.longitude,
            bearing=v.position.bearing if v.position.HasField("bearing") else None,
            current_stop_sequence=v.current_stop_sequence if v.HasField("current_stop_sequence") else None,
            timestamp=v.timestamp if v.HasField("timestamp") else int(time.time()),
        )
    return vehicles

def decode_trip_updates(raw: bytes) -> dict[str, TripUpdate]:
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(raw)

    trip_updates = {}
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue

        tu = entity.trip_update
        stop_time_updates = []
        for stu in tu.stop_time_update:
            stop_time_updates.append(StopTimeUpdate(
                stop_id=stu.stop_id,
                stop_sequence=stu.stop_sequence,
                arrival_time=stu.arrival.time if stu.HasField("arrival") else None,
                departure_time=stu.departure.time if stu.HasField("departure") else None,
            ))

        trip_updates[tu.trip.trip_id] = TripUpdate(
            trip_id=tu.trip.trip_id,
            route_id=tu.trip.route_id,
            vehicle_id=tu.vehicle.id if tu.HasField("vehicle") else None,
            stop_time_updates=stop_time_updates,
        )

    return trip_updates

def decode_service_alerts(raw: bytes) -> list[ServiceAlert]:
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(raw)

    alerts = []
    for entity in feed.entity:
        if not entity.HasField("alert"):
            continue

        a = entity.alert
        affected_route_ids = []
        affected_stop_ids = []
        for i in a.informed_entity:
            if i.HasField("route_id"):
                affected_route_ids.append(i.route_id)
            if i.HasField("stop_id"):
                affected_stop_ids.append(i.stop_id)

        alerts.append(ServiceAlert(
            alert_id=entity.id,
            header=a.header_text.translation[0].text if a.header_text.translation else "",
            description=a.description_text.translation[0].text if a.description_text.translation else "",
            affected_route_ids=affected_route_ids,
            affected_stop_ids=affected_stop_ids,
        ))

    return alerts

async def poll_vehicle_positions():
    try:
        raw = await fetch_pb(VEHICLE_POSITIONS_URL)
        vehicles = decode_vehicle_positions(raw)
        store.vehicles = vehicles
    except Exception as e:
        print(f"Error fetching vehicle positions: {e}")

async def poll_trip_updates():
    try:
        raw = await fetch_pb(TRIP_UPDATES_URL)
        trip_updates = decode_trip_updates(raw)
        store.trip_updates = trip_updates
    except Exception as e:
        print(f"Error fetching trip updates: {e}")

async def poll_service_alerts():
    try:
        raw = await fetch_pb(SERVICE_ALERTS_URL)
        service_alerts = decode_service_alerts(raw)
        store.service_alerts = service_alerts
    except Exception as e:
        print(f"Error fetching service alerts: {e}")

async def poll_all_feeds():
    await asyncio.gather(
        poll_vehicle_positions(),
        poll_trip_updates(),
        poll_service_alerts(),
    )