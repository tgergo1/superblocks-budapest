# Access Control and Traffic Flow Optimization

This document describes the access control algorithms implemented in the superblocks toolkit. These algorithms calculate optimal street direction changes and modal filter placements to prevent through-traffic while maintaining local access.

## Overview

The goal of access control in superblocks is to achieve:
- **High accessibility**: Residents and visitors can reach any destination within the superblock
- **Low permeability**: Through-traffic is prevented – you can go into and out of a superblock, but not through it

This is accomplished through:
1. **One-way street configurations**: Strategic conversion of two-way streets to one-way
2. **Modal filters**: Physical barriers that allow pedestrians and cyclists but block motor vehicles

## Algorithm Components

### 1. Street Direction Optimization

**Location**: `src/superblocks/access_control.py::calculate_street_directions()`

This algorithm analyzes internal streets within each superblock and determines optimal one-way configurations.

#### Methodology

1. **Identify internal streets**: Find all streets within each superblock polygon
2. **Calculate capacity threshold**: Determine which streets are candidates for one-way conversion
   - Streets below the 40th percentile of capacity are preferred candidates
   - This targets narrow, low-traffic streets
3. **Apply directional heuristics**:
   - Streets already one-way in OSM data remain unchanged
   - For east-west streets: prefer eastward direction
   - For north-south streets: prefer northward direction
   - This creates a consistent flow pattern reducing confusion
4. **Ensure connectivity**: Verify that all areas remain accessible

#### Output

Each internal street receives:
- `oneway` (boolean): Whether the street is one-way
- `direction` (string): 'forward', 'reverse', or 'both'
- `access_control` (string): 'oneway' or 'open'

### 2. Modal Filter Placement

**Location**: `src/superblocks/access_control.py::identify_modal_filters()`

Modal filters are physical interventions that prevent motor vehicle through-traffic while allowing pedestrians and cyclists to pass freely.

#### Methodology

1. **Identify candidate streets**: Look for longer internal streets (> 50m) that could serve as through-routes
2. **Prioritize by capacity**: Target streets in the upper 60th percentile of internal street capacity
3. **Place filters strategically**: Position filters at the midpoint of candidate streets to break long through-routes

#### Filter Types

Current implementation places `modal_filter` type barriers, which typically include:
- Planters with trees or shrubs
- Decorative bollards
- Street furniture
- Small plazas

#### Output

Each modal filter location includes:
- `geometry` (Point): Geographic location
- `filter_type`: Type of intervention
- `street_name`: Name of affected street
- `superblock_id`: Associated superblock
- `reason`: Justification for placement

### 3. Permeability Analysis

**Location**: `src/superblocks/access_control.py::analyze_permeability()`

This function quantifies how well each superblock achieves the goal of high accessibility with low permeability.

#### Metrics

For each superblock:

1. **Total internal streets**: Count of all internal street segments
2. **One-way vs two-way counts**: Distribution of street types
3. **Permeability score** (0-1, lower is better):
   - Formula: `twoway_streets / total_internal_streets`
   - Measures ease of through-traffic
   - Lower scores indicate better through-traffic prevention
4. **Accessibility score** (0-1, higher is better):
   - Currently binary (1 if any streets exist, 0 otherwise)
   - Future versions could measure graph connectivity

#### Interpretation

Ideal superblocks have:
- Permeability score < 0.5 (most streets are one-way)
- Accessibility score = 1.0 (all areas remain reachable)

## Integration with Pipeline

The access control module integrates into the main pipeline through `SuperblockPipeline.calculate_access_control()`:

```python
def calculate_access_control(self) -> None:
    """Calculate street directions and modal filter placements."""
    edges = self._require_edges(with_capacity=True)
    superblocks = self._require_superblocks()
    boundary = self._require_boundary_streets()
    internal = self._require_internal_streets()
    
    # Calculate optimal street directions
    internal_with_directions = calculate_street_directions(
        edges, superblocks, boundary, internal, self.config
    )
    
    # Identify modal filter locations
    modal_filters = identify_modal_filters(
        internal_with_directions, superblocks, self.config
    )
    
    # Analyze permeability
    permeability = analyze_permeability(
        internal_with_directions, superblocks, boundary
    )
```

This is called automatically as part of `run_full_pipeline()`.

## Visualization

The results are visualized in the interactive map with:

### Street Directions Layer
- Blue polylines with directional arrows
- `>` indicates one-way direction
- `<>` indicates two-way street
- Tooltips show street metadata

### Modal Filters Layer
- Red circle markers at filter locations
- Tooltips show street name and reason for placement
- Displayed by default for easy identification

## Exported Data

Three new output files are generated:

1. **`budapest_street_directions.geojson`**
   - All internal streets with direction attributes
   - Fields: `oneway`, `direction`, `access_control`, plus original OSM attributes

2. **`budapest_modal_filters.geojson`**
   - Point locations of suggested modal filters
   - Fields: `filter_type`, `street_name`, `superblock_id`, `reason`

3. **`budapest_permeability_metrics.json`**
   - JSON array of metrics per superblock
   - Fields: `superblock_id`, `total_internal_streets`, `oneway_streets`, `twoway_streets`, `permeability_score`, `accessibility_score`

## Scientific Basis

The access control algorithms are based on established superblock design principles:

### Barcelona Superblocks (BCNecologia)
- Interior streets become "slow zones" (10-20 km/h speed limits)
- Through-traffic is eliminated via one-way systems and filters
- Perimeter arterials handle strategic traffic movement

### London Low Traffic Neighborhoods (LTNs)
- Modal filters prevent rat-running while maintaining access
- Emergency vehicle access is preserved
- Cycling and walking are prioritized

### Research Evidence
- Eliminates 60-75% of through-traffic in interior zones (Eggimann, 2022)
- Reduces NOx by 25-40% on interior streets (Mueller et al., 2020)
- Increases pedestrian activity by 30-50% (Nieuwenhuijsen, 2020)

## Future Enhancements

Planned improvements include:

1. **Emergency access optimization**: Ensure emergency vehicles can reach all points
2. **Network flow analysis**: Use graph algorithms to optimize overall connectivity
3. **Traffic simulation**: Model expected traffic redistribution
4. **Stakeholder input**: Allow manual override of automated decisions
5. **Delivery zones**: Identify areas needing goods vehicle access

## References

- Mueller, N. et al. (2020). "Changing the urban design of cities for health: The superblock model." Environment International.
- Eggimann, S. (2022). "The potential of implementing superblocks for multifunctional street use in cities." npj Urban Sustainability.
- Nieuwenhuijsen, M. J. (2020). "Urban and transport planning pathways to carbon neutral, liveable and healthy cities." Environment International.
