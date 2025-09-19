# Superblocks for Budapest

This repository contains Python tools to analyse Budapest's street network and generate **superblocks** – clusters of city blocks bounded by high‑capacity roads. The code relies on OpenStreetMap data and provides interactive maps and GeoJSON outputs for further exploration.

## Main workflow

The refactored toolkit centres around `superblocks.pipeline.SuperblockPipeline` which
implements the end-to-end workflow:

1. **Download** the OpenStreetMap network for the configured place.
2. **Enrich** every edge with a normalised capacity score that handles mixed data formats.
3. **Classify** streets into boundary and internal sets via tunable highway rules and capacity quantiles.
4. **Polygonise** internal streets into candidate blocks and clean geometries in metric space.
5. **Construct** superblock polygons from buffered boundary streets and attach blocks to their nearest container.
6. **Visualise** the results through rich Folium maps and a high-resolution static export with optional tiling.
7. **Persist** artefacts as GeoJSON, GraphML, PNG, and evidence-aligned metric reports for planning briefings.

Alternative detection methods remain available through the `RoadNetwork` wrapper: `cluster_superblocks()` (HDBSCAN) and `modularity_superblocks()` (community detection).

## High‑resolution map exports

`src/experiments/wireframe_test.py` includes a `num_tiles` parameter for splitting a map into tiles before stitching the result. This allows exporting large, detailed images when standard plotting sizes are insufficient.

## Evidence-informed analytics

- `src/superblocks/metrics.py` synthesises coverage, street hierarchy lengths, and heritage footprints, then scales peer-reviewed impact baselines (NO₂, noise, green area, avoided premature deaths) to the current scenario.
- Running the pipeline now emits `budapest_superblocks_metrics.json` and `budapest_superblocks_report.md` alongside the interactive maps.
- See `docs/evidence_based_superblocks.md` for a condensed literature review and pointers to headline studies underpinning the heuristics.

## Installation

```bash
pip install -r requirements.txt
```

After installing the dependencies, run

```bash
python src/main.py --place "Budapest, Hungary" --tiles 4
```

Output files are written to the configured `outputs/` directory:

- `budapest_streets.html`
- `budapest_blocks.html`
- `budapest_superblocks_map.html`
- `budapest_superblocks.geojson`
- `budapest_superblocks.png`
- `budapest_superblocks_metrics.json`
- `budapest_superblocks_report.md`
- `budapest_superblocks_brief.md`

## Further reading

- `docs/evidence_based_superblocks.md` – evidence-based analysis mirroring the international report structure.
- Generated `budapest_superblocks_brief.md` – executive-ready summary tailored to the configured city.

## Development

The repository contains a small pytest suite. Execute tests with:

```bash
pytest -q
```

## License

This project is available under the terms of the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.en.html).
