#!/usr/bin/env python3
"""Build the Sprint 2 Kibana dashboard and export it as NDJSON.

The script is idempotent: saved objects are written with overwrite=true, so it can
be re-run safely while refining the dashboard.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

KIBANA_URL = os.environ.get("KIBANA_URL", "http://localhost:5601").rstrip("/")
DASHBOARD_ID = "security-overview"


def request(method: str, path: str, body: dict | None = None) -> bytes:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{KIBANA_URL}{path}",
        data=data,
        method=method,
        headers={"kbn-xsrf": "true", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        raise SystemExit(f"HTTP {exc.code} on {method} {path}: {detail}") from exc


def create_data_view(data_view_id: str, title: str, name: str) -> None:
    request(
        "POST",
        "/api/data_views/data_view",
        {
            "data_view": {
                "id": data_view_id,
                "title": title,
                "name": name,
                "timeFieldName": "@timestamp",
            },
            "override": True,
        },
    )


def save_visualization(
    viz_id: str,
    title: str,
    vis_state: dict,
    data_view_id: str,
    query: str = "",
    description: str = "",
) -> None:
    search_source = {
        "query": {"query": query, "language": "kuery"},
        "filter": [],
        "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index",
    }
    request(
        "POST",
        f"/api/saved_objects/visualization/{viz_id}?overwrite=true",
        {
            "attributes": {
                "title": title,
                "visState": json.dumps(vis_state),
                "uiStateJSON": "{}",
                "description": description,
                "version": 1,
                "kibanaSavedObjectMeta": {
                    "searchSourceJSON": json.dumps(search_source)
                },
            },
            "references": [
                {
                    "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
                    "type": "index-pattern",
                    "id": data_view_id,
                }
            ],
        },
    )


def count_agg() -> dict:
    return {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}}


def metric_viz(title: str) -> dict:
    return {
        "title": title,
        "type": "metric",
        "params": {
            "addTooltip": True,
            "addLegend": False,
            "type": "metric",
            "metric": {
                "percentageMode": False,
                "useRanges": False,
                "colorSchema": "Green to Red",
                "metricColorMode": "None",
                "colorsRange": [{"from": 0, "to": 10000}],
                "labels": {"show": True},
                "invertColors": False,
                "style": {
                    "bgFill": "#000",
                    "bgColor": False,
                    "labelColor": False,
                    "subText": "",
                    "fontSize": 60,
                },
            },
        },
        "aggs": [count_agg()],
        "listeners": {},
    }


def terms_agg(field: str, size: int = 10) -> dict:
    return {
        "id": "2",
        "enabled": True,
        "type": "terms",
        "schema": "bucket",
        "params": {
            "field": field,
            "orderBy": "1",
            "order": "desc",
            "size": size,
            "otherBucket": False,
            "otherBucketLabel": "Other",
            "missingBucket": False,
            "missingBucketLabel": "Missing",
        },
    }


def pie_viz(title: str, field: str) -> dict:
    return {
        "title": title,
        "type": "pie",
        "params": {
            "type": "pie",
            "addTooltip": True,
            "addLegend": True,
            "legendPosition": "right",
            "isDonut": True,
            "labels": {"show": True, "values": True, "last_level": True, "truncate": 100},
        },
        "aggs": [
            count_agg(),
            {
                "id": "2",
                "enabled": True,
                "type": "terms",
                "schema": "segment",
                "params": {
                    "field": field,
                    "orderBy": "1",
                    "order": "desc",
                    "size": 5,
                    "otherBucket": False,
                    "otherBucketLabel": "Other",
                    "missingBucket": False,
                    "missingBucketLabel": "Missing",
                },
            },
        ],
        "listeners": {},
    }


def histogram_viz(title: str, split_field: str) -> dict:
    return {
        "title": title,
        "type": "histogram",
        "params": {
            "type": "histogram",
            "grid": {"categoryLines": False, "style": {"color": "#eee"}},
            "categoryAxes": [
                {
                    "id": "CategoryAxis-1",
                    "type": "category",
                    "position": "bottom",
                    "show": True,
                    "style": {},
                    "scale": {"type": "linear"},
                    "labels": {"show": True, "filter": True, "rotate": 0, "truncate": 100},
                    "title": {},
                }
            ],
            "valueAxes": [
                {
                    "id": "ValueAxis-1",
                    "name": "LeftAxis-1",
                    "type": "value",
                    "position": "left",
                    "show": True,
                    "style": {},
                    "scale": {"type": "linear", "mode": "normal"},
                    "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                    "title": {"text": "Count"},
                }
            ],
            "seriesParams": [
                {
                    "show": True,
                    "type": "histogram",
                    "mode": "stacked",
                    "dataLabel": "Count",
                    "valueAxis": "ValueAxis-1",
                    "drawLinesBetweenPoints": True,
                    "lineWidth": 2,
                    "showCircles": True,
                }
            ],
            "addTooltip": True,
            "addLegend": True,
            "legendPosition": "right",
            "times": [],
            "addTimeMarker": False,
            "labels": {"show": False},
            "thresholdLine": {
                "show": False,
                "value": 10,
                "width": 1,
                "style": "full",
                "color": "#E7664C",
            },
        },
        "aggs": [
            count_agg(),
            {
                "id": "2",
                "enabled": True,
                "type": "date_histogram",
                "schema": "segment",
                "params": {
                    "field": "@timestamp",
                    "timeRange": {"from": "now-30d", "to": "now"},
                    "useNormalizedEsInterval": True,
                    "scaleMetricValues": False,
                    "interval": "auto",
                    "drop_partials": False,
                    "min_doc_count": 1,
                    "extended_bounds": {},
                },
            },
            {
                "id": "3",
                "enabled": True,
                "type": "terms",
                "schema": "group",
                "params": {
                    "field": split_field,
                    "orderBy": "1",
                    "order": "desc",
                    "size": 5,
                    "otherBucket": False,
                    "otherBucketLabel": "Other",
                    "missingBucket": False,
                    "missingBucketLabel": "Missing",
                },
            },
        ],
        "listeners": {},
    }


def table_viz(title: str, field: str, size: int = 10) -> dict:
    return {
        "title": title,
        "type": "table",
        "params": {
            "perPage": 10,
            "showPartialRows": False,
            "showMetricsAtAllLevels": False,
            "showTotal": False,
            "totalFunc": "sum",
            "percentageCol": "",
            "sort": {"columnIndex": 1, "direction": "desc"},
        },
        "aggs": [count_agg(), terms_agg(field, size)],
        "listeners": {},
    }


def save_dashboard() -> None:
    panels = [
        ("sec-total-events", {"x": 0, "y": 0, "w": 8, "h": 8, "i": "1"}),
        ("sec-parse-errors", {"x": 8, "y": 0, "w": 8, "h": 8, "i": "2"}),
        ("sec-levels-over-time", {"x": 16, "y": 0, "w": 32, "h": 16, "i": "3"}),
        ("sec-dataset-pie", {"x": 0, "y": 8, "w": 16, "h": 16, "i": "4"}),
        ("sec-failed-logins", {"x": 16, "y": 16, "w": 16, "h": 16, "i": "5"}),
        ("sec-top-ips", {"x": 32, "y": 16, "w": 16, "h": 16, "i": "6"}),
    ]
    panels_json = [
        {
            "version": "8.19.0",
            "type": "visualization",
            "gridData": grid,
            "panelIndex": grid["i"],
            "embeddableConfig": {"enhancements": {}},
            "panelRefName": f"panel_{index}",
        }
        for index, (_, grid) in enumerate(panels)
    ]
    references = [
        {"name": f"panel_{index}", "type": "visualization", "id": viz_id}
        for index, (viz_id, _) in enumerate(panels)
    ]
    request(
        "POST",
        f"/api/saved_objects/dashboard/{DASHBOARD_ID}?overwrite=true",
        {
            "attributes": {
                "title": "Security Overview",
                "hits": 0,
                "description": (
                    "Vue d'ensemble des logs de sécurité normalisés "
                    "(CSV + JSON, erreurs d'ingestion incluses)."
                ),
                "panelsJSON": json.dumps(panels_json),
                "optionsJSON": json.dumps(
                    {
                        "useMargins": True,
                        "syncColors": False,
                        "syncCursor": True,
                        "syncTooltips": False,
                        "hidePanelTitles": False,
                    }
                ),
                "version": 1,
                "timeRestore": True,
                "timeFrom": "now-30d",
                "timeTo": "now",
                "kibanaSavedObjectMeta": {
                    "searchSourceJSON": json.dumps(
                        {"query": {"query": "", "language": "kuery"}, "filter": []}
                    )
                },
            },
            "references": references,
        },
    )


def export_dashboard(output: Path) -> None:
    body = {
        "objects": [{"type": "dashboard", "id": DASHBOARD_ID}],
        "includeReferencesDeep": True,
    }
    data = request("POST", "/api/saved_objects/_export", body)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    print(f"Exported {output} ({len(data)} bytes)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("infra/kibana/exports/security-overview.ndjson"),
        help="NDJSON export destination",
    )
    args = parser.parse_args()

    create_data_view("security-logs", "logs-security-*", "Security Logs")
    create_data_view("parse-errors", "logs-parse-errors-*", "Parse Errors")

    save_visualization(
        "sec-total-events", "Total events", metric_viz("Total events"), "security-logs"
    )
    save_visualization(
        "sec-parse-errors",
        "Parse errors",
        metric_viz("Parse errors"),
        "parse-errors",
    )
    save_visualization(
        "sec-levels-over-time",
        "Events over time by level",
        histogram_viz("Events over time by level", "log.level"),
        "security-logs",
    )
    save_visualization(
        "sec-dataset-pie",
        "Events by dataset",
        pie_viz("Events by dataset", "event.dataset"),
        "security-logs",
    )
    save_visualization(
        "sec-top-ips",
        "Top source IPs",
        table_viz("Top source IPs", "source.ip"),
        "security-logs",
    )
    save_visualization(
        "sec-failed-logins",
        "Failed logins by user",
        table_viz("Failed logins by user", "user.name"),
        "security-logs",
        query='event.outcome: "failure" and event.action: "login"',
    )
    save_dashboard()
    export_dashboard(args.output)
    print("Kibana dashboard ready: Security Overview")
    return 0


if __name__ == "__main__":
    sys.exit(main())
