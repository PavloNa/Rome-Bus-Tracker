#!/usr/bin/env python3
"""Inspect in-memory `store` and optionally a GTFS zip file.

Usage:
  python inspect_data.py            # prints store summary
  python inspect_data.py --zip /path/to/gtfs.zip --sample 10
"""
import argparse
import csv
import io
import json
import sys
from pathlib import Path
from zipfile import ZipFile


def add_backend_path():
    # allow running from repo root
    repo_backend = Path(__file__).resolve().parent
    if str(repo_backend) not in sys.path:
        sys.path.insert(0, str(repo_backend))


def sample_store(sample: int = 5) -> None:
    add_backend_path()
    try:
        from store import store
    except Exception as e:
        print(f"Could not import store: {e}")
        return

    def pick(d, n=5):
        it = list(d.items())[:n]
        return {k: v for k, v in it}

    out = {
        "stops_count": len(store.stops),
        "routes_count": len(store.routes),
        "trips_count": len(store.trips),
        "vehicles_count": len(store.vehicles),
        "trip_updates_count": len(store.trip_updates),
        "service_alerts_count": len(store.service_alerts),
        "active_service_ids_count": len(store.active_service_ids),
        "active_trip_ids_count": len(store.active_trip_ids),
        "stops_sample": None,
        "vehicles_sample": None,
        "trip_ids_from_vehicles_sample": None,
    }

    try:
        out["stops_sample"] = {k: {"lat": v.lat, "lng": v.lng, "name": getattr(v, "stop_name", None)} for k, v in list(store.stops.items())[:sample]}
    except Exception:
        out["stops_sample"] = pick(store.stops, sample)

    try:
        out["vehicles_sample"] = [{
            "vehicle_id": v.vehicle_id,
            "trip_id": v.trip_id,
            "route_short_name": v.route_short_name,
            "lat": v.lat,
            "lng": v.lng,
        } for v in list(store.vehicles.values())[:sample]]
    except Exception:
        out["vehicles_sample"] = list(store.vehicles.items())[:sample]

    # sample trip_id formats seen in vehicles vs static trips
    trip_ids_from_vehicles = list({v.trip_id for v in store.vehicles.values() if v.trip_id})[:sample]
    trip_ids_from_trips = list(store.trips.keys())[:sample]
    out["trip_ids_from_vehicles_sample"] = trip_ids_from_vehicles
    out["trip_ids_from_trips_sample"] = trip_ids_from_trips

    print(json.dumps(out, default=str, indent=2, ensure_ascii=False))


def inspect_gtfs_zip(zip_path: str, sample: int = 5) -> None:
    p = Path(zip_path)
    if not p.exists():
        print(f"Zip file not found: {zip_path}")
        return

    with ZipFile(p, "r") as z:
        names = z.namelist()
        print(json.dumps({"files": names}, indent=2, ensure_ascii=False))

        # helpful GTFS files to preview
        targets = ["stops.txt", "routes.txt", "trips.txt", "calendar.txt", "stop_times.txt"]
        for t in targets:
            # find case-insensitive match
            candidate = next((n for n in names if n.lower().endswith(t)), None)
            if not candidate:
                continue
            print(f"\n--- {candidate} (first {sample} rows) ---")
            with z.open(candidate) as fh:
                text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace")
                reader = csv.DictReader(text)
                rows = []
                for i, row in enumerate(reader):
                    if i >= sample:
                        break
                    rows.append(row)
                print(json.dumps(rows, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", "-z", help="Path to GTFS zip to inspect")
    parser.add_argument("--sample", "-n", type=int, default=5, help="Number of sample rows")
    args = parser.parse_args()

    sample_store(args.sample)
    if args.zip:
        inspect_gtfs_zip(args.zip, args.sample)


if __name__ == "__main__":
    main()
