# src/main.py

from road_network import RoadNetwork
import logging

def main():
    # Initialize RoadNetwork for Budapest
    place_name = 'Budapest, Hungary'
    network = RoadNetwork(place_name)

    # Step 1: Download Complete Street Network
    network.download_street_network()

    # Step 2: Classify Streets into Boundary and Internal Streets Based on Capacity
    network.classify_streets()

    # Step 3: Visualize Streets for Verification
    network.visualize_streets(output_file='budapest_streets.html')

    # Step 4: Create Block Polygons
    network.create_block_polygons()

    # Step 5: Visualize Blocks for Verification
    network.visualize_blocks(output_file='budapest_blocks.html')

    # Step 6: Assign Blocks to Superblocks
    network.assign_blocks_to_superblocks()

    # Step 7: Visualize Superblocks
    network.visualize_superblocks(output_file='budapest_superblocks_map.html')

    # Step 8: Save Superblocks to GeoJSON
    network.save_superblocks_geojson(output_file='budapest_superblocks.geojson')

    # Step 9: Save Street Network Graph
    network.save_graph(output_file='budapest_street_network.graphml')

    logging.info("Superblock identification process completed successfully.")

if __name__ == '__main__':
    main()
