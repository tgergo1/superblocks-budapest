from pyrosm import OSM
from pyrosm import get_data
from collections import Counter
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import pandas as pd
matplotlib.use('Agg')

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

# Create a sorted list of all unique capacity values
capacity_values = edges["capacity"].sort_values(ascending=False)

# Create a set of the top 10 capacity values
most_common_capacity_values = Counter(capacity_values).most_common()[:19][0]

# Create a new column in the edges dataframe called "color" that is initially set to black
edges["color"] = "black"

# Set the color of the edges with capacity in the top 10 to red
edges.loc[edges["capacity"].isin(most_common_capacity_values), "color"] = "red"

# Define the size of the figure
figsizeside = 300

# Plot the road network, coloring the roads based on their capacity
fig, ax = plt.subplots(figsize=(figsizeside,figsizeside))
edges.plot(ax=ax, color=edges["color"])
#nodes.plot(ax=ax, color="red", markersize=1)

# Save the plot to an image file
fig.savefig("output.png")