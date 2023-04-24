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
        print("Plotting the road network...")
        if self.edges is None:
            self.color_by_capacity()

        fig, ax = plt.subplots(figsize=size, dpi=dpi)

        x_min, y_min, x_max, y_max = self.edges.total_bounds
        m = Basemap(
            projection='merc',
            llcrnrlat=y_min,
            urcrnrlat=y_max,
            llcrnrlon=x_min,
            urcrnrlon=x_max,
            resolution='i',  # or 'i' for intermediate resolution
            ax=ax
        )

        for idx, row in self.edges.iterrows():
            if row['geometry'].geom_type == 'LineString':
                x_coords, y_coords = np.array(row['geometry'].coords).T
                m.plot(x_coords, y_coords, '-', color=row['color'], latlon=True, ax=ax, linewidth=linewidth)
            elif row['geometry'].geom_type == 'MultiLineString':
                for line_string in row['geometry'].geoms:
                    x_coords, y_coords = np.array(line_string.coords).T
                    m.plot(x_coords, y_coords, '-', color=row['color'], latlon=True, ax=ax, linewidth=linewidth)

        plt.axis('off')

        if save:
            filename = str(self.city_name) + "." + str(ext)
            plt.savefig(filename, format=ext, dpi=dpi, bbox_inches='tight', pad_inches=0)
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


# Initialize a RoadNetwork object for the city of Boston
#new_york = RoadNetwork("new_york")

new_york = RoadNetwork("new_york","../../res")

# Calculate the capacity of each road segment in the network
new_york.calculate_capacity()

# Color the road segments by their capacity and plot the network
new_york.color_by_capacity()

#new_york.serialize()

#new_york.deserialize()

#with open("new_york_colors.pickle", "rb") as f:
#    colors = pickle.load(f)
#    new_york.edges["color"] = colors
new_york.plot(size=(20, 20), edge_color="color", save=True, dpi=300, num_tiles=4, linewidth=0.1, ext="svg")


