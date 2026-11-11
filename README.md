# Telangana WaterMap

First working slice of the Telangana water atlas.

## Run locally

From this directory:

```bash
python -m http.server 8767 --bind 127.0.0.1 --directory apps/web
```

Open `http://127.0.0.1:8767/index.html`.

## Included in v0.1

- Esri World Imagery satellite basemap with OpenStreetMap street-map switch.
- Telangana-focused pan/zoom map.
- Reservoir polygons, ICAD projects, named rivers, streams, and Telangana administrative boundary.
- Lazy-loaded canal network and 36,576 TGRAC lake/pond/tank polygons (simplified local snapshot) so initial pan/zoom stays responsive.
- Search over loaded features.
- Feature detail drawer with source and data-quality context.
- Layer toggles and loaded feature count.
- Terrain-oriented 3D canvas: exaggerated elevation surface, DEM-gradient downhill arrows, and lift-project transfer markers.
- Local snapshots of the official source layers under `apps/web/data/`.

The bundled snapshots are the starting inventory, not a live telemetry feed. Natural-flow arrows are derived from sampled DEM gradients and do not represent measured discharge; lift markers show project records, not operating status. For production scale, move the large lake/canal layers to vector tiles or PMTiles and add versioned ingestion/reconciliation.

## Public links

- Repository: https://github.com/akhilparimi97/telangana-watermap
- Collaboration landing page: https://akhilparimi97.github.io/telangana-watermap/
- Live interactive map: https://akhilparimi97.github.io/telangana-watermap/map/
- Editable collaboration board: https://akhilparimi97.github.io/telangana-watermap/COLLABORATION-BOARD.html
- Contributing guide: https://akhilparimi97.github.io/CONTRIBUTING.md
- Data model: https://akhilparimi97.github.io/telangana-watermap/DATA-MODEL.html
- Technical handoff: https://akhilparimi97.github.io/telangana-watermap/PROJECT-HANDOFF.html


The editable collaboration plan is in `docs/COLLABORATION-BOARD.md`. Use it to review waterbody locations, determine likely lift intakes, identify outflow/destination points, and record evidence and confidence. See `CONTRIBUTING.md` for review rules and `docs/DATA-MODEL.md` for proposed editable fields. The `docs/` folder is also a GitHub Pages landing page for inviting collaborators.

## Tests

```bash
python -m unittest tests.test_smoke -v
```
