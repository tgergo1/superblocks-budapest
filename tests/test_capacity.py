import geopandas as gpd
from shapely.geometry import LineString

from superblocks.capacity import estimate_capacity
from superblocks.config import PipelineConfig
from superblocks.blocks import build_blocks


def _sample_internal_streets():
    lines = [
        LineString([(0, 0), (2, 0)]),
        LineString([(2, 0), (2, 2)]),
        LineString([(2, 2), (0, 2)]),
        LineString([(0, 2), (0, 0)]),
        LineString([(0, 1), (2, 1)]),
        LineString([(1, 0), (1, 2)]),
    ]
    return gpd.GeoDataFrame({"geometry": lines}, crs="EPSG:4326")


def test_estimate_capacity_adds_numeric_column():
    edges = gpd.GeoDataFrame(
        {
            "geometry": [
                LineString([(0, 0), (1, 0)]),
                LineString([(1, 0), (1, 1)]),
            ],
            "lanes": ["2", "3;2"],
            "maxspeed": ["50 km/h", "60"],
            "width": ["7.0", None],
        },
        crs="EPSG:4326",
    )
    config = PipelineConfig()
    enriched = estimate_capacity(edges, config)
    assert "capacity" in enriched.columns
    assert not enriched["capacity"].isna().any()
    assert (enriched["capacity"] > 0).all()


def test_build_blocks_returns_polygons():
    streets = _sample_internal_streets()
    config = PipelineConfig()
    blocks = build_blocks(streets, config)
    assert not blocks.empty
    assert "geometry" in blocks.columns
