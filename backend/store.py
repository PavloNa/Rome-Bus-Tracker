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
    stop_id: Optional[str]            # current stop ID (if available)
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
    # key: (trip_id, stop_id), value: (arrival_seconds_since_midnight, departure_seconds_since_midnight)
    # Used as fallback when trip_updates unavailable
    stop_times: dict[tuple[str, str], tuple[int, int]] = field(default_factory=dict)
    # set of service_ids active today
    active_service_ids: set[str] = field(default_factory=set)
    # set of trip_ids running today (pre-computed from active_service_ids)
    active_trip_ids: set[str] = field(default_factory=set)

    current_static_md5: str = ""

# Global singleton — import this in all other modules
store = AppStore()