"""Match openly licensed OpenStreetMap waterbody names to TGRAC polygons.

The government geometry remains authoritative for shape. OSM contributes only
public/reference names, with ODbL attribution and a per-name evidence URL.

Refresh the input snapshot separately with an Overpass query for named water
features, then run:
  uv run --with shapely python tools/enrich_waterbody_names.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from shapely import make_valid
from shapely.geometry import Point, shape
from shapely.ops import nearest_points
from shapely.strtree import STRtree

ROOT = Path(__file__).parents[1]
DATA = ROOT / "apps" / "web" / "data"
SOURCE = DATA / "lakes-ponds-tanks-lite.geojson"
OSM_SNAPSHOT = DATA / "osm-named-waterbodies.json"
OUTPUT = DATA / "lakes-ponds-tanks-enriched.geojson"
NAME_INDEX = DATA / "waterbody-name-index.geojson"
CANDIDATES = DATA / "osm-named-waterbody-candidates.geojson"
MAX_NEAREST_METRES = 500
WATERBODY_TYPES = {"lake", "reservoir", "pond", "basin", "lagoon", "oxbow", "reflecting_pool"}
REJECTED_WATER_TYPES = {"river", "canal", "ditch", "drain", "stream"}
GENERIC_NAMES = {"water tank", "water pond", "pond", "reservoir", "balancing reservoir", "water holding reservoir", "local lake", "kunta"}


def osm_point(element):
    if element.get("type") == "node" and "lon" in element and "lat" in element:
        return Point(element["lon"], element["lat"])
    center = element.get("center") or {}
    if "lon" in center and "lat" in center:
        return Point(center["lon"], center["lat"])
    return None


def distance_metres(first, second):
    lon1, lat1, lon2, lat2 = map(math.radians, (first.x, first.y, second.x, second.y))
    dlon, dlat = lon2 - lon1, lat2 - lat1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6_371_008.8 * 2 * math.asin(min(1, math.sqrt(value)))


def eligible_waterbody(tags, name):
    water_type = str(tags.get("water") or "").casefold()
    lowered_name = name.casefold().strip()
    if water_type in REJECTED_WATER_TYPES or lowered_name in GENERIC_NAMES:
        return False
    if any(phrase in lowered_name for phrase in (" pump house", "approach canal")):
        return False
    if "checkdam" in lowered_name or "check dam" in lowered_name:
        return False
    if lowered_name.endswith(" river") or lowered_name.endswith(" canal"):
        return False
    return tags.get("landuse") == "reservoir" or water_type in WATERBODY_TYPES or (tags.get("natural") == "water" and water_type not in REJECTED_WATER_TYPES)


def main():
    collection = json.loads(SOURCE.read_text(encoding="utf-8"))
    snapshot = json.loads(OSM_SNAPSHOT.read_text(encoding="utf-8"))
    geometries = []
    valid_feature_indexes = []
    for feature_index, feature in enumerate(collection["features"]):
        geometry = shape(feature.get("geometry"))
        if not geometry.is_valid:
            geometry = make_valid(geometry)
        if geometry.is_empty:
            continue
        geometries.append(geometry)
        valid_feature_indexes.append(feature_index)
    tree = STRtree(geometries)
    proposals = {}
    matched_elements = set()
    conflict_elements = set()
    for element in snapshot.get("elements", []):
        tags = element.get("tags") or {}
        name = str(tags.get("name") or "").strip()
        point = osm_point(element)
        if not name or point is None or not eligible_waterbody(tags, name):
            continue
        containing = [int(index) for index in tree.query(point) if geometries[int(index)].covers(point)]
        if containing:
            geometry_index = min(containing, key=lambda index: geometries[index].area)
            method = "OSM centre contained by TGRAC polygon"
            match_distance = 0
        else:
            geometry_index = int(tree.nearest(point))
            nearest_on_geometry, _ = nearest_points(geometries[geometry_index], point)
            match_distance = distance_metres(point, nearest_on_geometry)
            if match_distance > MAX_NEAREST_METRES:
                continue
            method = "OSM centre matched to nearest TGRAC polygon within 500 m"
        feature_index = valid_feature_indexes[geometry_index]
        score = (0 if containing else 1, match_distance, int(element["id"]))
        proposals.setdefault(feature_index, []).append((score, element, name, method, match_distance))

    assignments = {}
    for feature_index, records in proposals.items():
        names = {record[2].casefold().strip() for record in records}
        element_keys = {(record[1]["type"], record[1]["id"]) for record in records}
        if len(names) > 1:
            conflict_elements.update(element_keys)
            continue
        assignments[feature_index] = min(records, key=lambda record: record[0])
        matched_elements.update(element_keys)

    for feature_index, (_, element, name, method, match_distance) in assignments.items():
        properties = collection["features"][feature_index].setdefault("properties", {})
        properties.update({
            "name": name,
            "name_source": "OpenStreetMap contributors",
            "name_source_category": "Public/reference source",
            "name_source_license": "ODbL 1.0",
            "name_source_url": f"https://www.openstreetmap.org/{element['type']}/{element['id']}",
            "name_match_method": method,
            "name_match_distance_m": round(match_distance, 2),
            "osm_element_type": element["type"],
            "osm_element_id": element["id"],
        })
    collection["name_enrichment"] = {
        "source": "OpenStreetMap contributors",
        "license": "ODbL 1.0",
        "source_url": "https://www.openstreetmap.org/copyright",
        "matched_feature_count": len(assignments),
        "geometry_source": "TGRAC lakes / ponds / tanks",
    }
    OUTPUT.write_text(json.dumps(collection, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    index_features = []
    for feature_index, (_, element, name, method, match_distance) in assignments.items():
        point = geometries[valid_feature_indexes.index(feature_index)].representative_point()
        properties = collection["features"][feature_index]["properties"]
        index_features.append({
            "type": "Feature",
            "properties": {key: properties[key] for key in properties if key.startswith("name") or key in ("OBJECTID", "Descr_2")},
            "geometry": {"type": "Point", "coordinates": [point.x, point.y]},
        })
    NAME_INDEX.write_text(json.dumps({"type": "FeatureCollection", "features": index_features}, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

    boundary = shape(json.loads((DATA / "state-boundary.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"])
    candidate_features = []
    seen_candidates = set()
    for element in snapshot.get("elements", []):
        key = (element.get("type"), element.get("id"))
        tags = element.get("tags") or {}
        name = str(tags.get("name") or "").strip()
        point = osm_point(element)
        if key in matched_elements or not name or point is None or not eligible_waterbody(tags, name) or not boundary.covers(point):
            continue
        dedupe_key = (name.casefold(), round(point.x, 3), round(point.y, 3))
        if dedupe_key in seen_candidates:
            continue
        seen_candidates.add(dedupe_key)
        candidate_features.append({
            "type": "Feature",
            "properties": {
                "name": name,
                "feature_class": "Named water body candidate",
                "candidate_status": "Name conflict with TGRAC polygon" if key in conflict_elements else "Needs geometry reconciliation",
                "source_category": "Public/reference source",
                "source_name": "OpenStreetMap contributors",
                "source_url": f"https://www.openstreetmap.org/{element['type']}/{element['id']}",
                "source_license": "ODbL 1.0",
            },
            "geometry": {"type": "Point", "coordinates": [point.x, point.y]},
        })
    CANDIDATES.write_text(json.dumps({"type": "FeatureCollection", "features": candidate_features}, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"matched {len(assignments)} names; indexed {len(index_features)}; retained {len(candidate_features)} unmatched Telangana candidates from {len(snapshot.get('elements', []))} OSM elements")


if __name__ == "__main__":
    main()
