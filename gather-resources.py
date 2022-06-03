from pyrosm import OSM
from pyrosm import get_data

budapest_data = get_data("Budapest", directory="res")
print("Data was downloaded to:", budapest_data)

osm = OSM(budapest_data)
print("Type of 'osm' instance: ", type(osm))

nodes, edges = osm.get_network(nodes=True, network_type="driving")

figsizeside = 150

ax = edges.plot(figsize=(figsizeside,figsizeside), color="gray")
ax = nodes.plot(ax=ax, color="red", markersize=2.5)

fig = ax.get_figure()
fig.savefig("output.png")