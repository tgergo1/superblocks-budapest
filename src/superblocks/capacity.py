"""Road capacity estimation utilities."""

from __future__ import annotations

import logging
import re
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd

from .config import PipelineConfig

logger = logging.getLogger(__name__)


_NUMERIC_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


def _extract_numeric(value: Any) -> float | None:
    """Best-effort conversion of heterogeneous OSM tags to floats."""

    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, (int, float, np.floating)):
        return float(value)
    if isinstance(value, (list, tuple, set)):
        values = [_extract_numeric(v) for v in value]
        values = [v for v in values if v is not None]
        return float(np.mean(values)) if values else None
    if isinstance(value, dict):
        return _extract_numeric(next(iter(value.values())))
    if isinstance(value, str):
        matches = _NUMERIC_PATTERN.findall(value)
        if not matches:
            return None
        numbers = [float(m) for m in matches]
        return float(np.mean(numbers))
    return None


def enrich_capacity_columns(
    edges: gpd.GeoDataFrame,
    config: PipelineConfig,
) -> gpd.GeoDataFrame:
    """Return a copy of ``edges`` with numeric capacity inputs populated."""

    result = edges.copy()

    for column in ("lanes", "maxspeed", "width"):
        if column not in result.columns:
            result[column] = np.nan

    result["lanes"] = result["lanes"].apply(_extract_numeric)
    result["lanes"] = result["lanes"].fillna(config.default_lanes)
    result.loc[result["lanes"] < config.min_lanes, "lanes"] = config.min_lanes

    result["maxspeed"] = result["maxspeed"].apply(_extract_numeric)
    result["maxspeed"] = result["maxspeed"].fillna(config.default_maxspeed)

    result["width"] = result["width"].apply(_extract_numeric)
    # If width is missing assume default lane width per lane
    default_width_series = result["lanes"] * config.default_width
    result["width"] = result["width"].fillna(default_width_series)

    return result


def estimate_capacity(
    edges: gpd.GeoDataFrame,
    config: PipelineConfig,
) -> gpd.GeoDataFrame:
    """Compute a synthetic capacity score for each edge."""

    prepared = enrich_capacity_columns(edges, config)

    capacity = (
        prepared["lanes"].astype(float)
        * config.lane_width
        * prepared["maxspeed"].astype(float)
        * config.capacity_scale_factor
    )
    prepared["capacity"] = capacity
    prepared["capacity_per_lane"] = (
        prepared["capacity"] / prepared["lanes"].replace(0, np.nan)
    )

    logger.debug(
        "Capacity statistics min=%s median=%s max=%s",
        float(prepared["capacity"].min()),
        float(prepared["capacity"].median()),
        float(prepared["capacity"].max()),
    )

    return prepared
