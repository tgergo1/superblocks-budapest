# ⚠️ This repository has been archived

**This project is no longer maintained here. Development continues at [Superblocker](https://github.com/tgergo1/Superblocker).**

---

# Superblocks for Budapest

This repository contains Python tools to analyse Budapest's street network and generate **superblocks** – clusters of city blocks bounded by high‑capacity roads. The code relies on OpenStreetMap data and provides interactive maps and GeoJSON outputs for further exploration.

## Key Features

### 🚗 Traffic Flow Control
The toolkit now includes comprehensive **access control** capabilities that calculate optimal street direction changes to prevent through-traffic while maintaining local access:

- **Street Direction Optimization**: Automatically determines which streets should be one-way to prevent through-traffic
- **Modal Filter Placement**: Identifies strategic locations for physical barriers (planters, bollards) that block motor vehicles but allow pedestrians and cyclists
- **Permeability Analysis**: Measures how accessible each superblock is while preventing through-routes
- **Before/After Visualization**: Interactive maps showing directional arrows and modal filter locations

### 🗺️ Main workflow

The refactored toolkit centres around `superblocks.pipeline.SuperblockPipeline` which
implements the end-to-end workflow:

1. **Download** the OpenStreetMap network for the configured place.
2. **Enrich** every edge with a normalised capacity score that handles mixed data formats.
3. **Classify** streets into boundary and internal sets via tunable highway rules and capacity quantiles.
4. **Polygonise** internal streets into candidate blocks and clean geometries in metric space.
5. **Construct** superblock polygons from buffered boundary streets and attach blocks to their nearest container.
6. **Optimize Access Control** – Calculate optimal street directions and modal filter placements to prevent through-traffic.
7. **Visualise** the results through rich Folium maps with directional arrows, modal filters, and interactive layers.
8. **Persist** artefacts as GeoJSON, GraphML, PNG, and evidence-aligned metric reports for planning briefings.

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

- `budapest_streets.html` – Street classification map
- `budapest_blocks.html` – Block-level visualization
- `budapest_superblocks_map.html` – **Interactive superblock map with street directions and modal filters**
- `budapest_superblocks.geojson` – Superblock polygons
- `budapest_street_directions.geojson` – **Street segments with direction changes**
- `budapest_modal_filters.geojson` – **Modal filter locations**
- `budapest_permeability_metrics.json` – **Permeability analysis for each superblock**
- `budapest_superblocks.png` – Static high-resolution map
- `budapest_superblocks_metrics.json` – Comprehensive metrics
- `budapest_superblocks_report.md` – Detailed analysis report
- `budapest_superblocks_brief.md` – Executive summary

## Understanding the Output

### Interactive Map Features

The main interactive map (`budapest_superblocks_map.html`) includes multiple layers:

1. **Superblocks** (colored polygons) – Main superblock boundaries
2. **Major Corridors** (red) – High-capacity streets that remain open to through-traffic
3. **Street Directions** (blue arrows) – Shows one-way street configurations
   - `>` indicates one-way direction
   - `<>` indicates two-way street
4. **Modal Filters** (red circles) – Suggested locations for physical traffic barriers
5. **Car-Light Candidates** (green) – Heritage area streets suitable for pedestrianization
6. **Blocks** (gray) – Individual city blocks within superblocks

### Permeability Metrics

The permeability analysis (`budapest_permeability_metrics.json`) provides for each superblock:
- Total internal streets
- Number of one-way vs two-way streets
- **Permeability score** (0-1, lower is better) – Measures ease of through-traffic
- **Accessibility score** (0-1, higher is better) – Ensures local access is maintained

## Further reading

- `docs/evidence_based_superblocks.md` – evidence-based analysis mirroring the international report structure.
- Generated `budapest_superblocks_brief.md` – executive-ready summary tailored to the configured city.

## Development

The repository contains a small pytest suite. Execute tests with:

```bash
PYTHONPATH=src pytest -q
```

## License

This project is available under the terms of the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.en.html).
