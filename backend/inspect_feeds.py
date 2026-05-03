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


def safe(obj, *attrs):
    for a in attrs:
        obj = getattr(obj, a, None)
        if obj is None:
            return None
    return obj


def sample_vehicle_positions(content: bytes, n: int = 5) -> list:
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
    for entity in feed.entity[:n]:
        if MessageToDict:
            out.append(MessageToDict(entity, preserving_proto_field_name=True))
        else:
            out.append(str(entity))
    return out


def sample_trip_updates(content: bytes, n: int = 5) -> list:
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
    for entity in feed.entity[:n]:
        if MessageToDict:
            out.append(MessageToDict(entity, preserving_proto_field_name=True))
        else:
            out.append(str(entity))
    return out


def sample_service_alerts(content: bytes, n: int = 5) -> list:
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
    for entity in feed.entity[:n]:
        if MessageToDict:
            out.append(MessageToDict(entity, preserving_proto_field_name=True))
        else:
            out.append(str(entity))
    return out


def sample_static_gtfs(content: bytes, n: int = 5) -> dict:
    out = {"files": []}
    try:
        with ZipFile(io.BytesIO(content)) as z:
            names = z.namelist()
            out["files"] = names
            # sample any CSV-like files (ending with .txt or .csv)
            csvs = [n for n in names if n.lower().endswith((".txt", ".csv"))][:10]
            samples = {}
            for name in csvs:
                try:
                    with z.open(name) as fh:
                        text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace")
                        reader = csv.DictReader(text)
                        rows = []
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


def main(sample: int = 5):
    results = {}

    ok, content = fetch(VEHICLE_POSITIONS_URL)
    if not ok:
        results["vehicle_positions"] = {"error": content.decode() if content else "no_url"}
    else:
        results["vehicle_positions"] = sample_vehicle_positions(content, sample)

    ok, content = fetch(TRIP_UPDATES_URL)
    if not ok:
        results["trip_updates"] = {"error": content.decode() if content else "no_url"}
    else:
        results["trip_updates"] = sample_trip_updates(content, sample)

    ok, content = fetch(SERVICE_ALERTS_URL)
    if not ok:
        results["service_alerts"] = {"error": content.decode() if content else "no_url"}
    else:
        results["service_alerts"] = sample_service_alerts(content, sample)

    ok, content = fetch(STATIC_GTFS_URL)
    if not ok:
        results["static_gtfs"] = {"error": content.decode() if content else "no_url"}
    else:
        results["static_gtfs"] = sample_static_gtfs(content, sample)

    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    n = 5
    if len(sys.argv) > 1:
        try:
            import argparse
            p = argparse.ArgumentParser()
            p.add_argument("--sample", "-n", type=int, default=5)
            args = p.parse_args()
            n = args.sample
        except Exception:
            pass
    main(n)
