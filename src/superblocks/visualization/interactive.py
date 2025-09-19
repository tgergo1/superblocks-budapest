"""Interactive map rendering with Folium."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable, Tuple

import geopandas as gpd
import pandas as pd
import folium
from branca.colormap import LinearColormap

from ..config import PipelineConfig

logger = logging.getLogger(__name__)


def _ensure_output_path(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _center_from_bounds(gdf: gpd.GeoDataFrame) -> Tuple[float, float] | None:
    if gdf.empty:
        return None
    bounds = gdf.total_bounds  # minx, miny, maxx, maxy
    lon = (bounds[0] + bounds[2]) / 2
    lat = (bounds[1] + bounds[3]) / 2
    return lat, lon


def _add_linestrings_to_map(
    feature_group: folium.FeatureGroup,
    gdf: gpd.GeoDataFrame,
    color_func,
    weight: float,
    tooltip_fields: Iterable[str] | None = None,
) -> None:
    for _, row in gdf.iterrows():
        geom = row.geometry
        tooltip = None
        if tooltip_fields:
            tooltip_data = {field: row.get(field, "-") for field in tooltip_fields}
            tooltip = folium.Tooltip(json.dumps(tooltip_data, indent=2))

        style_kwargs = {
            "color": color_func(row),
            "weight": weight,
            "opacity": 0.9,
        }

        folium.GeoJson(
            geom,
            tooltip=tooltip,
            style_function=lambda *_args, **_kwargs: style_kwargs,
        ).add_to(feature_group)



def render_street_map(
    boundary_streets: gpd.GeoDataFrame,
    internal_streets: gpd.GeoDataFrame,
    config: PipelineConfig,
    output_path: str | Path,
    centre: Tuple[float, float] | None = None,
) -> Path:
    """Render a rich street layer map highlighting boundary streets."""

    if centre is None:
        if not boundary_streets.empty and internal_streets.empty:
            combined = boundary_streets
        elif boundary_streets.empty and not internal_streets.empty:
            combined = internal_streets
        elif not boundary_streets.empty and not internal_streets.empty:
            combined = gpd.GeoDataFrame(
                pd.concat([boundary_streets, internal_streets], ignore_index=True),
                crs=boundary_streets.crs,
            )
        else:
            combined = boundary_streets
        centre = _center_from_bounds(combined)
    if centre is None:
        raise ValueError("Cannot determine map centre; supply `centre` explicitly")

    folium_map = folium.Map(location=centre, zoom_start=config.folium_zoom_start, tiles=config.folium_tiles)

    if not internal_streets.empty:
        internal_group = folium.FeatureGroup(name="Internal Streets", show=False)
        _add_linestrings_to_map(
            internal_group,
            internal_streets,
            color_func=lambda _row: config.internal_street_color,
            weight=config.internal_street_weight,
            tooltip_fields=("highway", "capacity"),
        )
        internal_group.add_to(folium_map)

    if not boundary_streets.empty:
        capacity_colormap = LinearColormap(
            colors=["#495057", "#228BE6", "#364FC7"],
            vmin=float(boundary_streets["capacity"].min()),
            vmax=float(boundary_streets["capacity"].max()),
        )
        boundary_group = folium.FeatureGroup(name="Boundary Streets", show=True)
        _add_linestrings_to_map(
            boundary_group,
            boundary_streets,
            color_func=lambda row: capacity_colormap(row["capacity"]),
            weight=config.boundary_street_weight,
            tooltip_fields=("highway", "capacity"),
        )
        boundary_group.add_to(folium_map)
        capacity_colormap.caption = "Boundary street capacity"
        capacity_colormap.add_to(folium_map)

    folium.LayerControl(collapsed=False).add_to(folium_map)

    path = _ensure_output_path(output_path)
    folium_map.save(str(path))
    logger.info("Saved street map to %s", path)
    return path


def render_blocks_map(
    blocks: gpd.GeoDataFrame,
    config: PipelineConfig,
    output_path: str | Path,
    centre: Tuple[float, float] | None = None,
) -> Path:
    if blocks.empty:
        raise ValueError("Cannot render blocks map without block geometries")

    if centre is None:
        centre = _center_from_bounds(blocks)
    if centre is None:
        raise ValueError("Cannot determine map centre; supply `centre` explicitly")

    folium_map = folium.Map(location=centre, zoom_start=config.folium_zoom_start + 1, tiles=config.folium_tiles)

    style = {
        "fillColor": "#9775FA",
        "color": "#7048E8",
        "weight": 1,
        "fillOpacity": 0.35,
    }

    folium.GeoJson(
        blocks,
        style_function=lambda *_args, **_kwargs: style,
        tooltip=folium.GeoJsonTooltip(fields=["block_id"], aliases=["Block"]),
    ).add_to(folium_map)

    path = _ensure_output_path(output_path)
    folium_map.save(str(path))
    logger.info("Saved block map to %s", path)
    return path


def render_superblocks_map(
    superblocks: gpd.GeoDataFrame,
    config: PipelineConfig,
    output_path: str | Path,
    centre: Tuple[float, float] | None = None,
    blocks: gpd.GeoDataFrame | None = None,
) -> Path:
    if superblocks.empty:
        raise ValueError("Cannot render superblock map without superblock polygons")

    if centre is None:
        centre = _center_from_bounds(superblocks)
    if centre is None:
        raise ValueError("Cannot determine map centre; supply `centre` explicitly")

    folium_map = folium.Map(location=centre, zoom_start=config.folium_zoom_start, tiles=config.folium_tiles)

    if blocks is not None and not blocks.empty:
        folium.GeoJson(
            blocks,
            name="Blocks",
            style_function=lambda *_args, **_kwargs: {
                "fillColor": "#CED4DA",
                "color": "#868E96",
                "weight": 0.5,
                "fillOpacity": 0.15,
            },
            tooltip=folium.GeoJsonTooltip(fields=["block_id", "superblock_id"], aliases=["Block", "Superblock"]),
            show=False,
        ).add_to(folium_map)

    palette = list(config.highlight_palette)
    palette_length = len(palette)

    def _color_for_index(idx: int) -> str:
        return palette[idx % palette_length]

    for _, row in superblocks.iterrows():
        color = _color_for_index(int(row.get("superblock_id", 0)))
        geom = row.geometry
        tooltip = folium.Tooltip(
            f"Superblock {row.get('superblock_id', '-'):<}")
        folium.GeoJson(
            geom,
            style_function=lambda *_args, color=color, **_kwargs: {
                "fillColor": color,
                "color": color,
                "weight": 2,
                "fillOpacity": 0.35,
            },
            tooltip=tooltip,
        ).add_to(folium_map)

    folium.LayerControl(collapsed=False).add_to(folium_map)

    path = _ensure_output_path(output_path)
    folium_map.save(str(path))
    logger.info("Saved superblock map to %s", path)
    return path
