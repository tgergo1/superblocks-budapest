import logging
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
import alphashape


def compute_superblocks_by_clustering(
    gdf_edges: gpd.GeoDataFrame,
    capacity_quantile: float = 0.75,
    min_cluster_size: int = 5,
    alpha: float = 1.5,
) -> gpd.GeoDataFrame:
    """Identify superblocks using HDBSCAN clustering and alphashape.

    Parameters
    ----------
    gdf_edges : GeoDataFrame
        Edges with geometries and a 'capacity' column.
    capacity_quantile : float, optional
        Quantile threshold to select high-capacity edges, by default 0.75.
    min_cluster_size : int, optional
        Minimum cluster size for HDBSCAN, by default 5.
    alpha : float, optional
        Alpha parameter for ``alphashape.alphashape``, by default 1.5.

    Returns
    -------
    GeoDataFrame
        GeoDataFrame containing polygons representing superblocks.
    """
    if 'capacity' not in gdf_edges.columns:
        raise ValueError("gdf_edges must contain a 'capacity' column")

    logging.info("Selecting high-capacity edges for clustering...")
    threshold = gdf_edges['capacity'].quantile(capacity_quantile)
    high_cap_edges = gdf_edges[gdf_edges['capacity'] >= threshold]
    logging.info(
        f"Using capacity threshold {threshold:.2f} (quantile {capacity_quantile})"
    )

    if high_cap_edges.empty:
        logging.warning("No edges above the capacity threshold were found.")
        return gpd.GeoDataFrame(columns=['geometry'], crs=gdf_edges.crs)

    logging.info("Extracting edge nodes for clustering...")
    points: list[Point] = []
    for geom in high_cap_edges.geometry:
        if geom.geom_type == 'LineString':
            coords = list(geom.coords)
            points.append(Point(coords[0]))
            points.append(Point(coords[-1]))
        elif geom.geom_type == 'MultiLineString':
            for line in geom.geoms:
                coords = list(line.coords)
                points.append(Point(coords[0]))
                points.append(Point(coords[-1]))

    if not points:
        logging.warning("No points extracted from high-capacity edges.")
        return gpd.GeoDataFrame(columns=['geometry'], crs=gdf_edges.crs)

    coords = np.array([(p.x, p.y) for p in points])
    logging.info("Clustering nodes with HDBSCAN...")
    import hdbscan
    clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size)
    labels = clusterer.fit_predict(coords)

    polygons = []
    for label in set(labels):
        if label == -1:
            continue  # noise
        cluster_points = [p for p, l in zip(points, labels) if l == label]
        if len(cluster_points) < 3:
            continue
        poly = alphashape.alphashape(cluster_points, alpha)
        if poly.is_empty:
            continue
        polygons.append(poly)

    logging.info(f"Generated {len(polygons)} superblock polygons from clusters")
    if not polygons:
        return gpd.GeoDataFrame(columns=['geometry'], crs=gdf_edges.crs)

    gdf = gpd.GeoDataFrame({'geometry': polygons}, crs=gdf_edges.crs)
    gdf['superblock_id'] = range(len(gdf))
    return gdf


def compute_superblocks_by_modularity(
    gdf_edges: gpd.GeoDataFrame,
    capacity_quantile: float = 0.75,
    resolution: float = 1.0,
    alpha: float = 1.5,
) -> gpd.GeoDataFrame:
    """Identify superblocks using community detection based on modularity.

    This method constructs a graph from high-capacity road segments and
    applies greedy modularity optimization to find communities. The nodes of
    each community are wrapped in a concave hull using ``alphashape`` to form
    the resulting superblock polygons.

    Parameters
    ----------
    gdf_edges : GeoDataFrame
        Edges with geometries and a ``capacity`` column.
    capacity_quantile : float, optional
        Quantile threshold to select high-capacity edges, by default ``0.75``.
    resolution : float, optional
        Resolution parameter for modularity optimization, by default ``1.0``.
    alpha : float, optional
        Alpha parameter for ``alphashape.alphashape``, by default ``1.5``.

    Returns
    -------
    GeoDataFrame
        GeoDataFrame containing polygons representing superblocks.
    """

    if "capacity" not in gdf_edges.columns:
        raise ValueError("gdf_edges must contain a 'capacity' column")

    threshold = gdf_edges["capacity"].quantile(capacity_quantile)
    high_cap_edges = gdf_edges[gdf_edges["capacity"] >= threshold]
    logging.info(
        f"Using capacity threshold {threshold:.2f} (quantile {capacity_quantile})"
    )

    import networkx as nx
    from networkx.algorithms import community as nx_comm

    G = nx.Graph()
    for geom, cap in zip(high_cap_edges.geometry, high_cap_edges["capacity"]):
        if geom.geom_type == "LineString":
            coords = list(geom.coords)
            G.add_edge(coords[0], coords[-1], weight=float(cap))
        elif geom.geom_type == "MultiLineString":
            for line in geom.geoms:
                coords = list(line.coords)
                G.add_edge(coords[0], coords[-1], weight=float(cap))

    if G.number_of_edges() == 0:
        logging.warning("No edges above the capacity threshold were found.")
        return gpd.GeoDataFrame(columns=["geometry"], crs=gdf_edges.crs)

    communities = nx_comm.greedy_modularity_communities(G, weight="weight", resolution=resolution)
    polygons = []
    for community in communities:
        points = [Point(node) for node in community]
        if len(points) < 3:
            continue
        coords = [(p.x, p.y) for p in points]
        poly = alphashape.alphashape(coords, alpha)
        if poly.is_empty:
            poly = gpd.GeoSeries(points).unary_union.convex_hull
        if not poly.is_empty:
            polygons.append(poly)

    if not polygons:
        logging.warning("Community detection returned no polygons.")
        return gpd.GeoDataFrame(columns=["geometry"], crs=gdf_edges.crs)

    gdf = gpd.GeoDataFrame({"geometry": polygons}, crs=gdf_edges.crs)
    gdf["superblock_id"] = range(len(gdf))
    return gdf
