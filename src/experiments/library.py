import os
import pickle
from collections import Counter
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
from pyrosm import OSM, get_data
from mpl_toolkits.basemap import Basemap


class RoadNetwork:
    def __init__(self, city_name, directory="."):
        """
        Initializes the RoadNetwork object by loading OSM data for the specified city.

        Parameters:
            city_name (str): Name of the city for which to load the road network data.
            directory (str): Directory to store the OSM data.
        """
        self.city_name = city_name
        self.directory = directory
        self.data = get_data(city_name, directory=directory)
        self.osm = OSM(self.data)
        self.edges = None

    def calculate_capacity(self, lane_width=0.75, default_lanes=2, default_maxspeed=50, default_width=3.5):
        """
        Calculates the capacity of each road segment in the network.

        Parameters:
            lane_width (float): Width of a single lane (default: 0.75).
            default_lanes (int): Default number of lanes if missing (default: 2).
            default_maxspeed (int): Default speed limit if missing (default: 50).
            default_width (float): Default width of the road if missing (default: 3.5).
        """
        if self.edges is None:
            self.edges = self.osm.get_network(network_type="driving")

        # Convert to numeric and handle missing values
        self.edges["lanes"] = pd.to_numeric(self.edges["lanes"], errors="coerce").fillna(default_lanes)
        self.edges["maxspeed"] = pd.to_numeric(self.edges["maxspeed"], errors="coerce").fillna(default_maxspeed)
        self.edges["width"] = pd.to_numeric(self.edges["width"], errors="coerce").fillna(default_width)

        # Calculate capacity with progress bar
        capacities = []
        for _, row in tqdm(self.edges.iterrows(), total=len(self.edges), desc="Calculating capacities"):
            capacity = round((row["width"] - 2 * lane_width) * row["lanes"] * row["maxspeed"] / 1000, 1)
            capacities.append(capacity)
        self.edges["capacity"] = capacities

    def color_by_capacity(self, top_n=10):
        """
        Assigns colors to road segments based on their capacity.

        Parameters:
            top_n (int): Number of top capacities to consider for coloring (default: 10).
        """
        if self.edges is None:
            raise ValueError("Capacity must be calculated before coloring.")

        # Identify top N capacities and assign colors
        capacity_counts = Counter(self.edges["capacity"])
        most_common_capacity_keys = [k for k, _ in capacity_counts.most_common(top_n)]
        most_common_capacity_keys.sort(reverse=True)

        self.edges["color"] = "black"
        for idx, row in tqdm(self.edges.iterrows(), total=self.edges.shape[0], desc="Assigning colors"):
            if row["capacity"] in most_common_capacity_keys:
                capacity_index = most_common_capacity_keys.index(row["capacity"])
                red_value = 255 * (capacity_index / top_n)
                green_value = 255 - red_value
                self.edges.at[idx, "color"] = f'#{round(red_value):02X}{round(green_value):02X}00'

    def plot(self, size=(10, 10), edge_color='color', save=True, ext="png", dpi=100, linewidth=0.5, **kwargs):
        """
        Plots the road network using the assigned colors.

        Parameters:
            size (tuple): Size of the plot (default: (10, 10)).
            edge_color (str): Column name to use for coloring edges (default: 'color').
            save (bool): Whether to save the plot to a file (default: True).
            ext (str): File extension for saving the plot (default: "png").
            dpi (int): Resolution of the saved plot (default: 100).
            linewidth (float): Line width for plotting roads (default: 0.5).
        """
        if self.edges is None:
            raise ValueError("Edges must be colored before plotting.")

        print("Initializing plot...")
        fig, ax = plt.subplots(figsize=size, dpi=dpi)
        x_min, y_min, x_max, y_max = self.edges.total_bounds
        m = Basemap(
            projection='merc',
            llcrnrlat=y_min, urcrnrlat=y_max,
            llcrnrlon=x_min, urcrnrlon=x_max,
            resolution='i', ax=ax
        )

        print("Drawing road segments...")
        for _, row in tqdm(self.edges.iterrows(), total=self.edges.shape[0], desc="Plotting roads"):
            if row['geometry'].geom_type == 'LineString':
                x_coords, y_coords = np.array(row['geometry'].coords).T
                m.plot(x_coords, y_coords, '-', color=row[edge_color], latlon=True, linewidth=linewidth)
            elif row['geometry'].geom_type == 'MultiLineString':
                for line_string in row['geometry'].geoms:
                    x_coords, y_coords = np.array(line_string.coords).T
                    m.plot(x_coords, y_coords, '-', color=row[edge_color], latlon=True, linewidth=linewidth)

        plt.axis('off')
        if save:
            print(f"Saving plot to {self.city_name}.{ext}...")
            plt.savefig(f"{self.city_name}.{ext}", format=ext, dpi=dpi, bbox_inches='tight', pad_inches=0)
        else:
            plt.show()

    def save(self, filepath=None):
        """
        Serializes the RoadNetwork object to a file.

        Parameters:
            filepath (str): Path to save the serialized object. Defaults to "<city_name>.save".
        """
        if filepath is None:
            filepath = f"{self.city_name}.save"
        print(f"Saving object to {filepath}...")
        with open(filepath, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(filepath):
        """
        Deserializes a RoadNetwork object from a file.

        Parameters:
            filepath (str): Path to the file containing the serialized object.

        Returns:
            RoadNetwork: The deserialized RoadNetwork object.
        """
        if not os.path.isfile(filepath):
            raise ValueError(f"The file {filepath} does not exist.")
        print(f"Loading object from {filepath}...")
        with open(filepath, "rb") as f:
            return pickle.load(f)


if __name__ == "__main__":
    # Initialize a RoadNetwork object for New York City
    budapest = RoadNetwork("budapest")

    # Calculate the capacity of each road segment
    budapest.calculate_capacity()

    # Color the road segments by their capacity
    budapest.color_by_capacity()

    # Plot the network and save the image
    budapest.plot(size=(20, 20), edge_color="color", save=True, dpi=300, linewidth=0.1, ext="svg")

    # Save the object for later use
    #budapest.save()

    # Load the object from a file
    #loaded_network = RoadNetwork.load("budapest.save")
