from pyrosm import OSM, get_data
from collections import Counter
import pandas as pd
import matplotlib.pyplot as plt
import pickle
import os
import numpy as np
import matplotlib
import networkx as nx
import osmnx as ox
import momepy
import geopandas as gpd
from shapely.geometry import Polygon
import warnings
warnings.filterwarnings("ignore")  # Suppress warnings for cleaner output
matplotlib.use('Agg')  # Use non-interactive backend

class RoadNetwork:
    def __init__(self, city_name, directory="."):
        self.city_name = city_name
        self.directory = directory
        self.data = get_data(city_name, directory=directory)
        self.osm = OSM(self.data)
        self.edges = None
        self.nodes = None  # Initialize nodes attribute
        self.superblocks = None

    def calculate_capacity(self, lane_width=3.5, default_lanes=2, default_maxspeed=50):
        if self.edges is None or self.nodes is None:
            # Retrieve both edges and nodes, including extra attributes
            self.edges, self.nodes = self.osm.get_network(
                network_type="driving",
                nodes=True,
                extra_attributes=["lanes", "maxspeed", "width"]
            )
        # Ensure the necessary columns are present
        for col in ["lanes", "maxspeed", "width"]:
            if col not in self.edges.columns:
                self.edges[col] = None  # Add the column if it doesn't exist

        # Convert to numeric and handle missing values
        self.edges["lanes"] = pd.to_numeric(self.edges["lanes"], errors="coerce").fillna(default_lanes)
        self.edges["maxspeed"] = pd.to_numeric(self.edges["maxspeed"], errors="coerce").fillna(default_maxspeed)
        # Use default lane width if 'width' is not available
        self.edges["width"] = pd.to_numeric(self.edges["width"], errors="coerce")
        self.edges["width"].fillna(self.edges["lanes"] * lane_width, inplace=True)

        # Calculate capacity
        self.edges["capacity"] = self.edges["width"] * self.edges["maxspeed"] / 1000  # Simplified capacity formula
        self.edges["capacity"] = self.edges["capacity"].round(1)

    def color_by_capacity(self, top_n=10):
        if self.edges is None:
            self.calculate_capacity()
        capacity_values = self.edges["capacity"]
        most_common_capacity = capacity_values.value_counts().nlargest(top_n)
        most_common_capacity_keys = most_common_capacity.index.tolist()
        self.edges["color"] = "black"
        capacity_color_map = {}
        for idx, capacity in enumerate(sorted(most_common_capacity_keys)):
            capacity_index = idx
            red_value = 255 * (capacity_index / top_n)
            green_value = 255 - red_value
            color = '#{:02X}{:02X}{:02X}'.format(int(red_value), int(green_value), 0)
            capacity_color_map[capacity] = color
        self.edges['color'] = self.edges['capacity'].map(capacity_color_map)
        self.edges['color'].fillna('black', inplace=True)

    def plot(self, size=(10, 10), edge_color='color', save=True, ext="png", dpi=100, linewidth=0.5, **kwargs):
        print("Plotting the road network...")
        if self.edges is None:
            self.color_by_capacity()

        fig, ax = plt.subplots(figsize=size, dpi=dpi)
        self.edges.plot(ax=ax, color=self.edges[edge_color], linewidth=linewidth)
        plt.axis('off')

        if save:
            filename = f"{self.city_name}.{ext}"
            plt.savefig(filename, format=ext, dpi=dpi, bbox_inches='tight', pad_inches=0)
            plt.close(fig)
        else:
            plt.show()

    def identify_superblocks(self, percentile=0.90):
        """
        Identifies superblocks based on high-capacity roads.

        Args:
            percentile (float): The percentile of capacity to use as threshold (e.g., 0.90 for top 10%).
        """
        if self.edges is None or self.nodes is None:
            self.calculate_capacity()

        # Calculate capacity threshold based on the specified percentile
        capacity_threshold = self.edges['capacity'].quantile(percentile)
        print(f"Using capacity threshold at the {percentile * 100}% percentile: {capacity_threshold}")

        # Filter edges to only include high-capacity roads
        high_capacity_edges = self.edges[self.edges['capacity'] >= capacity_threshold]

        if high_capacity_edges.empty:
            raise ValueError("No edges meet the capacity threshold. Please adjust the percentile.")

        # Prepare nodes GeoDataFrame
        nodes = self.nodes.copy()
        nodes = nodes.set_index('id')

        # Extract 'x' and 'y' from geometry
        nodes['x'] = nodes.geometry.x
        nodes['y'] = nodes.geometry.y

        # Create the graph
        G = ox.graph_from_gdfs(nodes, high_capacity_edges, graph_attrs=None)
        G_un = G.to_undirected()

        # Convert graph to GeoDataFrame
        edges_gdf = ox.graph_to_gdfs(G_un, nodes=False, edges=True, node_geometry=False, fill_edge_geometry=True)

        # Simplify the edges to reduce complexity
        edges_gdf = edges_gdf[['geometry']].drop_duplicates().reset_index(drop=True)

        # Extract blocks (faces) using momepy
        try:
            blocks = momepy.Blocks(edges_gdf)
            self.superblocks = blocks.blocks
            print("Superblocks identified successfully.")
        except Exception as e:
            print(f"An error occurred while identifying superblocks: {e}")
            self.superblocks = None

    def plot_superblocks(self, size=(10, 10), save=True, ext="png", dpi=100, linewidth=0.5, **kwargs):
        """
        Plots the superblocks over the road network.

        Args:
            size (tuple): Figure size.
            save (bool): Whether to save the plot.
            ext (str): File extension for saving.
            dpi (int): Resolution of the plot.
        """
        if self.superblocks is None:
            raise ValueError("Superblocks have not been identified. Call identify_superblocks() first.")

        fig, ax = plt.subplots(figsize=size, dpi=dpi)
        self.edges.plot(ax=ax, color='gray', linewidth=linewidth)
        self.superblocks.boundary.plot(ax=ax, color='red', linewidth=1)
        plt.axis('off')

        if save:
            filename = f"{self.city_name}_superblocks.{ext}"
            plt.savefig(filename, format=ext, dpi=dpi, bbox_inches='tight', pad_inches=0)
            plt.close(fig)
        else:
            plt.show()

    def serialize(self):
        with open(f"{self.city_name}.save", "wb") as f:
            pickle.dump(self, f)

    def deserialize(self):
        filename = f"{self.city_name}.save"
        if os.path.isfile(filename):
            with open(filename, "rb") as f:
                self = pickle.load(f)
        else:
            raise ValueError("The file does not exist.")

if __name__ == "__main__":
    # Initialize a RoadNetwork object for Budapest
    budapest = RoadNetwork("Budapest", directory="res")

    # Calculate the capacity of each road segment
    budapest.calculate_capacity()

    # Print capacity statistics
    print("Capacity statistics:")
    print(budapest.edges['capacity'].describe())

    # Check for missing or zero capacities
    missing_capacities = budapest.edges[budapest.edges['capacity'].isna() | (budapest.edges['capacity'] == 0)]
    print(f"Number of edges with missing or zero capacity: {len(missing_capacities)}")

    # Color the road segments by their capacity and plot the network
    budapest.color_by_capacity()
    budapest.plot(size=(20, 20), edge_color="color", save=True, dpi=300, linewidth=0.1, ext="svg")

    # Identify superblocks using adaptive capacity threshold
    percentile = 0.90  # Use top 10% of capacities
    budapest.identify_superblocks(percentile=percentile)

    # Plot the superblocks over the road network
    budapest.plot_superblocks(size=(20, 20), save=True, dpi=300, linewidth=0.1, ext="png")
