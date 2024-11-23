import requests
import osmnx as ox
import networkx as nx
import folium
import matplotlib.colors as mcolors
import matplotlib.cm as cm

# Step 1: Download the car traffic network from OSM for a given city
def download_osm_network(city_name):
    # Download the road network for the given city
    graph = ox.graph_from_place(city_name, network_type='drive')
    return graph

# Step 2: Fetch real-time traffic data from OpenWeatherMap API
def fetch_real_time_traffic_data(lat, lon, api_key):
    url = f"http://api.openweathermap.org/data/2.5/traffic?lat={lat}&lon={lon}&appid={api_key}"
    response = requests.get(url)
    traffic_data = response.json()
    return traffic_data

# Step 3: Update the graph with real-time traffic data
def update_graph_with_traffic_data(graph, traffic_data):
    for u, v, key, data in graph.edges(keys=True, data=True):
        # Assume data comes with a "speed" and "congestion" metric (simplified example)
        traffic_speed = data.get('speed', None)
        traffic_congestion = data.get('congestion', None)
        
        # Update edge data with traffic information if available
        if traffic_speed:
            data['real_time_speed'] = traffic_speed
        if traffic_congestion:
            data['congestion'] = traffic_congestion
    
    return graph

# Step 4: Calculate the capacity for each road segment
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

# Step 5: Visualize the real-time traffic data on a folium map
def visualize_real_time_traffic_folium(graph, city_name):
    # Get the geographic center of the city for map initialization
    centroid = ox.geocode(city_name)
    folium_map = folium.Map(location=centroid, zoom_start=12)
    
    # Prepare capacity and speed data for color scaling
    capacities = [data.get('capacity', 1) for u, v, key, data in graph.edges(keys=True, data=True)]
    speeds = [data.get('real_time_speed', 1) for u, v, key, data in graph.edges(keys=True, data=True)]
    
    # Normalize capacities and speeds for color mapping
    norm_capacity = mcolors.Normalize(vmin=min(capacities), vmax=max(capacities))
    norm_speed = mcolors.Normalize(vmin=min(speeds), vmax=max(speeds))
    
    cmap_capacity = cm.ScalarMappable(norm=norm_capacity, cmap='viridis')
    cmap_speed = cm.ScalarMappable(norm=norm_speed, cmap='coolwarm')

    for u, v, key, data in graph.edges(keys=True, data=True):
        coords = [(graph.nodes[u]['y'], graph.nodes[u]['x']), 
                  (graph.nodes[v]['y'], graph.nodes[v]['x'])]

        # Determine which color to use based on capacity or real-time speed
        capacity = data.get('capacity', 1)
        speed = data.get('real_time_speed', None)
        
        if speed:
            # Use the speed data to color the line
            color = mcolors.to_hex(cmap_speed.to_rgba(speed))
        else:
            # Fallback to using capacity if speed data is not available
            color = mcolors.to_hex(cmap_capacity.to_rgba(capacity))

        # Add the road segment to the folium map
        folium.PolyLine(coords, color=color, weight=5, opacity=0.7).add_to(folium_map)
    
    # Add color scales (legends) to the map
    folium_map.add_child(folium.map.LayerControl())
    
    return folium_map

# Main function to execute the steps
def main(city_name, api_key):
    graph = download_osm_network(city_name)
    graph = calculate_road_capacity(graph)
    
    # Get the center of the city for traffic data (latitude, longitude)
    centroid = ox.geocode(city_name)
    lat, lon = centroid[0], centroid[1]
    
    # Fetch real-time traffic data
    traffic_data = fetch_real_time_traffic_data(lat, lon, api_key)
    
    # Update the graph with real-time traffic data
    graph = update_graph_with_traffic_data(graph, traffic_data)
    
    # Visualize the updated graph
    folium_map = visualize_real_time_traffic_folium(graph, city_name)
    folium_map.save(f"{city_name}_real_time_traffic_map.html")

if __name__ == "__main__":
    city_name = "Budapest"  # Replace with any city
    api_key = "423f51fb7d86e4f59323488b23db65a4"  # Replace with your OpenWeatherMap API key
    main(city_name, api_key)
