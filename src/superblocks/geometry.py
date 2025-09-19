"""Geometry processing utilities for blocks and superblocks."""

from __future__ import annotations

import logging
from typing import Iterable

import geopandas as gpd
from geopandas import GeoDataFrame
from shapely.geometry import Polygon
from shapely.ops import polygonize

logger = logging.getLogger(__name__)


def _metric_crs(gdf: GeoDataFrame) -> str | None:
    if gdf.empty or gdf.crs is None:
        return None
    try:
        return gdf.estimate_utm_crs()  # type: ignore[return-value]
    except Exception:  # pragma: no cover - fallback path for exotic CRS
        return "EPSG:3857"


def get_metric_crs(gdf: GeoDataFrame) -> str | None:
    """Expose the internally used metric CRS helper for reuse."""

    return _metric_crs(gdf)


def buffer_in_meters(gdf: GeoDataFrame, distance: float) -> GeoDataFrame:
    if distance <= 0 or gdf.empty or gdf.crs is None:
        return gdf.copy()

    metric_crs = _metric_crs(gdf)
    if metric_crs is None:
        return gdf.copy()

    projected = gdf.to_crs(metric_crs)
    projected["geometry"] = projected.geometry.buffer(distance)
    return projected.to_crs(gdf.crs)


def make_polygons_from_lines(lines: GeoDataFrame) -> GeoDataFrame:
    if lines.empty:
        return gpd.GeoDataFrame(columns=["geometry"], crs=lines.crs)

    union = lines.geometry.unary_union
    polygons = list(polygonize(union))
    logger.info("Polygonised %s line geometries into %s polygons", len(lines), len(polygons))
    return gpd.GeoDataFrame({"geometry": polygons}, crs=lines.crs)


def clean_polygons(
    polygons: GeoDataFrame,
    min_area_m2: float,
    clean_tolerance: float,
) -> GeoDataFrame:
    if polygons.empty:
        return polygons

    metric_crs = _metric_crs(polygons)
    if metric_crs is None:
        return polygons

    projected = polygons.to_crs(metric_crs)
    projected["geometry"] = projected.geometry.buffer(0)
    projected = projected[projected.geometry.is_valid]

    if min_area_m2 > 0:
        projected["area_m2"] = projected.area
        projected = projected[projected["area_m2"] >= min_area_m2]
        projected = projected.drop(columns=["area_m2"], errors="ignore")

    if clean_tolerance > 0:
        projected["geometry"] = projected.geometry.simplify(clean_tolerance, preserve_topology=True)

    return projected.to_crs(polygons.crs)


def dissolve_polygons(polygons: GeoDataFrame) -> GeoDataFrame:
    if polygons.empty:
        return polygons
    dissolved = polygons.dissolve()
    dissolved.reset_index(drop=True, inplace=True)
    expanded = []
    for geom in dissolved.geometry:
        if geom.geom_type == "Polygon":
            expanded.append(geom)
        elif geom.geom_type == "MultiPolygon":
            expanded.extend(list(geom.geoms))
    return gpd.GeoDataFrame({"geometry": expanded}, crs=polygons.crs)
