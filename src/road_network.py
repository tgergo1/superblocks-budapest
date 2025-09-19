"""Modernised road network analysis for superblock detection."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple

import geopandas as gpd
import pandas as pd

from superblocks.blocks import build_blocks
from superblocks.capacity import estimate_capacity
from superblocks.config import PipelineConfig
from superblocks.geometry import buffer_in_meters
from superblocks.pipeline import SuperblockPipeline
from superblocks.streets import classify_streets
from superblocks.superblocks import assign_blocks_to_superblocks, build_superblocks
from superblocks.visualization import interactive as vis_interactive

try:  # Backwards compatibility: lazily import optional dependencies
    import osmnx as ox
except Exception:  # pragma: no cover - handled gracefully during tests
    ox = None

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class RoadNetwork:
    """High-level workflow wrapper maintaining backwards compatibility."""

    def __init__(self, place_name: str, output_dir: str = "outputs", config: PipelineConfig | None = None):
        if config is None:
            config = PipelineConfig(place_name=place_name, output_dir=output_dir)
        else:
            config.place_name = place_name
            config.output_dir = output_dir
        self.config = config
        self.pipeline = SuperblockPipeline(config)

        # Public attributes maintained for compatibility
        self.graph = None
        self.nodes: gpd.GeoDataFrame | None = None
        self.edges: gpd.GeoDataFrame | None = None
        self.boundary_streets: gpd.GeoDataFrame | None = None
        self.internal_streets: gpd.GeoDataFrame | None = None
        self.blocks: gpd.GeoDataFrame | None = None
        self.superblocks: gpd.GeoDataFrame | None = None
        self.centroid: Tuple[float, float] | None = None

    # ------------------------------------------------------------------
    # Data ingestion & enrichment
    # ------------------------------------------------------------------

    def download_street_network(self) -> None:
        """Download the road network graph and derive GeoDataFrames."""

        self.pipeline.download()
        state = self.pipeline.state
        self.graph = state.graph
        self.nodes = state.nodes
        self.edges = state.edges
        self.centroid = state.centre
        logger.info(
            "Downloaded street network containing %s nodes and %s edges",
            len(self.nodes) if self.nodes is not None else 0,
            len(self.edges) if self.edges is not None else 0,
        )

    def classify_streets(self) -> None:
        """Classify streets based on capacity and highway type."""

        if self.edges is None:
            raise ValueError("Street network not downloaded. Call download_street_network() first.")

        if "capacity" not in self.edges.columns:
            self.edges = estimate_capacity(self.edges, self.config)
            self.pipeline.state.edges = self.edges

        boundary, internal, threshold = classify_streets(self.edges, self.config)
        self.boundary_streets = boundary
        self.internal_streets = internal
        self.pipeline.state.boundary_streets = boundary
        self.pipeline.state.internal_streets = internal
        if self.centroid is None:
            self.centroid = self.pipeline.state.centre
        logger.info(
            "Classified streets using threshold %.2f, resulting in %s boundary and %s internal segments",
            threshold,
            len(boundary),
            len(internal),
        )

    def calculate_road_capacity(self, gdf_edges: gpd.GeoDataFrame) -> pd.Series:
        """Expose capacity estimation for compatibility with legacy scripts."""

        return estimate_capacity(gdf_edges, self.config)["capacity"]

    def buffer_streets(self, gdf: gpd.GeoDataFrame, buffer_distance: float | None = None) -> gpd.GeoDataFrame:
        """Buffer street geometries in metres for robust polygonisation."""

        distance = buffer_distance if buffer_distance is not None else self.config.boundary_buffer_metres
        return buffer_in_meters(gdf, distance)

    # ------------------------------------------------------------------
    # Block & superblock creation
    # ------------------------------------------------------------------

    def create_block_polygons(self) -> None:
        if self.internal_streets is None:
            raise ValueError("Internal streets not available. Run classify_streets() first.")
        self.blocks = build_blocks(self.internal_streets, self.config)
        self.pipeline.state.blocks = self.blocks

    def assign_blocks_to_superblocks(self) -> None:
        if self.boundary_streets is None:
            raise ValueError("Boundary streets not available. Run classify_streets() first.")
        if self.blocks is None:
            self.create_block_polygons()
        self.superblocks = build_superblocks(self.boundary_streets, self.config)
        self.pipeline.state.superblocks = self.superblocks
        self.blocks = assign_blocks_to_superblocks(self.blocks, self.superblocks)

    # ------------------------------------------------------------------
    # Alternative algorithms
    # ------------------------------------------------------------------

    def cluster_superblocks(self, capacity_quantile: float = 0.75, min_cluster_size: int = 5, alpha: float = 1.5) -> None:
        if self.boundary_streets is None:
            raise ValueError("Streets must be classified before clustering.")
        from superblock_algorithms import compute_superblocks_by_clustering

        enriched = self.boundary_streets
        if "capacity" not in enriched.columns:
            enriched = estimate_capacity(enriched, self.config)
        self.superblocks = compute_superblocks_by_clustering(
            enriched,
            capacity_quantile=capacity_quantile,
            min_cluster_size=min_cluster_size,
            alpha=alpha,
        )
        self.pipeline.state.superblocks = self.superblocks

    def modularity_superblocks(self, capacity_quantile: float = 0.75, resolution: float = 1.0, alpha: float = 1.5) -> None:
        if self.boundary_streets is None:
            raise ValueError("Streets must be classified before community detection.")
        from superblock_algorithms import compute_superblocks_by_modularity

        enriched = self.boundary_streets
        if "capacity" not in enriched.columns:
            enriched = estimate_capacity(enriched, self.config)
        self.superblocks = compute_superblocks_by_modularity(
            enriched,
            capacity_quantile=capacity_quantile,
            resolution=resolution,
            alpha=alpha,
        )
        self.pipeline.state.superblocks = self.superblocks

    # ------------------------------------------------------------------
    # Visualisation
    # ------------------------------------------------------------------

    def visualize_streets(self, output_file: str = "budapest_streets.html") -> Path:
        if self.boundary_streets is None or self.internal_streets is None:
            raise ValueError("Streets must be classified before visualisation.")
        centre = self.centroid or self.pipeline.state.centre
        if centre is None:
            raise ValueError("Map centre unknown; run download_street_network() first.")
        path = Path(self.config.output_dir) / output_file
        return vis_interactive.render_street_map(
            self.boundary_streets,
            self.internal_streets,
            self.config,
            output_path=path,
            centre=centre,
        )

    def visualize_blocks(self, output_file: str = "budapest_blocks.html") -> Path:
        if self.blocks is None or self.blocks.empty:
            raise ValueError("Blocks have not been created. Run create_block_polygons() first.")
        centre = self.centroid or self.pipeline.state.centre
        path = Path(self.config.output_dir) / output_file
        return vis_interactive.render_blocks_map(
            self.blocks,
            self.config,
            output_path=path,
            centre=centre,
        )

    def visualize_superblocks(self, output_file: str = "budapest_superblocks_map.html") -> Path:
        if self.superblocks is None or self.superblocks.empty:
            raise ValueError("Superblocks have not been created.")
        centre = self.centroid or self.pipeline.state.centre
        path = Path(self.config.output_dir) / output_file
        return vis_interactive.render_superblocks_map(
            self.superblocks,
            self.config,
            output_path=path,
            centre=centre,
            blocks=self.blocks,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_superblocks_geojson(self, output_file: str = "budapest_superblocks.geojson") -> Path:
        if self.superblocks is None or self.superblocks.empty:
            raise ValueError("No superblocks to save. Run assign_blocks_to_superblocks() first.")
        path = Path(self.config.output_dir) / output_file
        path.parent.mkdir(parents=True, exist_ok=True)
        self.superblocks.to_file(path, driver="GeoJSON")
        logger.info("Superblocks GeoJSON saved to %s", path)
        return path

    def save_graph(self, output_file: str = "budapest_street_network.graphml") -> Path:
        if self.graph is None:
            raise ValueError("Graph not available. Run download_street_network() first.")
        if ox is None:
            raise ImportError("osmnx is required to save GraphML files")
        path = Path(self.config.output_dir) / output_file
        path.parent.mkdir(parents=True, exist_ok=True)
        ox.save_graphml(self.graph, filepath=path)
        logger.info("GraphML file saved to %s", path)
        return path
