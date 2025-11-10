"""
Example: Complete Superblock Analysis with Access Control

This example demonstrates how to use the superblock toolkit to:
1. Analyze a city's street network
2. Identify superblock boundaries
3. Calculate optimal street directions to prevent through-traffic
4. Place modal filters strategically
5. Generate comprehensive visualizations and reports
"""

from superblocks.config import PipelineConfig
from superblocks.pipeline import SuperblockPipeline

# Configure the analysis
config = PipelineConfig(
    place_name="Budapest, Hungary",  # Can be any city/area recognized by OpenStreetMap
    output_dir="outputs",
    
    # Street classification thresholds (higher = more selective)
    boundary_capacity_quantile=0.65,  # Top 35% of streets become boundaries
    
    # Superblock sizing
    superblock_min_area_m2=5000.0,  # Minimum superblock size in square meters
    
    # Visualization
    folium_zoom_start=12,
    tile_export_num_tiles=4,  # For high-resolution exports
)

# Create and run the pipeline
print("Starting superblock analysis...")
pipeline = SuperblockPipeline(config)

# Option 1: Run everything at once (recommended)
pipeline.run_full_pipeline()

# Option 2: Step-by-step execution for more control
"""
pipeline.download()
print(f"Downloaded {len(pipeline.state.edges)} street segments")

pipeline.enrich_edges()
print("Enriched streets with capacity estimates")

pipeline.classify()
print(f"Classified {len(pipeline.state.boundary_streets)} boundary streets")
print(f"Identified {len(pipeline.state.internal_streets)} internal streets")

pipeline.build_blocks()
print(f"Created {len(pipeline.state.blocks)} blocks")

pipeline.build_superblocks()
print(f"Constructed {len(pipeline.state.superblocks)} superblocks")

pipeline.assign_blocks()
print("Assigned blocks to superblocks")

# NEW: Calculate access control
pipeline.calculate_access_control()
print("Calculated optimal street directions and modal filter locations")

# Access the results
if pipeline.state.internal_streets_with_directions is not None:
    oneway_count = (pipeline.state.internal_streets_with_directions['oneway'] == True).sum()
    total = len(pipeline.state.internal_streets_with_directions)
    print(f"  {oneway_count} of {total} internal streets are one-way ({100*oneway_count/total:.1f}%)")

if pipeline.state.modal_filters is not None:
    print(f"  {len(pipeline.state.modal_filters)} modal filter locations identified")

if pipeline.state.permeability_metrics is not None:
    avg_permeability = pipeline.state.permeability_metrics['permeability_score'].mean()
    print(f"  Average permeability score: {avg_permeability:.2f} (lower is better)")

# Export all results
pipeline.export_maps()
pipeline.export_geojson()
pipeline.export_graph()
pipeline.export_access_control()  # NEW: Export direction and filter data
pipeline.export_reports()
"""

print("\n✅ Analysis complete!")
print("\nGenerated files in 'outputs/' directory:")
print("  - budapest_superblocks_map.html (interactive map with all layers)")
print("  - budapest_street_directions.geojson (streets with direction info)")
print("  - budapest_modal_filters.geojson (filter locations)")
print("  - budapest_permeability_metrics.json (accessibility metrics)")
print("  - budapest_superblocks_metrics.json (comprehensive metrics)")
print("  - budapest_superblocks_report.md (analysis report)")

# Access specific results for further analysis
print("\n📊 Quick Statistics:")
print(f"Total superblocks: {len(pipeline.state.superblocks)}")

if pipeline.state.internal_streets_with_directions is not None:
    oneway = (pipeline.state.internal_streets_with_directions['oneway'] == True).sum()
    total = len(pipeline.state.internal_streets_with_directions)
    print(f"One-way streets: {oneway}/{total} ({100*oneway/total:.1f}%)")

if pipeline.state.modal_filters is not None:
    print(f"Modal filters: {len(pipeline.state.modal_filters)}")

if pipeline.state.permeability_metrics is not None:
    avg_perm = pipeline.state.permeability_metrics['permeability_score'].mean()
    print(f"Average permeability: {avg_perm:.2f} (target: <0.5)")

print("\n🗺️  Open 'outputs/budapest_superblocks_map.html' to explore the interactive map!")
