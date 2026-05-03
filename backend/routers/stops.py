from fastapi import APIRouter, HTTPException
from store import store
from matcher import get_incoming_buses, get_nearest_stop, get_alerts_for_stop

router = APIRouter(prefix="/stops", tags=["stops"])

@router.get("")
async def search_stops(q: str):
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
    nearest_stop = get_nearest_stop(lat, lng)
    if not nearest_stop:
        raise HTTPException(status_code=404, detail="No nearby stop found")

    return nearest_stop

@router.get("/{stop_id}")
async def get_stop_info(stop_id: str):
    stop = store.stops.get(stop_id)
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    return {
        "stop_id": stop.stop_id,
        "stop_name": stop.stop_name,
        "lat": stop.lat,
        "lng": stop.lng,
    }

@router.get("/{stop_id}/incoming")
async def get_incoming_buses_for_stop(stop_id: str):
    if stop_id not in store.stops:
        raise HTTPException(status_code=404, detail="Stop not found")

    incoming = get_incoming_buses(stop_id)
    alerts = get_alerts_for_stop(stop_id)
    return {"buses": incoming, "alerts": alerts}