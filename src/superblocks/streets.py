"""Street classification logic."""

from __future__ import annotations

from typing import Iterable

import geopandas as gpd
import pandas as pd

from .config import PipelineConfig


def _matches_type(value: object, candidates: Iterable[str]) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value in candidates
    if isinstance(value, Iterable):
        return any(v in candidates for v in value)
    return False


def classify_streets(
    edges: gpd.GeoDataFrame,
    config: PipelineConfig,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, float]:
    """Split edges into boundary and internal streets.

    Returns
    -------
    (boundary, internal, threshold)
        Boundary and internal GeoDataFrames plus the numeric threshold used.
    """

    work = edges.copy()
    if "capacity" not in work.columns:
        raise ValueError("Edges must contain a 'capacity' column before classification")

    threshold = float(work["capacity"].quantile(config.boundary_capacity_quantile))

    highway_col = work.get("highway")

    if isinstance(highway_col, pd.Series):
        boundary_mask = highway_col.apply(_matches_type, args=(config.boundary_highway_types,))
        internal_mask = highway_col.apply(_matches_type, args=(config.internal_highway_types,))
    else:
        boundary_mask = pd.Series(True, index=work.index)
        internal_mask = pd.Series(True, index=work.index)

    boundary_subset = work[boundary_mask & (work["capacity"] >= threshold)].copy()
    internal_subset = work[internal_mask | (work["capacity"] < threshold)].copy()

    return boundary_subset, internal_subset, threshold
