"""Configuration helpers for the superblock processing pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Tuple


@dataclass(slots=True)
class PipelineConfig:
    """Container for all tunable parameters of the pipeline.

    The defaults are tuned for Budapest but can be customised when
    instantiating :class:`~superblocks.pipeline.SuperblockPipeline` or the
    legacy :class:`road_network.RoadNetwork` wrapper.
    """

    place_name: str = "Budapest, Hungary"
    network_type: str = "drive"
    retain_all: bool = True
    simplify: bool = True
    custom_filter: str | None = None
    output_dir: str = "outputs"

    # Capacity estimation defaults
    default_lanes: float = 2.0
    default_maxspeed: float = 50.0  # km/h
    default_width: float = 3.5  # metres per lane
    min_lanes: float = 1.0
    lane_width: float = 3.5
    capacity_scale_factor: float = 1.0

    # Street classification thresholds
    boundary_capacity_quantile: float = 0.65
    boundary_highway_types: Tuple[str, ...] = field(
        default_factory=lambda: (
            "motorway",
            "motorway_link",
            "trunk",
            "trunk_link",
            "primary",
            "primary_link",
            "secondary",
            "secondary_link",
        )
    )
    internal_highway_types: Tuple[str, ...] = field(
        default_factory=lambda: (
            "tertiary",
            "tertiary_link",
            "unclassified",
            "residential",
            "living_street",
            "service",
            "road",
            "pedestrian",
            "track",
        )
    )
    major_road_capacity_quantile: float = 0.85
    major_highway_types: Tuple[str, ...] = field(
        default_factory=lambda: (
            "motorway",
            "motorway_link",
            "trunk",
            "trunk_link",
            "primary",
            "primary_link",
        )
    )
    major_road_buffer_metres: float = 25.0

    heritage_zone_radius_m: float = 1500.0
    heritage_capacity_quantile: float = 0.55
    heritage_priority_highway_types: Tuple[str, ...] = field(
        default_factory=lambda: (
            "residential",
            "living_street",
            "pedestrian",
            "service",
            "unclassified",
        )
    )
    heritage_place_queries: Tuple[str, ...] = field(
        default_factory=lambda: (
            "District V, Budapest, Hungary",
            "District I, Budapest, Hungary",
            "District VI, Budapest, Hungary",
            "District VII, Budapest, Hungary",
        )
    )
    heritage_zone_buffer_m: float = 150.0
    heritage_zone_min_area_m2: float = 25000.0

    # Geometry handling
    boundary_buffer_metres: float = 5.0
    block_min_area_m2: float = 75.0
    superblock_min_area_m2: float = 5000.0
    clean_tolerance: float = 0.5

    # Superblock alternatives
    clustering_capacity_quantile: float = 0.75
    clustering_min_cluster_size: int = 5
    concave_alpha: float = 1.5
    modularity_resolution: float = 1.0

    # Visualisation
    folium_tiles: str = "cartodbpositron"
    folium_zoom_start: int = 12
    highlight_palette: Tuple[str, ...] = field(
        default_factory=lambda: (
            "#0B7285",
            "#1864AB",
            "#364FC7",
            "#5F3DC4",
            "#862E9C",
            "#9C36B5",
            "#C2255C",
            "#E03131",
        )
    )
    internal_street_color: str = "#ADB5BD"
    internal_street_weight: float = 1.0
    boundary_street_weight: float = 2.5

    # Static tiling exports
    tile_export_num_tiles: int = 1
    tile_export_dpi: int = 300
    tile_export_linewidth: float = 0.3

    def as_dict(self) -> dict[str, object]:
        """Return a shallow dict useful for serialisation or debugging."""

        return {
            field_.name: getattr(self, field_.name)
            for field_ in self.__dataclass_fields__.values()
        }
