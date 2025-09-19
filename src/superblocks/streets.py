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


def detect_major_roads(
    edges: gpd.GeoDataFrame,
    config: PipelineConfig,
) -> gpd.GeoDataFrame:
    """Identify high-capacity corridors that should remain open to through traffic."""

    if edges.empty:
        return edges.copy()
    if "capacity" not in edges.columns:
        raise ValueError("Edges must contain 'capacity' before detecting major roads")

    work = edges.copy()
    threshold = float(work["capacity"].quantile(config.major_road_capacity_quantile))

    highway_col = work.get("highway")
    if isinstance(highway_col, pd.Series):
        highway_mask = highway_col.apply(_matches_type, args=(config.major_highway_types,))
    else:
        highway_mask = pd.Series(False, index=work.index)

    capacity_mask = work["capacity"] >= threshold
    combined_mask = highway_mask | capacity_mask

    major = work[combined_mask].copy()

    def _reason(row: pd.Series) -> str:
        reasons = []
        if _matches_type(row.get("highway"), config.major_highway_types):
            reasons.append("classification")
        if row.get("capacity", 0) >= threshold:
            reasons.append("capacity")
        return "+".join(reasons) or "unspecified"

    major["major_reason"] = major.apply(_reason, axis=1)
    major["capacity_threshold"] = threshold
    return major


def identify_heritage_priorities(
    edges: gpd.GeoDataFrame,
    config: PipelineConfig,
    heritage_zone: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Select inner-city streets that should become calmer based on a heritage zone."""

    if edges.empty:
        return edges.iloc[0:0].copy()
    if "capacity" not in edges.columns:
        raise ValueError("Edges must contain 'capacity' before identifying heritage priorities")

    zone = heritage_zone
    if zone is None or zone.empty:
        return edges.iloc[0:0].copy()

    if edges.crs is None or zone.crs is None:
        return edges.iloc[0:0].copy()

    if zone.crs != edges.crs:
        zone = zone.to_crs(edges.crs)

    try:
        metric_crs = edges.estimate_utm_crs()  # type: ignore[assignment]
    except Exception:  # pragma: no cover - fallback for unprojectable CRS
        metric_crs = "EPSG:3857"

    edges_metric = edges.to_crs(metric_crs)
    zone_metric = zone.to_crs(metric_crs)

    zone_union = zone_metric.geometry.unary_union
    if zone_union.is_empty:
        return edges.iloc[0:0].copy()

    within_mask = edges_metric.geometry.intersects(zone_union)
    if not within_mask.any():
        return edges.iloc[0:0].copy()

    candidates = edges_metric[within_mask].copy()

    highway_col = candidates.get("highway")
    if isinstance(highway_col, pd.Series):
        highway_mask = highway_col.apply(_matches_type, args=(config.heritage_priority_highway_types,))
    else:
        highway_mask = pd.Series(False, index=candidates.index)

    if not highway_mask.any():
        return edges.iloc[0:0].copy()

    capacity_threshold = float(candidates["capacity"].quantile(config.heritage_capacity_quantile))
    capacity_mask = candidates["capacity"] <= capacity_threshold

    priority_metric = candidates[highway_mask & capacity_mask].copy()
    if priority_metric.empty:
        return priority_metric

    core_centroid = zone_union.centroid
    priority_metric["distance_to_centre"] = priority_metric.geometry.distance(core_centroid).round(1)
    priority_metric["heritage_priority"] = True
    priority_metric["capacity_threshold"] = capacity_threshold

    return priority_metric.to_crs(edges.crs)
