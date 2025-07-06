# Proposed Tasks

The following tasks capture features and improvements that are referenced in the repository but are not yet implemented or complete.

1. **Integrate Real-Time Traffic Data**
   - Extend the project to pull real-world traffic volumes from an external API.
   - Update the road network graph with this data and adjust capacity calculations accordingly.
   - Provide configuration for API keys and document usage.

2. **Optimize Superblock Boundaries**
   - Develop algorithms to refine superblock polygons for better accessibility and connectivity.
   - Consider pedestrian and cycling routes when adjusting boundaries.
   - Expose parameters so users can tune optimization goals.

3. **Run Comprehensive Traffic Simulations**
   - Implement simulation modules to quantify environmental and social impacts of proposed superblocks.
   - Incorporate metrics such as congestion, emissions, and travel times.
   - Present results through reports or interactive visualizations.

4. **Utilize Modularity-Based Superblock Detection**
   - Connect `compute_superblocks_by_modularity` from `superblock_algorithms.py` into the main `RoadNetwork` workflow.
   - Create a method similar to `cluster_superblocks` that invokes the modularity approach.
   - Add tests covering this new method.

5. **High‑Resolution Map Tiling**
   - Activate the unused `num_tiles` parameter in `wireframe_test.py` to export large maps by stitching tiles.
   - Document the feature and ensure existing scripts can opt into tile-based exports.

6. **Improve Test Environment Setup**
   - Simplify running tests by mocking heavy dependencies like `geopandas` or providing lightweight fixtures.
   - Update CI configuration to install required packages so `pytest` succeeds.


