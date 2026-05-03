import asyncio
from static_gtfs import load_static_gtfs
from store import store
from matcher import haversine

async def check():
    await load_static_gtfs()
    your_lat, your_lng = 41.938042, 12.44235

    # Find all stops within 500m
    nearby = []
    for stop_id, stop in store.stops.items():
        dist = haversine(your_lat, your_lng, stop.lat, stop.lng)
        if dist < 500:
            nearby.append((dist, stop_id, stop.stop_name, stop.lat, stop.lng))

    nearby.sort()
    print(f'Found {len(nearby)} stops within 500m:')
    for dist, stop_id, name, lat, lng in nearby[:10]:
        print(f'  {dist:.1f}m - {stop_id}: {name} ({lat}, {lng})')

asyncio.run(check())