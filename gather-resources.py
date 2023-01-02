from pyrosm import OSM
from pyrosm import get_data

import matplotlib.pyplot as plt
from matplotlib.colors import Normalize

import pandas as pd
import plotly.express as px
import pandas as pd
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from matplotlib import rcParams

from shapely.geometry import LineString

budapest_data = get_data("Budapest", update=True, directory="res")
osm = OSM(budapest_data)
edges = osm.get_network(network_type="driving")

# Convert the "lanes" and "maxspeed" attributes to numeric values
edges["lanes"] = pd.to_numeric(edges["lanes"], errors="coerce")
edges["maxspeed"] = pd.to_numeric(edges["maxspeed"], errors="coerce")

# Filter the data to only include major roads with at least 2 lanes
#edges = edges[(edges["highway"] == "motorway") | (edges["highway"] == "trunk") | (edges["highway"] == "primary")]
#edges = edges[edges["lanes"] >= 2]

edges["lanes"].fillna(1, inplace=True)
edges["maxspeed"].fillna(50, inplace=True)


# Estimate the capacity of each road based on the number of lanes and the maximum speed
edges["capacity"] = edges["lanes"] * edges["maxspeed"]

# Create a color map to visualize the capacity of the roads
# Set the colors of the roads based on their capacity
colors = ["black" if pd.isnull(c) else "red" if c < edges["capacity"].quantile(0.25) else "yellow" if c < edges["capacity"].quantile(0.5) else "green" for c in edges["capacity"]]

# Define the size of the figure
figsizeside = 200

# Plot the road network, coloring the roads based on their capacity
fig, ax = plt.subplots(figsize=(figsizeside,figsizeside))
edges.plot(ax=ax, color=colors)
#nodes.plot(ax=ax, color="red", markersize=1)

# Save the plot to an image file
fig.savefig("output.png")