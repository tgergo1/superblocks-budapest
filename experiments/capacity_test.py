from pyrosm import OSM
from pyrosm import get_data
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import pandas as pd

budapest_data = get_data("Budapest", directory="res")
osm = OSM(budapest_data)
edges = osm.get_network(network_type="driving")

# Convert the "lanes", "maxspeed", and "width" attributes to numeric values
edges["lanes"] = pd.to_numeric(edges["lanes"], errors="coerce")
edges["maxspeed"] = pd.to_numeric(edges["maxspeed"], errors="coerce")
edges["width"] = pd.to_numeric(edges["width"], errors="coerce")

# Fill any missing values in the "lanes", "maxspeed", and "width" columns with default values
edges["lanes"].fillna(2, inplace=True)
edges["maxspeed"].fillna(50, inplace=True)
edges["width"].fillna(3.5, inplace=True)

lane_width = 0.75
edges["capacity"] = (edges["width"] - 2 * lane_width) * edges["lanes"] * edges["maxspeed"] / 1000
edges["color"] = ["black"] * len(edges)

# Define the color map
cmap = colors.LinearSegmentedColormap.from_list("capacity", ["red", "green"])

# Normalize the capacity values to the range [0, 1]
norm = colors.Normalize(vmin=edges["capacity"].min(), vmax=edges["capacity"].max())

# Map the capacity values to colors using the color map
edges["color"] = cmap(norm(edges["capacity"]))

# Convert the single color values to RGBA values
edges["color"] = [colors.to_rgba(c) for c in edges["color"]]

# Define the size of the figure
figsizeside = 200

# Plot the road network, coloring the roads based on their capacity
fig, ax = plt.subplots(figsize=(figsizeside,figsizeside))
edges.plot(ax=ax, color=edges["color"])
#nodes.plot(ax=ax, color="red", markersize=1)

# Save the plot to an image file
fig.savefig("output.png")
