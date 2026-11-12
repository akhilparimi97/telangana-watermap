"""Build viewport-addressable GeoJSON chunks from the TGRAC inventory."""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "apps" / "web" / "data" / "lakes-ponds-tanks-lite.geojson"
TARGET = ROOT / "apps" / "web" / "data" / "waterbody-tiles"
CELL = 0.5


def coordinates(geometry):
    value = geometry.get("coordinates", [])
    if geometry.get("type") == "Polygon":
        return [point for ring in value for point in ring]
    if geometry.get("type") == "MultiPolygon":
        return [point for polygon in value for ring in polygon for point in ring]
    return []


def main():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    buckets = defaultdict(list)
    for feature in data["features"]:
        points = coordinates(feature.get("geometry", {}))
        if not points:
            continue
        lon = sum(point[0] for point in points) / len(points)
        lat = sum(point[1] for point in points) / len(points)
        x = math.floor(lon / CELL)
        y = math.floor(lat / CELL)
        props = feature.setdefault("properties", {})
        props.setdefault("feature_class", "tank/lake/pond")
        props.setdefault("source_category", "Government source")
        props.setdefault("source_name", "TGRAC lakes / ponds / tanks")
        buckets[(x, y)].append(feature)

    TARGET.mkdir(parents=True, exist_ok=True)
    manifest = {"cell_degrees": CELL, "feature_count": 0, "tiles": {}}
    for (x, y), features in sorted(buckets.items()):
        name = f"{x}_{y}.geojson"
        (TARGET / name).write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")), encoding="utf-8")
        manifest["tiles"][f"{x}:{y}"] = {
            "file": name,
            "count": len(features),
            "bounds": [x * CELL, y * CELL, (x + 1) * CELL, (y + 1) * CELL],
        }
        manifest["feature_count"] += len(features)
    (TARGET / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {len(buckets)} viewport tiles with {manifest['feature_count']} features")


if __name__ == "__main__":
    main()
