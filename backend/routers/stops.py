from fastapi import APIRouter, HTTPException
from store import store
from matcher import get_incoming_buses, get_scheduled_buses, get_nearest_stop, get_nearby_stops, get_alerts_for_stop, get_alerts_for_route_stop

router = APIRouter(prefix="/stops", tags=["stops"])

@router.get("")
async def search_stops(q: str):
    """Search for stops by name."""
    q = q.strip().lower()
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    results = []
    for stop in store.stops.values():
        if q in stop.stop_name.lower():
            results.append({
                "stop_id": stop.stop_id,
                "stop_name": stop.stop_name,
                "lat": stop.lat,
                "lng": stop.lng,
            })

    return results[:20]

@router.get("/nearest")
async def get_nearest_stops(lat: float, lng: float):
    """Get nearest stop to coordinates."""
    nearest_stop = get_nearest_stop(lat, lng)
    if not nearest_stop:
        raise HTTPException(status_code=404, detail="No nearby stop found")

    return nearest_stop

@router.get("/nearby")
async def get_nearby_stops_endpoint(lat: float, lng: float, radius: float = 1000):
    """Get all stops within walking distance (default 1km)."""
    nearby = get_nearby_stops(lat, lng, radius)
    if not nearby:
        raise HTTPException(status_code=404, detail=f"No stops found within {radius}m")
    
    return {
        "lat": lat,
        "lng": lng,
        "radius_meters": radius,
        "stops": nearby,
    }

@router.get("/{stop_id}")
async def get_stop_info(stop_id: str):
    """Get stop details."""
    stop = store.stops.get(stop_id)
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    return {
        "stop_id": stop.stop_id,
        "stop_name": stop.stop_name,
        "lat": stop.lat,
        "lng": stop.lng,
    }

@router.get("/{stop_id}/arriving-buses")
async def get_arriving_buses(stop_id: str, include_scheduled: bool = True):
    """
    Get buses currently en route to this stop with stops remaining count.
    
    Returns:
    - realtime_buses: Buses currently active (with real-time position)
    - scheduled_buses: Upcoming buses from timetable (next 2 hours by default)
    
    Returns array of buses sorted by arrival time (closest first), including:
    - vehicle_id (only for real-time), route info
    - stops_remaining: number of stops until arrival (only for real-time)
    - current_stop_name: where the bus is now (only for real-time)
    - delay_seconds: real-time delay
    - minutes_until_arrival: estimated time to reach this stop
    - is_realtime: whether this is from real-time feed or static schedule
    """
    if stop_id not in store.stops:
        raise HTTPException(status_code=404, detail="Stop not found")

    realtime = get_incoming_buses(stop_id)
    scheduled = get_scheduled_buses(stop_id, limit_minutes=120) if include_scheduled else []
    alerts = get_alerts_for_stop(stop_id)
    
    return {
        "stop_id": stop_id,
        "stop_name": store.stops[stop_id].stop_name,
        "realtime_buses": realtime,
        "scheduled_buses": scheduled,
        "alerts": alerts,
    }

@router.get("/{stop_id}/incoming")
async def get_incoming_buses_for_stop(stop_id: str):
    """Get buses arriving at this stop (legacy endpoint)."""
    if stop_id not in store.stops:
        raise HTTPException(status_code=404, detail="Stop not found")

    incoming = get_incoming_buses(stop_id)
    alerts = get_alerts_for_stop(stop_id)
    return {"buses": incoming, "alerts": alerts}