"""Superblock polygon creation and block assignment."""

from __future__ import annotations

import logging

import geopandas as gpd
from geopandas import GeoDataFrame
import pandas as pd

from .config import PipelineConfig
from .geometry import buffer_in_meters, make_polygons_from_lines, clean_polygons


def _metric_crs_for(gdf: GeoDataFrame) -> str | None:
    """Return a projected CRS suited for distance calculations."""

    if gdf.empty or gdf.crs is None:
        return None
    try:
        return gdf.estimate_utm_crs()  # type: ignore[return-value]
    except Exception:  # pragma: no cover - fall back to web mercator when estimation fails
        return "EPSG:3857"

logger = logging.getLogger(__name__)


def build_superblocks(
    boundary_streets: GeoDataFrame,
    config: PipelineConfig,
    exclusions: GeoDataFrame | None = None,
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

    if exclusions is not None and not exclusions.empty:
        buffered_exclusions = buffer_in_meters(exclusions, config.major_road_buffer_metres)
        exclusion_union = buffered_exclusions.geometry.unary_union
        cleaned["geometry"] = cleaned.geometry.difference(exclusion_union)
        cleaned = cleaned[~cleaned.geometry.is_empty]
        cleaned = cleaned.explode(index_parts=False).reset_index(drop=True)
    else:
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
        metric_crs = None
        if blocks.crs is not None and superblocks.crs is not None and blocks.crs == superblocks.crs:
            metric_crs = _metric_crs_for(blocks)

        if metric_crs is not None:
            metric_blocks = blocks.to_crs(metric_crs)
            metric_superblocks = superblocks.to_crs(metric_crs)
            metric_block_geoms = metric_blocks.geometry
            metric_super_geoms = metric_superblocks.geometry
        else:
            metric_block_geoms = blocks.geometry
            metric_super_geoms = superblocks.geometry

        for idx in join[missing_mask].index:
            block_geom_metric = metric_block_geoms.loc[idx]
            distances = metric_super_geoms.distance(block_geom_metric)
            nearest_idx = distances.idxmin()
            join.at[idx, "superblock_id"] = superblocks.at[nearest_idx, "superblock_id"]

    join["superblock_id"] = join["superblock_id"].fillna(-1).astype(int)
    return join
