# Rome Bus Tracker - Implementation Guide

## Feature: Buses Arriving at a Specific Stop

### Overview
Display buses currently en route to a given stop, showing:
- Bus/Vehicle ID
- Route line number
- Current position/last known stop
- **Number of stops remaining until arrival**
- Estimated arrival time (if available from trip updates)

---

## Data Flow & Relationships

```
QUERY INPUT: target_stop_id
    ↓
STEP 1: Find all trips serving this stop
    → stops.txt                 [stop_id, stop_name, stop_lat, stop_lon]
    → stop_times.txt            [trip_id, stop_id, arrival_time, stop_sequence]
    ↓
STEP 2: Find active vehicles on those trips
    → vehicle_positions feed    [vehicle_id, trip_id, stop_id, latitude, longitude]
    → trip_updates feed         [trip_id, stop_id, delay_seconds]
    ↓
STEP 3: Calculate stops remaining for each vehicle
    → For each vehicle with matching trip_id:
        a) Find current stop_sequence from stop_times.txt
        b) Find target stop_sequence for the query stop
        c) stops_remaining = target_stop_sequence - current_stop_sequence
    ↓
STEP 4: Enrich with route & alert info
    → trips.txt                 [trip_id, route_id, shape_id]
    → routes.txt                [route_id, route_short_name, agency_id]
    → alerts feed               [route_id, stop_id] → disruptions
```

---

## Algorithm: Calculate Stops Until Arrival

### Input
- `target_stop_id`: The stop user is querying
- `vehicle_positions`: Current real-time vehicle data
- `trip_updates`: Real-time schedule modifications
- Static GTFS tables: `stop_times.txt`, `trips.txt`, `routes.txt`, `stops.txt`

### Process

```python
def get_buses_at_stop(target_stop_id, 
                      vehicle_positions,     # protobuf FeedMessage
                      trip_updates,          # protobuf FeedMessage
                      static_gtfs):          # dict of parsed CSV tables
    
    result_buses = []
    
    # 1. Find all trips that serve target_stop_id
    trips_at_target = static_gtfs['stop_times'].filter(stop_id == target_stop_id)
    target_trip_ids = set(trip['trip_id'] for trip in trips_at_target)
    
    # 2. For each active vehicle
    for entity in vehicle_positions.entity:
        vehicle = entity.vehicle
        vehicle_id = vehicle.vehicle.id
        trip_id = vehicle.trip.trip_id
        current_stop_id = vehicle.stop_id
        
        # Check if this vehicle is on a trip serving our target stop
        if trip_id not in target_trip_ids:
            continue
        
        # 3. Get stop sequences
        current_stop_seq = find_stop_sequence(trip_id, current_stop_id, static_gtfs)
        target_stop_seq = find_stop_sequence(trip_id, target_stop_id, static_gtfs)
        
        # Safety checks
        if current_stop_seq is None or target_stop_seq is None:
            continue
        
        if current_stop_seq > target_stop_seq:
            # Vehicle already passed the target stop
            continue
        
        # 4. Calculate stops remaining
        stops_remaining = target_stop_seq - current_stop_seq
        
        # 5. Get delay from trip_updates
        delay_seconds = get_trip_delay(trip_id, target_stop_id, trip_updates)
        
        # 6. Get route info
        route_info = get_route_info(trip_id, static_gtfs)
        
        # 7. Check for alerts
        alerts = get_alerts_for_route_stop(route_info['route_id'], 
                                           target_stop_id)
        
        result_buses.append({
            'vehicle_id': vehicle_id,
            'route_short_name': route_info['route_short_name'],
            'route_id': route_info['route_id'],
            'current_stop_id': current_stop_id,
            'current_stop_name': get_stop_name(current_stop_id, static_gtfs),
            'stops_until_arrival': stops_remaining,
            'delay_seconds': delay_seconds,
            'latitude': vehicle.position.latitude,
            'longitude': vehicle.position.longitude,
            'alerts': alerts,
        })
    
    # Sort by stops_remaining (ascending)
    return sorted(result_buses, key=lambda x: x['stops_until_arrival'])
```

---

## Helper Functions Needed

### 1. `find_stop_sequence(trip_id, stop_id, static_gtfs) → int | None`
**Purpose**: Get the sequence number of a stop within a trip's route

**Logic**:
```python
def find_stop_sequence(trip_id, stop_id, static_gtfs):
    """Returns the stop_sequence for a given trip and stop."""
    for row in static_gtfs['stop_times']:
        if row['trip_id'] == trip_id and row['stop_id'] == stop_id:
            return int(row['stop_sequence'])
    return None
```

### 2. `get_trip_delay(trip_id, stop_id, trip_updates) → int`
**Purpose**: Extract real-time delay from trip_updates feed

**Logic**:
```python
def get_trip_delay(trip_id, stop_id, trip_updates):
    """Returns delay in seconds (0 if on-time, negative if early, positive if late)."""
    for entity in trip_updates.entity:
        if entity.trip_update.trip.trip_id == trip_id:
            for stop_update in entity.trip_update.stop_time_update:
                if stop_update.stop_id == stop_id:
                    # arrival.delay is in seconds
                    return stop_update.arrival.delay if stop_update.arrival else 0
    return 0
```

### 3. `get_route_info(trip_id, static_gtfs) → dict`
**Purpose**: Get route details (line number, agency) for a trip

**Logic**:
```python
def get_route_info(trip_id, static_gtfs):
    """Returns route_id, route_short_name, etc."""
    trip = find_in_csv(static_gtfs['trips'], trip_id=trip_id)
    if not trip:
        return None
    route_id = trip['route_id']
    route = find_in_csv(static_gtfs['routes'], route_id=route_id)
    return {
        'route_id': route_id,
        'route_short_name': route['route_short_name'],
        'agency_id': route.get('agency_id'),
    }
```

### 4. `get_stop_name(stop_id, static_gtfs) → str`
**Purpose**: Look up human-readable stop name

**Logic**:
```python
def get_stop_name(stop_id, static_gtfs):
    """Returns the stop name."""
    stop = find_in_csv(static_gtfs['stops'], stop_id=stop_id)
    return stop['stop_name'] if stop else f"Stop {stop_id}"
```

### 5. `get_alerts_for_route_stop(route_id, stop_id, alerts_feed) → list`
**Purpose**: Find any active service alerts for this route/stop combination

**Logic**:
```python
def get_alerts_for_route_stop(route_id, stop_id, alerts_feed):
    """Returns list of active alerts affecting this route/stop."""
    active_alerts = []
    for entity in alerts_feed.entity:
        alert = entity.alert
        # Check if alert applies to this route/stop
        for informed_entity in alert.informed_entity:
            if (informed_entity.route_id == route_id or 
                informed_entity.stop_id == stop_id):
                active_alerts.append({
                    'header': alert.header_text.translation[0].text if alert.header_text else '',
                    'description': alert.description_text.translation[0].text if alert.description_text else '',
                })
                break
    return active_alerts
```

---

## Integration Points

### 1. **Add new endpoint** (in `routers/stops.py`)
```python
@router.get("/stops/{stop_id}/arriving-buses")
async def get_arriving_buses(stop_id: str):
    """
    Get buses currently en route to this stop.
    
    Returns:
    [
        {
            "vehicle_id": "1234",
            "route_short_name": "64",
            "stops_until_arrival": 3,
            "current_stop_name": "Via Roma",
            "delay_seconds": 45,
            "latitude": 41.9028,
            "longitude": 12.4964,
            "alerts": [...]
        }
    ]
    """
```

### 2. **Load & cache static GTFS** (in `static_gtfs.py`)
- Parse and store `stop_times.txt`, `trips.txt`, `routes.txt`, `stops.txt`
- Index by trip_id and stop_id for O(1) lookups
- Consider caching strategy (refresh daily or on-demand)

### 3. **Store real-time feeds** (in `store.py`)
- Keep latest snapshots of vehicle_positions, trip_updates, alerts
- Ensure timestamps are tracked for freshness checks

---

## Data Validation & Edge Cases

| Case | Handling |
|------|----------|
| Vehicle already passed target stop | Filter out (stop_seq > target_seq) |
| Vehicle not on a trip serving the stop | Skip |
| Stop sequence data missing | Return error or default to -1 |
| Delay data stale (>5 min old) | Flag as unreliable or exclude |
| Multiple trips per vehicle | Use most recent trip_id from vehicle_positions |
| Stop_id format mismatch | Normalize (trim whitespace, case handling) |

---

## Testing Data Sources

Check `backend/data/`:
- `vehicle_positions_feed.json` — Sample vehicle data
- `trip_updates_feed.json` — Sample delays/real-time changes
- `service_alerts_feed.json` — Sample disruptions
- `static_gtfs_samples.json` — Sample stops, trips, routes

Use these samples to:
1. Verify data parsing logic
2. Test edge cases (missing fields, null values)
3. Validate calculation logic

---

## Performance Considerations

- **Stop sequence lookup**: Build in-memory index `{(trip_id, stop_id): stop_sequence}`
- **Route lookup**: Index trips and routes by ID
- **Real-time updates**: Cache vehicle_positions and trip_updates; refresh every 5-30 seconds
- **Query latency**: Should be <100ms with proper indexing
