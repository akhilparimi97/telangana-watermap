# Telangana WaterMap — Final Implementation Handoff

Status: requirements confirmed by Akhil; do not begin implementation until this handoff is used as the build contract.

## 1. Product definition

Build a public educational and research atlas for the Telangana administrative boundary, inspired by Zoom Earth and the Telangana ICAD map.

The primary question is:

> How does water move naturally across Telangana, and how does Telangana collect, lift, store, and distribute Godavari and Krishna water?

The product is a state-wide visualisation overview, not a live operations dashboard and not an engineering-grade hydraulic simulator.

## 2. Locked product decisions

- Audience: public explorers and engineers/researchers.
- Geography: Telangana administrative boundary first; no wider-basin requirement in this release.
- Product type: stable infrastructure and environmental atlas.
- Imagery: licensed satellite basemap for visual context.
- Remote sensing: Sentinel-2/Landsat-style historical observations for water detection where available.
- Elevation: DEM-backed project elevations, catchments, terrain, and gravity-flow interpretation.
- Time interaction: selected year/month plus historical monthly comparison where available; initial target is 2015–present.
- Default map: satellite imagery with all relevant layers available, but detail density controlled by zoom.
- Layer detail: fixed zoom thresholds in the first implementation.
- Editing: authenticated owner-only persistent editing of lift-project coordinates and routes. Visitors cannot edit.
- Map engine: MapLibre GL JS with vector tiles/PMTiles for scale and smooth zooming.
- Implementation style: one coherent coding session from this handoff; no planned phased product rollout.
- Required quality: robust tests, browser acceptance tests, visible provenance, and explicit limitations.

## 3. Map information hierarchy

### State-level zoom

Show:

- Telangana boundary.
- Major rivers and basin context.
- Major reservoirs and irrigation projects.
- Major collection, storage, and lift systems.
- High-level water-body density or simplified outlines.

### Regional zoom

Reveal:

- Medium reservoirs.
- Major and medium canals.
- Lift-project markers and documented project relationships.
- Catchment and drainage zones.
- Larger lakes, tanks, and ponds.

### District/mandal zoom

Reveal:

- Individual tanks, lakes, ponds, and candidate bodies.
- Streams and local drainage.
- Project elevation markers.
- Engineered distribution features.
- Satellite-derived water extents.

### Local zoom

Reveal:

- Individual water-body polygon and observed extent.
- Month/year water-extent view.
- Area and percentage of maximum observed extent.
- Elevation estimate.
- Source category and source line.
- Nearby rivers, canals, projects, and catchments.
- Lift intake/discharge relationship details where documented.

## 4. Source and classification model

A feature may carry multiple source categories:

- Government source.
- Satellite-derived.
- DEM-inferred.
- Public/reference source.

Government source means the record originates from a government dataset or document. It does not automatically mean current, complete, or geometrically verified.

### Water-body classification

Use exact modelled classes where possible:

- Reservoir.
- Lake.
- Tank.
- Pond.
- Wetland.
- Seasonal/flood water.

The classification may use:

- Satellite appearance.
- Terrain and surrounding landform.
- Nearby government/reference names.
- Geometry and persistence across observations.

Every modelled classification must carry a source description such as:

> Source: Modelled from satellite interpretation and terrain context.

Do not build a heavy reconciliation workflow into this release. Do not hide uncertainty; disclose it in the feature detail.

## 5. Water-body discovery

Start from the satellite/terrain evidence that visibly contains more bodies than the current ICAD snapshot.

Use:

- Licensed basemap imagery for user-facing context.
- Sentinel-2/Landsat-style data for repeatable historical water detection.
- DEM for terrain context and derived elevation.
- TGRAC, ICAD, and other named government sources where available.
- Public/reference sources for candidate names and locations.

Do not scrape or re-host commercial imagery. Do not claim that every satellite-visible patch is a permanent water body.

Initial display threshold:

- Default detailed inventory: bodies >= 1 hectare.
- Larger/important bodies visible at lower zoom.
- Smaller bodies available at higher zoom.
- Temporary or uncertain detections use a separate class/source description.

## 6. Time slider

The first useful historical mode is:

- Selected year/month.
- Historical monthly comparison where data exists.
- Initial temporal target: 2015–present.
- Water extent as polygon and area.
- Percentage of maximum observed extent.

Missing observations should remain blank/unavailable. Do not interpolate or fabricate estimates in the first implementation.

Do not present water extent as storage volume. Do not infer live reservoir level from satellite area without a separately validated storage curve.

## 7. Flow visual language

### Natural gravity flow

- Blue dots and directional lines on the normal map.
- Based on DEM-derived downhill interpretation plus mapped drainage where available.
- Existing gravity interpretation remains present.
- Blue means natural/terrain-derived interpretation, not measured discharge.
- Sparse enough to remain understandable at state scale.

### Engineered distribution

- Amber or clearly distinct distribution styling for canals, tunnels, and documented engineered paths.
- Reveal detail progressively with zoom.

### Lift projects

- Red dots at lift-project locations.
- Red arrows/relationships for documented lift transfers.
- Project elevation shown in tooltip/detail.
- Red does not mean live pumping or current operating status.

### Lift-route evidence

Government press releases and department documents are acceptable evidence sources.

A documented lift relationship may be shown even when exact geometry is unavailable. If only endpoints are known:

- Allow the owner to set or move intake and destination coordinates.
- Allow the owner to plot or adjust the route.
- A straight red connection may be used as a conceptual route, but it must be visibly labelled as conceptual/owner-edited.
- Never imply that a straight line is the actual pipeline, tunnel, or canal alignment.
- If a document provides route alignment, coordinates, canal, tunnel, or mapped infrastructure, use that geometry instead.

Visitors may view routes but may not edit them.

## 8. Educational guided mode

Provide clickable steps that toggle layers, move the camera, and show short explanatory text:

1. Terrain and basins.
2. Natural drainage.
3. Collection reservoirs and tanks.
4. Lift projects.
5. Storage and balancing reservoirs.
6. Canals and distribution.

The guided mode should teach the system without requiring the user to understand GIS layer controls first.

## 9. Feature detail card

Initial card should remain concise but useful. Minimum fields:

- Name or generated identifier.
- Feature class.
- Area where available.
- Elevation estimate where relevant.
- Source category/categories.
- Source line, e.g. `Source: TGRAC`, `Source: ICAD`, `Source: Modelled from satellite interpretation`, or `Source: Public reference`.
- Source date or layer date when available.
- Seasonal water-extent overview where available.
- Confidence/limitations in plain language.
- Nearby or linked project/water features.

Keep the main card uncluttered. A small link icon may open the named source/document; avoid large citation blocks in the first view.

## 10. Owner-only editing

The owner editing surface may:

- Move lift intake coordinates.
- Move lift discharge/destination coordinates.
- Plot, replace, or adjust conceptual lift routes.
- Add a note explaining the correction.
- Save a versioned edit.
- Preserve the prior geometry and source state.

Visitors must have read-only access.

Persistent editing requires:

- Owner authentication.
- Audit history.
- Versioned edits.
- Revert capability.
- Explicit edited-by and edited-at metadata.

Never overwrite the original government or satellite-derived record.

## 11. Technical architecture

Recommended production path:

- MapLibre GL JS.
- Vector tiles or PMTiles for large inventories.
- PostgreSQL/PostGIS or an equivalent canonical spatial catalog.
- Immutable raw source snapshots.
- Normalized feature records with source metadata.
- Tile generation with zoom-dependent generalization.
- Licensed satellite basemap.
- Separate derived-data pipeline for satellite water detection and DEM flow.
- Owner-only editing API with versioned geometry records.

Feature classes must remain separate:

- Water-body polygon.
- Dam/structure.
- Irrigation project.
- Lift station.
- Intake.
- Discharge/destination.
- Canal/tunnel/pipeline.
- River/stream.
- Catchment/basin.
- Satellite water observation.
- DEM-derived flow segment.
- Source/document/evidence record.

Do not collapse all of these into one generic water feature.

## 12. Acceptance criteria

### Product behavior

- [ ] Opens directly over Telangana at a useful state zoom.
- [ ] Satellite basemap works with attribution.
- [ ] Normal map remains usable during pan/zoom without full-page refresh.
- [ ] Zoom changes visible information density according to the defined hierarchy.
- [ ] Layer controls are available but do not overwhelm the first view.
- [ ] Blue gravity-flow interpretation is visible and understandable.
- [ ] Red lift-project markers are visible and distinct.
- [ ] Project elevation appears on hover/detail.
- [ ] Candidate/modelled water bodies are visually distinguishable through source text and styling.
- [ ] Historical month/year control changes the displayed water observation when data exists.
- [ ] Missing observations remain explicitly unavailable.
- [ ] Guided sequence toggles layers, moves camera, and shows explanatory text.
- [ ] Owner can edit lift coordinates/routes; visitor cannot.
- [ ] Edited routes retain version history and do not overwrite source records.

### Data correctness

- [ ] Telangana boundary is present.
- [ ] Official ICAD/TGRAC records retain source names.
- [ ] Satellite-derived records retain acquisition/observation dates where available.
- [ ] DEM-derived elevations are labelled as DEM estimates, not FRL, crest, or water level.
- [ ] Natural-flow lines are labelled as derived/inferred.
- [ ] Lift routes distinguish documented geometry from conceptual owner-edited geometry.
- [ ] Water extent is not presented as storage volume.
- [ ] Major known reservoirs missing from ICAD can be represented as modelled/reference candidates.
- [ ] Source lines appear in feature details.

### Performance

- [ ] Initial state does not ship the full tank inventory as one giant GeoJSON payload.
- [ ] Large layers load through vector tiles/PMTiles or equivalent viewport-aware delivery.
- [ ] Satellite/time-slider updates do not reload the entire application.
- [ ] Mobile layout remains usable.
- [ ] Full-state overview remains responsive before detailed layers are enabled.

### Verification

- [ ] Unit tests cover source normalization and classification metadata.
- [ ] Data validation checks geometry, coordinates, dates, areas, and required source fields.
- [ ] Tests verify DEM grid dimensions and finite values.
- [ ] Tests verify water-body source categories and seasonal observation states.
- [ ] Tests verify owner-only edit authorization.
- [ ] Tests verify edit versioning and revert behavior.
- [ ] Browser tests verify initial map render, zoom hierarchy, layer visibility, time control, feature card, guided mode, and editor access control.
- [ ] Browser screenshot verification confirms blue and red overlays are visible over satellite imagery.
- [ ] Acceptance test confirms no page refresh occurs during normal zooming, layer toggling, or time-slider changes.

## 13. Explicit non-goals for this release

- Live reservoir levels.
- Live pump, gate, or discharge status.
- Engineering-grade hydraulic simulation.
- Bathymetric storage estimation.
- Automatic claim that every detected feature is officially verified.
- Automatic claim that every satellite-visible body is permanent.
- Perfect completeness of Telangana water inventory.
- Visitor editing.

## 14. Final product statement

Telangana WaterMap is a Zoom Earth-inspired, source-aware educational atlas that combines satellite context, government project records, terrain-derived natural-flow interpretation, modelled water-body discovery, seasonal water-extent observations, and documented lift/distribution relationships. It is designed to explain the water system spatially and visually, while making clear which information is government-sourced, satellite-derived, DEM-inferred, public/reference-based, or owner-edited.
