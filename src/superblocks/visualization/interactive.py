"""Interactive map rendering with Folium."""

from __future__ import annotations

import base64
import gzip
import json
import logging
import textwrap
from pathlib import Path
from typing import Iterable, Tuple

import geopandas as gpd
import pandas as pd
import folium
from branca.colormap import LinearColormap
from folium.plugins import Fullscreen, MeasureControl, MiniMap, MousePosition
from shapely.geometry import LineString, MultiLineString, MultiPolygon

try:
    # Shapely 2.0+
    from shapely import set_precision as shapely_set_precision
except ImportError:  # pragma: no cover - fallback for Shapely < 2
    shapely_set_precision = None

from ..config import PipelineConfig

logger = logging.getLogger(__name__)

VENDOR_JS_DIR = Path(__file__).resolve().parents[3] / "assets" / "vendor"
_PAKO_CDN = "https://cdn.jsdelivr.net/npm/pako@2.1.0/dist/pako.min.js"
_TEXTPATH_CDN = "https://cdn.jsdelivr.net/npm/leaflet-textpath@1.2.3/leaflet.textpath.min.js"
_PAKO_INLINE: str | None = None
_TEXTPATH_INLINE: str | None = None


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


def _safe_simplify_geometry(geom, tolerance: float):
    if geom is None or geom.is_empty or tolerance <= 0:
        return geom
    simplified = geom.simplify(tolerance, preserve_topology=True)
    if simplified.is_empty:
        return geom
    if geom.geom_type == simplified.geom_type:
        return simplified
    if geom.geom_type == "MultiLineString" and simplified.geom_type == "LineString":
        return MultiLineString([simplified])
    if geom.geom_type == "MultiPolygon" and simplified.geom_type == "Polygon":
        return MultiPolygon([simplified])
    return geom


def _simplify_geometries(gdf: gpd.GeoDataFrame, tolerance_m: float | None) -> gpd.GeoDataFrame:
    if tolerance_m is None or tolerance_m <= 0:
        return gdf
    if gdf.crs is None:
        logger.debug("Skipping simplification because CRS is undefined")
        return gdf

    projected = gdf.to_crs(3857)
    simplified = projected.geometry.apply(lambda geom: _safe_simplify_geometry(geom, tolerance_m))
    projected = projected.set_geometry(simplified)
    if gdf.crs == projected.crs:
        return projected
    return projected.to_crs(gdf.crs)


def _apply_precision(gdf: gpd.GeoDataFrame, precision_digits: int | None) -> gpd.GeoDataFrame:
    if precision_digits is None or precision_digits <= 0 or shapely_set_precision is None:
        return gdf
    grid_size = 10 ** (-precision_digits)
    adjusted = gdf.set_geometry(
        gdf.geometry.apply(
            lambda geom: shapely_set_precision(geom, grid_size=grid_size) if geom and not geom.is_empty else geom
        )
    )
    return adjusted


def _prepare_layer(
    gdf: gpd.GeoDataFrame | None,
    keep_fields: Iterable[str] | None,
    tolerance_m: float | None,
    coordinate_precision: int | None,
) -> gpd.GeoDataFrame | None:
    if gdf is None or gdf.empty:
        return gdf

    geometry_col = gdf.geometry.name
    if keep_fields:
        keep = [field for field in keep_fields if field in gdf.columns and field != geometry_col]
        keep.append(geometry_col)
        working = gdf[keep].copy()
    else:
        working = gdf.copy()

    simplified = _simplify_geometries(working, tolerance_m)
    precise = _apply_precision(simplified, coordinate_precision)
    return precise


def _load_vendor_script(filename: str) -> str | None:
    path = VENDOR_JS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    logger.warning("Missing vendor script %s; falling back to CDN delivery", path)
    return None


def _ensure_direction_assets(folium_map: folium.Map) -> None:
    root = folium_map.get_root()
    if getattr(root, "_direction_assets_loaded", False):
        return
    root._direction_assets_loaded = True  # type: ignore[attr-defined]
    global _PAKO_INLINE, _TEXTPATH_INLINE
    if _PAKO_INLINE is None:
        _PAKO_INLINE = _load_vendor_script("pako.min.js")
    if _TEXTPATH_INLINE is None:
        _TEXTPATH_INLINE = _load_vendor_script("leaflet.textpath.min.js")

    if _PAKO_INLINE is not None:
        root.html.add_child(folium.Element(f"<script>{_PAKO_INLINE}</script>"))  # type: ignore[attr-defined]
    else:
        root.html.add_child(folium.Element(f'<script src="{_PAKO_CDN}"></script>'))  # type: ignore[attr-defined]

    if _TEXTPATH_INLINE is not None:
        root.html.add_child(folium.Element(f"<script>{_TEXTPATH_INLINE}</script>"))  # type: ignore[attr-defined]
    else:
        root.html.add_child(  # type: ignore[attr-defined]
            folium.Element(f'<script src="{_TEXTPATH_CDN}"></script>')
        )


def _encode_direction_segments(gdf: gpd.GeoDataFrame) -> str:
    lowercase_true = {"yes", "true", "1", "y"}
    segments = []
    for _, row in gdf.iterrows():
        oneway_value = row.get("oneway")
        if isinstance(oneway_value, str):
            oneway_value = oneway_value.lower()
        is_oneway = oneway_value in lowercase_true or oneway_value is True
        for coords in _iter_lines(row.geometry):
            if len(coords) < 2:
                continue
            latlon = [[coord[1], coord[0]] for coord in coords]
            if len(latlon) < 2:
                continue
            segments.append({"c": latlon, "o": bool(is_oneway)})
    payload = json.dumps(segments, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(payload)
    return base64.b64encode(compressed).decode("ascii")


def _compressed_direction_script(group_name: str, color: str, data_b64: str) -> str:
    return textwrap.dedent(
        f"""
        <script>
        (function() {{
            function decodeBase64(data) {{
                var raw = atob(data);
                var bytes = new Uint8Array(raw.length);
                for (var i = 0; i < raw.length; i++) {{
                    bytes[i] = raw.charCodeAt(i);
                }}
                return bytes;
            }}
            var compressed = "{data_b64}";
            var bytes = decodeBase64(compressed);
            var jsonText = window.pako.inflate(bytes, {{ to: 'string' }});
            var segments = JSON.parse(jsonText);
            var targetGroup = {group_name};
            segments.forEach(function(segment) {{
                if (!Array.isArray(segment.c) || segment.c.length < 2) {{
                    return;
                }}
                var polyline = L.polyline(segment.c, {{
                    color: "{color}",
                    weight: 2.0,
                    opacity: 0.65
                }}).addTo(targetGroup);
                var arrow = segment.o ? " > " : " <> ";
                if (polyline.setText) {{
                    polyline.setText(arrow, {{
                        repeat: true,
                        offset: 8,
                        attributes: {{
                            fill: "{color}",
                            "font-weight": "bold",
                            "font-size": "12"
                        }}
                    }});
                }}
            }});
        }})();
        </script>
        """
    )


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


def _iter_lines(geometry) -> Iterable[list[tuple[float, float]]]:
    if geometry is None or geometry.is_empty:
        return []
    if isinstance(geometry, LineString):
        return [list(geometry.coords)]
    if isinstance(geometry, MultiLineString):
        return [list(line.coords) for line in geometry.geoms]
    return []


def _add_directional_layer(
    folium_map: folium.Map,
    gdf: gpd.GeoDataFrame | None,
    name: str,
    color: str,
    show: bool = False,
) -> None:
    if gdf is None or gdf.empty:
        return

    group = folium.FeatureGroup(name=name, show=show)
    group.add_to(folium_map)
    _ensure_direction_assets(folium_map)
    encoded = _encode_direction_segments(gdf)
    script = _compressed_direction_script(group.get_name(), color, encoded)
    folium_map.get_root().html.add_child(folium.Element(script))  # type: ignore[attr-defined]



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

    internal_layer = _prepare_layer(
        internal_streets,
        keep_fields=("highway", "capacity"),
        tolerance_m=config.map_line_simplify_tolerance_m,
        coordinate_precision=config.map_coordinate_precision,
    )

    boundary_layer = _prepare_layer(
        boundary_streets,
        keep_fields=("highway", "capacity"),
        tolerance_m=config.map_line_simplify_tolerance_m,
        coordinate_precision=config.map_coordinate_precision,
    )

    if internal_layer is not None and not internal_layer.empty:
        internal_group = folium.FeatureGroup(name="Internal Streets", show=False)
        _add_linestrings_to_map(
            internal_group,
            internal_layer,
            color_func=lambda _row: config.internal_street_color,
            weight=config.internal_street_weight,
            tooltip_fields=("highway", "capacity"),
        )
        internal_group.add_to(folium_map)

    if boundary_layer is not None and not boundary_layer.empty:
        capacity_colormap = LinearColormap(
            colors=["#495057", "#228BE6", "#364FC7"],
            vmin=float(boundary_layer["capacity"].min()),
            vmax=float(boundary_layer["capacity"].max()),
        )
        boundary_group = folium.FeatureGroup(name="Boundary Streets", show=True)
        _add_linestrings_to_map(
            boundary_group,
            boundary_layer,
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

    blocks_layer = _prepare_layer(
        blocks,
        keep_fields=("block_id", "superblock_id"),
        tolerance_m=config.map_polygon_simplify_tolerance_m,
        coordinate_precision=config.map_coordinate_precision,
    )

    style = {
        "fillColor": "#9775FA",
        "color": "#7048E8",
        "weight": 1,
        "fillOpacity": 0.35,
    }

    folium.GeoJson(
        blocks_layer,
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
    major_roads: gpd.GeoDataFrame | None = None,
    heritage_priority: gpd.GeoDataFrame | None = None,
    heritage_zone: gpd.GeoDataFrame | None = None,
    street_directions: gpd.GeoDataFrame | None = None,
    modal_filters: gpd.GeoDataFrame | None = None,
) -> Path:
    if superblocks.empty:
        raise ValueError("Cannot render superblock map without superblock polygons")

    if centre is None:
        centre = _center_from_bounds(superblocks)
    if centre is None:
        raise ValueError("Cannot determine map centre; supply `centre` explicitly")

    folium_map = folium.Map(location=centre, zoom_start=config.folium_zoom_start, tiles=config.folium_tiles)
    folium.TileLayer(
        "cartodbdark_matter",
        name="Dark Matter",
        attr="© OpenStreetMap contributors © CARTO",
    ).add_to(folium_map)
    folium.TileLayer(
        "Stamen Terrain",
        name="Terrain",
        attr="Map tiles by Stamen Design, CC BY 3.0 — Map data © OpenStreetMap contributors",
    ).add_to(folium_map)
    Fullscreen(position="topleft").add_to(folium_map)
    MiniMap(toggle_display=True, minimized=True).add_to(folium_map)
    MeasureControl(primary_length_unit="meters", secondary_length_unit="miles").add_to(folium_map)
    MousePosition(
        position="bottomright",
        separator=" | ",
        empty_string="Out of bounds",
        lng_first=True,
        num_digits=5,
    ).add_to(folium_map)

    polygon_opts = {
        "tolerance_m": config.map_polygon_simplify_tolerance_m,
        "coordinate_precision": config.map_coordinate_precision,
    }
    line_opts = {
        "tolerance_m": config.map_line_simplify_tolerance_m,
        "coordinate_precision": config.map_coordinate_precision,
    }

    superblock_layer = _prepare_layer(superblocks, keep_fields=("superblock_id",), **polygon_opts)
    blocks_layer = _prepare_layer(blocks, keep_fields=("block_id", "superblock_id"), **polygon_opts) if blocks is not None else None
    major_layer = _prepare_layer(major_roads, keep_fields=("highway", "capacity", "major_reason"), **line_opts)
    heritage_priority_layer = _prepare_layer(
        heritage_priority,
        keep_fields=("highway", "capacity", "distance_to_centre"),
        **line_opts,
    )
    street_direction_layer = _prepare_layer(
        street_directions,
        keep_fields=("oneway",),
        tolerance_m=config.access_control_simplify_tolerance_m,
        coordinate_precision=config.map_coordinate_precision,
    )
    modal_filters_layer = _prepare_layer(modal_filters, keep_fields=("street_name", "reason"), **line_opts)
    heritage_zone_layer = _prepare_layer(heritage_zone, keep_fields=None, **polygon_opts)

    if heritage_zone_layer is not None and not heritage_zone_layer.empty:
        folium.GeoJson(
            heritage_zone_layer,
            name="Heritage Core",
            style_function=lambda *_args, **_kwargs: {
                "fillColor": "#ffe066",
                "color": "#f08c00",
                "weight": 1.5,
                "fillOpacity": 0.15,
            },
        ).add_to(folium_map)

    if blocks_layer is not None and not blocks_layer.empty:
        folium.GeoJson(
            blocks_layer,
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

    if major_layer is not None and not major_layer.empty:
        major_group = folium.FeatureGroup(name="Major Corridors", show=True)
        _add_linestrings_to_map(
            major_group,
            major_layer,
            color_func=lambda _row: "#fa5252",
            weight=4.0,
            tooltip_fields=("highway", "capacity", "major_reason"),
        )
        major_group.add_to(folium_map)

    if heritage_priority_layer is not None and not heritage_priority_layer.empty:
        heritage_group = folium.FeatureGroup(name="Car-Light Candidates", show=True)
        _add_linestrings_to_map(
            heritage_group,
            heritage_priority_layer,
            color_func=lambda _row: "#2f9e44",
            weight=3.0,
            tooltip_fields=("highway", "capacity", "distance_to_centre"),
        )
        heritage_group.add_to(folium_map)

    if street_direction_layer is not None and not street_direction_layer.empty:
        _add_directional_layer(
            folium_map,
            street_direction_layer,
            name="Street Directions",
            color="#4dabf7",
            show=True,
        )

    # Add modal filters layer
    if modal_filters_layer is not None and not modal_filters_layer.empty:
        filters_group = folium.FeatureGroup(name="Modal Filters", show=True)
        for _, filter_row in modal_filters_layer.iterrows():
            folium.CircleMarker(
                location=[filter_row.geometry.y, filter_row.geometry.x],
                radius=8,
                color="#e03131",
                fill=True,
                fillColor="#e03131",
                fillOpacity=0.8,
                weight=2,
                tooltip=folium.Tooltip(
                    f"Modal Filter<br>"
                    f"Street: {filter_row.get('street_name', 'Unknown')}<br>"
                    f"Reason: {filter_row.get('reason', 'N/A')}"
                ),
            ).add_to(filters_group)
        filters_group.add_to(folium_map)

    palette = list(config.highlight_palette)
    palette_length = len(palette)
    fallback_color = "#2b8a3e"

    def _color_for_value(value) -> str:
        if palette_length == 0:
            return fallback_color
        try:
            idx = int(value)
        except (TypeError, ValueError):
            idx = 0
        return palette[idx % palette_length]

    color_field = "__fill_color"
    superblock_render = superblock_layer.copy()
    superblock_render[color_field] = superblock_render["superblock_id"].apply(_color_for_value)
    folium.GeoJson(
        superblock_render,
        name="Superblocks",
        style_function=lambda feature: {
            "fillColor": feature["properties"].get(color_field, fallback_color if palette_length == 0 else palette[0]),
            "color": feature["properties"].get(color_field, fallback_color if palette_length == 0 else palette[0]),
            "weight": 2,
            "fillOpacity": 0.35,
        },
        tooltip=folium.GeoJsonTooltip(fields=["superblock_id"], aliases=["Superblock"]),
    ).add_to(folium_map)

    folium.LayerControl(collapsed=False).add_to(folium_map)

    path = _ensure_output_path(output_path)
    folium_map.save(str(path))
    logger.info("Saved superblock map to %s", path)
    return path
