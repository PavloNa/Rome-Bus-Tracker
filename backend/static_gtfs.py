import os
import csv
import datetime
import io
import logging
import zipfile

import httpx
from dotenv import load_dotenv

from store import Stop, store

load_dotenv()

STATIC_GTFS_URL = os.getenv("STATIC_GTFS_URL")
STATIC_GTFS_MD5_URL = os.getenv("STATIC_GTFS_MD5_URL")

logger = logging.getLogger(__name__)


def _open_csv(zip_ref: zipfile.ZipFile, filename: str):
    try:
        raw_file = zip_ref.open(filename)
    except KeyError:
        return None

    return csv.DictReader(io.TextIOWrapper(raw_file, encoding="utf-8-sig"))


def _parse_date(value: str) -> datetime.date:
    return datetime.datetime.strptime(value, "%Y%m%d").date()


def _parse_time_to_seconds(value: str) -> int | None:
    if not value:
        return None

    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds)

async def fetch_current_md5() -> str:
    if not STATIC_GTFS_MD5_URL:
        raise RuntimeError("STATIC_GTFS_MD5_URL is not configured")

    async with httpx.AsyncClient() as client:
        resp = await client.get(STATIC_GTFS_MD5_URL, follow_redirects=True)
        resp.raise_for_status()
        return resp.text.strip()

async def download_gtfs_zip() -> bytes:
    if not STATIC_GTFS_URL:
        raise RuntimeError("STATIC_GTFS_URL is not configured")

    async with httpx.AsyncClient() as client:
        resp = await client.get(STATIC_GTFS_URL, follow_redirects=True)
        resp.raise_for_status()
        return resp.content


def parse_stops(zip_ref: zipfile.ZipFile) -> dict[str, Stop]:
    reader = _open_csv(zip_ref, "stops.txt")
    if reader is None:
        return {}

    stops: dict[str, Stop] = {}
    for row in reader:
        stop_id = (row.get("stop_id") or "").strip()
        if not stop_id:
            continue

        stop_name = (row.get("stop_name") or "").strip()
        stop_lat = float(row.get("stop_lat") or 0.0)
        stop_lon = float(row.get("stop_lon") or 0.0)
        stops[stop_id] = Stop(stop_id=stop_id, stop_name=stop_name, lat=stop_lat, lng=stop_lon)

    return stops


def parse_routes(zip_ref: zipfile.ZipFile) -> dict[str, str]:
    reader = _open_csv(zip_ref, "routes.txt")
    if reader is None:
        return {}

    routes: dict[str, str] = {}
    for row in reader:
        route_id = (row.get("route_id") or "").strip()
        if not route_id:
            continue

        route_short_name = (row.get("route_short_name") or "").strip()
        routes[route_id] = route_short_name

    return routes


def parse_trips(zip_ref: zipfile.ZipFile) -> tuple[dict[str, str], dict[str, str]]:
    reader = _open_csv(zip_ref, "trips.txt")
    if reader is None:
        return {}, {}

    trip_to_route: dict[str, str] = {}
    trip_to_service: dict[str, str] = {}

    for row in reader:
        trip_id = (row.get("trip_id") or "").strip()
        if not trip_id:
            continue

        route_id = (row.get("route_id") or "").strip()
        service_id = (row.get("service_id") or "").strip()

        if route_id:
            trip_to_route[trip_id] = route_id
        if service_id:
            trip_to_service[trip_id] = service_id

    return trip_to_route, trip_to_service


def parse_calendar(zip_ref: zipfile.ZipFile) -> set[str]:
    today = datetime.date.today()
    weekday_column = today.strftime("%A").lower()
    active_service_ids: set[str] = set()

    calendar_reader = _open_csv(zip_ref, "calendar.txt")
    if calendar_reader is not None:
        for row in calendar_reader:
            service_id = (row.get("service_id") or "").strip()
            if not service_id:
                continue

            if (row.get(weekday_column) or "0").strip() != "1":
                continue

            start_date_raw = row.get("start_date") or ""
            end_date_raw = row.get("end_date") or ""
            if not start_date_raw or not end_date_raw:
                continue

            start_date = _parse_date(start_date_raw)
            end_date = _parse_date(end_date_raw)
            if start_date <= today <= end_date:
                active_service_ids.add(service_id)

    # The current Rome static GTFS zip does not include calendar.txt.
    # In that case, calendar_dates.txt is the only source of service activity.

    calendar_dates_reader = _open_csv(zip_ref, "calendar_dates.txt")
    if calendar_dates_reader is not None:
        for row in calendar_dates_reader:
            service_id = (row.get("service_id") or "").strip()
            date_raw = (row.get("date") or "").strip()
            exception_type = (row.get("exception_type") or "").strip()

            if not service_id or not date_raw or not exception_type:
                continue

            if _parse_date(date_raw) != today:
                continue

            if exception_type == "1":
                active_service_ids.add(service_id)
            elif exception_type == "2":
                active_service_ids.discard(service_id)

    return active_service_ids


def parse_stop_times(zip_ref: zipfile.ZipFile) -> tuple[dict[str, list[tuple[str, int]]], dict[str, list[tuple[str, int]]]]:
    reader = _open_csv(zip_ref, "stop_times.txt")
    if reader is None:
        return {}, {}

    stop_to_trips: dict[str, list[tuple[str, int]]] = {}
    trip_to_stops: dict[str, list[tuple[str, int]]] = {}

    for row in reader:
        trip_id = (row.get("trip_id") or "").strip()
        stop_id = (row.get("stop_id") or "").strip()
        stop_sequence_raw = (row.get("stop_sequence") or "").strip()

        if not trip_id or not stop_id or not stop_sequence_raw:
            continue

        stop_sequence = int(stop_sequence_raw)

        stop_to_trips.setdefault(stop_id, []).append((trip_id, stop_sequence))
        trip_to_stops.setdefault(trip_id, []).append((stop_id, stop_sequence))

        _parse_time_to_seconds((row.get("arrival_time") or "").strip())
        _parse_time_to_seconds((row.get("departure_time") or "").strip())

    for stop_id, trip_entries in stop_to_trips.items():
        trip_entries.sort(key=lambda item: (item[1], item[0]))

    for trip_id, stop_entries in trip_to_stops.items():
        stop_entries.sort(key=lambda item: (item[1], item[0]))

    return stop_to_trips, trip_to_stops


async def load_static_gtfs() -> None:
    raw_zip = await download_gtfs_zip()

    with zipfile.ZipFile(io.BytesIO(raw_zip)) as zip_ref:
        stops = parse_stops(zip_ref)
        routes = parse_routes(zip_ref)
        trip_to_route, trip_to_service = parse_trips(zip_ref)
        active_service_ids = parse_calendar(zip_ref)
        stop_to_trips, trip_to_stops = parse_stop_times(zip_ref)

    active_trip_ids = {trip_id for trip_id, service_id in trip_to_service.items() if service_id in active_service_ids}

    store.stops = stops
    store.routes = routes
    store.trips = trip_to_route
    store.stop_to_trips = stop_to_trips
    store.trip_to_stops = trip_to_stops
    store.active_service_ids = active_service_ids
    store.active_trip_ids = active_trip_ids

    logger.info(
        "Loaded static GTFS: %s stops, %s routes, %s trips, %s stop-to-trip mappings, %s active services, %s active trips",
        len(stops),
        len(routes),
        len(trip_to_route),
        len(stop_to_trips),
        len(active_service_ids),
        len(active_trip_ids),
    )


async def check_and_reload_if_needed() -> None:
    current_md5 = await fetch_current_md5()
    if current_md5 == store.current_static_md5:
        return

    await load_static_gtfs()
    store.current_static_md5 = current_md5