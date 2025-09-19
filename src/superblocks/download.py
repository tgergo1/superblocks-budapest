"""Data access helpers for OpenStreetMap powered analysis."""

from __future__ import annotations

import logging
from typing import Tuple

import geopandas as gpd
import networkx as nx
import osmnx as ox

from .config import PipelineConfig

logger = logging.getLogger(__name__)


def download_graph(config: PipelineConfig) -> nx.MultiDiGraph:
    """Download a city-scale graph using :mod:`osmnx`.

    Parameters
    ----------
    config:
        Pipeline configuration that provides place name and download options.

    Returns
    -------
    networkx.MultiDiGraph
        The downloaded road network graph.
    """

    logger.info("Downloading street network for %s", config.place_name)
    graph = ox.graph_from_place(
        config.place_name,
        network_type=config.network_type,
        retain_all=config.retain_all,
        simplify=config.simplify,
        custom_filter=config.custom_filter,
    )
    logger.info(
        "Downloaded network with %s nodes and %s edges",
        graph.number_of_nodes(),
        graph.number_of_edges(),
    )
    return graph


def graph_to_gdfs(graph: nx.MultiDiGraph) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Convert a graph to GeoDataFrames for nodes and edges."""

    nodes, edges = ox.graph_to_gdfs(graph, nodes=True, edges=True)
    return nodes, edges
