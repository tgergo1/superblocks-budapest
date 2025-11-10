"""High-level orchestration of the superblock analysis workflow."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import geopandas as gpd
import networkx as nx

from . import capacity
from .access_control import (
    calculate_street_directions,
    identify_modal_filters,
    analyze_permeability,
)
from .blocks import build_blocks
from .config import PipelineConfig
from .download import download_graph, graph_to_gdfs
from .heritage import derive_heritage_zone
from .metrics import compute_metrics, write_markdown, write_metrics
from .reporting import generate_full_report
from .streets import classify_streets, detect_major_roads, identify_heritage_priorities
from .superblocks import assign_blocks_to_superblocks, build_superblocks
from .visualization import interactive as vis_interactive
from .visualization import static as vis_static

logger = logging.getLogger(__name__)


@dataclass
class PipelineState:
    graph: nx.MultiDiGraph | None = None
    nodes: gpd.GeoDataFrame | None = None
    edges: gpd.GeoDataFrame | None = None
    boundary_streets: gpd.GeoDataFrame | None = None
    internal_streets: gpd.GeoDataFrame | None = None
    internal_streets_with_directions: gpd.GeoDataFrame | None = None
    modal_filters: gpd.GeoDataFrame | None = None
    permeability_metrics: gpd.GeoDataFrame | None = None
    major_roads: gpd.GeoDataFrame | None = None
    heritage_priority_streets: gpd.GeoDataFrame | None = None
    heritage_zone: gpd.GeoDataFrame | None = None
    blocks: gpd.GeoDataFrame | None = None
    superblocks: gpd.GeoDataFrame | None = None
    centre: Tuple[float, float] | None = None
    metrics: dict | None = None


class SuperblockPipeline:
    """Encapsulates the end-to-end computation for superblocks."""

    def __init__(self, config: PipelineConfig | None = None):
        self.config = config or PipelineConfig()
        self.state = PipelineState()

    # ------------------------------------------------------------------
    # Core pipeline steps
    # ------------------------------------------------------------------

    def download(self) -> None:
        self.state.graph = download_graph(self.config)
        nodes, edges = graph_to_gdfs(self.state.graph)
        self.state.nodes = nodes
        self.state.edges = edges
        self.state.centre = self._derive_centre()

    def enrich_edges(self) -> None:
        self._require_edges()
        enriched = capacity.estimate_capacity(self.state.edges, self.config)
        self.state.edges = enriched

    def classify(self) -> None:
        self._require_edges(with_capacity=True)
        boundary, internal, threshold = classify_streets(self.state.edges, self.config)
        logger.info("Using capacity threshold %.2f for boundary streets", threshold)
        self.state.boundary_streets = boundary
        self.state.internal_streets = internal
        self.detect_priority_layers()

    def detect_priority_layers(self) -> None:
        edges = self._require_edges(with_capacity=True)
        centre = self._derive_centre()
        major = detect_major_roads(edges, self.config)
        heritage_zone = derive_heritage_zone(edges, self.config, centre)
        heritage_priority = identify_heritage_priorities(edges, self.config, heritage_zone)
        self.state.major_roads = major
        self.state.heritage_priority_streets = heritage_priority
        self.state.heritage_zone = heritage_zone

    def analyse_metrics(self) -> None:
        if self.state.edges is None:
            return
        metrics = compute_metrics(
            edges=self.state.edges,
            boundary=self.state.boundary_streets,
            internal=self.state.internal_streets,
            superblocks=self.state.superblocks,
            heritage_zone=self.state.heritage_zone,
            heritage_priority=self.state.heritage_priority_streets,
            major_roads=self.state.major_roads,
            config=self.config,
        )
        self.state.metrics = metrics

    def build_blocks(self) -> None:
        internal = self._require_internal_streets()
        blocks = build_blocks(internal, self.config)
        self.state.blocks = blocks

    def build_superblocks(self) -> None:
        boundary = self._require_boundary_streets()
        exclusions = None
        if self.state.major_roads is not None and not self.state.major_roads.empty:
            exclusions = self.state.major_roads
        superblocks = build_superblocks(boundary, self.config, exclusions=exclusions)
        self.state.superblocks = superblocks

    def assign_blocks(self) -> None:
        blocks = self._require_blocks()
        superblocks = self._require_superblocks()
        assigned = assign_blocks_to_superblocks(blocks, superblocks)
        self.state.blocks = assigned
        self.analyse_metrics()

    def calculate_access_control(self) -> None:
        """Calculate street directions and modal filter placements."""
        edges = self._require_edges(with_capacity=True)
        superblocks = self._require_superblocks()
        boundary = self._require_boundary_streets()
        internal = self._require_internal_streets()
        
        # Calculate optimal street directions
        internal_with_directions = calculate_street_directions(
            edges, superblocks, boundary, internal, self.config
        )
        self.state.internal_streets_with_directions = internal_with_directions
        
        # Identify modal filter locations
        modal_filters = identify_modal_filters(
            internal_with_directions, superblocks, self.config
        )
        self.state.modal_filters = modal_filters
        
        # Analyze permeability
        permeability = analyze_permeability(
            internal_with_directions, superblocks, boundary
        )
        self.state.permeability_metrics = permeability
        
        logger.info("Calculated access control: %d streets with directions, %d modal filters",
                    len(internal_with_directions), len(modal_filters))

    # ------------------------------------------------------------------
    # Visual outputs
    # ------------------------------------------------------------------

    def export_maps(self) -> None:
        centre = self._derive_centre()
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if self.state.boundary_streets is not None and self.state.internal_streets is not None:
            vis_interactive.render_street_map(
                self.state.boundary_streets,
                self.state.internal_streets,
                self.config,
                output_dir / "budapest_streets.html",
                centre=centre,
            )

        if self.state.blocks is not None and not self.state.blocks.empty:
            vis_interactive.render_blocks_map(
                self.state.blocks,
                self.config,
                output_dir / "budapest_blocks.html",
                centre=centre,
            )

        if self.state.superblocks is not None and not self.state.superblocks.empty:
            # Use internal streets with directions if available
            street_dirs = self.state.internal_streets_with_directions
            if street_dirs is None or street_dirs.empty:
                street_dirs = self.state.internal_streets
            
            vis_interactive.render_superblocks_map(
                self.state.superblocks,
                self.config,
                output_dir / "budapest_superblocks_map.html",
                centre=centre,
                blocks=self.state.blocks,
                major_roads=self.state.major_roads,
                heritage_priority=self.state.heritage_priority_streets,
                heritage_zone=self.state.heritage_zone,
                street_directions=street_dirs,
                modal_filters=self.state.modal_filters,
            )

        if self.state.edges is not None:
            vis_static.tiled_edge_plot(
                self.state.edges,
                output_dir / "budapest_superblocks.png",
                num_tiles=self.config.tile_export_num_tiles,
                dpi=self.config.tile_export_dpi,
                linewidth=self.config.tile_export_linewidth,
                color_column="capacity",
            )

    def export_geojson(self, output_file: str = "budapest_superblocks.geojson") -> Path:
        superblocks = self._require_superblocks()
        path = Path(self.config.output_dir) / output_file
        path.parent.mkdir(parents=True, exist_ok=True)
        superblocks.to_file(path, driver="GeoJSON")
        logger.info("Saved superblocks GeoJSON to %s", path)
        return path

    def export_graph(self, output_file: str = "budapest_street_network.graphml") -> Path:
        if self.state.graph is None:
            raise ValueError("Street network graph is not available")
        path = Path(self.config.output_dir) / output_file
        path.parent.mkdir(parents=True, exist_ok=True)
        import osmnx as ox

        ox.save_graphml(self.state.graph, filepath=path)
        logger.info("Saved street network GraphML to %s", path)
        return path

    def export_access_control(self) -> None:
        """Export access control data (street directions and modal filters)."""
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Export streets with directions
        if self.state.internal_streets_with_directions is not None:
            streets_path = output_dir / "budapest_street_directions.geojson"
            self.state.internal_streets_with_directions.to_file(streets_path, driver="GeoJSON")
            logger.info("Saved street directions to %s", streets_path)
        
        # Export modal filters
        if self.state.modal_filters is not None and not self.state.modal_filters.empty:
            filters_path = output_dir / "budapest_modal_filters.geojson"
            self.state.modal_filters.to_file(filters_path, driver="GeoJSON")
            logger.info("Saved modal filters to %s", filters_path)
        
        # Export permeability metrics
        if self.state.permeability_metrics is not None:
            metrics_path = output_dir / "budapest_permeability_metrics.json"
            self.state.permeability_metrics.to_json(metrics_path, orient="records", indent=2)
            logger.info("Saved permeability metrics to %s", metrics_path)

    # ------------------------------------------------------------------
    # Convenience orchestration
    # ------------------------------------------------------------------

    def run_full_pipeline(self) -> None:
        self.download()
        self.enrich_edges()
        self.classify()
        self.build_blocks()
        self.build_superblocks()
        self.assign_blocks()
        self.calculate_access_control()
        self.export_maps()
        self.export_geojson()
        self.export_graph()
        self.export_access_control()
        self.export_reports()

    def export_reports(self) -> None:
        if self.state.metrics is None:
            logger.warning("Metrics unavailable; skipping analytics export")
            return

        output_dir = Path(self.config.output_dir)
        metrics_path = write_metrics(output_dir / "budapest_superblocks_metrics.json", self.state.metrics)
        report_path = write_markdown(output_dir / "budapest_superblocks_report.md", self.state.metrics)
        brief_path = generate_full_report(
            self.state.metrics,
            output_dir / "budapest_superblocks_brief.md",
        )
        logger.info("Saved metrics to %s, %s, and %s", metrics_path, report_path, brief_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _derive_centre(self) -> Tuple[float, float] | None:
        if self.state.nodes is not None and not self.state.nodes.empty:
            lon = float(self.state.nodes.geometry.x.mean())
            lat = float(self.state.nodes.geometry.y.mean())
            return lat, lon
        if self.state.edges is not None and not self.state.edges.empty:
            bounds = self.state.edges.total_bounds
            lon = (bounds[0] + bounds[2]) / 2
            lat = (bounds[1] + bounds[3]) / 2
            return lat, lon
        return None

    def _require_edges(self, with_capacity: bool = False) -> gpd.GeoDataFrame:
        if self.state.edges is None:
            raise ValueError("Edges have not been downloaded yet")
        if with_capacity and "capacity" not in self.state.edges:
            raise ValueError("Edges have not been enriched with capacity")
        return self.state.edges

    def _require_boundary_streets(self) -> gpd.GeoDataFrame:
        if self.state.boundary_streets is None:
            raise ValueError("Boundary streets are unavailable; run classify() first")
        return self.state.boundary_streets

    def _require_internal_streets(self) -> gpd.GeoDataFrame:
        if self.state.internal_streets is None:
            raise ValueError("Internal streets are unavailable; run classify() first")
        return self.state.internal_streets

    def _require_blocks(self) -> gpd.GeoDataFrame:
        if self.state.blocks is None:
            raise ValueError("Blocks have not been generated; run build_blocks() first")
        return self.state.blocks

    def _require_superblocks(self) -> gpd.GeoDataFrame:
        if self.state.superblocks is None:
            raise ValueError("Superblocks have not been created; run build_superblocks() first")
        return self.state.superblocks
