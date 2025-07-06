import sys
import types
import os
sys.path.append('src')
import geopandas as gpd
from shapely.geometry import LineString
import matplotlib.pyplot as plt

# Stub Basemap which is not available in test environment
basemap_mod = types.ModuleType("mpl_toolkits.basemap")
class _Basemap:
    def __init__(self, *args, **kwargs):
        self.ax = kwargs.get("ax")
    def plot(self, *args, **kwargs):
        pass
basemap_mod.Basemap = _Basemap
sys.modules.setdefault("mpl_toolkits.basemap", basemap_mod)

# Stub pyrosm to avoid heavy dependency
pyrosm_stub = types.ModuleType("pyrosm")
class _OSM:
    def __init__(self, *args, **kwargs):
        pass
    def get_network(self, *args, **kwargs):
        return gpd.GeoDataFrame()
pyrosm_stub.OSM = _OSM
pyrosm_stub.get_data = lambda *args, **kwargs: None
sys.modules["pyrosm"] = pyrosm_stub

# Ensure real matplotlib modules in case other tests inserted stubs
import importlib
sys.modules.pop("matplotlib", None)
sys.modules.pop("matplotlib.pyplot", None)
sys.modules["matplotlib"] = importlib.import_module("matplotlib")
sys.modules["matplotlib.pyplot"] = importlib.import_module("matplotlib.pyplot")

import pathlib
source = pathlib.Path("src/experiments/wireframe_test.py").read_text()
source = source.split("budapest =", 1)[0]
module = types.ModuleType("wireframe_test")
exec(source, module.__dict__)
RoadNetwork = module.RoadNetwork


def test_num_tiles_creates_image(tmp_path):
    rn = RoadNetwork("tile_test")
    rn.edges = gpd.GeoDataFrame(
        {"geometry": [LineString([(0, 0), (1, 1)])], "color": ["black"]},
        geometry="geometry",
    )
    os.chdir(tmp_path)
    rn.plot(size=(2, 2), dpi=50, num_tiles=2, save=True, ext="png")
    assert (tmp_path / "tile_test.png").exists()
