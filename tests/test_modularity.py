import sys
sys.path.append('src')

import geopandas as gpd
from shapely.geometry import LineString
import types
import sys

ox_stub = types.ModuleType("osmnx")
sys.modules.setdefault("osmnx", ox_stub)

from road_network import RoadNetwork


def build_simple_boundary():
    lines = [
        LineString([(0, 0), (2, 0)]),
        LineString([(2, 0), (2, 2)]),
        LineString([(2, 2), (0, 2)]),
        LineString([(0, 2), (0, 0)]),
        LineString([(4, 0), (6, 0)]),
        LineString([(6, 0), (6, 2)]),
        LineString([(6, 2), (4, 2)]),
        LineString([(4, 2), (4, 0)]),
    ]
    gdf = gpd.GeoDataFrame({'geometry': lines, 'capacity': [1]*len(lines)}, crs='EPSG:4326')
    return gdf


def test_modularity_superblocks_returns_polygons():
    rn = RoadNetwork('test')
    rn.boundary_streets = build_simple_boundary()
    rn.modularity_superblocks(capacity_quantile=0.0)
    assert rn.superblocks is not None
    assert not rn.superblocks.empty
    assert 'geometry' in rn.superblocks.columns
