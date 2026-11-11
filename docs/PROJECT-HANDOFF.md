# Telangana WaterMap — implementation handoff

**Status:** discovery complete; no application code written yet  
**Scope:** Telangana surface-water inventory, irrigation infrastructure, river/stream network, catchment context, and 3D-ready elevation model  
**Primary user experience:** Google-Maps-like pan/zoom/search/satellite basemap, with water infrastructure as the primary visual layer

## 1. The uncomfortable constraint

“Every single reservoir and water flow” cannot be treated as one clean, authoritative dataset. Public sources disagree in naming, geometry, date, and coverage. The product must therefore expose **provenance, source date, confidence, and conflicts** instead of silently merging records and presenting them as fact.

The first release should be an auditable **water-resource atlas**, not a live operational control system. Live reservoir level, discharge, gate, and telemetry data require explicit agency access and a separate validation path.

## 2. Verified source discovery

### Government of Telangana / TGRAC ArcGIS

Service: `https://tgrac.telangana.gov.in/arcgis/rest/services/TGIIC_Folder/BaseLayers/MapServer`

Verified layers and current query counts:

| Layer | Geometry | Count | Useful fields / notes |
|---|---:|---:|---|
| Lakes / Ponds / Tanks (14) | Polygon | 36,580 | `Descr_1..3`, `PI_CODE`, `LU_Code`, area/length fields |
| Rivers (15) | Polygon | 1,891 | `Descr_1..3`, `PI_CODE`, `LU_Code`, geometry fields |
| Reservoirs (16) | Polygon | 57 | `Name`, `TYPE`, `Category`, `res`, `R_Type` |

The service extent covers Telangana and nearby geographic context. The “Water Bodies” group layer (13) contains these sublayers.

### Telangana Irrigation & CAD map

`https://irrigation.telangana.gov.in/icad/maps`

The page loads these public GeoJSON assets:

- `home-map-rivers.geojson` — 23 named river features
- `home-map-streams.geojson` — 443 stream features
- `maj_med.geojson` — 81 major/medium/lift project features
- `home-map-state.geojson`, `home-map-districts.geojson` — boundaries/context

`maj_med.geojson` exposes project-related fields including project/dam name, category, status, latitude/longitude, storage in TMC, FRL, lift indicators, and metadata fields. These must be normalized, not copied blindly.

### India-WRIS / CWC / NRSC

`https://indiawris.gov.in/wris/`

India-WRIS provides national layers and modules for dams, reservoirs, rivers, canals, command areas, basin/watershed context, and reservoir observations. It should be used for cross-checking and filling gaps, subject to access and licensing confirmation for each downloaded layer.

### Official statistics and inventory references

- Telangana State Portal, Irrigation & CAD: `https://www.telangana.gov.in/departments/irrigation-and-cad/`
- Telangana DES “At a Glance” irrigation tables: `https://des.telangana.gov.in/publications/At%20glance%20Book%202023%20%2012%20dec%2023.pdf`
- India-WRIS Telangana dams page: `https://indiawris.gov.in/wiki/doku.php?id=dams_in_telangana`

These are valuable for totals, classification, and attributes, but tabular statistics must not be mistaken for spatially complete geometry.

## 3. Product definition

### Canonical feature classes

1. **Water body** — lake, pond, tank, reservoir, barrage impoundment, wetland, or other polygonal surface-water feature.
2. **Structure** — dam, barrage, weir, anicut, regulator, check dam, intake, pumping station, powerhouse, or lift component.
3. **Flow path** — named river, stream, canal, distributary, pipeline, tunnel, or inferred drainage path. Store whether observed, official, or derived.
4. **Project** — an irrigation or water-supply scheme that may contain multiple structures, water bodies, flow paths, command areas, and phases.
5. **Command area** — the land served or intended to be served by a project; distinguish CCA, ayacut, stabilized ayacut, and proposed area.
6. **Observation** — time-indexed water level, storage, inflow, outflow, rainfall, quality, or telemetry reading.
7. **Terrain surface** — DEM-derived elevation and terrain products used for visualization and analysis.

### Identity and provenance rules

Every canonical record needs:

- stable internal ID;
- source system and source record ID;
- source URL/API endpoint;
- source publication or retrieval date;
- geometry type and CRS;
- original name plus normalized display name;
- aliases/transliterations;
- feature class and subtype;
- data quality/confidence grade;
- last verification status;
- conflict links when two sources may represent the same real-world feature.

Never deduplicate only by name. Use geometry proximity, aliases, project relationships, structure type, and source IDs; preserve both source records until a match is reviewed.

## 4. Recommended architecture

### Frontend

- React + TypeScript.
- MapLibre GL JS for the map interaction and vector-tile rendering.
- Satellite imagery from a properly licensed provider; do not scrape or re-host Google satellite tiles.
- Layer controls, search, district/project filters, timeline, legend, feature detail drawer, measurement tools, shareable URL state.
- 3D mode using MapLibre terrain for initial terrain and CesiumJS only if true globe/terrain analysis becomes necessary.

### Data and backend

- PostgreSQL + PostGIS as the canonical store.
- Python ingestion jobs using `httpx`/stdlib HTTP, GeoPandas or GDAL where available, and explicit source adapters.
- Object storage for raw source snapshots and generated tiles.
- Tippecanoe/PMTiles or a tile server for large static layers.
- API: FastAPI or equivalent, with spatial filtering, search, provenance, and version endpoints.
- Scheduled ingestion must create a new dataset version; it must never overwrite raw source evidence.

### Suggested repository layout

```text
 telangana-watermap/
   apps/web/
   services/api/
   pipelines/
     sources/tgrac_arcgis/
     sources/icad_geojson/
     sources/indiawris/
     transforms/
   data/
     raw/              # immutable snapshots; large files externalized
     processed/
   db/migrations/
   docs/
   infra/
```

## 5. Initial database shape

Core tables:

- `source_dataset(id, publisher, endpoint, license, retrieved_at, version_label, checksum)`
- `source_feature(id, source_dataset_id, source_record_id, raw_properties, raw_geometry)`
- `water_feature(id, class, subtype, canonical_name, geometry, elevation_m, confidence)`
- `feature_source_link(water_feature_id, source_feature_id, match_method, reviewed_by, reviewed_at)`
- `structure(water_feature_id, structure_type, height_m, length_m, status)`
- `project(id, name, basin, category, status, storage_tmc, frl_m, ayacut_acres)`
- `project_feature(project_id, water_feature_id, relationship_type)`
- `flow_path(id, flow_type, name, geometry, directionality, source_kind)`
- `elevation_surface(id, provider, resolution_m, vertical_datum, coverage, acquired_at)`
- `observation(feature_id, observed_at, metric, value, unit, source_dataset_id)`
- `review_queue(id, issue_type, affected_ids, severity, status, notes)`

Important distinction: `elevation_m` on a feature is not the same as water level, FRL, MWL, bed level, or dam crest elevation. Store each with an explicit metric and vertical datum.

## 6. Map behavior for v1

### Base map

- Pan, zoom, rotate, pitch, compass, geolocation where permitted.
- Satellite/hybrid/streets basemap switch.
- Search by project, reservoir, tank, river, stream, district, mandal, village, and source ID.
- URL-shareable center, zoom, active layers, and selected feature.

### Water-first overlays

Default visual hierarchy:

1. reservoirs and major project storages;
2. rivers and named streams;
3. canals and lift/pipeline infrastructure;
4. tanks/ponds, clustered at low zoom and decluttered at high zoom;
5. dams, barrages, weirs, intakes, pump houses, and other structures;
6. basins, sub-basins, watersheds, districts, mandals, and command areas.

Each feature card should show name, type, status, source(s), source date, key attributes, elevation metrics with datum, and a “data quality / conflicts” section.

### 3D readiness without premature complexity

V1 should store elevation and vertical datum now, but ship 2.5D first: terrain exaggeration, hillshade, contour toggle, and extruded structures where data supports it. Full reservoir bathymetry and water-surface volume simulation are not available from ordinary DEM data and should not be implied.

## 7. Data pipeline phases

### Phase A — inventory and baseline map

- Ingest TGRAC layers 14–16.
- Ingest ICAD GeoJSON assets.
- Record raw snapshots and checksums.
- Normalize CRS to EPSG:4326 for interchange and a projected CRS for area/length calculations.
- Load Telangana administrative boundaries.
- Produce a first map with provenance and search.
- Generate a reconciliation report: counts, duplicate candidates, unmatched names, invalid geometries, missing attributes.

### Phase B — complete the network

- Add India-WRIS dams/reservoirs/rivers/canals/command-area layers where legally and technically accessible.
- Add hydrographic/drainage data such as HydroSHEDS or another licensed source for derived flow direction and catchments.
- Add OpenStreetMap only as a supplemental source, never as the sole authority for irrigation infrastructure.
- Add project-to-structure and project-to-flow relationships.

### Phase C — terrain and analytical layers

- Add a documented DEM source and vertical datum.
- Generate hillshade, contours, slope, flow accumulation, drainage basins, and pour-point tools.
- Add cross-sections and elevation profiles along selected flow paths.
- Add storage/elevation curves only where official curves or bathymetry exist.

### Phase D — observations and governance

- Add time-series observations only from identified official feeds or licensed datasets.
- Add source freshness indicators and update history.
- Add review workflow for conflicts and user-submitted corrections.
- Add export to GeoJSON, CSV, KML, and printable map/report.

## 8. Acceptance criteria for the first working release

- A user can open Telangana in satellite view, pan/zoom/rotate, and switch base maps.
- The map renders the verified TGRAC and ICAD layers without blocking at the full-state view.
- A user can search and select a project, reservoir, river, stream, tank, or district.
- Every displayed feature has a source link and retrieval/source date.
- Feature counts and source versions are visible in a data catalog.
- Duplicate/conflict candidates are retained in a review queue rather than silently merged.
- The system stores elevation as a typed metric with source and vertical datum.
- A reproducible ingestion command can rebuild processed data from raw snapshots.
- No Google satellite tiles are used outside Google’s permitted API/product terms.

## 9. Locked product decisions

- **Audience:** public atlas for exploration and education.
- **Basemap path:** Mapbox or Esri licensed satellite imagery; perform a cost/licensing comparison before implementation.
- **Initial coverage:** Telangana administrative boundary first.
- **Freshness:** versioned static inventory with scheduled refresh.
- **First 3D release:** terrain, hillshade, contours, and elevation profiles.

Still unresolved: data redistribution policy, review model, deployment target, and the exact refresh schedule.

## 10. First implementation slice

Build the catalog and map around the verified TGRAC + ICAD sources first. Do not begin by attempting to scrape every web portal. The first slice should prove: source snapshots → normalization → PostGIS → vector tiles/API → satellite map → searchable provenance-aware detail panel. Once this works, add India-WRIS and terrain as separate source adapters.
