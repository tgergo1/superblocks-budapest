from pyrosm import OSM
from pyrosm import get_data
from collections import Counter
import pandas as pd
import matplotlib.pyplot as plt
import pickle
import os
from tqdm import tqdm
import io
from PIL import Image
import numpy as np
from mpl_toolkits.basemap import Basemap



class RoadNetwork:
    def __init__(self, city_name, directory="."):
        self.city_name = city_name
        self.directory = directory
        self.data = get_data(city_name, directory=directory)
        self.osm = OSM(self.data)
        self.edges = None
        
    def calculate_capacity(self, lane_width=0.75, default_lanes=2, default_maxspeed=50, default_width=3.5):
        if self.edges is None:
            self.edges = self.osm.get_network(network_type="driving")
        self.edges["lanes"] = pd.to_numeric(self.edges["lanes"], errors="coerce")
        self.edges["maxspeed"] = pd.to_numeric(self.edges["maxspeed"], errors="coerce")
        self.edges["width"] = pd.to_numeric(self.edges["width"], errors="coerce")
        self.edges["lanes"].fillna(default_lanes, inplace=True)
        self.edges["maxspeed"].fillna(default_maxspeed, inplace=True)
        self.edges["width"].fillna(default_width, inplace=True)
        #self.edges["capacity"] = (self.edges["width"] - 2 * lane_width) * self.edges["lanes"] * self.edges["maxspeed"] / 1000
        #self.edges["capacity"] = self.edges["capacity"].round(1)

        # Use tqdm to add a progress bar to the loop over edges
        self.edges["capacity"] = [0.0] * len(self.edges)
        for i, edge in tqdm(self.edges.iterrows(), total=len(self.edges), desc="Calculating capacities"):
            capacity = (edge["width"] - 2 * lane_width) * edge["lanes"] * edge["maxspeed"] / 1000
            self.edges.at[i, "capacity"] = round(capacity, 1)
        
    def color_by_capacity(self, top_n=10):
        if self.edges is None:
            self.calculate_capacity()
        capacity_values = self.edges["capacity"].sort_values(ascending=False)
        most_common_capacity_keys = dict(Counter(capacity_values).most_common(top_n)).keys()
        most_common_capacity_values = dict(Counter(capacity_values).most_common(top_n)).values()
        most_common_capacity_keys = sorted(most_common_capacity_keys, reverse=True)
        self.edges["color"] = "black"
        for idx, edge in tqdm(self.edges.iterrows(), total=self.edges.shape[0], desc="Calculating colors"):
            if edge["capacity"] in most_common_capacity_keys:
                capacity_index = most_common_capacity_keys.index(edge["capacity"])
                red_value = 255*(capacity_index/top_n)
                green_value = 255-red_value
                self.edges.at[idx, "color"] = '#{:02X}{:02X}{:02X}'.format(round(red_value),round(green_value),0)
    
    def plot(self, size=(10, 10), edge_color='color', save=True, ext="png", dpi=100, num_tiles=1, linewidth=0.5, **kwargs):
        """Plot the road network colored by capacity.

        Parameters
        ----------
        size : tuple of int, optional
            Figure size ``(width, height)`` in inches. Defaults to ``(10, 10)``.
        edge_color : str, optional
            Column name or color value used to draw the road segments. By
            default the ``"color"`` column produced by :meth:`color_by_capacity`
            is used.
        save : bool, optional
            If ``True`` the figure is written to disk, otherwise it is shown
            interactively. Defaults to ``True``.
        ext : str, optional
            File extension for the saved figure. Defaults to ``"png"``.
        dpi : int, optional
            Resolution of the plot in dots per inch. Defaults to ``100``.
        num_tiles : int, optional
            Number of tiles used to split the map for higher resolution
            exports. When greater than ``1`` the map is rendered on a grid
            of tiles which are stitched together into a single image.
            Defaults to ``1``.
        linewidth : float, optional
            Width of the plotted road lines. Defaults to ``0.5``.
        **kwargs
            Additional keyword arguments passed to ``matplotlib`` plotting
            functions.
        """

        print("Plotting the road network...")
        if self.edges is None:
            self.color_by_capacity()

        x_min, y_min, x_max, y_max = self.edges.total_bounds
        width = x_max - x_min
        height = y_max - y_min

        if num_tiles <= 1:
            fig, axes = plt.subplots(figsize=size, dpi=dpi)
            axes = [axes]
            tile_bounds = [
                (x_min, x_max, y_min, y_max, axes[0])
            ]
        else:
            fig, axes = plt.subplots(
                num_tiles,
                num_tiles,
                figsize=(size[0] * num_tiles, size[1] * num_tiles),
                dpi=dpi,
            )
            tile_bounds = []
            for j in range(num_tiles):
                for i in range(num_tiles):
                    llx = x_min + i * width / num_tiles
                    urx = x_min + (i + 1) * width / num_tiles
                    lly = y_min + j * height / num_tiles
                    ury = y_min + (j + 1) * height / num_tiles
                    ax = axes[j][i]
                    tile_bounds.append((llx, urx, lly, ury, ax))

        for llx, urx, lly, ury, ax in tile_bounds:
            m = Basemap(
                projection="merc",
                llcrnrlat=lly,
                urcrnrlat=ury,
                llcrnrlon=llx,
                urcrnrlon=urx,
                resolution="i",
                ax=ax,
            )

            for _, row in self.edges.iterrows():
                geom = row["geometry"]
                if geom.geom_type == "LineString":
                    x_coords, y_coords = np.array(geom.coords).T
                    m.plot(
                        x_coords,
                        y_coords,
                        "-",
                        color=row[edge_color],
                        latlon=True,
                        ax=ax,
                        linewidth=linewidth,
                    )
                elif geom.geom_type == "MultiLineString":
                    for line_string in geom.geoms:
                        x_coords, y_coords = np.array(line_string.coords).T
                        m.plot(
                            x_coords,
                            y_coords,
                            "-",
                            color=row[edge_color],
                            latlon=True,
                            ax=ax,
                            linewidth=linewidth,
                        )
            ax.axis("off")

        plt.subplots_adjust(wspace=0, hspace=0)

        if save:
            filename = str(self.city_name) + "." + str(ext)
            plt.savefig(filename, format=ext, dpi=dpi, bbox_inches="tight", pad_inches=0)
        else:
            plt.show()



    def serialize(self):
        with open(self.city_name+".save", "wb") as f:
            pickle.dump(self, f)
            
    def deserialize(self):
        filename = self.city_name+".save"
        if os.path.isfile(filename):
            with open(filename, "rb") as f:
                self = pickle.load(f)
        else:
            raise ValueError("The file does not exist.")


if __name__ == "__main__":
    # Initialize a RoadNetwork object for the city of Budapest
    budapest = RoadNetwork("budapest")

    # Example usage for generating a high-resolution map
    budapest.calculate_capacity()
    budapest.color_by_capacity()

    # Export the map split across tiles and stitched together
    budapest.plot(
        size=(20, 20),
        edge_color="color",
        save=True,
        dpi=300,
        num_tiles=4,
        linewidth=0.1,
        ext="svg",
    )


