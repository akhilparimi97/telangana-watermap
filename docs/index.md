# Telangana WaterMap

## Collaborate on Telangana's water network

Telangana WaterMap is an open, provenance-aware atlas for improving the locations and relationships of reservoirs, tanks, rivers, streams, canals, barrages, lift-project intakes, and outflow or destination points.

The current map is a working static release. The next phase needs reviewers who can reconcile waterbody locations, identify likely lift intakes, and document receiving or outflow points with evidence.

## Open the map

[Open the interactive Telangana WaterMap](map/)

The map is published at `https://akhilparimi97.github.io/telangana-watermap/map/`.

## Where to contribute

- [Collaboration board](COLLABORATION-BOARD.md) — editable queue and review log.
- [Contributing guide](../CONTRIBUTING.md) — evidence and review standards.
- [Data model](DATA-MODEL.md) — fields for proposed waterbody, intake, outflow, and inferred-connection records.
- [Technical handoff](PROJECT-HANDOFF.md) — sources, architecture, and known limitations.

## Priority questions

1. Is this waterbody correctly located and named?
2. Which barrage, weir, regulator, or river point is the most defensible lift intake?
3. Where does the project actually deliver water: reservoir, canal, command area, balancing reservoir, or another node?
4. Which parts are official geometry, which are mapped evidence, and which remain inferred?

## Evidence policy

Do not present an inferred lift corridor as a surveyed pipeline. Each proposed edit should include a source, date checked, confidence, and an explanation of conflicting evidence.

## Run the map locally

```bash
python -m http.server 8767 --bind 127.0.0.1 --directory apps/web
```

Then open `index.html` from the local server.
