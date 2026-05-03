#!/usr/bin/env python3
"""Debug script to inspect what data exists for a stop."""
import asyncio
from static_gtfs import load_static_gtfs
from feed import poll_all_feeds
from store import store

async def debug_stop(stop_id: str):
    print(f"\n=== Debugging stop {stop_id} ===\n")
    
    # Load all data
    await load_static_gtfs()
    await poll_all_feeds()
    
    # Check if stop exists
    stop = store.stops.get(stop_id)
    if not stop:
        print(f"❌ Stop {stop_id} not found!")
        return

    print(f"✓ Stop found: {stop.stop_name}")

    # Get trips serving this stop
    trips_at_stop = store.stop_to_trips.get(stop_id, [])
    print(f"\n📍 Trips serving this stop: {len(trips_at_stop)}")

    if not trips_at_stop:
        print("   No trips found!")
        return

    # Show first 10 trips
    for i, (trip_id, stop_seq) in enumerate(trips_at_stop[:10]):
        route_id = store.trips.get(trip_id)
        route_name = store.routes.get(route_id) if route_id else "?"
        is_active = trip_id in store.active_trip_ids
        has_vehicle = any(v.trip_id == trip_id for v in store.vehicles.values())
        has_update = trip_id in store.trip_updates

        status = "✓ ACTIVE" if is_active else "✗ INACTIVE"
        vehicle_str = " (has vehicle)" if has_vehicle else ""
        update_str = " (has trip_update)" if has_update else ""

        print(f"   {i+1}. Trip {trip_id} | Route {route_name} | Seq {stop_seq} | {status}{vehicle_str}{update_str}")

    # Check active trip count
    print(f"\n📊 Active trips in store: {len(store.active_trip_ids)}")
    print(f"📊 Trip updates in store: {len(store.trip_updates)}")
    print(f"📊 Vehicles in store: {len(store.vehicles)}")

    # Show sample trip update if available
    if trips_at_stop:
        sample_trip = trips_at_stop[0][0]
        trip_update = store.trip_updates.get(sample_trip)
        if trip_update:
            print(f"\n📋 Sample trip update for {sample_trip}:")
            print(f"   - Route ID: {trip_update.route_id}")
            print(f"   - Vehicle ID: {trip_update.vehicle_id}")
            print(f"   - Stop updates: {len(trip_update.stop_time_updates)}")
            for su in trip_update.stop_time_updates[:3]:
                print(f"     - Stop {su.stop_id}: arrival={su.arrival_time}, departure={su.departure_time}")

if __name__ == "__main__":
    stop_id = "73211"  # CAMILLUCCIA/MARSCIANO
    asyncio.run(debug_stop(stop_id))
