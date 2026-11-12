"""Build a real Sentinel-2 monthly water-extent case study for Mid Manair.

This is a bounded, reproducible seed dataset—not statewide historical coverage.
It uses Microsoft Planetary Computer Sentinel-2 L2A COGs, NDWI and the Sentinel
scene-classification water class. Missing or unusable months are omitted.

Run with:
  uv run --with pystac-client --with planetary-computer --with rasterio \
    --with pyproj --with shapely --with numpy \
    python tools/build_seasonal_observations.py
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import planetary_computer as pc
import pystac_client
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.features import geometry_mask, shapes
from rasterio.vrt import WarpedVRT
from rasterio.windows import from_bounds
from shapely import transform as shapely_transform
from shapely.geometry import Point, mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "apps" / "web" / "data" / "seasonal-observations.json"
CENTER = (78.96111, 18.39278)
BBOX = [CENTER[0] - 0.10, CENTER[1] - 0.10, CENTER[0] + 0.10, CENTER[1] + 0.10]
YEAR = 2025
MAX_SCENE_CLOUD = 20
MIN_AOI_VALID_PERCENT = 90
MAX_AOI_CLOUD_SHADOW_PERCENT = 5
MAX_AOI_NODATA_PERCENT = 1
NDWI_THRESHOLD = 0.05
MIN_EXTENT_HECTARES = 500
DISPLAY_SIMPLIFY_METRES = 40


def candidate_items(catalog, month: int):
    start = date(YEAR, month, 1)
    end = date(YEAR + (month == 12), month % 12 + 1, 1)
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=BBOX,
        datetime=f"{start.isoformat()}/{end.isoformat()}",
        query={"eo:cloud_cover": {"lt": MAX_SCENE_CLOUD}},
        max_items=100,
    )
    point = Point(*CENTER)
    candidates = [item for item in search.items() if shape(item.geometry).covers(point)]
    return sorted(candidates, key=lambda item: item.properties.get("eo:cloud_cover", 100))


def derive_extent(item):
    with rasterio.open(item.assets["B03"].href) as green_source, rasterio.open(item.assets["B08"].href) as nir_source, rasterio.open(item.assets["SCL"].href) as scl_source:
        to_projected = Transformer.from_crs("EPSG:4326", green_source.crs, always_xy=True).transform
        projected_bbox = shapely_transform(shape({
            "type": "Polygon",
            "coordinates": [[
                [BBOX[0], BBOX[1]], [BBOX[2], BBOX[1]], [BBOX[2], BBOX[3]],
                [BBOX[0], BBOX[3]], [BBOX[0], BBOX[1]],
            ]],
        }), to_projected, interleaved=False)
        window = from_bounds(*projected_bbox.bounds, transform=green_source.transform).round_offsets().round_lengths()
        window = window.intersection(rasterio.windows.Window(0, 0, green_source.width, green_source.height))
        green = green_source.read(1, window=window).astype("float32")
        nir = nir_source.read(1, window=window).astype("float32")
        window_transform = green_source.window_transform(window)
        with WarpedVRT(
            scl_source,
            crs=green_source.crs,
            transform=green_source.transform,
            width=green_source.width,
            height=green_source.height,
            resampling=Resampling.nearest,
        ) as scl_vrt:
            scl = scl_vrt.read(1, window=window)
        denominator = green + nir
        ndwi = np.divide(green - nir, denominator, out=np.full_like(green, -1), where=denominator > 0)
        water = (ndwi > NDWI_THRESHOLD) & (scl == 6)
        candidates = []
        projected_center = Point(*to_projected(*CENTER))
        for geometry, value in shapes(water.astype("uint8"), mask=water, transform=window_transform):
            if value != 1:
                continue
            candidate = shape(geometry)
            if candidate.area >= MIN_EXTENT_HECTARES * 10_000:
                candidates.append(candidate)
        if not candidates:
            return None
        containing = [candidate for candidate in candidates if candidate.covers(projected_center)]
        selected = max(containing, key=lambda geometry: geometry.area) if containing else min(candidates, key=lambda geometry: geometry.distance(projected_center))
        if selected.distance(projected_center) > 2_000:
            return None
        area_ha = selected.area / 10_000
        display_geometry = selected.simplify(DISPLAY_SIMPLIFY_METRES, preserve_topology=True)
        to_wgs84 = Transformer.from_crs(green_source.crs, "EPSG:4326", always_xy=True).transform
        return (
            shapely_transform(display_geometry, to_wgs84, interleaved=False),
            area_ha,
            shapely_transform(selected, to_wgs84, interleaved=False),
        )


def aoi_quality(item, reference_geometry):
    """Return SCL quality percentages over one fixed maximum-water reference AOI."""
    with rasterio.open(item.assets["SCL"].href) as source:
        to_projected = Transformer.from_crs("EPSG:4326", source.crs, always_xy=True).transform
        projected = shapely_transform(reference_geometry, to_projected, interleaved=False)
        window = from_bounds(*projected.bounds, transform=source.transform).round_offsets().round_lengths()
        window = window.intersection(rasterio.windows.Window(0, 0, source.width, source.height))
        scl = source.read(1, window=window)
        mask = geometry_mask(
            [mapping(projected)], out_shape=scl.shape,
            transform=source.window_transform(window), invert=True,
        )
        values = scl[mask]
        if values.size == 0:
            return None
        nodata = np.isin(values, [0])
        cloud_shadow = np.isin(values, [3, 8, 9, 10])
        valid = np.isin(values, [2, 4, 5, 6, 7])
        return {
            "aoi_valid_coverage_percent": round(float(valid.mean() * 100), 2),
            "aoi_cloud_shadow_percent": round(float(cloud_shadow.mean() * 100), 2),
            "aoi_nodata_percent": round(float(nodata.mean() * 100), 2),
        }


def quality_is_usable(quality):
    return quality is not None and (
        quality["aoi_valid_coverage_percent"] >= MIN_AOI_VALID_PERCENT
        and quality["aoi_cloud_shadow_percent"] <= MAX_AOI_CLOUD_SHADOW_PERCENT
        and quality["aoi_nodata_percent"] <= MAX_AOI_NODATA_PERCENT
    )


def main():
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=pc.sign_inplace,
    )
    items_by_month = {month: candidate_items(catalog, month) for month in range(1, 13)}
    reference_extents = []
    extent_cache = {}
    for month, items in items_by_month.items():
        for item in items:
            reference_result = derive_extent(item)
            extent_cache[item.id] = reference_result
            if reference_result is not None:
                reference_extents.append(reference_result[2])
                break
    if not reference_extents:
        raise RuntimeError("Could not derive an observed-union reference AOI")
    reference_geometry = unary_union(reference_extents)

    observations = []
    for month in range(1, 13):
        accepted = None
        for item in items_by_month[month]:
            quality = aoi_quality(item, reference_geometry)
            if not quality_is_usable(quality):
                print(month, "rejected for AOI quality", item.id, quality)
                continue
            result = extent_cache.get(item.id)
            if item.id not in extent_cache:
                result = derive_extent(item)
                extent_cache[item.id] = result
            if result is None:
                print(month, "no connected water extent near reference point", item.id)
                continue
            accepted = item, quality, result
            break
        if accepted is None:
            print(month, "no usable observation")
            continue
        item, quality, (geometry, area_ha, _analysis_geometry) = accepted
        observations.append({
            "body_id": "mid-manair-sentinel-case-study",
            "name": "Mid Manair Reservoir — satellite-derived case study",
            "year": YEAR,
            "month": month,
            "observed_at": item.datetime.isoformat(),
            "area_ha": round(area_ha, 2),
            "source_category": "Satellite-derived",
            "source_name": "Sentinel-2 L2A via Microsoft Planetary Computer",
            "source_scene_id": item.id,
            "scene_cloud_cover_percent": round(item.properties.get("eo:cloud_cover", 0), 3),
            **quality,
            "method": f"NDWI > {NDWI_THRESHOLD} intersected with Sentinel-2 SCL water class; observed-union reference AOI quality screen; reported area uses unsimplified analysis geometry; display geometry simplified {DISPLAY_SIMPLIFY_METRES} m",
            "confidence": "case-study interpretation; inspect imagery before engineering use",
            "geometry": mapping(geometry),
        })
        print(month, observations[-1]["area_ha"], item.id, quality)
    if not observations:
        raise RuntimeError("No usable observations were derived; existing file was not changed")

    maximum = max(observation["area_ha"] for observation in observations)
    monthly_areas = {}
    for observation in observations:
        monthly_areas.setdefault(observation["month"], []).append(observation["area_ha"])
    for observation in observations:
        observation["percent_of_observed_maximum"] = round(observation["area_ha"] / maximum * 100, 1)
        values = monthly_areas[observation["month"]]
        observation["comparison_year_count"] = len(values)
        if len(values) >= 2:
            observation["monthly_mean_area_ha"] = round(sum(values) / len(values), 2)

    payload = {
        "period": {"start_year": 2015, "end_year": 2026},
        "missing_policy": "unavailable",
        "units": {"area": "hectares", "extent": "percent_of_observed_maximum"},
        "coverage_note": "Timeline interface spans 2015–2026; bundled verified geometry is limited to quality-screened 2025 Mid Manair observations. Unavailable months and years are not interpolated.",
        "source": "Sentinel-2 L2A via Microsoft Planetary Computer",
        "method_version": "sentinel2-ndwi-scl-aoi-v3",
        "reference_aoi_method": "union_of_unscreened_monthly_candidate_extents",
        "quality_thresholds": {
            "minimum_aoi_valid_coverage_percent": MIN_AOI_VALID_PERCENT,
            "maximum_aoi_cloud_shadow_percent": MAX_AOI_CLOUD_SHADOW_PERCENT,
            "maximum_aoi_nodata_percent": MAX_AOI_NODATA_PERCENT,
        },
        "observations": observations,
    }
    OUTPUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {len(observations)} observations ({OUTPUT.stat().st_size} bytes) to {OUTPUT}")


if __name__ == "__main__":
    main()
