"""Build static Mapbox Vector Tiles for large waterbody and canal layers.

Run with:
  uv run --with mapbox-vector-tile --with shapely --with mercantile \
    python tools/build_vector_tiles.py
"""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import mapbox_vector_tile
import mercantile
from shapely import make_valid
from shapely.geometry import box, shape
from shapely.strtree import STRtree

ROOT = Path(__file__).parents[1]
DATA = ROOT / "apps" / "web" / "data"
TARGET = DATA / "vector"
EARTH_RADIUS_M = 6_378_137.0


def ring_area_hectares(ring: list[list[float]]) -> float:
    if len(ring) < 3:
        return 0.0
    total = 0.0
    points = ring if ring[0] == ring[-1] else [*ring, ring[0]]
    for first, second in zip(points, points[1:]):
        lon1, lat1 = map(math.radians, first[:2])
        lon2, lat2 = map(math.radians, second[:2])
        total += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))
    return abs(total) * EARTH_RADIUS_M**2 / 2 / 10_000


def polygon_area_hectares(geometry: dict) -> float:
    coordinates = geometry.get("coordinates", [])
    polygons = [coordinates] if geometry.get("type") == "Polygon" else coordinates if geometry.get("type") == "MultiPolygon" else []
    total = 0.0
    for polygon in polygons:
        if not polygon:
            continue
        total += ring_area_hectares(polygon[0])
        total -= sum(ring_area_hectares(hole) for hole in polygon[1:])
    return max(0.0, total)


def waterbody_properties(properties: dict, geometry: dict) -> dict:
    area_ha = round(polygon_area_hectares(geometry), 2)
    if area_ha >= 100:
        feature_class, confidence = "Reservoir", "medium"
    elif area_ha >= 1:
        feature_class, confidence = "Tank", "medium"
    else:
        feature_class, confidence = "Pond", "low"
    name = properties.get("Name") or properties.get("name") or properties.get("L_NAME")
    result = {
        "feature_id": f"tgrac-waterbody-{properties.get('OBJECTID', properties.get('OBJECTID_1', 'unknown'))}",
        "name": name or "Unnamed water body",
        "feature_class": feature_class,
        "area_ha": area_ha,
        "source_category": "Government source",
        "source_name": "TGRAC lakes / ponds / tanks",
        "source_date": "undated source snapshot",
        "classification_method": "TGRAC reservoir/tank class refined by geodesic area",
        "classification_confidence": confidence,
        "display_minzoom": 9 if area_ha >= 1 else 13,
    }
    for key in ("name_source", "name_source_category", "name_source_license", "name_source_url", "name_match_method", "name_match_distance_m", "osm_element_type", "osm_element_id"):
        if properties.get(key) is not None:
            result[key] = properties[key]
    return result


def canal_properties(properties: dict, index: int) -> dict:
    name = properties.get("Name") or properties.get("name") or properties.get("CANAL_NAME") or properties.get("L_NAME")
    return {
        "feature_id": f"hmda-canal-{properties.get('OBJECTID', index)}",
        "name": name or "Unnamed canal segment",
        "feature_class": "Canal / engineered distribution",
        "source_category": "Government source",
        "source_name": "TGRAC HMDA water distribution layer",
        "source_date": "undated source snapshot",
    }


def prepare(source: Path, kind: str):
    collection = json.loads(source.read_text(encoding="utf-8"))
    records = []
    for index, feature in enumerate(collection["features"]):
        geometry_json = feature.get("geometry")
        if not geometry_json:
            continue
        geometry = shape(geometry_json)
        if not geometry.is_valid:
            geometry = make_valid(geometry)
        if geometry.is_empty:
            continue
        properties = waterbody_properties(feature.get("properties") or {}, geometry_json) if kind == "waterbodies" else canal_properties(feature.get("properties") or {}, index)
        records.append((geometry, properties))
    return records


def build_layer(name: str, records, minimum_zoom: int, maximum_zoom: int):
    output = TARGET / name
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    geometries = [record[0] for record in records]
    tree = STRtree(geometries)
    west = min(geometry.bounds[0] for geometry in geometries)
    south = min(geometry.bounds[1] for geometry in geometries)
    east = max(geometry.bounds[2] for geometry in geometries)
    north = max(geometry.bounds[3] for geometry in geometries)
    tile_count = feature_count = byte_count = 0
    for zoom in range(minimum_zoom, maximum_zoom + 1):
        for tile in mercantile.tiles(west, south, east, north, [zoom]):
            bounds = mercantile.bounds(tile)
            tile_box = box(bounds.west, bounds.south, bounds.east, bounds.north)
            encoded_features = []
            for record_index in tree.query(tile_box):
                geometry, properties = records[int(record_index)]
                if name == "waterbodies" and zoom < properties["display_minzoom"]:
                    continue
                clipped = geometry.intersection(tile_box)
                if clipped.is_empty:
                    continue
                tolerance = max(bounds.east - bounds.west, bounds.north - bounds.south) / 8192
                simplified = clipped.simplify(tolerance, preserve_topology=True)
                if simplified.is_empty:
                    continue
                encoded_features.append({"geometry": simplified, "properties": properties})
            payload = mapbox_vector_tile.encode(
                {"name": name, "features": encoded_features},
                default_options={"quantize_bounds": (bounds.west, bounds.south, bounds.east, bounds.north), "extents": 4096},
            )
            path = output / str(zoom) / str(tile.x) / f"{tile.y}.pbf"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            tile_count += 1
            feature_count += len(encoded_features)
            byte_count += len(payload)
    manifest = {
        "format": "Mapbox Vector Tile",
        "source_layer": name,
        "minimum_zoom": minimum_zoom,
        "maximum_zoom": maximum_zoom,
        "bounds": [west, south, east, north],
        "source_feature_count": len(records),
        "named_feature_count": sum(record[1].get("name") not in (None, "", "Unnamed water body") for record in records) if name == "waterbodies" else 0,
        "written_tile_count": tile_count,
        "encoded_feature_instances": feature_count,
        "bytes": byte_count,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(name, manifest)


def main():
    enriched = DATA / "lakes-ponds-tanks-enriched.geojson"
    waterbodies = prepare(enriched if enriched.exists() else DATA / "lakes-ponds-tanks-lite.geojson", "waterbodies")
    canals = prepare(DATA / "hmda-canals.geojson", "canals")
    TARGET.mkdir(exist_ok=True)
    build_layer("waterbodies", waterbodies, 9, 13)
    build_layer("canals", canals, 10, 13)


if __name__ == "__main__":
    main()
