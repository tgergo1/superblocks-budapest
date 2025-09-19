"""Evidence-aligned metrics and lightweight impact estimates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import geopandas as gpd

from .config import PipelineConfig
from .geometry import get_metric_crs


EVIDENCE_BASELINES = {
    "no2_reduction_percent": 24.0,
    "noise_reduction_db": 5.0,
    "green_space_increase_percent": 270.0,
    "prevented_deaths": 667.0,
    "traffic_reduction_percent": 58.0,
    "walk_mode_share_percent": 66.0,
    "cycle_mode_share_percent": 11.0,
    "public_transport_increase_percent": 43.5,
    "co2_reduction_percent": 42.0,
    "economic_savings_eur_billion": 1.7,
    "life_expectancy_gain_days": 200.0,
}


def _length_km(gdf: gpd.GeoDataFrame | None) -> float:
    if gdf is None or gdf.empty:
        return 0.0
    metric_crs = get_metric_crs(gdf)
    if metric_crs is None:
        return 0.0
    metric = gdf.to_crs(metric_crs)
    return float(metric.length.sum() / 1000.0)


def _area_km2(gdf: gpd.GeoDataFrame | None) -> float:
    if gdf is None or gdf.empty:
        return 0.0
    metric_crs = get_metric_crs(gdf)
    if metric_crs is None:
        return 0.0
    metric = gdf.to_crs(metric_crs)
    return float(metric.area.sum() / 1_000_000.0)


def _study_area_km2(edges: gpd.GeoDataFrame | None) -> float:
    if edges is None or edges.empty:
        return 0.0
    if edges.crs is None:
        return 0.0
    metric_crs = get_metric_crs(edges)
    if metric_crs is None:
        return 0.0
    hull = gpd.GeoSeries(edges.unary_union.convex_hull, crs=edges.crs).to_crs(metric_crs)
    return float(hull.area.iloc[0] / 1_000_000.0)


def _coverage_ratio(superblocks_area: float, study_area: float) -> float:
    if superblocks_area <= 0 or study_area <= 0:
        return 0.0
    return max(0.0, min(1.0, superblocks_area / study_area))


def compute_metrics(
    *,
    edges: gpd.GeoDataFrame | None,
    boundary: gpd.GeoDataFrame | None,
    internal: gpd.GeoDataFrame | None,
    superblocks: gpd.GeoDataFrame | None,
    heritage_zone: gpd.GeoDataFrame | None,
    heritage_priority: gpd.GeoDataFrame | None,
    major_roads: gpd.GeoDataFrame | None,
    config: PipelineConfig,
) -> Dict[str, Any]:
    """Return key metrics and heuristic impact estimates for reporting."""

    study_area = _study_area_km2(edges)
    superblock_area = _area_km2(superblocks)
    heritage_area = _area_km2(heritage_zone)

    coverage = _coverage_ratio(superblock_area, study_area)

    metrics: Dict[str, Any] = {
        "context": {
            "place": config.place_name,
            "study_area_km2": round(study_area, 3),
        },
        "network": {
            "total_edges_km": round(_length_km(edges), 2),
            "boundary_street_km": round(_length_km(boundary), 2),
            "internal_street_km": round(_length_km(internal), 2),
            "major_road_km": round(_length_km(major_roads), 2),
            "heritage_priority_km": round(_length_km(heritage_priority), 2),
        },
        "superblocks": {
            "count": int(0 if superblocks is None else len(superblocks)),
            "total_area_km2": round(superblock_area, 3),
            "average_area_km2": round(superblock_area / len(superblocks), 4)
            if superblocks is not None and len(superblocks) > 0
            else 0.0,
            "coverage_ratio": round(coverage, 3),
        },
        "heritage_zone": {
            "area_km2": round(heritage_area, 3),
            "share_of_study_area": round(_coverage_ratio(heritage_area, study_area), 3),
        },
    }

    estimates = {
        "expected_no2_reduction_percent": round(coverage * EVIDENCE_BASELINES["no2_reduction_percent"], 2),
        "expected_noise_reduction_db": round(coverage * EVIDENCE_BASELINES["noise_reduction_db"], 2),
        "expected_green_space_increase_percent": round(
            coverage * EVIDENCE_BASELINES["green_space_increase_percent"], 1
        ),
        "expected_prevented_premature_deaths": round(
            coverage * EVIDENCE_BASELINES["prevented_deaths"], 1
        ),
    }

    mode_shift = {
        "projected_internal_traffic_reduction_percent": round(
            coverage * EVIDENCE_BASELINES["traffic_reduction_percent"], 1
        ),
        "projected_walk_mode_share_percent": round(
            coverage * EVIDENCE_BASELINES["walk_mode_share_percent"], 1
        ),
        "projected_cycle_mode_share_percent": round(
            coverage * EVIDENCE_BASELINES["cycle_mode_share_percent"], 1
        ),
        "projected_public_transport_uplift_percent": round(
            coverage * EVIDENCE_BASELINES["public_transport_increase_percent"], 1
        ),
    }

    environment = {
        "expected_co2_reduction_percent": round(
            coverage * EVIDENCE_BASELINES["co2_reduction_percent"], 1
        ),
        "expected_life_expectancy_gain_days": round(
            coverage * EVIDENCE_BASELINES["life_expectancy_gain_days"], 1
        ),
    }

    economy = {
        "projected_health_economic_savings_eur": round(
            coverage * EVIDENCE_BASELINES["economic_savings_eur_billion"] * 1_000_000_000, 0
        ),
    }

    boundary_len = metrics["network"].get("boundary_street_km", 0) or 0.0
    major_len = metrics["network"].get("major_road_km", 0) or 0.0
    heritage_share = metrics["heritage_zone"].get("share_of_study_area", 0) or 0.0

    perimeter_pressure_index = round(major_len / boundary_len, 2) if boundary_len else 0.0

    def _risk_level(value: float, *, medium: float, high: float) -> str:
        if value >= high:
            return "high"
        if value >= medium:
            return "medium"
        return "low"

    equity_flags = {
        "gentrification_risk": _risk_level(heritage_share, medium=0.015, high=0.03),
        "perimeter_pressure": _risk_level(perimeter_pressure_index, medium=3.0, high=5.0),
        "coverage_intensity": _risk_level(coverage, medium=0.15, high=0.3),
    }

    metrics["evidence_based_estimates"] = estimates
    metrics["mode_shift_estimates"] = mode_shift
    metrics["environmental_health_estimates"] = environment
    metrics["economic_estimates"] = economy
    metrics["equity_risk_flags"] = equity_flags
    return metrics


def write_metrics(path: Path, metrics: Dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        json.dump(metrics, fp, indent=2)
    return path


def metrics_to_markdown(metrics: Dict[str, Any]) -> str:
    context = metrics.get("context", {})
    network = metrics.get("network", {})
    superblocks = metrics.get("superblocks", {})
    heritage_zone = metrics.get("heritage_zone", {})
    estimates = metrics.get("evidence_based_estimates", {})
    mode_shift = metrics.get("mode_shift_estimates", {})
    environment = metrics.get("environmental_health_estimates", {})
    economy = metrics.get("economic_estimates", {})
    equity = metrics.get("equity_risk_flags", {})

    lines = [
        "# Evidence-Aligned Superblock Summary",
        "",
        f"**Location:** {context.get('place', 'unknown')}",
        "",
        "## Network Snapshot",
        f"- Study area: {context.get('study_area_km2', 0)} km²",
        f"- Total street length: {network.get('total_edges_km', 0)} km",
        f"- Boundary streets: {network.get('boundary_street_km', 0)} km",
        f"- Internal streets: {network.get('internal_street_km', 0)} km",
        f"- Major corridors: {network.get('major_road_km', 0)} km",
        f"- Heritage-priority streets: {network.get('heritage_priority_km', 0)} km",
        "",
        "## Superblock Footprint",
        f"- Superblock count: {superblocks.get('count', 0)}",
        f"- Total area: {superblocks.get('total_area_km2', 0)} km²",
        f"- Average size: {superblocks.get('average_area_km2', 0)} km²",
        f"- Coverage ratio: {superblocks.get('coverage_ratio', 0)}",
        "",
        "## Heritage Core",
        f"- Heritage zone area: {heritage_zone.get('area_km2', 0)} km²",
        f"- Share of study area: {heritage_zone.get('share_of_study_area', 0)}",
        "",
        "## Evidence-Based Impact Estimates",
        f"- NO₂ reduction (modeled): {estimates.get('expected_no2_reduction_percent', 0)}%",
        f"- Noise reduction (modeled): {estimates.get('expected_noise_reduction_db', 0)} dB",
        f"- Green space potential: {estimates.get('expected_green_space_increase_percent', 0)}%",
        f"- Prevented premature deaths (modeled): {estimates.get('expected_prevented_premature_deaths', 0)} per year",
        "",
        "## Mobility Shift Signals",
        f"- Internal traffic reduction: {mode_shift.get('projected_internal_traffic_reduction_percent', 0)}%",
        f"- Walk mode share: {mode_shift.get('projected_walk_mode_share_percent', 0)}%",
        f"- Cycle mode share: {mode_shift.get('projected_cycle_mode_share_percent', 0)}%",
        f"- Public transport uplift: {mode_shift.get('projected_public_transport_uplift_percent', 0)}%",
        "",
        "## Environmental & Health Outlook",
        f"- CO₂ reduction: {environment.get('expected_co2_reduction_percent', 0)}%",
        f"- Life expectancy gain: {environment.get('expected_life_expectancy_gain_days', 0)} days",
        "",
        "## Economic Outlook",
        f"- Health-related savings: €{int(economy.get('projected_health_economic_savings_eur', 0)):,} per year",
        "",
        "## Equity & Risk Flags",
        f"- Coverage intensity: {equity.get('coverage_intensity', 'n/a')}",
        f"- Perimeter pressure: {equity.get('perimeter_pressure', 'n/a')}",
        f"- Gentrification risk: {equity.get('gentrification_risk', 'n/a')}",
        "",
        "*Estimates scale evidence from Barcelona to the current coverage ratio and should be interpreted as illustrative ranges rather than precise forecasts.*",
    ]
    return "\n".join(lines)


def write_markdown(path: Path, metrics: Dict[str, Any]) -> Path:
    content = metrics_to_markdown(metrics)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
