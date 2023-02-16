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
edges["capacity"] = edges["capacity"].round(1)

# Create a sorted list of all unique capacity values
capacity_values = edges["capacity"].sort_values(ascending=False)

top_n = 10

# Create a set of the top 10 capacity values
most_common_capacity_keys = dict(Counter(capacity_values).most_common(top_n)).keys()
most_common_capacity_values = dict(Counter(capacity_values).most_common(top_n)).values()
most_common_capacity_keys = sorted(most_common_capacity_keys, reverse=True)

# Create a new column in the edges dataframe called "color" that is initially set to black
edges["color"] = "black"

for idx, edge in edges.iterrows():
    if edge["capacity"] in most_common_capacity_keys:
        capacity_index = most_common_capacity_keys.index(edge["capacity"])
        red_value = 255*(capacity_index/top_n)
        green_value = 255-red_value
        #edge["color"] = '#{:02X}{:02X}{:02X}'.format(round(red_value),round(green_value),0)
        edges.at[idx, "color"] = '#{:02X}{:02X}{:02X}'.format(round(red_value),round(green_value),0)

# Define the size of the figure
figsizeside = 400

# Plot the road network, coloring the roads based on their capacity
fig, ax = plt.subplots(figsize=(figsizeside,figsizeside))
edges.plot(ax=ax, color=edges["color"])

# Save the plot to an image file
fig.savefig("edges.svg", format="svg")
fig.savefig("output.png")