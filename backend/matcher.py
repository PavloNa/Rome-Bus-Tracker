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


def find_stop_sequence(trip_id: str, stop_id: str) -> Optional[int]:
    """Get the sequence number of a stop within a trip's route."""
    for candidate_stop_id, sequence in store.trip_to_stops.get(trip_id, []):
        if candidate_stop_id == stop_id:
            return sequence
    return None


def get_trip_delay(trip_id: str, stop_id: str) -> int:
    """Extract real-time delay in seconds from trip_updates feed."""
    trip_update = store.trip_updates.get(trip_id)
    if not trip_update:
        return 0
    
    for stop_update in trip_update.stop_time_updates:
        if stop_update.stop_id == stop_id and stop_update.arrival_time:
            # Calculate delay: scheduled_time would come from stop_times.txt
            # For now, return the arrival_time directly (Unix epoch)
            # A proper implementation would compare against scheduled time
            return int(stop_update.arrival_time - time.time())
    return 0


def get_route_trip_ids(route_id: str) -> list[str]:
    """Get all active trip IDs for a route."""
    return [trip_id for trip_id, stored_route_id in store.trips.items() 
            if stored_route_id == route_id and trip_id in store.active_trip_ids]


def get_stop_name(stop_id: str) -> str:
    """Look up human-readable stop name."""
    stop = store.stops.get(stop_id)
    return stop.stop_name if stop else f"Stop {stop_id}"


def get_incoming_buses(stop_id: str) -> list[dict]:
    """
    Get buses currently en route to a specific stop.
    
    Returns list of buses sorted by stops_remaining, with:
    - vehicle_id, route_id, route_short_name
    - current_stop_name, stops_until_arrival
    - delay_seconds, estimated arrival time
    - lat, lng position
    """
    incoming: list[dict] = []

    # Get all trips serving this stop
    trips_at_stop = store.stop_to_trips.get(stop_id, [])
    target_trip_ids = {trip_id for trip_id, _ in trips_at_stop}

    # Iterate through all active vehicles
    for vehicle in store.vehicles.values():
        # Skip if missing critical data
        if not vehicle.route_id or vehicle.current_stop_sequence is None or not vehicle.trip_id:
            continue

        # Check if this vehicle is on a trip serving the target stop
        if vehicle.trip_id not in target_trip_ids:
            continue

        # Find target stop sequence in this trip
        target_stop_seq = find_stop_sequence(vehicle.trip_id, stop_id)
        if target_stop_seq is None:
            continue

        # Calculate stops remaining
        stops_remaining = target_stop_seq - vehicle.current_stop_sequence

        # Skip if vehicle already passed the stop or too far away
        if stops_remaining < 0 or stops_remaining > 30:
            continue

        # Get current stop name
        current_stop_name = get_stop_name(vehicle.stop_id) if hasattr(vehicle, 'stop_id') and vehicle.stop_id else "Unknown"

        # Get delay in seconds
        delay_seconds = get_trip_delay(vehicle.trip_id, stop_id)

        # Calculate estimated arrival time
        arrival_time = None
        trip_update = store.trip_updates.get(vehicle.trip_id)
        if trip_update:
            for stop_update in trip_update.stop_time_updates:
                if stop_update.stop_id == stop_id and stop_update.arrival_time:
                    if stop_update.arrival_time >= int(time.time()):
                        arrival_time = stop_update.arrival_time
                    break

        # Calculate minutes until arrival
        minutes_until_arrival = None
        if arrival_time:
            minutes_until_arrival = max(0, (arrival_time - int(time.time())) / 60)

        bus_info = {
            "vehicle_id": vehicle.vehicle_id,
            "route_id": vehicle.route_id,
            "route_short_name": vehicle.route_short_name,
            "trip_id": vehicle.trip_id,
            "current_stop_name": current_stop_name,
            "stops_remaining": stops_remaining,
            "delay_seconds": delay_seconds,
            "minutes_until_arrival": minutes_until_arrival,
            "arrival_time": arrival_time,
            "lat": vehicle.lat,
            "lng": vehicle.lng,
            "is_realtime": True,
        }
        incoming.append(bus_info)

    # Sort by stops_remaining (closest first)
    incoming.sort(key=lambda x: (x["stops_remaining"], x["arrival_time"] is None, x["arrival_time"] or 0))
    return incoming


def get_scheduled_buses(stop_id: str, limit_minutes: int = 120) -> list[dict]:
    """
    Get all scheduled buses for a stop (from static GTFS + trip updates if available).
    Shows buses not yet in real-time feed (scheduled for later).
    
    Uses trip_updates if available, falls back to static stop_times.txt.
    """
    scheduled: list[dict] = []
    now = int(time.time())
    future_cutoff = now + (limit_minutes * 60)
    
    # Get today's seconds since midnight (for static GTFS time conversion)
    import datetime
    today = datetime.date.today()
    midnight_today = int(datetime.datetime.combine(today, datetime.time.min).timestamp())
    
    # Get all trips serving this stop
    trips_at_stop = store.stop_to_trips.get(stop_id, [])
    
    for trip_id, stop_sequence in trips_at_stop:
        # Only include active trips
        if trip_id not in store.active_trip_ids:
            continue
        
        # Get route info
        route_id = store.trips.get(trip_id)
        if not route_id:
            continue
        
        route_short_name = store.routes.get(route_id)
        if not route_short_name:
            continue
        
        # Check if this trip already has a real-time vehicle (skip if it does)
        vehicle = next((v for v in store.vehicles.values() if v.trip_id == trip_id), None)
        if vehicle:
            continue  # Already shown in real-time buses
        
        # Try to get arrival time from trip_updates first (real-time if available)
        arrival_time = None
        trip_update = store.trip_updates.get(trip_id)
        
        if trip_update:
            for stop_update in trip_update.stop_time_updates:
                if stop_update.stop_id == stop_id:
                    if stop_update.arrival_time:
                        arrival_time = stop_update.arrival_time
                    break
        
        # If no trip_update, try static GTFS stop_times
        if not arrival_time:
            static_times = store.stop_times.get((trip_id, stop_id))
            if static_times and static_times[0] is not None:
                # Convert seconds-since-midnight to Unix timestamp
                arrival_time = midnight_today + static_times[0]
        
        # Skip if no arrival time or already in the past
        if not arrival_time or arrival_time < now:
            continue
        
        # Skip if beyond our cutoff window
        if arrival_time > future_cutoff:
            continue
        
        minutes_until_arrival = (arrival_time - now) / 60
        
        bus_info = {
            "route_id": route_id,
            "route_short_name": route_short_name,
            "trip_id": trip_id,
            "scheduled_arrival_time": arrival_time,
            "minutes_until_arrival": minutes_until_arrival,
            "is_realtime": False,
        }
        scheduled.append(bus_info)
    
    # Sort by arrival time and limit to reasonable number per route
    scheduled.sort(key=lambda x: x["scheduled_arrival_time"])
    
    # Limit to next 5 buses per route to avoid clutter
    result = []
    route_counts = {}
    for bus in scheduled:
        route = bus["route_short_name"]
        if route_counts.get(route, 0) < 5:
            result.append(bus)
            route_counts[route] = route_counts.get(route, 0) + 1
    
    return result


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


def get_nearby_stops(lat: float, lng: float, radius_meters: float = 1000) -> list[dict]:
    """Get all stops within a specified radius (default 1km)."""
    nearby = []
    for stop in store.stops.values():
        d = haversine(lat, lng, stop.lat, stop.lng)
        if d <= radius_meters:
            nearby.append({
                "stop_id": stop.stop_id,
                "stop_name": stop.stop_name,
                "distance": d,
                "lat": stop.lat,
                "lng": stop.lng,
            })
    
    # Sort by distance (closest first)
    nearby.sort(key=lambda x: x["distance"])
    return nearby


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
    """Find any active service alerts affecting this stop."""
    res = []
    for alert in store.service_alerts:
        if stop_id in alert.affected_stop_ids:
            res.append({
                "alert_id": alert.alert_id, 
                "header": alert.header, 
                "description": alert.description
            })
    return res


def get_alerts_for_route(route_id: str) -> list[dict]:
    """Find any active service alerts affecting this route."""
    res = []
    for alert in store.service_alerts:
        if route_id in alert.affected_route_ids:
            res.append({
                "alert_id": alert.alert_id, 
                "header": alert.header, 
                "description": alert.description
            })
    return res


def get_alerts_for_route_stop(route_id: str, stop_id: str) -> list[dict]:
    """Find any active service alerts for route/stop combination."""
    res = []
    for alert in store.service_alerts:
        if route_id in alert.affected_route_ids or stop_id in alert.affected_stop_ids:
            res.append({
                "alert_id": alert.alert_id, 
                "header": alert.header, 
                "description": alert.description
            })
    return res
