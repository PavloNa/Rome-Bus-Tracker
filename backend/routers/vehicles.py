from fastapi import APIRouter, HTTPException
from store import store
from matcher import get_nearest_vehicles

router = APIRouter(prefix="/vehicles", tags=["vehicles"])

@router.get("")
async def get_vehicles():
    return [
        {
            "vehicle_id": vehicle.vehicle_id,
            "route_short_name": vehicle.route_short_name,
            "lat": vehicle.lat,
            "lng": vehicle.lng,
            "bearing": vehicle.bearing,
            "trip_id": vehicle.trip_id,
        }
        for vehicle in store.vehicles.values()
    ]
@router.get("/nearest")
async def get_nearest_vehicles_endpoint(lat: float, lng: float, limit: int = 5):
    vehicles = get_nearest_vehicles(lat, lng, limit)
    return vehicles


@router.get("/{vehicle_id}")
async def get_vehicle_info(vehicle_id: str):
    vehicle = store.vehicles.get(vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    return {
        "vehicle_id": vehicle.vehicle_id,
        "route_id": vehicle.route_id,
        "route_short_name": vehicle.route_short_name,
        "lat": vehicle.lat,
        "lng": vehicle.lng,
        "bearing": vehicle.bearing,
        "trip_id": vehicle.trip_id,
        "current_stop_sequence": vehicle.current_stop_sequence,
        "timestamp": vehicle.timestamp,
    }

@router.get("/nearest")
async def get_nearest_vehicles_endpoint(lat: float, lng: float, limit: int = 5):
    vehicles = get_nearest_vehicles(lat, lng, limit)
    return vehicles