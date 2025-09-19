"""Superblock polygon creation and block assignment."""

from __future__ import annotations

import logging

import geopandas as gpd
from geopandas import GeoDataFrame
import pandas as pd

from .config import PipelineConfig
from .geometry import buffer_in_meters, make_polygons_from_lines, clean_polygons

logger = logging.getLogger(__name__)


def build_superblocks(
    boundary_streets: GeoDataFrame,
    config: PipelineConfig,
) -> GeoDataFrame:
    """Create superblock polygons from boundary streets."""

    if boundary_streets.empty:
        logger.warning("No boundary streets provided; returning empty superblocks GeoDataFrame")
        return gpd.GeoDataFrame(columns=["geometry", "superblock_id"], crs=boundary_streets.crs)

    buffered = buffer_in_meters(boundary_streets, config.boundary_buffer_metres)
    polygons = make_polygons_from_lines(buffered)
    cleaned = clean_polygons(
        polygons,
        min_area_m2=config.superblock_min_area_m2,
        clean_tolerance=config.clean_tolerance,
    )

    cleaned = cleaned.reset_index(drop=True)
    cleaned["superblock_id"] = cleaned.index
    logger.info("Constructed %s superblock polygons", len(cleaned))
    return cleaned


def assign_blocks_to_superblocks(
    blocks: GeoDataFrame,
    superblocks: GeoDataFrame,
) -> GeoDataFrame:
    """Attach a ``superblock_id`` to each block polygon."""

    if blocks.empty:
        result = blocks.copy()
        result["superblock_id"] = pd.Series(dtype=int)
        return result
    if superblocks.empty:
        logger.warning("Superblocks are empty; blocks cannot be assigned")
        result = blocks.copy()
        result["superblock_id"] = -1
        return result

    join = gpd.sjoin(
        blocks,
        superblocks[["geometry", "superblock_id"]],
        how="left",
        predicate="within",
    )
    join = join.drop(columns=["index_right"], errors="ignore")

    missing_mask = join["superblock_id"].isna()

    if missing_mask.any():
        logger.info("Assigning %s uncontained blocks to nearest superblock", missing_mask.sum())
        for idx in join[missing_mask].index:
            distances = superblocks.distance(join.at[idx, "geometry"])
            nearest_idx = distances.idxmin()
            join.at[idx, "superblock_id"] = superblocks.at[nearest_idx, "superblock_id"]

    join["superblock_id"] = join["superblock_id"].fillna(-1).astype(int)
    return join
