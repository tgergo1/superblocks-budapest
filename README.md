# Superblocks for Budapest

This repository contains Python tools to analyse Budapest's street network and generate **superblocks** – clusters of city blocks bounded by high‑capacity roads. The code relies on OpenStreetMap data and provides interactive maps and GeoJSON outputs for further exploration.

## Main workflow

`src/main.py` illustrates the typical steps:

1. **Download the street network** using OSMnx.
2. **Estimate road capacity** from lanes and speed limits (Michigan model).
3. **Classify streets** as boundary or internal based on relative capacity.
4. **Polygonise internal streets** to create block geometries.
5. **Assign blocks to superblocks** formed by boundary streets.
6. **Visualise** streets, blocks and superblocks with Folium.
7. **Export** the resulting superblocks to GeoJSON and the network to GraphML.

Alternative detection methods are available via `cluster_superblocks()` and `modularity_superblocks()`, which rely on HDBSCAN clustering or community detection to form concave‑hull polygons.

## High‑resolution map exports

`src/experiments/wireframe_test.py` includes a `num_tiles` parameter for splitting a map into tiles before stitching the result. This allows exporting large, detailed images when standard plotting sizes are insufficient.

## Installation

```bash
pip install -r requirements.txt
```

After installing the dependencies, run

```bash
python src/main.py
```

Output files are written to the `outputs/` directory:

- `budapest_streets.html`
- `budapest_blocks.html`
- `budapest_superblocks_map.html`
- `budapest_superblocks.geojson`

## Development

The repository contains a small pytest suite. Execute tests with:

```bash
pytest -q
```

## License

This project is available under the terms of the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.en.html).
