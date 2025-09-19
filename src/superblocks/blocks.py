"""Block polygon creation helpers."""

from __future__ import annotations

import logging

import geopandas as gpd
from geopandas import GeoDataFrame

from .config import PipelineConfig
from .geometry import make_polygons_from_lines, clean_polygons

logger = logging.getLogger(__name__)


def build_blocks(
    internal_streets: GeoDataFrame,
    config: PipelineConfig,
) -> GeoDataFrame:
    if internal_streets.empty:
        logger.warning("No internal streets supplied; returning empty blocks GeoDataFrame")
        return gpd.GeoDataFrame(columns=["geometry", "block_id"], crs=internal_streets.crs)

    polygons = make_polygons_from_lines(internal_streets)
    cleaned = clean_polygons(
        polygons,
        min_area_m2=config.block_min_area_m2,
        clean_tolerance=config.clean_tolerance,
    )
    cleaned = cleaned.reset_index(drop=True)
    cleaned["block_id"] = cleaned.index
    logger.info("Created %s blocks from internal streets", len(cleaned))
    return cleaned
