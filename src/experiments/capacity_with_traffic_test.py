import osmnx as ox
import networkx as nx
import folium
from folium.plugins import HeatMap
import matplotlib.colors as mcolors
import matplotlib.cm as cm  # Correct import for colormaps
import requests

# Assuming you have a function to fetch real-time traffic data from an API
def fetch_real_time_traffic_data(city_name):
    # Example API call (Replace with your actual API call)
    # This is a dummy URL; you will need to use the actual traffic API
    traffic_data_url = f"https://api.trafficprovider.com/data?city={city_name}"
    
    # Make the API request
    response = requests.get(traffic_data_url)
    traffic_data = response.json()
    
    return traffic_data

# Update the graph with real-time traffic data
def update_graph_with_traffic_data(graph, traffic_data):
    for u, v, key, data in graph.edges(keys=True, data=True):
        # Match the road segment with traffic data (simplified example)
        # You need to properly match traffic data to OSM edges by coordinates or road IDs
        segment_id = data.get('osmid')
        traffic_info = traffic_data.get(segment_id, {})
        
        if traffic_info:
            # Update speed or add a new attribute like 'traffic_density'
            real_time_speed = traffic_info.get('speed', data.get('maxspeed', 50))
            data['real_time_speed'] = real_time_speed
            
            # Optionally adjust the capacity based on real-time speed
            base_capacity_per_lane = 2000
            lanes = data.get('lanes', 1)
            capacity = lanes * base_capacity_per_lane
            capacity_adjustment_factor = real_time_speed / data.get('maxspeed', 50)
            data['real_time_capacity'] = capacity * capacity_adjustment_factor
    
    return graph

# Step 4: Modify the visualization function to reflect real-time data
def visualize_real_time_traffic_folium(graph, city_name):
    centroid = ox.geocode(city_name)
    folium_map = folium.Map(location=centroid, zoom_start=12)
    
    capacities = [data.get('real_time_capacity', data['capacity']) for u, v, key, data in graph.edges(keys=True, data=True)]
    norm = mcolors.Normalize(vmin=min(capacities), vmax=max(capacities))
    cmap = cm.ScalarMappable(norm=norm, cmap='viridis')
    
    for u, v, key, data in graph.edges(keys=True, data=True):
        coords = [(graph.nodes[u]['y'], graph.nodes[u]['x']), 
                  (graph.nodes[v]['y'], graph.nodes[v]['x'])]
        capacity = data.get('real_time_capacity', data['capacity'])
        color = mcolors.to_hex(cmap.to_rgba(capacity))
        folium.PolyLine(coords, color=color, weight=5, opacity=0.7).add_to(folium_map)
    
    folium_map.add_child(folium.map.LayerControl())
    
    return folium_map

# Main function including real-time traffic data integration
def main_with_traffic(city_name):
    graph = download_osm_network(city_name)
    graph = calculate_road_capacity(graph)
    
    # Fetch real-time traffic data
    traffic_data = fetch_real_time_traffic_data(city_name)
    
    # Update graph with real-time traffic data
    graph = update_graph_with_traffic_data(graph, traffic_data)
    
    # Visualize the updated graph
    folium_map = visualize_real_time_traffic_folium(graph, city_name)
    folium_map.save(f"{city_name}_real_time_traffic_map.html")
    folium_map

# Step 1: Download the car traffic network from OSM for a given city
def download_osm_network(city_name):
    # Download the road network for the given city
    graph = ox.graph_from_place(city_name, network_type='drive')
    return graph

# Step 2: Calculate the capacity for each road segment
def calculate_road_capacity(graph):
    for u, v, key, data in graph.edges(keys=True, data=True):
        # Get road type, number of lanes, and speed limit
        road_type = data.get('highway', None)
        lanes = data.get('lanes', 1)  # Default to 1 lane if not provided
        speed = data.get('maxspeed', 50)  # Default to 50 km/h if not provided

        # Convert lanes and speed to integers if they are lists or strings
        if isinstance(lanes, list):
            lanes = int(lanes[0])
        elif isinstance(lanes, str):
            lanes = int(lanes)
        
        if isinstance(speed, list):
            speed = int(speed[0])
        elif isinstance(speed, str):
            speed = int(speed.split()[0])  # Handles cases like "50 km/h"

        # Simplified capacity calculation (vehicles per hour)
        # Capacity = lanes * base_capacity_per_lane (adjusted by road type and speed)
        base_capacity_per_lane = 2000  # standard vehicles per hour per lane
        capacity = lanes * base_capacity_per_lane

        # Adjust capacity by road type
        if road_type in ['motorway', 'trunk']:
            capacity *= 1.5
        elif road_type in ['primary', 'secondary']:
            capacity *= 1.2
        elif road_type in ['tertiary']:
            capacity *= 1.0
        elif road_type in ['residential']:
            capacity *= 0.8
        
        # Store the capacity in the edge data
        data['capacity'] = capacity

    return graph

# Step 3: Create an interactive folium map with road capacities
def visualize_road_capacity_folium(graph, city_name):
    # Get the geographic center of the city for the map initialization
    centroid = ox.geocode(city_name)
    folium_map = folium.Map(location=centroid, zoom_start=12)

    # Normalize the capacity values for color scaling
    capacities = [data['capacity'] for u, v, key, data in graph.edges(keys=True, data=True)]
    norm = mcolors.Normalize(vmin=min(capacities), vmax=max(capacities))
    cmap = cm.ScalarMappable(norm=norm, cmap='viridis')  # Correct usage of colormap

    for u, v, key, data in graph.edges(keys=True, data=True):
        # Get the coordinates of the road segment
        coords = [(graph.nodes[u]['y'], graph.nodes[u]['x']), 
                  (graph.nodes[v]['y'], graph.nodes[v]['x'])]

        # Get the capacity of the road segment
        capacity = data['capacity']

        # Convert capacity to a color
        color = mcolors.to_hex(cmap.to_rgba(capacity))

        # Add the road segment to the folium map
        folium.PolyLine(coords, color=color, weight=5, opacity=0.7).add_to(folium_map)

    # Add a color scale (legend) to the map
    folium_map.add_child(folium.map.LayerControl())
    
    return folium_map

# Main function to execute the steps
def main(city_name):
    graph = download_osm_network(city_name)
    graph = calculate_road_capacity(graph)
    folium_map = visualize_road_capacity_folium(graph, city_name)
    folium_map.save(f"{city_name}_road_capacity_map.html")
    folium_map

if __name__ == "__main__":
    city_name = "Budapest"  # Replace with any city
    main_with_traffic(city_name)
