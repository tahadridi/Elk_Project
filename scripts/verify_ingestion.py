#!/usr/bin/env python3
"""End-to-end verification for the Sprint 2 ELK ingestion pipeline."""
import argparse
import json
import sys
import urllib.error
import urllib.request

FAILED = []


def http(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode()
    return json.loads(raw) if raw else {}


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -> {detail}" if detail else ""))
    if not ok:
        FAILED.append(name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--es", default="http://localhost:9200")
    parser.add_argument("--min-docs", type=int, default=1)
    args = parser.parse_args()
    es = args.es.rstrip("/")

    try:
        health = http("GET", f"{es}/_cluster/health")
    except Exception as exc:
        print(f"[FAIL] Elasticsearch unreachable at {es}: {exc}")
        return 1
    check("Elasticsearch reachable", health.get("status") in {"yellow", "green"}, health.get("status"))

    try:
        http("GET", f"{es}/_index_template/logs-security")
        check("Index template logs-security installed", True)
    except urllib.error.HTTPError as exc:
        check("Index template logs-security installed", False, f"HTTP {exc.code}")

    try:
        count = http("GET", f"{es}/logs-security-*/_count").get("count", 0)
    except urllib.error.HTTPError:
        count = 0
    check("logs-security-* index has documents", count >= args.min_docs, f"{count} docs")

    try:
        errors = http("GET", f"{es}/logs-parse-errors-*/_count").get("count", 0)
    except urllib.error.HTTPError:
        errors = 0
    check("logs-parse-errors-* received invalid rows", errors >= 1, f"{errors} docs")

    agg = {
        "size": 0,
        "aggs": {
            "levels": {"terms": {"field": "log.level"}},
            "datasets": {"terms": {"field": "event.dataset"}},
            "sources": {"terms": {"field": "source.ip"}},
        },
    }
    try:
        res = http("POST", f"{es}/logs-security-*/_search", agg)
    except urllib.error.HTTPError as exc:
        check("Aggregations on normalized fields", False, f"HTTP {exc.code}")
        res = {"aggregations": {}}

    aggs = res.get("aggregations", {})
    levels = [b["key"] for b in aggs.get("levels", {}).get("buckets", [])]
    datasets = [b["key"] for b in aggs.get("datasets", {}).get("buckets", [])]
    check("log.level populated (bug fixed)", bool(levels), ",".join(levels))
    check("event.dataset populated", bool(datasets), ",".join(datasets))
    check("source.ip populated", bool(aggs.get("sources", {}).get("buckets")), "")

    try:
        sample = http("GET", f"{es}/logs-security-*/_search?size=1")
        hits = sample.get("hits", {}).get("hits", [])
        src = hits[0]["_source"] if hits else {}
    except Exception:
        src = {}
    has_ts = "@timestamp" in src
    has_level = bool(src.get("log", {}).get("level"))
    has_ip = bool(src.get("source", {}).get("ip"))
    check("Sample doc has @timestamp", has_ts)
    check("Sample doc has log.level", has_level, src.get("log", {}).get("level", ""))
    check("Sample doc has source.ip", has_ip, src.get("source", {}).get("ip", ""))

    print()
    if FAILED:
        print(f"RESULT: FAILED ({len(FAILED)} check(s)): {', '.join(FAILED)}")
        return 1
    print("RESULT: OK - Sprint 2 ingestion verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
