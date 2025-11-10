import geopandas as gpd
from shapely.geometry import LineString

from superblocks.visualization.static import tiled_edge_plot


def test_num_tiles_creates_image(tmp_path):
    edges = gpd.GeoDataFrame(
        {
            "geometry": [
                LineString([(0, 0), (1, 1)]),
                LineString([(1, 1), (2, 0)]),
            ],
            "capacity": [1.0, 2.0],
        },
        crs="EPSG:4326",
    )

    output_path = tmp_path / "tile_test.png"
    tiled_edge_plot(
        edges,
        output_path,
        num_tiles=2,
        dpi=50,
        linewidth=0.5,
        color_column="capacity",
    )

    assert output_path.exists()
