#!/usr/bin/env python3
"""Fetch GTFS-RT feeds and the static GTFS zip (in-memory) and print 5 sample entities each.

This script does not write files to disk. It just fetches and prints structured
samples from each feed so we can inspect real payload formats.

Usage:
  python inspect_feeds.py
  python inspect_feeds.py --sample 10
"""
import json
import os
import csv
import io
import sys
from zipfile import ZipFile
from pathlib import Path

import httpx
from dotenv import load_dotenv

try:
    from google.protobuf.json_format import MessageToDict
except Exception:
    MessageToDict = None

load_dotenv()

VEHICLE_POSITIONS_URL = os.getenv("VEHICLE_POSITIONS_URL")
TRIP_UPDATES_URL = os.getenv("TRIP_UPDATES_URL")
SERVICE_ALERTS_URL = os.getenv("SERVICE_ALERTS_URL")
STATIC_GTFS_URL = os.getenv("STATIC_GTFS_URL")
TRIP_UPDATES_URL = os.getenv("TRIP_UPDATES_URL")
SERVICE_ALERTS_URL = os.getenv("SERVICE_ALERTS_URL")
STATIC_GTFS_URL = os.getenv("STATIC_GTFS_URL")


def safe(obj, *attrs):
    for a in attrs:
        obj = getattr(obj, a, None)
        if obj is None:
            return None
    return obj


def sample_vehicle_positions(content: bytes, n: int | None = None) -> list:
    try:
        from google.transit import gtfs_realtime_pb2
    except Exception as e:
        return [{"error": "gtfs_realtime_bindings missing", "detail": str(e)}]

    feed = gtfs_realtime_pb2.FeedMessage()
    try:
        feed.ParseFromString(content)
    except Exception as e:
        return [{"error": "parse_error", "detail": str(e)}]

    out = []
    entities = list(feed.entity)
    if n is not None:
        entities = entities[:n]
    for entity in entities:
        if MessageToDict:
            out.append(MessageToDict(entity, preserving_proto_field_name=True))
        else:
            out.append(str(entity))
    return out


def sample_trip_updates(content: bytes, n: int | None = None) -> list:
    try:
        from google.transit import gtfs_realtime_pb2
    except Exception as e:
        return [{"error": "gtfs_realtime_bindings missing", "detail": str(e)}]

    feed = gtfs_realtime_pb2.FeedMessage()
    try:
        feed.ParseFromString(content)
    except Exception as e:
        return [{"error": "parse_error", "detail": str(e)}]

    out = []
    entities = list(feed.entity)
    if n is not None:
        entities = entities[:n]
    for entity in entities:
        if MessageToDict:
            out.append(MessageToDict(entity, preserving_proto_field_name=True))
        else:
            out.append(str(entity))
    return out


def sample_service_alerts(content: bytes, n: int | None = None) -> list:
    try:
        from google.transit import gtfs_realtime_pb2
    except Exception as e:
        return [{"error": "gtfs_realtime_bindings missing", "detail": str(e)}]

    feed = gtfs_realtime_pb2.FeedMessage()
    try:
        feed.ParseFromString(content)
    except Exception as e:
        return [{"error": "parse_error", "detail": str(e)}]

    out = []
    entities = list(feed.entity)
    if n is not None:
        entities = entities[:n]
    for entity in entities:
        if MessageToDict:
            out.append(MessageToDict(entity, preserving_proto_field_name=True))
        else:
            out.append(str(entity))
    return out


def sample_static_gtfs(content: bytes, n: int | None = None) -> dict:
    out = {"files": []}
    try:
        with ZipFile(io.BytesIO(content)) as z:
            names = z.namelist()
            out["files"] = names
            # sample any CSV-like files (ending with .txt or .csv)
            csvs = [n for n in names if n.lower().endswith((".txt", ".csv"))][:5]
            samples = {}
            for name in csvs:
                try:
                    with z.open(name) as fh:
                        text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace")
                        reader = csv.DictReader(text)
                        rows = []
                        if n is None:
                            for r in reader:
                                rows.append(r)
                        else:
                            for i, r in enumerate(reader):
                                if i >= n:
                                    break
                                rows.append(r)
                        samples[name] = rows
                except Exception as e:
                    samples[name] = {"error": str(e)}
            out["csv_samples"] = samples
    except Exception as e:
        out["error"] = str(e)
    return out


def fetch(url: str) -> tuple[bool, bytes | None]:
    if not url:
        return False, None
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=30.0)
        resp.raise_for_status()
        return True, resp.content
    except Exception as e:
        return False, str(e).encode()


def main(sample: int = 50):
    outdir = Path(os.getenv("OUTDIR", "backend/data"))
    outdir.mkdir(parents=True, exist_ok=True)

    ok, content = fetch(VEHICLE_POSITIONS_URL)
    if not ok:
        vehicle_res = {"error": content.decode() if content else "no_url"}
    else:
        vehicle_res = sample_vehicle_positions(content, sample)
    with open(outdir / "vehicle_positions_feed.json", "w", encoding="utf-8") as fh:
        json.dump(vehicle_res, fh, indent=2, ensure_ascii=False)

    ok, content = fetch(TRIP_UPDATES_URL)
    if not ok:
        trip_res = {"error": content.decode() if content else "no_url"}
    else:
        trip_res = sample_trip_updates(content, sample)
    with open(outdir / "trip_updates_feed.json", "w", encoding="utf-8") as fh:
        json.dump(trip_res, fh, indent=2, ensure_ascii=False)

    ok, content = fetch(SERVICE_ALERTS_URL)
    if not ok:
        alerts_res = {"error": content.decode() if content else "no_url"}
    else:
        alerts_res = sample_service_alerts(content, sample)
    with open(outdir / "service_alerts_feed.json", "w", encoding="utf-8") as fh:
        json.dump(alerts_res, fh, indent=2, ensure_ascii=False)

    ok, content = fetch(STATIC_GTFS_URL)
    if not ok:
        static_res = {"error": content.decode() if content else "no_url"}
    else:
        static_res = sample_static_gtfs(content, sample)
    with open(outdir / "static_gtfs_samples.json", "w", encoding="utf-8") as fh:
        json.dump(static_res, fh, indent=2, ensure_ascii=False)

    print(f"Wrote JSON files to {outdir}")


if __name__ == "__main__":
    n = None
    if len(sys.argv) > 1:
        try:
            import argparse
            p = argparse.ArgumentParser()
            p.add_argument("--sample", "-n", type=int, default=None,
                           help="Number of items to sample; omit for full export")
            args = p.parse_args()
            n = args.sample
        except Exception:
            pass
    main(n)
