"""Generate narrative reports that align toolkit outputs with literature evidence."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent


def _fmt_percent(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}%"


def _fmt_db(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f} dB"


def _fmt_number(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:,}"


def _fmt_days(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.0f} days"


def _fmt_currency(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    billions = value / 1_000_000_000
    if billions >= 1:
        return f"€{billions:.2f} billion"
    millions = value / 1_000_000
    if millions >= 1:
        return f"€{millions:.1f} million"
    return f"€{value:,.0f}"


def _equity_summary(flags: dict) -> str:
    parts = []
    for key, label in (
        ("coverage_intensity", "Coverage intensity"),
        ("perimeter_pressure", "Perimeter pressure"),
        ("gentrification_risk", "Gentrification risk"),
    ):
        value = flags.get(key, "n/a")
        parts.append(f"- {label}: **{value}**")
    return "\n".join(parts)


def generate_full_report(metrics: dict, output_path: Path) -> Path:
    context = metrics.get("context", {})
    network = metrics.get("network", {})
    superblocks = metrics.get("superblocks", {})
    heritage = metrics.get("heritage_zone", {})
    estimates = metrics.get("evidence_based_estimates", {})
    mobility = metrics.get("mode_shift_estimates", {})
    environment = metrics.get("environmental_health_estimates", {})
    economy = metrics.get("economic_estimates", {})
    equity = metrics.get("equity_risk_flags", {})

    place = context.get("place", "Unknown City")
    coverage = superblocks.get("coverage_ratio", 0)
    study_area = context.get("study_area_km2", 0)

    lines: list[str] = []
    lines.append(f"# The Superblock Model: Evidence-Based Analysis for {place}")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(
        f"- {place} study area analysed: **{study_area} km²** with superblocks covering **{superblocks.get('total_area_km2', 0)} km²** ({coverage:.3f} coverage ratio)."
    )
    lines.append(
        "- Expected annual health benefits: NO₂ ↓ "
        f"{_fmt_percent(estimates.get('expected_no2_reduction_percent'))}, noise ↓ {_fmt_db(estimates.get('expected_noise_reduction_db'))}, "
        f"green space ↑ {_fmt_percent(estimates.get('expected_green_space_increase_percent'))}, preventing approximately {_fmt_number(estimates.get('expected_prevented_premature_deaths'))} premature deaths if the evidence scales proportionally."
    )
    lines.append(
        "- Mobility outlook points to internal traffic reductions of "
        f"{_fmt_percent(mobility.get('projected_internal_traffic_reduction_percent'))}, walking share around {_fmt_percent(mobility.get('projected_walk_mode_share_percent'))}, "
        f"cycling share {_fmt_percent(mobility.get('projected_cycle_mode_share_percent'))}, and public transport uplift {_fmt_percent(mobility.get('projected_public_transport_uplift_percent'))} across the treated area."
    )
    lines.append(
        "- Environmental estimates include CO₂ ↓ "
        f"{_fmt_percent(environment.get('expected_co2_reduction_percent'))} and life-expectancy gains of {_fmt_days(environment.get('expected_life_expectancy_gain_days'))} per adult, "
        f"with annual health-related savings near {_fmt_currency(economy.get('projected_health_economic_savings_eur'))}."
    )
    lines.append("- Equity watchpoints derived from heuristics:")
    lines.extend(_equity_summary(equity).splitlines())
    lines.append("")

    lines.append("## I. The Superblock Paradigm: Concept, Principles, Objectives")
    lines.append("")
    lines.append(
        "**Definition & Origins.** Superblocks reorganise mobility into multi-block cells (~400×400 m) bounded by transit-capable arterials, "
        "eliminating interior through-traffic to reclaim public space. Barcelona’s BCNecologia work under Salvador Rueda translated Cerdà’s "
        "19th-century grid ambitions into contemporary planning from the 1990s onwards, inspiring a global family of \"super\" interventions "
        "(Superilles, Supergrätzl, Kiezblocks, Low Traffic Neighbourhoods)."
    )
    lines.append("")
    lines.append("**Core Principles.**")
    lines.append(
        "1. *Reclaim public space*: interior carriageways and parking become plazas, widened sidewalks, playgrounds, and cycle streets—Barcelona simulations cite +270% pedestrian space city-wide."
    )
    lines.append(
        "2. *Calm traffic*: interior speeds of 10–20 km/h and removal of through journeys produce \"pacified\" streets while perimeter arterials handle strategic movement."
    )
    lines.append(
        "3. *Prioritise people and active mobility*: pedestrians, cyclists, and transit gain hierarchy over private cars, reinforcing health, safety, and sense of place."
    )
    lines.append("")
    lines.append(
        "**Strategic Objectives.** Deliver sustainable mobility, cleaner air, cooler microclimates, better health outcomes, social cohesion, equitable access, and resilient local economies. Actions in one pillar reinforce others—e.g. modal shift reduces noise, enabling outdoor social life and business vitality."
    )
    lines.append("")

    lines.append("## II. Assessed Impacts: Scientific Evidence & Real Outcomes")
    lines.append("")
    lines.append(
        f"- **Air quality:** Local pilots (Sant Antoni, Horta) measured NO₂ drops of 17–25%; scaling to {place} suggests {_fmt_percent(estimates.get('expected_no2_reduction_percent'))} reduction with current coverage."
    )
    lines.append(
        f"- **Noise:** Poblenou and Glòries documented 5–9 dB reductions; applying heuristics to {place} anticipates {_fmt_db(estimates.get('expected_noise_reduction_db'))} improvements."
    )
    lines.append(
        f"- **Greening:** Tactical-to-structural transformations add permeable, shaded space; coverage-adjusted green potential reaches {_fmt_percent(estimates.get('expected_green_space_increase_percent'))}."
    )
    lines.append(
        "- **Mobility:** Evidence indicates internal traffic ↓ up to 58%, walking 66%, cycling 11%, PT +43.5%. "
        f"Our scaled projections mirror these ratios ({_fmt_percent(mobility.get('projected_internal_traffic_reduction_percent'))}, {_fmt_percent(mobility.get('projected_walk_mode_share_percent'))}, {_fmt_percent(mobility.get('projected_cycle_mode_share_percent'))})."
    )
    lines.append(
        f"- **Road safety & health:** Reduced conflict points, shaded play streets, and active lifestyles extend life expectancy by {_fmt_days(environment.get('expected_life_expectancy_gain_days'))} on average when fully realised."
    )
    lines.append(
        f"- **Economics:** City-wide programmes demonstrate ~€1.7 bn annual healthcare/productivity savings; coverage-adjusted estimate for {place}: {_fmt_currency(economy.get('projected_health_economic_savings_eur'))}."
    )
    lines.append("")
    lines.append("### Table: Selected Evidence Benchmarks")
    lines.append("")
    lines.append("| Category | Benchmark | Source | Scaled estimate |")
    lines.append("| --- | --- | --- | --- |")
    lines.append(
        f"| NO₂ reduction | 24% (Barcelona full network) | Nieuwenhuijsen et al. 2024 | {_fmt_percent(estimates.get('expected_no2_reduction_percent'))} |"
    )
    lines.append(
        f"| Noise reduction | 5–9 dB | Poblenou / Glòries studies | {_fmt_db(estimates.get('expected_noise_reduction_db'))} |"
    )
    lines.append(
        f"| Internal traffic ↓ | 58% | Barcelona pilots | {_fmt_percent(mobility.get('projected_internal_traffic_reduction_percent'))} |"
    )
    lines.append(
        f"| Walking share | 66% | Vitoria-Gasteiz pilot | {_fmt_percent(mobility.get('projected_walk_mode_share_percent'))} |"
    )
    lines.append(
        f"| Health savings | €1.7 bn/year | ISGlobal / TTI 2019 | {_fmt_currency(economy.get('projected_health_economic_savings_eur'))} |"
    )
    lines.append("")

    lines.append("## III. Superblocks in Practice: Case Study Takeaways")
    lines.append("")
    lines.append(
        "- **Barcelona:** Poblenou (tactical first, -58% traffic, +13,350 m² public space) taught lessons on co-design; Sant Antoni emphasised air-quality gains but raised gentrification alerts; Eixample green axes show value and speculation risk."
    )
    lines.append(
        "- **Vitoria-Gasteiz:** Integrated SUMP with PT restructuring, 30 km/h grid, CO₂ ↓ 42%, PT +43.5% ridership, survey approval 7.4/10."
    )
    lines.append(
        "- **Emerging models:** Vienna’s rapid Supergrätzl faced resistance; Berlin’s bottom-up Kiezblocks illustrate slower but community-backed pathways; London LTNs underscore need for emergency access protocols and communication."
    )
    lines.append("")

    lines.append("## IV. Implementation Journey: From Diagnosis to Evaluation")
    lines.append("")
    lines.append("1. **Diagnosis & analysis:** map traffic, environmental burdens, demographics, vulnerability indices.")
    lines.append("2. **Concept & goal setting:** align with mobility, climate, health, housing agendas.")
    lines.append(
        "3. **Co-design:** blend charrettes, surveys, digital platforms; clarify negotiables."
    )
    lines.append(
        "4. **Implementation:** tactical (paint, planters, quick-build networks) → structural (permanent civil works) once validated."
    )
    lines.append(
        "5. **Monitoring & evaluation:** maintain practical indicators (traffic counts, NO₂ sensors, public-space occupancy, sentiment) to iterate."
    )
    lines.append("")

    lines.append("## V. Building Superblocks: Key Interventions")
    lines.append("")
    lines.append(
        "- **Physical:** circulation redesigns, filters, raised crossings, protected cycle links, curbless shared surfaces, extensive greening."
    )
    lines.append(
        "- **Tactical vs structural:** quick wins de-risk change; investment in materials, drainage, furniture, trees cements success."
    )
    lines.append(
        "- **Policy & regulation:** embed in UMP, climate plans, land-use; codify speed limits, access rules, parking reforms; manage perimeter signal timing."
    )
    lines.append(
        "- **Funding:** mix municipal budgets, climate/transport grants, EU programmes, IFIs. Emphasise co-benefits (health, resilience, equity) in bids."
    )
    lines.append("")

    lines.append("## VI. Navigating Hurdles")
    lines.append("")
    lines.append(
        "- **Traffic displacement:** monitor perimeter flows, support transit/cycling, apply demand management to encourage evaporation."
    )
    lines.append(
        "- **Accessibility:** guarantee emergency routing, delivery windows, universal design features."
    )
    lines.append(
        "- **Business adaptation:** maintain servicing, provide marketing/public realm support, diversify commercial mix policies."
    )
    lines.append(
        f"- **Equity & gentrification:** pair with affordable housing, rent stabilisation, community land trusts, targeted deployment beyond heritage cores; our heuristics flag gentrification risk as **{equity.get('gentrification_risk', 'n/a')}**."
    )
    lines.append(
        "- **Political resistance:** invest in transparent engagement, tactical pilots, coalitions across health, education, economic actors."
    )
    lines.append("")

    lines.append("## VII. Guidelines & Best Practices")
    lines.append("")
    lines.append("- Prioritise health outcomes in design choices.")
    lines.append("- Integrate holistically with mobility, climate, housing, and social policies.")
    lines.append("- Engage inclusively and continuously; measure legitimacy as well as technical KPIs.")
    lines.append("- Tailor to context—there is no one-size superblock.")
    lines.append("- Phase strategically using tactical urbanism to build evidence and trust.")
    lines.append("- Monitor, evaluate, adapt using the metrics exported by this toolkit.")
    lines.append(
        "- Mitigate negative impacts proactively, especially displacement and perimeter load."
    )
    lines.append("- Guarantee universal accessibility from the outset.")
    lines.append("")

    lines.append(f"## Recommended Next Steps for {place}")
    lines.append("")
    lines.append(
        "1. **Equity deep-dive:** augment heuristics with socio-economic and rent datasets to refine gentrification risk screening."
    )
    lines.append(
        f"2. **Perimeter strategy:** use `_major_roads` layer (total {network.get('major_road_km', 0)} km) to co-design signal and bus priority upgrades mitigating {_fmt_number(network.get('major_road_km', 0))} km of boundary stress."
    )
    lines.append(
        f"3. **Monitoring plan:** deploy sensors and community observatories to validate {_fmt_percent(estimates.get('expected_no2_reduction_percent'))} NO₂ reductions and {_fmt_db(estimates.get('expected_noise_reduction_db'))} noise improvements."
    )
    lines.append(
        "4. **Engagement roadmap:** co-create with residents, schools, businesses, emergency services; document participation metrics alongside physical KPIs."
    )
    lines.append(
        f"5. **Financing mix:** align savings estimate {_fmt_currency(economy.get('projected_health_economic_savings_eur'))} with climate finance narratives for EU or IFI grant applications."
    )
    lines.append("")

    lines.append("## References & Further Reading")
    lines.append("")
    lines.append("- Nieuwenhuijsen, M. J., et al. (2024). *The superblock model: A review...*")
    lines.append("- Marí-Dell'Olmo, M., et al. (2025). *Environmental and health effects of the Barcelona superblocks.*")
    lines.append(
        "- ISGlobal / TTI (2019). *Superblocks project could prevent almost 700 premature deaths every year in Barcelona.*"
    )
    lines.append(
        "- Council of Europe Development Bank (2023). *Resilience in Action: Barcelona’s Superblock Programme.*"
    )
    lines.append("- SMARTEES Project (2020). *Local Social Innovation Case Study: Vitoria-Gasteiz.*")
    lines.append("- Tonello, G., et al. (2022). *Public acceptance of the superblocks of Barcelona.*")
    lines.append("")
    lines.append(
        "*This brief was auto-generated from the pipeline outputs and the shared literature review. Adapt the templates as you incorporate local datasets and stakeholder input.*"
    )

    content = "\n".join(lines) + "\n"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path
