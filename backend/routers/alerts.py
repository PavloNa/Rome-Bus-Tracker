from fastapi import APIRouter
from store import store
from matcher import get_alerts_for_route

router = APIRouter(prefix="/alerts", tags=["alerts"])

@router.get("")
async def get_alerts():
    return [
        {
            "alert_id": alert.alert_id,
            "header": alert.header,
            "description": alert.description,
            "affected_route_ids": alert.affected_route_ids,
            "affected_stop_ids": alert.affected_stop_ids,
        }
        for alert in store.service_alerts
    ]

@router.get("/route/{route_id}")
async def get_alerts_for_route_endpoint(route_id: str):
    alerts = get_alerts_for_route(route_id)
    return alerts