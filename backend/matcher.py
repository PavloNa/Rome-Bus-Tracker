import time
import math
from typing import Optional

from store import store


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def get_incoming_buses(stop_id: str) -> list[dict]:
    now = int(time.time())
    incoming: list[dict] = []

    stop_entries = store.stop_to_trips.get(stop_id, [])
    for trip_id, _stop_sequence in stop_entries:
        if trip_id not in store.active_trip_ids:
            continue

        trip_update = store.trip_updates.get(trip_id)

        if trip_update:
            # find the stop_time_update for this stop
            target = next((stu for stu in trip_update.stop_time_updates if stu.stop_id == stop_id), None)
            if not target:
                continue
            arrival = target.arrival_time
            if arrival is None or arrival < now:
                continue

            # find vehicle
            vehicle = None
            if trip_update.vehicle_id:
                vehicle = store.vehicles.get(trip_update.vehicle_id)
            if not vehicle:
                vehicle = next((v for v in store.vehicles.values() if v.trip_id == trip_id), None)

            # compute stops remaining from static trip_to_stops (approx)
            stops = store.trip_to_stops.get(trip_id, [])
            stops_remaining = None
            for idx, (s_id, _seq) in enumerate(stops):
                if s_id == stop_id:
                    stops_remaining = max(0, len(stops) - idx - 1)
                    break

            incoming.append({
                "vehicle_id": vehicle.vehicle_id if vehicle else None,
                "route_short_name": vehicle.route_short_name if vehicle else store.routes.get(trip_update.route_id or ""),
                "arrival_time": arrival,
                "stops_remaining": stops_remaining,
                "lat": vehicle.lat if vehicle else None,
                "lng": vehicle.lng if vehicle else None,
            })
        else:
            # fallback: if no trip update, include vehicle positions for the trip
            vehicle = next((v for v in store.vehicles.values() if v.trip_id == trip_id), None)
            if not vehicle:
                continue

            stops = store.trip_to_stops.get(trip_id, [])
            target_index = None
            for idx, (s_id, _seq) in enumerate(stops):
                if s_id == stop_id:
                    target_index = idx
                    break
            if target_index is None:
                continue

            stops_remaining = None
            if vehicle.current_stop_sequence is not None:
                # map current_stop_sequence to index in stops
                curr_idx = None
                for idx, (_s_id, seq) in enumerate(stops):
                    if seq == vehicle.current_stop_sequence:
                        curr_idx = idx
                        break
                if curr_idx is not None:
                    stops_remaining = max(0, target_index - curr_idx)

            incoming.append({
                "vehicle_id": vehicle.vehicle_id,
                "route_short_name": vehicle.route_short_name or store.routes.get(store.trips.get(trip_id, ""), None),
                "arrival_time": None,
                "stops_remaining": stops_remaining,
                "lat": vehicle.lat,
                "lng": vehicle.lng,
            })

    incoming.sort(key=lambda x: (x["arrival_time"] is None, x["arrival_time"] or 0))
    return incoming


def get_stops_remaining(trip_id: str, target_stop_id: str) -> Optional[int]:
    trip_update = store.trip_updates.get(trip_id)
    # find target stop sequence from static data
    target_seq = None
    for s_id, seq in store.trip_to_stops.get(trip_id, []):
        if s_id == target_stop_id:
            target_seq = seq
            break
    if target_seq is None:
        return None

    vehicle = None
    if trip_update and trip_update.vehicle_id:
        vehicle = store.vehicles.get(trip_update.vehicle_id)
    if not vehicle:
        vehicle = next((v for v in store.vehicles.values() if v.trip_id == trip_id), None)
    if not vehicle or vehicle.current_stop_sequence is None:
        return None

    return max(0, target_seq - vehicle.current_stop_sequence)


def get_nearest_stop(lat: float, lng: float) -> Optional[dict]:
    nearest = None
    best = float("inf")
    for stop in store.stops.values():
        d = haversine(lat, lng, stop.lat, stop.lng)
        if d < best:
            best = d
            nearest = stop
    if not nearest:
        return None
    return {"stop_id": nearest.stop_id, "stop_name": nearest.stop_name, "distance": best}


def get_nearest_vehicles(lat: float, lng: float, limit: int = 5) -> list[dict]:
    items = []
    for v in store.vehicles.values():
        d = haversine(lat, lng, v.lat, v.lng)
        items.append({
            "vehicle_id": v.vehicle_id,
            "route_id": v.route_id,
            "route_short_name": v.route_short_name,
            "trip_id": v.trip_id,
            "lat": v.lat,
            "lng": v.lng,
            "bearing": v.bearing,
            "distance": d,
        })
    items.sort(key=lambda x: x["distance"])
    return items[:limit]


def get_alerts_for_stop(stop_id: str) -> list[dict]:
    res = []
    for alert in store.service_alerts:
        if stop_id in alert.affected_stop_ids:
            res.append({"alert_id": alert.alert_id, "header": alert.header, "description": alert.description})
    return res


def get_alerts_for_route(route_id: str) -> list[dict]:
    res = []
    for alert in store.service_alerts:
        if route_id in alert.affected_route_ids:
            res.append({"alert_id": alert.alert_id, "header": alert.header, "description": alert.description})
    return res
