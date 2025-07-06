import geopandas as gpd
from shapely.geometry import LineString, Point
import networkx as nx
import types
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

mpl_stub = types.ModuleType("matplotlib")
pyplot_stub = types.ModuleType("matplotlib.pyplot")
mpl_stub.pyplot = pyplot_stub
mpl_stub.use = lambda *args, **kwargs: None
sys.modules.setdefault("matplotlib", mpl_stub)
sys.modules.setdefault("matplotlib.pyplot", pyplot_stub)

# Create lightweight stubs for osmnx and momepy to avoid heavy dependencies
ox_stub = types.ModuleType("osmnx")

def _graph_from_gdfs(nodes, edges, graph_attrs=None):
    G = nx.Graph()
    for idx, row in nodes.iterrows():
        G.add_node(idx, x=row.geometry.x, y=row.geometry.y)
    for _, row in edges.iterrows():
        coords = list(row.geometry.coords)
        G.add_edge(0, 1, geometry=row.geometry)  # minimal edge
    return G

def _graph_to_gdfs(G, nodes=False, edges=True, node_geometry=False, fill_edge_geometry=True):
    geoms = [data["geometry"] for _, _, data in G.edges(data=True)]
    return gpd.GeoDataFrame({"geometry": geoms})

ox_stub.graph_from_gdfs = _graph_from_gdfs
ox_stub.graph_to_gdfs = _graph_to_gdfs
sys.modules.setdefault("osmnx", ox_stub)

momepy_stub = types.ModuleType("momepy")

class _Blocks:
    def __init__(self, gdf):
        self.blocks = gdf

momepy_stub.Blocks = _Blocks
sys.modules.setdefault("momepy", momepy_stub)

pyrosm_stub = types.ModuleType("pyrosm")
pyrosm_stub.OSM = object
pyrosm_stub.get_data = lambda city_name, directory=None: None
sys.modules.setdefault("pyrosm", pyrosm_stub)

from src.experiments.capacity_test import calculate_capacity, identify_superblocks


def sample_network():
    edges_data = {
        "u": [0, 1, 2, 3],
        "v": [1, 2, 3, 0],
        "lanes": [2, 2, 2, 2],
        "maxspeed": [50, 50, 50, 50],
        "width": [7, 7, 7, 7],
        "geometry": [
            LineString([(0, 0), (0, 1)]),
            LineString([(0, 1), (1, 1)]),
            LineString([(1, 1), (1, 0)]),
            LineString([(1, 0), (0, 0)]),
        ],
    }
    edges = gpd.GeoDataFrame(edges_data, geometry="geometry")

    nodes_data = {
        "id": [0, 1, 2, 3],
        "geometry": [Point(0, 0), Point(0, 1), Point(1, 1), Point(1, 0)],
    }
    nodes = gpd.GeoDataFrame(nodes_data, geometry="geometry")
    return edges, nodes


def test_calculate_capacity():
    edges, _ = sample_network()
    result = calculate_capacity(edges.copy())
    assert "capacity" in result.columns
    assert not result["capacity"].isna().any()


def test_identify_superblocks():
    edges, nodes = sample_network()
    edges = calculate_capacity(edges)
    blocks = identify_superblocks(edges, nodes)
    assert not blocks.empty
