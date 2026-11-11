# Contributing to Telangana WaterMap

Telangana WaterMap is a provenance-aware atlas for locating water bodies, irrigation infrastructure, and inferred water-transfer relationships across Telangana.

## Collaboration priorities

1. Improve waterbody locations and names.
2. Determine likely lift intakes, especially barrage, weir, regulator, and river connections.
3. Determine receiving, destination, and outflow points.
4. Cross-check project, reservoir, canal, river, stream, and structure records against authoritative sources.
5. Record uncertainty instead of presenting inferred routes as surveyed infrastructure.

## Editable collaboration files

- `docs/COLLABORATION-BOARD.md` — shared work queue and review log.
- `docs/DATA-MODEL.md` — proposed fields for waterbodies, structures, intakes, outflows, and inferred connections.
- `docs/PROJECT-HANDOFF.md` — technical and data-source context.

Edit the collaboration board directly in GitHub, or submit a pull request that updates it.

## Evidence standard

Every proposed correction should include:

- feature name and source record ID, when available;
- latitude/longitude or a GeoJSON geometry;
- source URL or document;
- date checked;
- confidence: high, medium, or low;
- explanation of why the intake, outflow, or location is supported;
- conflicts with other sources.

Mark an intake-to-destination corridor as inferred unless an authoritative source publishes the route geometry.

## Local development

Run the static app from the repository root:

```bash
python -m http.server 8767 --bind 127.0.0.1 --directory apps/web
```

Run smoke tests:

```bash
python -m unittest tests.test_smoke -v
```
