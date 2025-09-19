"""Utilities for deriving heritage priority zones from OSM sources."""

from __future__ import annotations

import logging
from typing import Iterable, Tuple

import geopandas as gpd
import pandas as pd
import osmnx as ox
from shapely.geometry import Point

from .config import PipelineConfig
from .geometry import buffer_in_meters

logger = logging.getLogger(__name__)


def _clean_queries(queries: Iterable[str]) -> Tuple[str, ...]:
    cleaned = []
    for query in queries:
        if query is None:
            continue
        qp = str(query).strip()
        if qp:
            cleaned.append(qp)
    return tuple(cleaned)


def _filter_min_area(zone: gpd.GeoDataFrame, min_area_m2: float) -> gpd.GeoDataFrame:
    if zone.empty or min_area_m2 <= 0:
        return zone

    try:
        metric_crs = zone.estimate_utm_crs()  # type: ignore[assignment]
    except Exception:  # pragma: no cover - fallback when CRS estimation fails
        return zone

    metric = zone.to_crs(metric_crs)
    metric["area_m2"] = metric.area
    metric = metric[metric["area_m2"] >= min_area_m2]
    metric = metric.drop(columns=["area_m2"], errors="ignore")
    return metric.to_crs(zone.crs)


def _fallback_circular_zone(
    centre: Tuple[float, float] | None,
    edges_crs,
    radius_m: float,
) -> gpd.GeoDataFrame:
    if centre is None or radius_m <= 0:
        return gpd.GeoDataFrame(columns=["geometry"], crs=edges_crs)

    centre_gdf = gpd.GeoDataFrame(
        geometry=[Point(centre[1], centre[0])],
        crs=edges_crs,
    )
    return buffer_in_meters(centre_gdf, radius_m)


def derive_heritage_zone(
    edges: gpd.GeoDataFrame,
    config: PipelineConfig,
    centre: Tuple[float, float] | None,
) -> gpd.GeoDataFrame:
    """Return a polygonal representation of the heritage core.

    Attempts to geocode configured region names from OpenStreetMap and combines
    them into a single zone. Falls back to a circular buffer around ``centre``
    if no polygons are obtained.
    """

    target_crs = getattr(edges, "crs", None)
    zone = gpd.GeoDataFrame(columns=["geometry"], crs=target_crs)

    if target_crs is None:
        logger.warning("Edges GeoDataFrame has no CRS; cannot derive heritage zone from polygons")
        return zone

    queries = _clean_queries(config.heritage_place_queries)
    geometries: list[gpd.GeoDataFrame] = []

    for query in queries:
        try:
            geo = ox.geocode_to_gdf(query)
        except Exception as exc:  # pragma: no cover - network or HTTP issues
            logger.warning("Failed to geocode heritage place '%s': %s", query, exc)
            continue

        if geo.empty:
            logger.warning("Geocode for heritage place '%s' returned no geometry", query)
            continue

        geometries.append(geo[["geometry"]])

    if geometries:
        merged = gpd.GeoDataFrame(
            pd.concat(geometries, ignore_index=True),
            crs=geometries[0].crs,
        )
        merged = merged.dissolve().explode(index_parts=False).reset_index(drop=True)
        merged = merged.to_crs(target_crs)

        if config.heritage_zone_buffer_m > 0:
            merged = buffer_in_meters(merged, config.heritage_zone_buffer_m)

        merged = _filter_min_area(merged, config.heritage_zone_min_area_m2)
        zone = merged.reset_index(drop=True)

    if zone.empty:
        zone = _fallback_circular_zone(centre, target_crs, config.heritage_zone_radius_m)

    return zone.reset_index(drop=True)
