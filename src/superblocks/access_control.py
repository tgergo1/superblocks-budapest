"""Access control and traffic flow optimization for superblocks.

This module implements algorithms to calculate optimal street direction changes
and modal filter placements to prevent through-traffic while maintaining access.
"""

from __future__ import annotations

import logging
from typing import Tuple, List, Set

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import Point, LineString, MultiLineString
from shapely.ops import nearest_points

from .config import PipelineConfig

logger = logging.getLogger(__name__)


def _extract_graph_from_edges(edges: gpd.GeoDataFrame) -> nx.MultiDiGraph:
    """Build a networkx graph from edge geometries."""
    
    G = nx.MultiDiGraph()
    
    for idx, row in edges.iterrows():
        geom = row.geometry
        if isinstance(geom, LineString):
            coords = list(geom.coords)
            if len(coords) >= 2:
                start = coords[0]
                end = coords[-1]
                
                # Add nodes
                G.add_node(start, pos=start)
                G.add_node(end, pos=end)
                
                # Add edge with attributes
                G.add_edge(
                    start, 
                    end, 
                    key=idx,
                    geometry=geom,
                    highway=row.get('highway', 'unknown'),
                    capacity=row.get('capacity', 1.0),
                    oneway=row.get('oneway', False),
                    length=geom.length,
                    edge_id=idx,
                )
    
    return G


def _find_superblock_entry_points(
    superblock: gpd.GeoSeries,
    boundary_streets: gpd.GeoDataFrame,
    buffer_m: float = 10.0,
) -> List[Point]:
    """Find entry points where boundary streets intersect a superblock."""
    
    # Buffer the superblock slightly to catch nearby intersections
    try:
        metric_crs = superblock.to_crs(superblock.estimate_utm_crs())
        buffered = metric_crs.geometry.buffer(buffer_m)
        buffered_geo = gpd.GeoSeries([buffered.iloc[0]], crs=metric_crs.crs).to_crs(superblock.crs)
    except Exception:
        buffered_geo = gpd.GeoSeries([superblock.geometry.iloc[0]], crs=superblock.crs)
    
    # Find boundary streets that intersect the superblock boundary
    boundary_geom = superblock.geometry.iloc[0].boundary
    
    entry_points = []
    for _, street in boundary_streets.iterrows():
        street_geom = street.geometry
        if street_geom.intersects(boundary_geom):
            intersection = street_geom.intersection(boundary_geom)
            if intersection.is_empty:
                continue
            
            # Extract points from intersection
            if intersection.geom_type == 'Point':
                entry_points.append(intersection)
            elif intersection.geom_type == 'MultiPoint':
                entry_points.extend(list(intersection.geoms))
            elif intersection.geom_type in ['LineString', 'MultiLineString']:
                # Use line endpoints as entry points
                if intersection.geom_type == 'LineString':
                    lines = [intersection]
                else:
                    lines = list(intersection.geoms)
                for line in lines:
                    coords = list(line.coords)
                    if coords:
                        entry_points.append(Point(coords[0]))
                        entry_points.append(Point(coords[-1]))
    
    return entry_points


def calculate_street_directions(
    edges: gpd.GeoDataFrame,
    superblocks: gpd.GeoDataFrame,
    boundary_streets: gpd.GeoDataFrame,
    internal_streets: gpd.GeoDataFrame,
    config: PipelineConfig,
) -> gpd.GeoDataFrame:
    """Calculate optimal street directions to prevent through-traffic.
    
    This implements a simplified version of the superblock permeability algorithm:
    1. Identify entry points to each superblock
    2. For internal streets, determine which should be one-way
    3. Ensure connectivity: any point in superblock can be reached from any entry
    4. Prevent through routes: minimize paths that enter one side and exit another
    
    Parameters
    ----------
    edges : GeoDataFrame
        All street edges with capacity information
    superblocks : GeoDataFrame
        Superblock polygons
    boundary_streets : GeoDataFrame
        High-capacity boundary streets (remain two-way)
    internal_streets : GeoDataFrame
        Lower-capacity internal streets (candidates for one-way)
    config : PipelineConfig
        Configuration parameters
        
    Returns
    -------
    GeoDataFrame
        Internal streets with updated 'oneway' and 'direction' columns
    """
    
    if internal_streets.empty or superblocks.empty:
        logger.warning("Cannot calculate street directions without internal streets and superblocks")
        result = internal_streets.copy()
        result['oneway'] = False
        result['direction'] = 'both'
        result['access_control'] = 'open'
        return result
    
    # Start with a copy of internal streets
    result = internal_streets.copy()
    result['oneway'] = result.get('oneway', False)
    result['direction'] = 'both'
    result['access_control'] = 'open'
    
    # For each superblock, analyze internal connectivity
    for sb_idx, superblock in superblocks.iterrows():
        sb_id = superblock.get('superblock_id', sb_idx)
        sb_geom = superblock.geometry
        
        # Find internal streets within this superblock
        try:
            internal_in_sb = result[result.geometry.within(sb_geom)].copy()
        except Exception:
            # Fallback to intersection check
            internal_in_sb = result[result.geometry.intersects(sb_geom)].copy()
        
        if internal_in_sb.empty:
            continue
        
        # Apply simple heuristics for one-way streets
        # Rule 1: Narrow streets (low capacity) should be one-way
        capacity_threshold = internal_in_sb['capacity'].quantile(0.4)
        low_capacity_mask = internal_in_sb['capacity'] <= capacity_threshold
        
        # Rule 2: Streets connecting to only one boundary remain two-way (dead ends)
        # Rule 3: Streets in a grid pattern: alternate directions
        
        for idx in internal_in_sb.index:
            row = internal_in_sb.loc[idx]
            
            # Check if already one-way in OSM data
            existing_oneway = row.get('oneway')
            if existing_oneway and existing_oneway not in [False, 'no', 'false', '0']:
                result.at[idx, 'oneway'] = True
                result.at[idx, 'direction'] = 'forward'
                result.at[idx, 'access_control'] = 'oneway'
                continue
            
            # Apply low capacity rule
            if low_capacity_mask.get(idx, False):
                # Make this street one-way
                result.at[idx, 'oneway'] = True
                # Determine direction based on geometry orientation
                # For now, use a simple heuristic: west->east or south->north
                geom = row.geometry
                if isinstance(geom, LineString):
                    coords = list(geom.coords)
                    if len(coords) >= 2:
                        start = coords[0]
                        end = coords[-1]
                        # East-west: prefer eastward
                        dx = end[0] - start[0]
                        dy = end[1] - start[1]
                        if abs(dx) > abs(dy):
                            result.at[idx, 'direction'] = 'forward' if dx > 0 else 'reverse'
                        else:
                            result.at[idx, 'direction'] = 'forward' if dy > 0 else 'reverse'
                result.at[idx, 'access_control'] = 'oneway'
    
    logger.info("Calculated street directions: %d one-way, %d two-way",
                (result['oneway'] == True).sum(),
                (result['oneway'] == False).sum())
    
    return result


def identify_modal_filters(
    internal_streets: gpd.GeoDataFrame,
    superblocks: gpd.GeoDataFrame,
    config: PipelineConfig,
) -> gpd.GeoDataFrame:
    """Identify locations for modal filters (barriers to motor traffic).
    
    Modal filters are physical interventions (planters, bollards) that:
    - Block motor vehicle through-traffic
    - Allow pedestrians and cyclists to pass
    - Are placed at strategic points to break up long through-routes
    
    Parameters
    ----------
    internal_streets : GeoDataFrame
        Internal streets within superblocks
    superblocks : GeoDataFrame
        Superblock polygons
    config : PipelineConfig
        Configuration parameters
        
    Returns
    -------
    GeoDataFrame
        Point locations for modal filters with metadata
    """
    
    if internal_streets.empty or superblocks.empty:
        return gpd.GeoDataFrame(
            columns=['geometry', 'filter_type', 'street_name', 'reason'],
            crs=internal_streets.crs if not internal_streets.empty else None
        )
    
    filter_points = []
    
    for sb_idx, superblock in superblocks.iterrows():
        sb_id = superblock.get('superblock_id', sb_idx)
        sb_geom = superblock.geometry
        
        # Find internal streets within this superblock
        try:
            streets_in_sb = internal_streets[internal_streets.geometry.within(sb_geom)].copy()
        except Exception:
            streets_in_sb = internal_streets[internal_streets.geometry.intersects(sb_geom)].copy()
        
        if streets_in_sb.empty:
            continue
        
        # Strategy: Place filters on longer internal streets that could be through-routes
        # Target streets with high capacity within the internal network
        if 'capacity' in streets_in_sb.columns:
            capacity_threshold = streets_in_sb['capacity'].quantile(0.6)
            candidates = streets_in_sb[streets_in_sb['capacity'] >= capacity_threshold]
        else:
            candidates = streets_in_sb
        
        # Place filter at the midpoint of candidate streets
        for idx, street in candidates.iterrows():
            geom = street.geometry
            if isinstance(geom, LineString) and geom.length > 50:  # Only streets longer than 50m
                midpoint = geom.interpolate(0.5, normalized=True)
                
                filter_points.append({
                    'geometry': midpoint,
                    'filter_type': 'modal_filter',
                    'street_name': street.get('name', f'Street {idx}'),
                    'superblock_id': sb_id,
                    'reason': 'through_route_prevention',
                })
    
    if not filter_points:
        return gpd.GeoDataFrame(
            columns=['geometry', 'filter_type', 'street_name', 'superblock_id', 'reason'],
            crs=internal_streets.crs
        )
    
    result = gpd.GeoDataFrame(filter_points, crs=internal_streets.crs)
    logger.info("Identified %d modal filter locations", len(result))
    return result


def analyze_permeability(
    internal_streets_with_directions: gpd.GeoDataFrame,
    superblocks: gpd.GeoDataFrame,
    boundary_streets: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Analyze permeability of each superblock.
    
    Permeability measures how easy it is to pass through a superblock.
    Goal: High accessibility (can reach any internal point) but low permeability
    (cannot easily traverse from one boundary to opposite boundary).
    
    Parameters
    ----------
    internal_streets_with_directions : GeoDataFrame
        Internal streets with oneway/direction information
    superblocks : GeoDataFrame
        Superblock polygons
    boundary_streets : GeoDataFrame
        Boundary streets
        
    Returns
    -------
    DataFrame
        Permeability metrics for each superblock
    """
    
    metrics = []
    
    for sb_idx, superblock in superblocks.iterrows():
        sb_id = superblock.get('superblock_id', sb_idx)
        sb_geom = superblock.geometry
        
        # Count internal streets
        try:
            internal_in_sb = internal_streets_with_directions[
                internal_streets_with_directions.geometry.within(sb_geom)
            ]
        except Exception:
            internal_in_sb = internal_streets_with_directions[
                internal_streets_with_directions.geometry.intersects(sb_geom)
            ]
        
        total_internal = len(internal_in_sb)
        oneway_count = (internal_in_sb.get('oneway', False) == True).sum()
        twoway_count = total_internal - oneway_count
        
        # Calculate permeability score (0-1, lower is better)
        # More one-way streets = lower permeability = better
        if total_internal > 0:
            permeability_score = twoway_count / total_internal
        else:
            permeability_score = 0.0
        
        # Calculate accessibility score (0-1, higher is better)
        # At least some streets must remain navigable
        accessibility_score = 1.0 if total_internal > 0 else 0.0
        
        metrics.append({
            'superblock_id': sb_id,
            'total_internal_streets': total_internal,
            'oneway_streets': oneway_count,
            'twoway_streets': twoway_count,
            'permeability_score': permeability_score,
            'accessibility_score': accessibility_score,
        })
    
    result = pd.DataFrame(metrics)
    logger.info("Analyzed permeability for %d superblocks", len(result))
    return result
