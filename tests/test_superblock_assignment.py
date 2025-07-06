import sys
sys.path.append('src')

import geopandas as gpd
from shapely.geometry import LineString, Polygon
import types
import sys

ox_stub = types.ModuleType("osmnx")
sys.modules.setdefault("osmnx", ox_stub)

from road_network import RoadNetwork


def build_network():
    rn = RoadNetwork('test')
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
    rn.boundary_streets = gpd.GeoDataFrame({'geometry': lines}, crs='EPSG:4326')

    block_inside_0 = Polygon([(0.2, 0.2), (1.8, 0.2), (1.8, 1.8), (0.2, 1.8)])
    block_inside_1 = Polygon([(4.2, 0.2), (5.8, 0.2), (5.8, 1.8), (4.2, 1.8)])
    block_outside = Polygon([(3.7, 0.5), (3.9, 0.5), (3.9, 1.5), (3.7, 1.5)])
    rn.blocks = gpd.GeoDataFrame({'geometry': [block_inside_0, block_inside_1, block_outside]}, crs='EPSG:4326')
    return rn


def test_unassigned_block_gets_nearest_superblock():
    rn = build_network()
    rn.assign_blocks_to_superblocks()
    # The third block is outside but should be assigned to the nearest superblock (index 1)
    assert rn.blocks.loc[2, 'superblock_id'] == 1
