# src/road_network.py

import os
import logging
import osmnx as ox
import networkx as nx
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import cascaded_union, polygonize
import folium
from branca.colormap import linear
import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RoadNetwork:
    def __init__(self, place_name, output_dir='outputs'):
        self.place_name = place_name
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.graph = None
        self.boundary_streets = None
        self.internal_streets = None
        self.blocks = None
        self.superblocks = None
        self.centroid = None

    def download_street_network(self):
        """
        Downloads the complete street network for the specified place using OSMnx.
        """
        logging.info(f"Downloading complete street network for {self.place_name}...")
        # Download the complete street network
        self.graph = ox.graph_from_place(
            self.place_name,
            network_type='drive'
        )
        logging.info(f"Downloaded street network with {len(self.graph.nodes)} nodes and {len(self.graph.edges)} edges.")

    def classify_streets(self):
        """
        Classify streets into boundary and internal streets based on highway types and calculated capacity.
        """
        logging.info("Classifying streets into boundary and internal streets based on capacity...")
        gdf_edges = ox.graph_to_gdfs(self.graph, nodes=False, edges=True)

        # Define major and minor street types
        major_street_types = ['motorway', 'trunk', 'primary', 'secondary']
        minor_street_types = ['tertiary', 'unclassified', 'residential', 'living_street', 'service', 'road', 
                              'secondary_link', 'primary_link', 'trunk_link', 'motorway_link']

        # Calculate road capacity for each street
        gdf_edges['capacity'] = self.calculate_road_capacity(gdf_edges)

        # Define capacity threshold (e.g., top 50% capacity as boundary streets)
        capacity_threshold = gdf_edges['capacity'].quantile(0.5)
        logging.info(f"Capacity threshold for boundary streets set at: {capacity_threshold:.2f}")

        # Separate boundary and internal streets
        # Boundary streets: Major street types AND capacity above threshold
        self.boundary_streets = gdf_edges[
            (gdf_edges['highway'].isin(major_street_types)) & 
            (gdf_edges['capacity'] >= capacity_threshold)
        ].copy()

        # Internal streets: Minor street types AND capacity below threshold
        self.internal_streets = gdf_edges[
            (gdf_edges['highway'].isin(minor_street_types)) & 
            (gdf_edges['capacity'] < capacity_threshold)
        ].copy()

        logging.info(f"Classified streets: {len(self.boundary_streets)} boundary streets, {len(self.internal_streets)} internal streets.")

        # Buffer boundary streets slightly to ensure proper intersections
        self.boundary_streets = self.buffer_streets(self.boundary_streets, buffer_distance=0.0001)

    def calculate_road_capacity(self, gdf_edges):
        """
        Estimates road capacity based on number of lanes, lane width, and speed limit.
        Uses the Michigan Model as a basis for estimation.
        
        Formula:
        Capacity (C) = n * w * v * k
        Where:
        - n: Number of lanes
        - w: Lane width (assumed 3.5 meters)
        - v: Speed limit (km/h)
        - k: Constant (set to 1.0 for simplicity)
        """
        logging.info("Calculating road capacities using the Michigan Model...")

        # Define lane width and constant
        lane_width = 3.5  # meters
        k = 1.0  # constant

        # Handle missing or zero lanes
        gdf_edges['lanes'] = pd.to_numeric(gdf_edges['lanes'], errors='coerce').fillna(2)  # Default to 2 lanes
        gdf_edges['lanes'] = gdf_edges['lanes'].apply(lambda x: x if x > 0 else 2)

        # Handle missing maxspeed
        gdf_edges['maxspeed'] = pd.to_numeric(gdf_edges['maxspeed'], errors='coerce')
        gdf_edges['maxspeed'] = gdf_edges['maxspeed'].fillna(50)  # Default speed limit to 50 km/h

        # Calculate capacity
        gdf_edges['capacity'] = gdf_edges['lanes'] * lane_width * gdf_edges['maxspeed'] * k

        return gdf_edges['capacity']

    def buffer_streets(self, gdf, buffer_distance=0.0001):
        """
        Buffers streets to ensure proper intersection for polygonization.
        
        Parameters:
        - gdf (GeoDataFrame): GeoDataFrame of streets.
        - buffer_distance (float): Buffer distance in degrees.
        
        Returns:
        - GeoDataFrame with buffered geometries.
        """
        logging.info(f"Buffering streets by {buffer_distance} degrees to ensure intersections...")
        gdf['geometry'] = gdf['geometry'].buffer(buffer_distance)
        return gdf

    def visualize_streets(self, output_file='streets.html'):
        """
        Visualizes boundary and internal streets on an interactive map.
        """
        logging.info("Visualizing boundary and internal streets...")
        # Get centroid for map centering
        self.centroid = ox.geocode(self.place_name)
        m = folium.Map(location=[self.centroid[0], self.centroid[1]], zoom_start=12, tiles='cartodbpositron')

        # Add boundary streets in blue
        for _, row in self.boundary_streets.iterrows():
            geom = row['geometry']
            if geom.geom_type == 'LineString':
                folium.PolyLine(locations=[(lat, lon) for lon, lat in geom.coords],
                                color='blue', weight=2, opacity=0.7).add_to(m)
            elif geom.geom_type == 'MultiLineString':
                for line in geom.geoms:
                    folium.PolyLine(locations=[(lat, lon) for lon, lat in line.coords],
                                    color='blue', weight=2, opacity=0.7).add_to(m)

        # Add internal streets in grey
        for _, row in self.internal_streets.iterrows():
            geom = row['geometry']
            if geom.geom_type == 'LineString':
                folium.PolyLine(locations=[(lat, lon) for lon, lat in geom.coords],
                                color='grey', weight=1, opacity=0.5).add_to(m)
            elif geom.geom_type == 'MultiLineString':
                for line in geom.geoms:
                    folium.PolyLine(locations=[(lat, lon) for lon, lat in line.coords],
                                    color='grey', weight=1, opacity=0.5).add_to(m)

        # Save the map
        output_path = os.path.join(self.output_dir, output_file)
        m.save(output_path)
        logging.info(f"Streets map saved to {output_path}")

    def create_block_polygons(self):
        """
        Polygonizes internal streets to create individual block polygons.
        """
        logging.info("Creating block polygons from internal streets...")
        from shapely.ops import polygonize

        # Merge all internal streets into a single MultiLineString
        internal_union = self.internal_streets['geometry'].unary_union
        logging.info("Merged internal streets into a single geometry.")

        # Polygonize to get blocks
        polygons = list(polygonize(internal_union))
        logging.info(f"Polygonized internal streets into {len(polygons)} blocks.")

        # Convert to GeoDataFrame
        self.blocks = gpd.GeoDataFrame({'geometry': polygons}, crs='EPSG:4326')

        # Validate polygons
        self.blocks = self.validate_polygons(self.blocks)
        logging.info(f"Validated block polygons. Total valid blocks: {len(self.blocks)}")

    def validate_polygons(self, gdf):
        """
        Validates and fixes invalid polygons in a GeoDataFrame.
        """
        logging.info("Validating polygons...")
        from shapely.validation import explain_validity

        invalid = gdf[~gdf.is_valid]
        if not invalid.empty:
            logging.warning(f"Found {len(invalid)} invalid polygons. Attempting to fix...")
            gdf['geometry'] = gdf['geometry'].buffer(0)
            invalid_after = gdf[~gdf.is_valid]
            if not invalid_after.empty:
                logging.error(f"Could not fix {len(invalid_after)} polygons.")
                gdf = gdf[gdf.is_valid]
        else:
            logging.info("All polygons are valid.")
        return gdf

    def visualize_blocks(self, output_file='blocks.html'):
        """
        Visualizes block polygons on an interactive map.
        """
        logging.info("Visualizing block polygons...")
        m = folium.Map(location=[self.centroid[0], self.centroid[1]], zoom_start=14, tiles='cartodbpositron')

        # Add block polygons in purple
        for _, row in self.blocks.iterrows():
            folium.GeoJson(
                row['geometry'],
                style_function=lambda feature: {
                    'fillColor': 'purple',
                    'color': 'black',
                    'weight': 1,
                    'fillOpacity': 0.2,
                }
            ).add_to(m)

        # Save the map
        output_path = os.path.join(self.output_dir, output_file)
        m.save(output_path)
        logging.info(f"Block polygons map saved to {output_path}")

    def assign_blocks_to_superblocks(self):
        """
        Assigns each block to a superblock based on spatial containment within boundary streets.
        """
        logging.info("Assigning blocks to superblocks...")
        from geopandas.tools import sjoin

        # Create superblock polygons from boundary streets
        boundary_union = self.boundary_streets['geometry'].unary_union
        superblock_polygons = list(polygonize(boundary_union))
        self.superblocks = gpd.GeoDataFrame({'geometry': superblock_polygons}, crs='EPSG:4326')
        logging.info(f"Polygonized boundary streets into {len(self.superblocks)} superblock polygons.")

        # Validate superblock polygons
        self.superblocks = self.validate_polygons(self.superblocks)
        logging.info(f"Validated superblock polygons. Total valid superblocks: {len(self.superblocks)}")

        # Spatial join: assign each block to a superblock
        self.blocks = sjoin(self.blocks, self.superblocks, how='left', predicate='within')
        logging.info("Performed spatial join to assign blocks to superblocks.")

        # Handle blocks not within any superblock
        unassigned = self.blocks[self.blocks['index_right'].isnull()]
        if not unassigned.empty:
            logging.warning(f"{len(unassigned)} blocks were not assigned to any superblock.")
            # Assign to nearest superblock
            self.assign_unassigned_blocks(unassigned)
        else:
            logging.info("All blocks assigned to superblocks.")

        # Add superblock_id to blocks
        self.blocks['superblock_id'] = self.blocks['index_right'].fillna(0).astype(int)
        self.blocks = self.blocks.drop(columns=['index_right'])

        logging.info(f"Assigned blocks to superblocks. Total assigned blocks: {len(self.blocks)}")

    def assign_unassigned_blocks(self, unassigned):
        """
        Assigns blocks not within any superblock to the nearest superblock.
        """
        logging.info("Assigning unassigned blocks to the nearest superblock...")
        from shapely.ops import nearest_points

        for idx, block in unassigned.iterrows():
            # Compute distance to all superblocks
            distances = self.superblocks['geometry'].distance(block.geometry)
            nearest_superblock = distances.idxmin()
            self.blocks.at[idx, 'superblock_id'] = nearest_superblock
            logging.info(f"Assigned block {idx} to superblock {nearest_superblock}.")

        # Drop remaining unassigned blocks if any
        self.blocks = self.blocks.dropna(subset=['superblock_id'])
        logging.info(f"Total blocks after assignment: {len(self.blocks)}")

    def visualize_superblocks(self, output_file='superblocks.html'):
        """
        Visualizes superblock polygons on an interactive map.
        """
        logging.info("Visualizing superblock polygons...")
        m = folium.Map(location=[self.centroid[0], self.centroid[1]], zoom_start=12, tiles='cartodbpositron')

        # Define a color palette
        num_superblocks = len(self.superblocks)
        colormap = linear.Set1_09.scale(0, num_superblocks)
        colormap = colormap.to_step(num_superblocks)

        # Add superblock polygons with distinct colors
        for idx, row in self.superblocks.iterrows():
            folium.GeoJson(
                row['geometry'],
                style_function=lambda feature, color=colormap(idx): {
                    'fillColor': color,
                    'color': color,
                    'weight': 2,
                    'fillOpacity': 0.3,
                },
                tooltip=folium.Tooltip(f"Superblock ID: {idx}")
            ).add_to(m)

        # Add color map legend
        colormap.caption = 'Superblocks'
        colormap.add_to(m)

        # Save the map
        output_path = os.path.join(self.output_dir, output_file)
        m.save(output_path)
        logging.info(f"Superblocks map saved to {output_path}")

    def save_superblocks_geojson(self, output_file='superblocks.geojson'):
        """
        Saves the superblocks GeoDataFrame to a GeoJSON file.
        """
        logging.info("Saving superblocks to GeoJSON file...")
        if self.superblocks is None or self.superblocks.empty:
            logging.error("No superblocks to save. Please run assign_blocks_to_superblocks() first.")
            return

        output_path = os.path.join(self.output_dir, output_file)
        self.superblocks.to_file(output_path, driver='GeoJSON')
        logging.info(f"Superblocks GeoJSON saved to {output_path}")

    def save_graph(self, output_file='street_network.graphml'):
        """
        Saves the street network graph to a GraphML file.
        """
        logging.info("Saving street network graph to GraphML file...")
        output_path = os.path.join(self.output_dir, output_file)
        ox.save_graphml(self.graph, filepath=output_path)
        logging.info(f"GraphML file saved to {output_path}")
