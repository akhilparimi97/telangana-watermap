"""Orient mapped drainage segments from higher to lower sampled DEM endpoints.

This does not infer discharge or hydraulic capacity. It only supplies a coarse,
reproducible downhill direction for the educational flow animation.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).parents[1]
DATA = ROOT / "apps" / "web" / "data"
OUTPUT = DATA / "gravity-flow.geojson"


def elevation_at(grid: dict, longitude: float, latitude: float) -> int:
    latitudes = grid["latitudes"]
    longitudes = grid["longitudes"]
    row = min(range(len(latitudes)), key=lambda index: abs(latitudes[index] - latitude))
    column = min(range(len(longitudes)), key=lambda index: abs(longitudes[index] - longitude))
    return round(grid["elevations"][row * grid["cols"] + column])


def paths(geometry: dict) -> list[list[list[float]]]:
    if geometry.get("type") == "LineString":
        return [geometry.get("coordinates", [])]
    if geometry.get("type") == "MultiLineString":
        return geometry.get("coordinates", [])
    return []


def main() -> None:
    grid = json.loads((DATA / "elevation-grid.json").read_text(encoding="utf-8"))
    datasets = [
        ("River", DATA / "home-map-rivers.geojson"),
        ("Stream", DATA / "home-map-streams.geojson"),
    ]
    features = []
    for feature_class, source in datasets:
        collection = json.loads(source.read_text(encoding="utf-8"))
        for feature_index, feature in enumerate(collection["features"]):
            for path_index, coordinates in enumerate(paths(feature.get("geometry", {}))):
                if len(coordinates) < 2:
                    continue
                start = elevation_at(grid, *coordinates[0][:2])
                end = elevation_at(grid, *coordinates[-1][:2])
                if end > start:
                    coordinates = list(reversed(coordinates))
                    start, end = end, start
                properties = deepcopy(feature.get("properties") or {})
                properties.update({
                    "feature_class": feature_class,
                    "source_category": "DEM-inferred",
                    "source_name": "ICAD mapped drainage oriented with Open-Meteo SRTM/ASTER-derived elevation grid",
                    "source_date": grid.get("retrieved_at"),
                    "flow_direction_basis": "endpoint elevations from sampled DEM grid",
                    "start_elevation_m": start,
                    "end_elevation_m": end,
                    "direction_confidence": "coarse; endpoint-only DEM interpretation",
                    "measured_discharge": False,
                    "source_feature_index": feature_index,
                    "source_path_index": path_index,
                })
                features.append({
                    "type": "Feature",
                    "properties": properties,
                    "geometry": {"type": "LineString", "coordinates": coordinates},
                })
    payload = {
        "type": "FeatureCollection",
        "metadata": {
            "purpose": "Educational downhill orientation; not measured flow or hydraulic modelling",
            "dem_provider": grid.get("provider"),
            "dem_retrieved_at": grid.get("retrieved_at"),
        },
        "features": features,
    }
    OUTPUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {len(features)} DEM-oriented drainage paths to {OUTPUT}")


if __name__ == "__main__":
    main()
