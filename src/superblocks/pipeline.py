"""High-level orchestration of the superblock analysis workflow."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import geopandas as gpd
import networkx as nx

from . import capacity
from .blocks import build_blocks
from .config import PipelineConfig
from .download import download_graph, graph_to_gdfs
from .streets import classify_streets
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
    blocks: gpd.GeoDataFrame | None = None
    superblocks: gpd.GeoDataFrame | None = None
    centre: Tuple[float, float] | None = None


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

    def build_blocks(self) -> None:
        internal = self._require_internal_streets()
        blocks = build_blocks(internal, self.config)
        self.state.blocks = blocks

    def build_superblocks(self) -> None:
        boundary = self._require_boundary_streets()
        superblocks = build_superblocks(boundary, self.config)
        self.state.superblocks = superblocks

    def assign_blocks(self) -> None:
        blocks = self._require_blocks()
        superblocks = self._require_superblocks()
        assigned = assign_blocks_to_superblocks(blocks, superblocks)
        self.state.blocks = assigned

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
            vis_interactive.render_superblocks_map(
                self.state.superblocks,
                self.config,
                output_dir / "budapest_superblocks_map.html",
                centre=centre,
                blocks=self.state.blocks,
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
        self.export_maps()
        self.export_geojson()
        self.export_graph()

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
