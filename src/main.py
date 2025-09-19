"""CLI entry point for computing and visualising Budapest superblocks."""

from __future__ import annotations

import argparse
import logging

from superblocks.config import PipelineConfig
from superblocks.pipeline import SuperblockPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Budapest superblocks with rich visualisations.")
    parser.add_argument("--place", default="Budapest, Hungary", help="Location name recognised by OpenStreetMap")
    parser.add_argument("--output-dir", default="outputs", help="Directory for exported artefacts")
    parser.add_argument("--tiles", type=int, default=4, help="Number of tiles for high-res static export")
    parser.add_argument("--zoom", type=int, default=12, help="Base zoom level for interactive maps")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    config = PipelineConfig(
        place_name=args.place,
        output_dir=args.output_dir,
    )
    config.tile_export_num_tiles = max(1, args.tiles)
    config.folium_zoom_start = args.zoom

    pipeline = SuperblockPipeline(config)
    pipeline.run_full_pipeline()
    logging.info("Superblock identification process completed successfully.")


if __name__ == "__main__":
    main()
