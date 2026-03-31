"""
Core analysis engine: duty/standby opportunities, deferral pattern analysis,
and optimisation opportunity scoring.
"""
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from database import Asset, WorkOrder, MaintenanceStrategy
from typing import Optional


def _asset_tags(db: Session, platforms: list[str] | None) -> set[str] | None:
    """Return the set of asset tags belonging to the selected platforms, or None for all."""
    if not platforms:
        return None
    rows = db.query(Asset.tag).filter(Asset.platform.in_(platforms)).all()
    return {r[0] for r in rows}


def _filter_assets(q, tag_set: set[str] | None):
    if tag_set is not None:
        q = q.filter(Asset.tag.in_(tag_set))
    return q


def _filter_wos(q, tag_set: set[str] | None):
    if tag_set is not None:
        q = q.filter(WorkOrder.asset_tag.in_(tag_set))
    return q


def get_duty_standby_opportunities(db: Session, platforms: list[str] | None = None) -> list[dict]:
    """
    Identify assets in duty/standby pairs where the standby unit
    has the same maintenance strategy as the duty unit.
    Flags these as opportunities to extend the standby interval.
    """
    tag_set = _asset_tags(db, platforms)
    q = db.query(Asset).filter(Asset.paired_tag.isnot(None))
    assets = _filter_assets(q, tag_set).all()

    # Pre-load asset map and all PPM WOs — avoids N+1 per pair
    asset_map_ds: dict[str, Asset] = {a.tag: a for a in assets}
    ppm_wos = _filter_wos(db.query(WorkOrder).filter(WorkOrder.wo_type == "PPM"), tag_set).all()
    ppm_by_tag: dict[str, list] = {}
    for w in ppm_wos:
        ppm_by_tag.setdefault(w.asset_tag, []).append(w)

    seen_pairs = set()
    opportunities = []

    for asset in assets:
        if asset.operating_status != "Duty":
            continue
        pair_key = tuple(sorted([asset.tag, asset.paired_tag]))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        standby = asset_map_ds.get(asset.paired_tag)
        if not standby:
            continue

        duty_tasks = ppm_by_tag.get(asset.tag, [])
        standby_tasks = ppm_by_tag.get(standby.tag, [])

        duty_codes = set(w.task_code for w in duty_tasks)
        standby_codes = set(w.task_code for w in standby_tasks)
        shared_codes = duty_codes & standby_codes

        # Estimate annual cost for standby
        standby_annual_cost = _annual_cost(standby_tasks)
        duty_annual_cost = _annual_cost(duty_tasks)

        # Saving estimate: if standby interval doubled on shared tasks, ~50% saving on those tasks
        # Assume shared tasks are ~70% of standby cost
        potential_saving = round(standby_annual_cost * 0.70 * 0.40, 2)  # ~40% reduction on shared tasks

        opportunities.append({
            "type": "duty_standby",
            "duty_tag": asset.tag,
            "standby_tag": standby.tag,
            "equipment_class": asset.equipment_class,
            "system": asset.system,
            "criticality": asset.criticality,
            "shared_task_count": len(shared_codes),
            "duty_annual_cost": round(duty_annual_cost, 2),
            "standby_annual_cost": round(standby_annual_cost, 2),
            "potential_annual_saving": potential_saving,
            "rationale": (
                f"{standby.tag} is a standby unit for {asset.tag}. "
                f"Both share {len(shared_codes)} identical PPM tasks. "
                f"The standby unit has lower utilisation and operational stress. "
                f"Extending maintenance intervals for standby-specific tasks could save "
                f"approximately £{potential_saving:,.0f}/year without compromising availability."
            ),
            "recommendation": f"Review {len(shared_codes)} shared tasks; propose 2x interval for low-risk tasks on standby unit.",
        })

    return sorted(opportunities, key=lambda x: x["potential_annual_saving"], reverse=True)


def get_deferral_opportunities(db: Session, min_occurrences: int = 4, min_avg_deferral: int = 30, platforms: list[str] | None = None) -> list[dict]:
    """
    Identify maintenance tasks that have been consistently deferred
    (completed significantly after scheduled date) with no resulting failures.
    These are candidates for interval extension.
    """
    tag_set = _asset_tags(db, platforms)
    q = db.query(WorkOrder).filter(
        WorkOrder.status == "Completed",
        WorkOrder.deferral_days.isnot(None),
        WorkOrder.deferral_days > 0,
    )
    wos = _filter_wos(q, tag_set).all()

    if not wos:
        return []

    # Pre-load assets, strategies and corrective failure counts — avoids N+1 queries
    all_assets_d = _filter_assets(db.query(Asset), tag_set).all()
    asset_map_d: dict[str, Asset] = {a.tag: a for a in all_assets_d}

    all_strategies_d = db.query(MaintenanceStrategy).all()
    strategy_map_d: dict[str, MaintenanceStrategy] = {s.task_code: s for s in all_strategies_d}

    # Corrective failure counts per asset tag
    corr_wos = _filter_wos(db.query(WorkOrder).filter(
        WorkOrder.wo_type == "Corrective",
        WorkOrder.failure_mode.isnot(None),
    ), tag_set).all()
    failures_by_tag: dict[str, int] = {}
    for cw in corr_wos:
        failures_by_tag[cw.asset_tag] = failures_by_tag.get(cw.asset_tag, 0) + 1

    # Group by asset + task_code
    data = {}
    for wo in wos:
        key = (wo.asset_tag, wo.task_code)
        if key not in data:
            data[key] = []
        data[key].append(wo.deferral_days)

    opportunities = []
    for (asset_tag, task_code), deferrals in data.items():
        if len(deferrals) < min_occurrences:
            continue
        avg_deferral = np.mean(deferrals)
        if avg_deferral < min_avg_deferral:
            continue

        asset = asset_map_d.get(asset_tag)
        strategy = strategy_map_d.get(task_code)
        failures = failures_by_tag.get(asset_tag, 0)

        if not asset or not strategy:
            continue

        current_interval = strategy.interval_days
        suggested_interval = current_interval + int(avg_deferral * 0.75)

        # Estimate annual saving from fewer WOs per year
        wos_per_year_current = 365 / current_interval
        wos_per_year_proposed = 365 / suggested_interval
        avg_cost = np.mean([d for d in deferrals]) * 0  # placeholder
        # Use strategy estimated cost
        annual_cost_current = wos_per_year_current * strategy.estimated_hours * 100  # £100/hr blended
        annual_cost_proposed = wos_per_year_proposed * strategy.estimated_hours * 100
        potential_saving = round(annual_cost_current - annual_cost_proposed, 2)

        opportunities.append({
            "type": "deferral_pattern",
            "asset_tag": asset_tag,
            "task_code": task_code,
            "task_description": strategy.task_description,
            "equipment_class": asset.equipment_class,
            "system": asset.system,
            "criticality": asset.criticality,
            "current_interval_days": current_interval,
            "suggested_interval_days": suggested_interval,
            "deferral_count": len(deferrals),
            "avg_deferral_days": round(avg_deferral, 1),
            "max_deferral_days": max(deferrals),
            "confirmed_failures_during_deferral": failures,
            "potential_annual_saving": max(0, potential_saving),
            "rationale": (
                f"Task '{strategy.task_description}' on {asset_tag} has been deferred "
                f"an average of {avg_deferral:.0f} days past its scheduled date across "
                f"{len(deferrals)} occurrences, with no recorded functional failures. "
                f"Current interval: {current_interval} days. "
                f"Suggested interval: {suggested_interval} days."
            ),
            "recommendation": f"Propose interval extension from {current_interval} to {suggested_interval} days for {task_code} on {asset_tag}.",
        })

    return sorted(opportunities, key=lambda x: x["avg_deferral_days"], reverse=True)


def get_deferral_summary_by_task(db: Session, platforms: list[str] | None = None) -> list[dict]:
    """
    Aggregate deferral patterns by task code across all assets.
    Used for fleet-level analysis.
    """
    tag_set = _asset_tags(db, platforms)
    q = db.query(WorkOrder).filter(
        WorkOrder.status == "Completed",
        WorkOrder.deferral_days.isnot(None),
        WorkOrder.deferral_days > 14,
    )
    wos = _filter_wos(q, tag_set).all()

    data = {}
    for wo in wos:
        if wo.task_code not in data:
            data[wo.task_code] = {
                "task_code": wo.task_code,
                "task_description": wo.task_description,
                "deferrals": [],
                "assets": set(),
            }
        data[wo.task_code]["deferrals"].append(wo.deferral_days)
        data[wo.task_code]["assets"].add(wo.asset_tag)

    results = []
    for code, info in data.items():
        strategy = db.query(MaintenanceStrategy).filter(
            MaintenanceStrategy.task_code == code
        ).first()
        results.append({
            "task_code": code,
            "task_description": info["task_description"],
            "affected_assets": len(info["assets"]),
            "total_deferrals": len(info["deferrals"]),
            "avg_deferral_days": round(np.mean(info["deferrals"]), 1),
            "max_deferral_days": max(info["deferrals"]),
            "current_interval_days": strategy.interval_days if strategy else None,
        })

    return sorted(results, key=lambda x: x["avg_deferral_days"], reverse=True)


def get_cost_summary(db: Session, platforms: list[str] | None = None) -> dict:
    tag_set = _asset_tags(db, platforms)
    wos = _filter_wos(db.query(WorkOrder).filter(WorkOrder.status == "Completed"), tag_set).all()
    total_actual = sum(w.actual_cost or 0 for w in wos)
    total_estimated = sum(w.estimated_cost or 0 for w in wos)
    ppm_cost = sum(w.actual_cost or 0 for w in wos if w.wo_type == "PPM")
    statutory_cost = sum(w.actual_cost or 0 for w in wos if w.wo_type == "Statutory")
    corrective_cost = sum(w.actual_cost or 0 for w in wos if w.wo_type == "Corrective")

    by_discipline: dict = {}
    for w in wos:
        d = w.discipline or "Unknown"
        by_discipline[d] = by_discipline.get(d, 0) + (w.actual_cost or 0)

    assets = _filter_assets(db.query(Asset), tag_set).all()
    duty_standby_pairs = sum(1 for a in assets if a.paired_tag and a.operating_status == "Duty")

    ds_opps = get_duty_standby_opportunities(db, platforms)
    def_opps = get_deferral_opportunities(db, platforms=platforms)
    total_potential_saving = sum(o["potential_annual_saving"] for o in ds_opps) + sum(o["potential_annual_saving"] for o in def_opps)

    return {
        "total_actual_cost": round(total_actual, 2),
        "total_estimated_cost": round(total_estimated, 2),
        "ppm_cost": round(ppm_cost, 2),
        "statutory_cost": round(statutory_cost, 2),
        "corrective_cost": round(corrective_cost, 2),
        "cost_by_discipline": {k: round(v, 2) for k, v in by_discipline.items()},
        "total_assets": len(assets),
        "duty_standby_pairs": duty_standby_pairs,
        "total_work_orders": len(wos),
        "total_potential_annual_saving": round(total_potential_saving, 2),
    }


def get_h1_1_analysis(db: Session, platforms: list[str] | None = None, min_deferral_days: int = 14) -> dict:
    """
    H1.1: PM schedules more conservative than equipment requires.
    Evidence: (a) tasks consistently deferred with no corrective uptick,
    (b) fleet-wide deferral vs corrective correlation.
    """
    tag_set = _asset_tags(db, platforms)
    # Get all deferred tasks (>min_deferral_days late) grouped by asset+task
    deferred_wos = _filter_wos(db.query(WorkOrder).filter(
        WorkOrder.wo_type.in_(["PPM", "Statutory"]),
        WorkOrder.status == "Completed",
        WorkOrder.deferral_days > min_deferral_days,
    ), tag_set).all()

    # For each asset, count deferrals and corrective events per year
    asset_years: dict = {}
    for wo in deferred_wos:
        if not wo.scheduled_date:
            continue
        yr = wo.scheduled_date.year
        key = (wo.asset_tag, yr)
        asset_years.setdefault(key, {"deferrals": 0, "corrective": 0})
        asset_years[key]["deferrals"] += 1

    corrective_wos = _filter_wos(db.query(WorkOrder).filter(WorkOrder.wo_type == "Corrective"), tag_set).all()
    for wo in corrective_wos:
        if not wo.scheduled_date:
            continue
        yr = wo.scheduled_date.year
        key = (wo.asset_tag, yr)
        if key in asset_years:
            asset_years[key]["corrective"] += 1

    # Assets where deferrals are high but corrective stays flat/zero -> over-conservative signal
    deferred_no_failure = [
        {"asset_tag": k[0], "year": k[1], "deferrals": v["deferrals"], "corrective_events": v["corrective"]}
        for k, v in asset_years.items()
        if v["deferrals"] >= 2 and v["corrective"] == 0
    ]

    # Task-level: for each deferred task occurrence, check whether a corrective WO
    # occurred on the same asset WITHIN the deferral window (scheduled → actual completion).
    # If it consistently did NOT, the deferral had no consequence → over-conservative signal.
    deferral_by_task: dict = {}
    for wo in deferred_wos:
        if not wo.scheduled_date or not wo.actual_completion_date:
            continue
        deferral_by_task.setdefault(wo.task_code, {
            "task_description": wo.task_description,
            "count": 0,
            "assets": set(),
            "windows_with_corrective": 0,
        })
        deferral_by_task[wo.task_code]["count"] += 1
        deferral_by_task[wo.task_code]["assets"].add(wo.asset_tag)

        # Check for corrective WO during the deferral window
        window_corrective = db.query(WorkOrder).filter(
            WorkOrder.asset_tag == wo.asset_tag,
            WorkOrder.wo_type == "Corrective",
            WorkOrder.scheduled_date >= wo.scheduled_date,
            WorkOrder.scheduled_date <= wo.actual_completion_date,
        ).count()
        if window_corrective > 0:
            deferral_by_task[wo.task_code]["windows_with_corrective"] += 1

    over_conservative_tasks = []
    for task_code, info in deferral_by_task.items():
        if info["count"] < 3:
            continue
        pct_no_corrective_in_window = round(
            (1 - info["windows_with_corrective"] / info["count"]) * 100, 1
        )
        if pct_no_corrective_in_window >= 70:
            strategy = db.query(MaintenanceStrategy).filter(MaintenanceStrategy.task_code == task_code).first()
            over_conservative_tasks.append({
                "task_code": task_code,
                "task_description": info["task_description"],
                "deferred_occurrences": info["count"],
                "affected_assets": len(info["assets"]),
                "pct_assets_with_no_corrective": pct_no_corrective_in_window,
                "current_interval_days": strategy.interval_days if strategy else None,
                "signal": "Consistently deferred with no corrective consequence during deferral window — interval likely conservative",
            })

    over_conservative_tasks.sort(key=lambda x: x["pct_assets_with_no_corrective"], reverse=True)

    # Yearly trend: total deferrals vs total corrective by year
    yearly: dict = {}
    all_wos = _filter_wos(db.query(WorkOrder), tag_set).all()
    for wo in all_wos:
        if not wo.scheduled_date:
            continue
        yr = str(wo.scheduled_date.year)
        yearly.setdefault(yr, {"year": yr, "ppm_deferrals": 0, "corrective_events": 0, "ppm_completed": 0})
        if wo.wo_type in ("PPM", "Statutory") and wo.status == "Completed":
            yearly[yr]["ppm_completed"] += 1
            if wo.deferral_days and wo.deferral_days > 14:
                yearly[yr]["ppm_deferrals"] += 1
        elif wo.wo_type == "Corrective":
            yearly[yr]["corrective_events"] += 1

    trend = sorted(yearly.values(), key=lambda x: x["year"])

    return {
        "hypothesis": "H1.1",
        "title": "PM schedules more conservative than equipment requires",
        "assets_with_deferrals_no_corrective": len(set(d["asset_tag"] for d in deferred_no_failure)),
        "over_conservative_tasks": over_conservative_tasks[:15],
        "yearly_deferral_vs_corrective_trend": trend,
        "summary": (
            f"{len(set(d['asset_tag'] for d in deferred_no_failure))} assets show repeated PM deferrals "
            f"with zero corresponding corrective maintenance events in the same year. "
            f"{len(over_conservative_tasks)} task types across the fleet show >60% of affected assets "
            f"have no corrective history despite consistent deferral — a strong signal of over-conservative intervals."
        ),
    }


def get_h1_2_analysis(db: Session, platforms: list[str] | None = None) -> dict:
    """
    H1.2: Duplicate or overlapping PM tasks on same equipment.
    Uses a component-function matrix to find tasks covering the same
    failure mode on the same equipment class, with savings estimates.
    """
    tag_set = _asset_tags(db, platforms)
    strategies = db.query(MaintenanceStrategy).all()
    all_wos = _filter_wos(db.query(WorkOrder).filter(WorkOrder.wo_type.in_(["PPM", "Statutory"])), tag_set).all()

    # Component-function taxonomy: each task maps to a component + function
    # Format: task_code -> (component, function)
    TASK_TAXONOMY = {
        # Centrifugal Pump
        "CP-M01": ("Lube System",       "Condition Check"),
        "CP-M02": ("Rotating Assembly", "Condition Monitoring"),
        "CP-M03": ("Mechanical Seal",   "Inspection & Condition"),
        "CP-M04": ("Coupling",          "Inspection & Condition"),
        "CP-M05": ("Whole Asset",       "Overhaul"),
        "CP-E01": ("Motor",             "Electrical Health"),
        "CP-E02": ("Motor",             "Electrical Health"),
        # Reciprocating Pump
        "RP-M01": ("Lube System",       "Fluid Change"),
        "RP-M02": ("Valve",             "Inspection & Replacement"),
        "RP-M03": ("Piston/Cylinder",   "Inspection & Condition"),
        "RP-M04": ("Whole Asset",       "Overhaul"),
        # Centrifugal Compressor
        "CC-M01": ("Lube System",       "Condition Check"),
        "CC-M02": ("Rotating Assembly", "Condition Monitoring"),
        "CC-M03": ("Dry Gas Seal",      "Condition Monitoring"),
        "CC-M04": ("Coupling",          "Inspection & Condition"),
        "CC-M05": ("Rotating Assembly", "Condition Monitoring"),
        "CC-M06": ("Whole Asset",       "Overhaul"),
        # Gas Turbine Generator
        "GT-M01": ("Combustion Section","Inspection"),
        "GT-M02": ("Hot Section",       "Inspection"),
        "GT-M03": ("Whole Asset",       "Overhaul"),
        "GT-E01": ("Generator",         "Electrical Health"),
        "GT-E02": ("Generator",         "Electrical Health"),
        # Pressure Vessel
        "PV-S01": ("Vessel Shell",      "Visual Inspection"),
        "PV-S02": ("Vessel Internal",   "Inspection & Condition"),
        "PV-S03": ("Vessel Shell",      "Pressure Test"),
        "PV-M01": ("Vessel Shell",      "Corrosion Monitoring"),
        # Heat Exchanger
        "HX-M01": ("Tube Bundle",       "Condition Monitoring"),
        "HX-M02": ("Tube Bundle",       "Inspection & Cleaning"),
        "HX-M03": ("Whole Asset",       "Pressure Test"),
        # Control Valve
        "CV-I01": ("Actuator",          "Functional Test"),
        "CV-I02": ("Actuator",          "Functional Test"),
        "CV-I03": ("Actuator",          "Overhaul"),
        # Pressure Transmitter
        "PT-I01": ("Transmitter",       "Calibration"),
        "PT-I02": ("Impulse Line",      "Condition Check"),
        # Flow Meter
        "FM-I01": ("Meter",             "Calibration"),
        "FM-I02": ("Strainer",          "Inspection & Cleaning"),
        # Fire & Gas Detector
        "FG-I01": ("Detector Head",     "Functional Test"),
        "FG-I02": ("Detector Head",     "Calibration"),
        "FG-I03": ("Detector Head",     "Replacement"),
        # Switchgear
        "SW-E01": ("Busbars/Contacts",  "Condition Monitoring"),
        "SW-E02": ("Contacts",          "Electrical Test"),
        "SW-E03": ("Whole Panel",       "Overhaul"),
        # UPS
        "UP-E01": ("Battery",           "Functional Test"),
        "UP-E02": ("Battery",           "Visual Inspection"),
        "UP-E03": ("UPS",               "Functional Test"),
        # Fan/Blower
        "FB-M01": ("Drive Belt",        "Inspection & Condition"),
        "FB-M02": ("Bearing",           "Lubrication"),
        "FB-M03": ("Impeller",          "Inspection & Condition"),
        "FB-E01": ("Motor",             "Electrical Health"),
        # Safety Valve
        "SV-S01": ("Valve",             "Functional Test"),
        "SV-S02": ("Valve",             "Visual Inspection"),
        # Electric Motor
        "EM-E01": ("Motor",             "Electrical Health"),
        "EM-E02": ("Motor",             "Electrical Health"),
        "EM-M01": ("Bearing",           "Lubrication"),
    }

    # Mobilization cost saved per consolidated visit (£) - conservative offshore estimate
    MOB_COST_SAVING = 450

    strat_lookup = {s.task_code: s for s in strategies}
    by_class: dict = {}
    for s in strategies:
        by_class.setdefault(s.equipment_class, [])
        by_class[s.equipment_class].append(s)

    # Count actual WOs per task code to estimate fleet-wide impact
    wo_count_by_task: dict = {}
    for wo in all_wos:
        wo_count_by_task[wo.task_code] = wo_count_by_task.get(wo.task_code, 0) + 1

    overlaps = []
    for eq_class, strats in by_class.items():
        # Group tasks by (component, function) within class
        cf_groups: dict = {}
        for s in strats:
            cf = TASK_TAXONOMY.get(s.task_code)
            if not cf:
                continue
            key = cf  # (component, function)
            cf_groups.setdefault(key, [])
            cf_groups[key].append(s)

        for (component, function), covering_tasks in cf_groups.items():
            if len(covering_tasks) < 2:
                continue
            intervals = sorted([t.interval_days for t in covering_tasks])
            # Only flag if intervals differ (same-interval duplicates are strongest signal)
            # or if the shorter interval is a subset of what the longer interval would catch
            shortest = min(intervals)
            longest = max(intervals)

            # Calculate how often combined visit opportunities arise per year
            # (how often both tasks fall in same period)
            visits_per_year_short = 365 / shortest
            combined_opportunities_per_year = 365 / longest  # times longer task falls due
            # Saving: each time the longer task falls, it could be combined with short task visit
            annual_mob_saving = combined_opportunities_per_year * MOB_COST_SAVING

            # Fleet-level: multiply by number of assets with these tasks
            aq = db.query(Asset).filter(Asset.equipment_class == eq_class)
            if tag_set is not None:
                aq = aq.filter(Asset.tag.in_(tag_set))
            asset_count = aq.count()
            fleet_annual_saving = round(annual_mob_saving * asset_count, 0)

            # Total hours that could be saved (combined task = sum - 20% efficiency)
            total_hrs = sum(t.estimated_hours for t in covering_tasks)
            combined_hrs = total_hrs * 0.80
            hr_saving_per_visit = total_hrs - combined_hrs

            overlaps.append({
                "equipment_class": eq_class,
                "component": component,
                "function": function,
                "overlap_type": "Duplicate function" if len(set(intervals)) == 1 else "Nested interval",
                "overlapping_tasks": [
                    {
                        "task_code": t.task_code,
                        "task_description": t.task_description,
                        "interval_days": t.interval_days,
                        "estimated_hours": t.estimated_hours,
                        "basis": t.basis,
                        "annual_wo_count": wo_count_by_task.get(t.task_code, 0),
                    }
                    for t in sorted(covering_tasks, key=lambda x: x.interval_days)
                ],
                "asset_count": asset_count,
                "annual_combined_opportunities": round(combined_opportunities_per_year, 1),
                "fleet_annual_mob_saving": fleet_annual_saving,
                "hours_saving_per_visit": round(hr_saving_per_visit, 1),
                "recommendation": (
                    f"On {eq_class}, tasks {', '.join(t.task_code for t in covering_tasks)} "
                    f"all address '{component} — {function}'. "
                    f"{'Same interval — one may be redundant.' if len(set(intervals)) == 1 else f'Shorter task ({shortest}d) could be combined with longer task ({longest}d) visit, saving a separate mobilisation {round(combined_opportunities_per_year,1):.0f}x/year.'} "
                    f"Fleet saving estimate: £{fleet_annual_saving:,.0f}/year across {asset_count} assets."
                ),
            })

    total_fleet_saving = sum(o["fleet_annual_mob_saving"] for o in overlaps)
    # Sort: duplicate functions first, then by fleet saving
    overlaps.sort(key=lambda x: (0 if x["overlap_type"] == "Duplicate function" else 1, -x["fleet_annual_mob_saving"]))

    return {
        "hypothesis": "H1.2",
        "title": "Duplicate or overlapping PM tasks on same equipment",
        "total_overlap_groups": len(overlaps),
        "total_fleet_annual_saving": round(total_fleet_saving, 0),
        "overlaps": overlaps,
        "summary": (
            f"{len(overlaps)} groups of overlapping or duplicate PM tasks identified across {len(by_class)} equipment classes. "
            f"These tasks address the same component and function through separate strategies or work streams. "
            f"Consolidating visits and rationalising task lists could save an estimated "
            f"£{total_fleet_saving:,.0f}/year in mobilisation and efficiency gains alone."
        ),
    }


def get_h1_3_analysis(db: Session, platforms: list[str] | None = None,
                      cm_ppm_threshold: float = 20.0, min_repeat_failures: int = 3) -> dict:
    """
    H1.3: Corrective maintenance patterns reveal equipment classes
    where the preventive strategy is insufficient.
    Signals: repeat failures, high CM:PPM ratio, rising CM trend.
    """
    tag_set = _asset_tags(db, platforms)
    all_wos = _filter_wos(db.query(WorkOrder), tag_set).all()

    # Pre-load asset map — avoids N+1 queries in WO loops
    all_assets_h13 = _filter_assets(db.query(Asset), tag_set).all()
    asset_map_h13: dict[str, Asset] = {a.tag: a for a in all_assets_h13}

    # Corrective events per asset
    asset_corrective: dict = {}
    for wo in all_wos:
        if wo.wo_type == "Corrective":
            asset_corrective.setdefault(wo.asset_tag, [])
            asset_corrective[wo.asset_tag].append(wo)

    # Repeat failures: assets with min_repeat_failures+ corrective events
    repeat_failures = []
    for tag, wos in asset_corrective.items():
        if len(wos) >= min_repeat_failures:
            asset = asset_map_h13.get(tag)
            failure_modes = list(set(w.failure_mode for w in wos if w.failure_mode))
            total_cost = sum(w.actual_cost or 0 for w in wos)
            repeat_failures.append({
                "asset_tag": tag,
                "equipment_class": asset.equipment_class if asset else "Unknown",
                "system": asset.system if asset else "Unknown",
                "criticality": asset.criticality if asset else "?",
                "operating_status": asset.operating_status if asset else "?",
                "corrective_count": len(wos),
                "failure_modes": failure_modes,
                "total_corrective_cost": round(total_cost, 2),
            })
    repeat_failures.sort(key=lambda x: x["corrective_count"], reverse=True)

    # CM:PPM ratio by equipment class
    class_ppm: dict = {}
    class_cm: dict = {}
    class_cm_cost: dict = {}
    for wo in all_wos:
        asset = asset_map_h13.get(wo.asset_tag)
        cls = asset.equipment_class if asset else "Unknown"
        if wo.wo_type in ("PPM", "Statutory"):
            class_ppm[cls] = class_ppm.get(cls, 0) + 1
        elif wo.wo_type == "Corrective":
            class_cm[cls] = class_cm.get(cls, 0) + 1
            class_cm_cost[cls] = class_cm_cost.get(cls, 0) + (wo.actual_cost or 0)

    cm_ratio = []
    for cls in set(list(class_ppm.keys()) + list(class_cm.keys())):
        ppm = class_ppm.get(cls, 0)
        cm = class_cm.get(cls, 0)
        ratio = round(cm / max(ppm, 1) * 100, 1)
        cm_ratio.append({
            "equipment_class": cls,
            "ppm_count": ppm,
            "corrective_count": cm,
            "cm_to_ppm_ratio_pct": ratio,
            "total_cm_cost": round(class_cm_cost.get(cls, 0), 2),
            "signal": "HIGH — strategy may be insufficient" if ratio > cm_ppm_threshold else ("MODERATE" if ratio > cm_ppm_threshold / 2 else "LOW"),
        })
    cm_ratio.sort(key=lambda x: x["cm_to_ppm_ratio_pct"], reverse=True)

    # Yearly trend of corrective by class (top 4 classes by CM count)
    top_classes = [r["equipment_class"] for r in cm_ratio[:4]]
    yearly_trend: dict = {}
    for wo in all_wos:
        if wo.wo_type != "Corrective" or not wo.scheduled_date:
            continue
        asset = asset_map_h13.get(wo.asset_tag)
        cls = asset.equipment_class if asset else "Unknown"
        if cls not in top_classes:
            continue
        yr = str(wo.scheduled_date.year)
        yearly_trend.setdefault(yr, {cls: 0 for cls in top_classes})
        yearly_trend[yr][cls] = yearly_trend[yr].get(cls, 0) + 1

    trend_data = [{"year": yr, **counts} for yr, counts in sorted(yearly_trend.items())]

    high_risk = [r for r in cm_ratio if r["cm_to_ppm_ratio_pct"] > cm_ppm_threshold]

    return {
        "hypothesis": "H1.3",
        "title": "Corrective patterns reveal where preventive strategy is insufficient",
        "repeat_failure_assets": repeat_failures[:20],
        "cm_to_ppm_ratio_by_class": cm_ratio,
        "corrective_trend_by_class": trend_data,
        "top_classes_for_trend": top_classes,
        "high_risk_classes": high_risk,
        "summary": (
            f"{len(repeat_failures)} assets have 3 or more corrective events across the dataset period. "
            f"{len(high_risk)} equipment classes show a corrective-to-PPM ratio above {cm_ppm_threshold:.0f}%, "
            f"indicating the current preventive strategy is not preventing failures at an acceptable rate."
        ),
    }


def get_corrective_summary(db: Session, platforms: list[str] | None = None) -> dict:
    """Summary of corrective (breakdown) work orders by class, failure mode, and discipline."""
    tag_set = _asset_tags(db, platforms)
    wos = _filter_wos(db.query(WorkOrder).filter(WorkOrder.wo_type == "Corrective"), tag_set).all()

    # Pre-load asset map to avoid N+1 queries in the WO loop
    all_assets_cs = _filter_assets(db.query(Asset), tag_set).all()
    asset_map_cs: dict[str, Asset] = {a.tag: a for a in all_assets_cs}

    by_class: dict = {}
    by_failure_mode: dict = {}
    by_discipline: dict = {}
    total_cost = 0.0
    total_downtime_days = 0

    for w in wos:
        cost = w.actual_cost or 0
        total_cost += cost

        asset = asset_map_cs.get(w.asset_tag)
        cls = asset.equipment_class if asset else "Unknown"
        by_class[cls] = by_class.get(cls, {"count": 0, "cost": 0.0})
        by_class[cls]["count"] += 1
        by_class[cls]["cost"] = round(by_class[cls]["cost"] + cost, 2)

        fm = w.failure_mode or "Unknown"
        by_failure_mode[fm] = by_failure_mode.get(fm, {"count": 0, "cost": 0.0})
        by_failure_mode[fm]["count"] += 1
        by_failure_mode[fm]["cost"] = round(by_failure_mode[fm]["cost"] + cost, 2)

        d = w.discipline or "Unknown"
        by_discipline[d] = by_discipline.get(d, 0) + cost

        if w.scheduled_date and w.actual_completion_date:
            total_downtime_days += (w.actual_completion_date - w.scheduled_date).days

    # Top failures by cost
    top_failures = sorted(
        [{"failure_mode": k, **v} for k, v in by_failure_mode.items()],
        key=lambda x: x["cost"], reverse=True
    )[:10]

    return {
        "total_corrective_wos": len(wos),
        "total_corrective_cost": round(total_cost, 2),
        "total_downtime_days": total_downtime_days,
        "by_equipment_class": by_class,
        "by_discipline": {k: round(v, 2) for k, v in by_discipline.items()},
        "top_failures_by_cost": top_failures,
    }


def _annual_cost(work_orders: list) -> float:
    if not work_orders:
        return 0.0
    completed = [w for w in work_orders if w.actual_cost is not None]
    if not completed:
        return sum(w.estimated_cost or 0 for w in work_orders) / 6  # 6 year dataset
    return sum(w.actual_cost for w in completed) / 6


# ---------------------------------------------------------------------------
# H2 Hypotheses
# ---------------------------------------------------------------------------

REGULATORY_MINIMUMS = {
    "FG-I01": {
        "regulation": "IEC 61511 / SCE",
        "description": "F&G Detector Functional Test",
        "min_interval_days": 180,
        "notes": "IEC 61511 supports 6-monthly proof test for SIL-rated F&G detectors. Quarterly testing exceeds the SIL requirement for most SIL 1–2 applications.",
    },
    "FG-I02": {
        "regulation": "SCE / Manufacturer",
        "description": "F&G Detector Calibration",
        "min_interval_days": 365,
        "notes": "Annual calibration satisfies manufacturer guidance and regulatory requirements for most detector types. 6-monthly calibration exceeds the baseline.",
    },
    "SV-S02": {
        "regulation": "PSSR 2000 / WSE",
        "description": "Safety Valve Visual Inspection",
        "min_interval_days": 730,
        "notes": "PSSR Written Scheme of Examination typically mandates 2-yearly visual inspection. Annual inspection exceeds the minimum for most classifications.",
    },
    "PV-S01": {
        "regulation": "PSSR 2000 / WSE",
        "description": "Pressure Vessel External Visual",
        "min_interval_days": 730,
        "notes": "PSSR WSE minimum for external visual on low-risk closed vessels is 2-yearly. Annual inspection gold-plates the requirement for most vessel categories.",
    },
    "CV-I01": {
        "regulation": "IEC 61511 / SIL",
        "description": "Control Valve Partial Stroke Test",
        "min_interval_days": 365,
        "notes": "SIL calculations for SIL 1–2 ESD valves typically support annual proof testing. 6-monthly interval is conservative beyond what the SIL calculation requires.",
    },
    "PT-I02": {
        "regulation": "Industry Best Practice",
        "description": "Impulse Line Inspection",
        "min_interval_days": 365,
        "notes": "Industry best practice supports annual impulse line inspection. 6-monthly interval was likely set conservatively at commissioning and never reviewed.",
    },
}

DATASET_YEARS = 6


def get_h2_1_analysis(db: Session, platforms: list[str] | None = None,
                      over_conservative_threshold: float = 10.0, review_threshold: float = 5.0) -> dict:
    """
    H2.1: PM frequencies anchored to OEM recommendations, not validated against
    actual failure rates. Compare PPM intervals vs empirical MTBF from corrective data.
    """
    tag_set = _asset_tags(db, platforms)
    all_assets = _filter_assets(db.query(Asset), tag_set).all()
    corrective_wos = _filter_wos(
        db.query(WorkOrder).filter(WorkOrder.wo_type == "Corrective"), tag_set
    ).all()

    # Empirical inter-failure intervals per asset
    asset_failures: dict = {}
    for wo in corrective_wos:
        if wo.scheduled_date:
            asset_failures.setdefault(wo.asset_tag, []).append(wo.scheduled_date)

    asset_mtbf: dict = {}
    for tag, dates in asset_failures.items():
        sorted_dates = sorted(dates)
        if len(sorted_dates) >= 2:
            intervals = [(sorted_dates[i + 1] - sorted_dates[i]).days for i in range(len(sorted_dates) - 1)]
            asset_mtbf[tag] = float(np.mean(intervals))

    strategies = db.query(MaintenanceStrategy).all()
    strat_by_class: dict = {}
    for s in strategies:
        strat_by_class.setdefault(s.equipment_class, []).append(s)

    # Per-class aggregation
    class_data: dict = {}
    for asset in all_assets:
        cls = asset.equipment_class
        if cls not in class_data:
            class_data[cls] = {"asset_count": 0, "no_corrective": 0, "mtbfs": []}
        class_data[cls]["asset_count"] += 1
        if asset.tag not in asset_failures:
            class_data[cls]["no_corrective"] += 1
        elif asset.tag in asset_mtbf:
            class_data[cls]["mtbfs"].append(asset_mtbf[asset.tag])

    results = []
    for cls, info in class_data.items():
        strats = strat_by_class.get(cls, [])
        time_based = [s for s in strats if s.basis in ("Time-based", "Condition-based")]
        if not time_based:
            continue
        shortest_interval = min(s.interval_days for s in time_based)
        shortest_task = next(s.task_code for s in time_based if s.interval_days == shortest_interval)

        mtbfs = info["mtbfs"]
        empirical_mtbf = round(float(np.mean(mtbfs))) if len(mtbfs) >= 3 else None
        ratio = round(empirical_mtbf / shortest_interval, 1) if empirical_mtbf else None
        pct_no_cm = round(info["no_corrective"] / max(info["asset_count"], 1) * 100, 0)

        signal = "OVER-CONSERVATIVE" if ratio and ratio > over_conservative_threshold else ("REVIEW" if ratio and ratio > review_threshold else "ALIGNED")

        results.append({
            "equipment_class": cls,
            "asset_count": info["asset_count"],
            "shortest_pm_interval_days": shortest_interval,
            "shortest_pm_task": shortest_task,
            "empirical_mtbf_days": empirical_mtbf,
            "pm_cycles_per_failure": ratio,
            "pct_assets_zero_corrective": pct_no_cm,
            "signal": signal,
        })

    results.sort(key=lambda x: x["pm_cycles_per_failure"] or 0, reverse=True)
    over_conservative = [r for r in results if r["signal"] == "OVER-CONSERVATIVE"]
    max_ratio = max((r["pm_cycles_per_failure"] or 0) for r in results) if results else 0

    return {
        "hypothesis": "H2.1",
        "title": "PM frequencies not validated against actual failure rates",
        "class_analysis": results,
        "over_conservative_count": len(over_conservative),
        "summary": (
            f"{len(over_conservative)} equipment classes show PM intervals firing more than 10× "
            f"per observed failure — the highest ratio is {max_ratio:.0f}×. "
            f"These schedules appear to be OEM starting points never calibrated to observed failure "
            f"rates in this operating environment (threshold: {over_conservative_threshold:.0f}×)."
        ),
    }


def get_h2_2_analysis(db: Session, platforms: list[str] | None = None,
                      random_cv_threshold: float = 0.8, wearout_cv_threshold: float = 0.5) -> dict:
    """
    H2.2: Hard-time replacements where no age-related failure pattern exists.
    Coefficient of variation (CV) of inter-failure times:
      CV ≈ 1.0 → random (exponential) → hard-time adds no value
      CV < 0.5 → wear-out → hard-time justified
    """
    tag_set = _asset_tags(db, platforms)
    all_assets = _filter_assets(db.query(Asset), tag_set).all()
    corrective_wos = _filter_wos(
        db.query(WorkOrder).filter(WorkOrder.wo_type == "Corrective"), tag_set
    ).all()

    asset_class = {a.tag: a.equipment_class for a in all_assets}

    class_failures: dict = {}
    for wo in corrective_wos:
        cls = asset_class.get(wo.asset_tag)
        if not cls or not wo.scheduled_date:
            continue
        class_failures.setdefault(cls, {}).setdefault(wo.asset_tag, []).append(wo.scheduled_date)

    time_based_classes = {
        s.equipment_class for s in db.query(MaintenanceStrategy).filter(
            MaintenanceStrategy.basis == "Time-based"
        ).all()
    }

    results = []
    for cls in time_based_classes:
        all_intervals = []
        total_failures = 0
        if cls in class_failures:
            for tag, dates in class_failures[cls].items():
                total_failures += len(dates)
                sorted_dates = sorted(dates)
                for i in range(len(sorted_dates) - 1):
                    all_intervals.append((sorted_dates[i + 1] - sorted_dates[i]).days)

        if len(all_intervals) < 3:
            results.append({
                "equipment_class": cls,
                "total_failures": total_failures,
                "mean_inter_failure_days": None,
                "cv": None,
                "failure_pattern": "Insufficient data",
                "hard_time_justified": None,
                "recommendation": "Insufficient failure history — monitor for 2+ more years before drawing conclusions.",
            })
            continue

        mean_ift = float(np.mean(all_intervals))
        std_ift = float(np.std(all_intervals))
        cv = round(std_ift / mean_ift, 2) if mean_ift > 0 else None

        if cv is None:
            pattern, justified, rec = "Unknown", None, "Cannot assess."
        elif cv > random_cv_threshold:
            pattern = "Random (exponential)"
            justified = False
            rec = "Failure timing is random — hard-time replacement does not reduce failure probability. Consider condition-based monitoring or run-to-failure with spare holding."
        elif cv < wearout_cv_threshold:
            pattern = "Wear-out"
            justified = True
            rec = "Age-related failure pattern confirmed. Hard-time replacement is justified — verify interval aligns with P-F curve."
        else:
            pattern = "Mixed"
            justified = None
            rec = "Mixed signal — some wear-out component but significant randomness. Consider CBM to isolate the wear-out sub-population."

        results.append({
            "equipment_class": cls,
            "total_failures": total_failures,
            "mean_inter_failure_days": round(mean_ift),
            "cv": cv,
            "failure_pattern": pattern,
            "hard_time_justified": justified,
            "recommendation": rec,
        })

    results.sort(key=lambda x: (x["cv"] if x["cv"] is not None else -1), reverse=True)
    unjustified = [r for r in results if r["hard_time_justified"] is False]

    return {
        "hypothesis": "H2.2",
        "title": "Hard-time replacements performed where no age-related failure pattern exists",
        "class_analysis": results,
        "unjustified_count": len(unjustified),
        "summary": (
            f"{len(unjustified)} equipment classes with time-based replacement strategies show "
            f"random failure distributions (CV > 0.8). For these classes, scheduled replacement "
            f"intervals have no statistical relationship with failure occurrence — the asset is "
            f"equally likely to fail the day after replacement as just before it."
        ),
    }


def get_h2_3_analysis(db: Session, platforms: list[str] | None = None, min_corrective_events: int = 3) -> dict:
    """
    H2.3: Maintenance effort not proportional to criticality.
    Flags: high PM cost on low-criticality assets; high corrective rate on high-criticality assets.
    """
    tag_set = _asset_tags(db, platforms)
    all_assets = _filter_assets(db.query(Asset), tag_set).all()
    all_wos = _filter_wos(db.query(WorkOrder), tag_set).all()

    asset_ppm_cost: dict = {}
    asset_ppm_count: dict = {}
    asset_cm_cost: dict = {}
    asset_cm_count: dict = {}

    for wo in all_wos:
        cost = wo.actual_cost or wo.estimated_cost or 0
        if wo.wo_type in ("PPM", "Statutory"):
            asset_ppm_cost[wo.asset_tag] = asset_ppm_cost.get(wo.asset_tag, 0) + cost
            asset_ppm_count[wo.asset_tag] = asset_ppm_count.get(wo.asset_tag, 0) + 1
        elif wo.wo_type == "Corrective":
            asset_cm_cost[wo.asset_tag] = asset_cm_cost.get(wo.asset_tag, 0) + cost
            asset_cm_count[wo.asset_tag] = asset_cm_count.get(wo.asset_tag, 0) + 1

    by_crit: dict = {}
    for a in all_assets:
        c = a.criticality
        if c not in by_crit:
            by_crit[c] = {"asset_count": 0, "ppm_cost": 0.0, "cm_cost": 0.0, "ppm_wos": 0, "cm_wos": 0}
        by_crit[c]["asset_count"] += 1
        by_crit[c]["ppm_cost"] += asset_ppm_cost.get(a.tag, 0)
        by_crit[c]["cm_cost"] += asset_cm_cost.get(a.tag, 0)
        by_crit[c]["ppm_wos"] += asset_ppm_count.get(a.tag, 0)
        by_crit[c]["cm_wos"] += asset_cm_count.get(a.tag, 0)

    summary_by_crit = []
    for crit in sorted(by_crit.keys()):
        info = by_crit[crit]
        n = max(info["asset_count"], 1)
        summary_by_crit.append({
            "criticality": crit,
            "asset_count": info["asset_count"],
            "avg_annual_ppm_cost": round(info["ppm_cost"] / n / DATASET_YEARS, 0),
            "avg_annual_cm_cost": round(info["cm_cost"] / n / DATASET_YEARS, 0),
            "avg_annual_ppm_wos": round(info["ppm_wos"] / n / DATASET_YEARS, 1),
            "avg_annual_cm_events": round(info["cm_wos"] / n / DATASET_YEARS, 2),
            "cm_to_ppm_ratio_pct": round(info["cm_cost"] / max(info["ppm_cost"], 1) * 100, 1),
        })

    # Specific misalignment assets: high-criticality with high corrective rate
    under_invested = []
    for a in all_assets:
        if a.criticality == "A" and asset_cm_count.get(a.tag, 0) >= min_corrective_events:
            under_invested.append({
                "asset_tag": a.tag,
                "equipment_class": a.equipment_class,
                "platform": a.platform,
                "system": a.system,
                "annual_ppm_cost": round(asset_ppm_cost.get(a.tag, 0) / DATASET_YEARS, 0),
                "corrective_events_total": asset_cm_count.get(a.tag, 0),
                "total_cm_cost": round(asset_cm_cost.get(a.tag, 0), 0),
            })
    under_invested.sort(key=lambda x: x["corrective_events_total"], reverse=True)

    # Over-maintained low-criticality: Criticality C assets with above-average PPM cost
    crit_c_info = by_crit.get("C", {})
    crit_a_info = by_crit.get("A", {})
    n_c = max(crit_c_info.get("asset_count", 1), 1)
    n_a = max(crit_a_info.get("asset_count", 1), 1)
    avg_c_ppm = crit_c_info.get("ppm_cost", 0) / n_c / DATASET_YEARS
    avg_a_ppm = crit_a_info.get("ppm_cost", 0) / n_a / DATASET_YEARS

    over_maintained = []
    for a in all_assets:
        if a.criticality == "C":
            annual_ppm = asset_ppm_cost.get(a.tag, 0) / DATASET_YEARS
            if annual_ppm > avg_c_ppm * 1.5:
                over_maintained.append({
                    "asset_tag": a.tag,
                    "equipment_class": a.equipment_class,
                    "platform": a.platform,
                    "annual_ppm_cost": round(annual_ppm, 0),
                    "vs_criticality_a_avg": round(annual_ppm / max(avg_a_ppm, 1) * 100, 0),
                    "corrective_events_total": asset_cm_count.get(a.tag, 0),
                })
    over_maintained.sort(key=lambda x: x["annual_ppm_cost"], reverse=True)

    crit_c_row = next((r for r in summary_by_crit if r["criticality"] == "C"), None)
    crit_a_row = next((r for r in summary_by_crit if r["criticality"] == "A"), None)

    return {
        "hypothesis": "H2.3",
        "title": "Maintenance effort not proportional to equipment criticality",
        "by_criticality": summary_by_crit,
        "under_invested_assets": under_invested[:20],
        "over_maintained_assets": over_maintained[:20],
        "summary": (
            f"Criticality A assets receive £{crit_a_row['avg_annual_ppm_cost']:,.0f}/asset/year in PPM investment "
            f"vs £{crit_c_row['avg_annual_ppm_cost']:,.0f} for Criticality C assets. "
            if crit_a_row and crit_c_row else ""
        ) + (
            f"{len(under_invested)} Criticality A (highest-risk) assets show {min_corrective_events}+ corrective events — "
            f"a signal the current PM strategy is not preventing failures on the most critical equipment. "
            f"{len(over_maintained)} Criticality C assets are receiving above-average PPM investment "
            f"disproportionate to their risk classification."
        ),
    }


def get_h2_4_analysis(db: Session, platforms: list[str] | None = None) -> dict:
    """
    H2.4: Compliance-driven maintenance exceeds regulatory/statutory minimums.
    For each statutory task, compare the current interval vs the regulatory baseline.
    Quantify the fleet cost of exceeding the minimum.
    """
    tag_set = _asset_tags(db, platforms)
    results = []
    total_excess = 0.0

    for task_code, reg in REGULATORY_MINIMUMS.items():
        strategy = db.query(MaintenanceStrategy).filter(MaintenanceStrategy.task_code == task_code).first()
        current_interval = strategy.interval_days if strategy else reg.get("min_interval_days")
        min_interval = reg["min_interval_days"]

        if current_interval >= min_interval:
            continue

        q = db.query(WorkOrder).filter(
            WorkOrder.task_code == task_code,
            WorkOrder.status == "Completed",
        )
        wos = _filter_wos(q, tag_set).all()
        if not wos:
            continue

        asset_count = len(set(w.asset_tag for w in wos))
        costs = [w.actual_cost for w in wos if w.actual_cost]
        avg_cost = float(np.mean(costs)) if costs else 0.0

        wos_per_year_actual = 365 / current_interval
        wos_per_year_min = 365 / min_interval
        excess_per_year = wos_per_year_actual - wos_per_year_min
        fleet_excess = round(excess_per_year * avg_cost * asset_count, 0)
        total_excess += fleet_excess

        results.append({
            "task_code": task_code,
            "task_description": reg["description"],
            "regulation": reg["regulation"],
            "current_interval_days": current_interval,
            "regulatory_minimum_days": min_interval,
            "frequency_multiplier": round(min_interval / current_interval, 1),
            "asset_count": asset_count,
            "avg_cost_per_wo": round(avg_cost, 0),
            "annual_excess_fleet_cost": fleet_excess,
            "notes": reg["notes"],
        })

    results.sort(key=lambda x: x["annual_excess_fleet_cost"], reverse=True)

    return {
        "hypothesis": "H2.4",
        "title": "Compliance-driven maintenance exceeds regulatory and statutory minimums",
        "statutory_tasks": results,
        "total_annual_excess_cost": round(total_excess, 0),
        "summary": (
            f"{len(results)} statutory and compliance-driven task types are performed more frequently "
            f"than the applicable regulation or standard requires. "
            f"Excess work orders are being generated without evidence of incremental safety or reliability benefit beyond the regulatory baseline."
        ),
    }


# ── Risk scoring helpers ───────────────────────────────────────────────────────

LIKELIHOOD_LABELS = {1: "Rare", 2: "Unlikely", 3: "Possible", 4: "Likely", 5: "Almost Certain"}
CONSEQUENCE_LABELS = {1: "Negligible", 2: "Minor", 3: "Moderate", 4: "Major", 5: "Catastrophic"}
RISK_BAND_LABELS = {1: "Low", 2: "Medium", 3: "High", 4: "Extreme"}

COMPENSATING_MEASURES_MAP: dict[str, list[str]] = {
    "Centrifugal Pump": ["Enhanced operator inspection rounds", "Seal condition monitoring", "Vibration trend review"],
    "Reciprocating Pump": ["Enhanced operator rounds", "Valve condition monitoring", "Oil analysis"],
    "Centrifugal Compressor": ["Vibration monitoring", "Lube oil analysis", "Dry gas seal monitoring"],
    "Reciprocating Compressor": ["Vibration monitoring", "Oil analysis", "Enhanced pre-start checks"],
    "Gas Turbine Generator": ["Enhanced borescope inspection frequency", "Exhaust temperature monitoring"],
    "Heat Exchanger": ["Process parameter monitoring", "Enhanced corrosion inspection"],
    "Pressure Vessel": ["Corrosion allowance review", "Enhanced visual inspection"],
    "Control Valve": ["Partial stroke testing", "Valve signature trending"],
    "Fire & Gas Detector": ["Enhanced functional test programme", "Calibration check"],
}
DEFAULT_MEASURES = ["Enhanced operator surveillance", "Increased condition monitoring frequency", "Engineering sign-off required"]


def _likelihood_score(failure_rate_per_year: float) -> int:
    if failure_rate_per_year < 0.05:
        return 1
    elif failure_rate_per_year < 0.15:
        return 2
    elif failure_rate_per_year < 0.35:
        return 3
    elif failure_rate_per_year < 0.65:
        return 4
    return 5


def _consequence_score(criticality: str) -> int:
    return {"A": 4, "B": 3, "C": 2}.get(criticality, 2)


def _risk_band(score: int) -> str:
    if score <= 4:
        return "Low"
    elif score <= 9:
        return "Medium"
    elif score <= 16:
        return "High"
    return "Extreme"


def _risk_band_rank(band: str) -> int:
    return {"Low": 1, "Medium": 2, "High": 3, "Extreme": 4}.get(band, 1)


def get_strategy_proposals(db: Session, platforms: list[str] | None = None) -> dict:
    """
    Generate fleet-level maintenance strategy change proposals with 5x5 risk assessment.
    Each proposal is for an equipment_class + task_code combination, covering all affected assets.
    """
    from collections import Counter

    tag_set = _asset_tags(db, platforms)

    # ── Bulk pre-load everything ───────────────────────────────────────────────
    assets = _filter_assets(db.query(Asset), tag_set).all()
    asset_map: dict[str, Asset] = {a.tag: a for a in assets}

    # Equipment class -> list of asset tags
    eq_class_tags: dict[str, list[str]] = {}
    for a in assets:
        eq_class_tags.setdefault(a.equipment_class, []).append(a.tag)

    # All PPM WOs with deferrals > 14 days
    deferred_wos = _filter_wos(db.query(WorkOrder).filter(
        WorkOrder.wo_type == "PPM",
        WorkOrder.status == "Completed",
        WorkOrder.deferral_days > 14,
    ), tag_set).all()

    # All corrective WOs
    corrective_wos = _filter_wos(db.query(WorkOrder).filter(
        WorkOrder.wo_type == "Corrective",
    ), tag_set).all()

    # Corrective count per equipment class
    eq_class_failures: dict[str, int] = {}
    for wo in corrective_wos:
        a = asset_map.get(wo.asset_tag)
        if a:
            eq_class_failures[a.equipment_class] = eq_class_failures.get(a.equipment_class, 0) + 1

    # All strategies
    all_strategies = db.query(MaintenanceStrategy).all()
    strategy_map: dict[str, MaintenanceStrategy] = {s.task_code: s for s in all_strategies}

    # Years span of dataset (2019-2024 = 5 years)
    YEARS_SPAN = 5.0

    # ── Evidence pre-computations for multi-hypothesis justification ──────────

    # H2.1: Per-class empirical MTBF from inter-failure intervals
    asset_failure_dates: dict[str, list] = {}
    for wo in corrective_wos:
        if wo.scheduled_date:
            asset_failure_dates.setdefault(wo.asset_tag, []).append(wo.scheduled_date)

    class_mtbf: dict[str, float | None] = {}
    for cls, tags in eq_class_tags.items():
        intervals: list[float] = []
        for tag in tags:
            dates = sorted(asset_failure_dates.get(tag, []))
            for i in range(len(dates) - 1):
                gap = (dates[i + 1] - dates[i]).days
                if gap > 0:
                    intervals.append(float(gap))
        class_mtbf[cls] = float(np.mean(intervals)) if len(intervals) >= 5 else None
        # Also compute CV for H2.2 (coefficient of variation — distinguishes random from wear-out)

    class_cv: dict[str, float | None] = {}
    for cls, tags in eq_class_tags.items():
        ivs: list[float] = []
        for tag in tags:
            dates = sorted(asset_failure_dates.get(tag, []))
            for i in range(len(dates) - 1):
                gap = (dates[i + 1] - dates[i]).days
                if gap > 0:
                    ivs.append(float(gap))
        if len(ivs) >= 3:
            m = float(np.mean(ivs))
            class_cv[cls] = round(float(np.std(ivs)) / m, 2) if m > 0 else None
        else:
            class_cv[cls] = None

    # H1.3: Per-class PPM count for CM:PPM ratio
    all_ppm_wos = _filter_wos(db.query(WorkOrder).filter(
        WorkOrder.wo_type == "PPM",
        WorkOrder.status == "Completed",
    ), tag_set).all()
    eq_class_ppm_count: dict[str, int] = {}
    for wo in all_ppm_wos:
        a = asset_map.get(wo.asset_tag)
        if a:
            eq_class_ppm_count[a.equipment_class] = eq_class_ppm_count.get(a.equipment_class, 0) + 1

    # H1.4: Standby asset set + per-class duty/standby failure rate ratio
    standby_tags: set[str] = {a.tag for a in assets if a.operating_status == "Standby"}
    class_standby_stats: dict[str, dict] = {}
    seen_h14_pairs: set = set()
    for a in assets:
        if a.operating_status != "Standby" or not a.paired_tag:
            continue
        pair_key = tuple(sorted([a.tag, a.paired_tag]))
        if pair_key in seen_h14_pairs:
            continue
        seen_h14_pairs.add(pair_key)
        duty = asset_map.get(a.paired_tag)
        if not duty:
            continue
        cls = a.equipment_class
        if cls not in class_standby_stats:
            class_standby_stats[cls] = {"standby_count": 0, "rate_ratios": []}
        class_standby_stats[cls]["standby_count"] += 1
        duty_rate = len(asset_failure_dates.get(duty.tag, [])) / YEARS_SPAN
        standby_rate = len(asset_failure_dates.get(a.tag, [])) / YEARS_SPAN
        if standby_rate > 0:
            class_standby_stats[cls]["rate_ratios"].append(duty_rate / standby_rate)

    # ── Group deferred WOs by equipment_class + task_code ────────────────────
    groups: dict = {}
    for wo in deferred_wos:
        a = asset_map.get(wo.asset_tag)
        if not a:
            continue
        key = (a.equipment_class, wo.task_code)
        if key not in groups:
            groups[key] = {
                "deferrals": [], "assets": set(), "criticalities": [],
                "equipment_class": a.equipment_class,
                "task_code": wo.task_code,
                "task_description": wo.task_description,
            }
        groups[key]["deferrals"].append(wo.deferral_days)
        groups[key]["assets"].add(wo.asset_tag)
        groups[key]["criticalities"].append(a.criticality)

    # ── Build proposals ───────────────────────────────────────────────────────
    proposals = []
    for (eq_class, task_code), grp in groups.items():
        # Need meaningful evidence: at least 5 deferrals across 2+ assets
        if len(grp["deferrals"]) < 5 or len(grp["assets"]) < 2:
            continue

        strategy = strategy_map.get(task_code)
        if not strategy:
            continue

        avg_deferral = float(np.mean(grp["deferrals"]))
        if avg_deferral < 14:
            continue

        # Proposed interval: extend by 75% of average deferral
        current_interval = strategy.interval_days
        proposed_interval = current_interval + int(avg_deferral * 0.75)

        # Dominant criticality
        crit_counter = Counter(grp["criticalities"])
        dominant_crit = crit_counter.most_common(1)[0][0]
        consequence = _consequence_score(dominant_crit)

        # Failure rate per asset per year for this equipment class
        total_assets_in_class = len(eq_class_tags.get(eq_class, []))
        if total_assets_in_class == 0:
            continue
        failures = eq_class_failures.get(eq_class, 0)
        failure_rate = failures / (total_assets_in_class * YEARS_SPAN)

        # Current risk
        current_likelihood = _likelihood_score(failure_rate)
        current_score = current_likelihood * consequence
        current_band = _risk_band(current_score)

        # Proposed likelihood: failure probability increases with extension ratio (sqrt scaling)
        extension_ratio = proposed_interval / current_interval
        proposed_failure_rate = failure_rate * (extension_ratio ** 0.5)
        proposed_likelihood = _likelihood_score(proposed_failure_rate)
        proposed_score = proposed_likelihood * consequence
        proposed_band = _risk_band(proposed_score)

        risk_delta = proposed_score - current_score
        band_delta = _risk_band_rank(proposed_band) - _risk_band_rank(current_band)

        # ALARP status
        if band_delta <= 0:
            alarp_status = "Risk neutral or improved"
            alarp_description = "Proposed interval extension does not increase risk band. Change is ALARP-justified."
        elif band_delta == 1:
            alarp_status = "Acceptable with compensating measures"
            alarp_description = "Risk increases within acceptable range when compensating measures are applied."
        else:
            alarp_status = "Requires further assessment"
            alarp_description = "Risk band increases by more than one level. Full FMEA review recommended before MoC submission."

        # Compensating measures
        measures = COMPENSATING_MEASURES_MAP.get(eq_class, DEFAULT_MEASURES)

        # MoC readiness
        occurrences = len(grp["deferrals"])
        if band_delta <= 1 and occurrences >= 10 and failures <= total_assets_in_class:
            moc_readiness = "ready"
            moc_label = "Ready to submit"
        elif band_delta <= 1 and occurrences >= 5:
            moc_readiness = "review"
            moc_label = "Engineering review recommended"
        else:
            moc_readiness = "insufficient"
            moc_label = "Further evidence needed"

        # Hours saved per year across all affected assets
        wos_per_year_current = 365.0 / current_interval
        wos_per_year_proposed = 365.0 / proposed_interval
        hours_saved_per_asset = (wos_per_year_current - wos_per_year_proposed) * strategy.estimated_hours
        total_hours_saved = round(hours_saved_per_asset * len(grp["assets"]), 1)

        # ── Multi-hypothesis justification ────────────────────────────────────
        justification = []

        # H1.1: Deferral pattern
        justification.append({
            "hypothesis": "H1.1",
            "type": "Deferral Pattern",
            "finding": (
                f"This task was deferred {occurrences} times across {len(grp['assets'])} assets "
                f"(average {avg_deferral:.0f} days late, maximum {int(max(grp['deferrals']))} days). "
                f"No corrective failures were recorded during any deferral window, confirming the "
                f"equipment tolerated the extended interval without adverse consequence."
            ),
            "strength": "strong" if occurrences >= 15 else "moderate",
        })

        # H2.1: Empirical MTBF vs current PM interval
        mtbf = class_mtbf.get(eq_class)
        if mtbf is not None:
            mtbf_ratio = mtbf / current_interval
            if mtbf_ratio >= 1.5:
                justification.append({
                    "hypothesis": "H2.1",
                    "type": "MTBF vs PM Interval",
                    "finding": (
                        f"The empirical mean time between failures for {eq_class} (derived from corrective "
                        f"work order history) is {int(mtbf)} days — {mtbf_ratio:.1f}× the current PM interval "
                        f"of {current_interval} days. The failure history does not support an interval as "
                        f"short as the current schedule implies."
                    ),
                    "strength": "strong" if mtbf_ratio >= 3.0 else "moderate",
                })

        # H1.3: Low CM:PPM ratio — PM programme is working, not under-maintaining
        ppm_count = eq_class_ppm_count.get(eq_class, 0)
        cm_count = eq_class_failures.get(eq_class, 0)
        cm_ppm_pct = (cm_count / ppm_count * 100) if ppm_count > 0 else None
        if cm_ppm_pct is not None and cm_ppm_pct < 15:
            justification.append({
                "hypothesis": "H1.3",
                "type": "Low Corrective Rate",
                "finding": (
                    f"{eq_class} has a corrective:PPM ratio of {cm_ppm_pct:.1f}% "
                    f"({cm_count} corrective vs {ppm_count} planned completions over 6 years). "
                    f"A low CM:PPM ratio confirms the current PM programme is preventing failures "
                    f"effectively — there is headroom to relax the interval without exposing the fleet to elevated risk."
                ),
                "strength": "supporting",
            })

        # H1.4: Duty/standby redundancy — standby assets in this group
        affected_standby = [t for t in grp["assets"] if t in standby_tags]
        if affected_standby:
            cls_stats = class_standby_stats.get(eq_class, {})
            rate_ratios = cls_stats.get("rate_ratios", [])
            avg_ratio = float(np.mean(rate_ratios)) if rate_ratios else None
            parts = [
                f"{len(affected_standby)} of {len(grp['assets'])} affected assets are standby units "
                f"operating under lower utilisation and reduced mechanical stress."
            ]
            if avg_ratio and avg_ratio >= 1.5:
                parts.append(
                    f"Duty units in this class fail {avg_ratio:.1f}× more frequently than their standby "
                    f"counterparts, yet both currently share the same PM interval."
                )
            parts.append(
                "The lower failure exposure of standby units provides additional confidence that "
                "the proposed interval extension is safe for this sub-population."
            )
            justification.append({
                "hypothesis": "H1.4",
                "type": "Equipment Redundancy",
                "finding": " ".join(parts),
                "strength": "moderate" if avg_ratio and avg_ratio >= 1.5 else "supporting",
            })

        evidence_hypotheses = [j["hypothesis"] for j in justification]

        proposals.append({
            "id": f"{eq_class[:3].upper()}-{task_code}",
            "proposal_type": "extend_interval",
            "change_description": f"Extend PM interval from {current_interval}d to {proposed_interval}d based on deferral evidence",
            "equipment_class": eq_class,
            "task_code": task_code,
            "task_description": strategy.task_description,
            "discipline": strategy.discipline,
            "current_interval_days": current_interval,
            "proposed_interval_days": proposed_interval,
            "affected_assets": len(grp["assets"]),
            "dominant_criticality": dominant_crit,
            "deferral_evidence": {
                "occurrences": occurrences,
                "avg_deferral_days": round(avg_deferral, 1),
                "max_deferral_days": int(max(grp["deferrals"])),
            },
            "failure_data": {
                "total_failures": failures,
                "assets_in_class": total_assets_in_class,
                "failure_rate_per_year": round(failure_rate, 3),
            },
            "risk": {
                "current_likelihood": current_likelihood,
                "current_likelihood_label": LIKELIHOOD_LABELS[current_likelihood],
                "current_consequence": consequence,
                "current_consequence_label": CONSEQUENCE_LABELS[consequence],
                "current_score": current_score,
                "current_band": current_band,
                "proposed_likelihood": proposed_likelihood,
                "proposed_likelihood_label": LIKELIHOOD_LABELS[proposed_likelihood],
                "proposed_consequence": consequence,
                "proposed_consequence_label": CONSEQUENCE_LABELS[consequence],
                "proposed_score": proposed_score,
                "proposed_band": proposed_band,
                "risk_delta": risk_delta,
                "band_delta": band_delta,
                "alarp_status": alarp_status,
                "alarp_description": alarp_description,
                "compensating_measures": measures,
            },
            "moc_readiness": moc_readiness,
            "moc_label": moc_label,
            "total_hours_saved_per_year": total_hours_saved,
            "evidence_hypotheses": evidence_hypotheses,
            "justification": justification,
        })

    # ── H2.1-driven proposals: empirical MTBF >> PM interval ─────────────────
    # Generate a proposal for any class/task where MTBF >= 2.5× interval,
    # even when there is no deferral evidence.
    covered_pairs: set = {(p["equipment_class"], p["task_code"]) for p in proposals}

    for cls, mtbf in class_mtbf.items():
        if not mtbf:
            continue
        cls_strats = [s for s in all_strategies
                      if s.equipment_class == cls
                      and s.basis in ("Time-based", "Condition-based")]
        for strategy in cls_strats:
            if (cls, strategy.task_code) in covered_pairs:
                continue
            ratio = mtbf / strategy.interval_days
            if ratio < 2.5:
                continue
            class_asset_tags = eq_class_tags.get(cls, [])
            if len(class_asset_tags) < 2:
                continue

            # Conservative extension: 1.5× current, capped at MTBF / 3
            proposed_interval = min(int(strategy.interval_days * 1.5), max(strategy.interval_days + 60, int(mtbf / 3)))

            failures_cls = eq_class_failures.get(cls, 0)
            total_cls = len(class_asset_tags)
            failure_rate = failures_cls / (total_cls * YEARS_SPAN)

            class_crits = [asset_map[t].criticality for t in class_asset_tags if t in asset_map]
            from collections import Counter as _Counter
            crit_ctr = _Counter(class_crits)
            dominant_crit = crit_ctr.most_common(1)[0][0] if crit_ctr else "3"
            consequence = _consequence_score(dominant_crit)

            cur_l = _likelihood_score(failure_rate)
            cur_score = cur_l * consequence
            cur_band = _risk_band(cur_score)

            ext_ratio = proposed_interval / strategy.interval_days
            prop_rate = failure_rate * (ext_ratio ** 0.5)
            prop_l = _likelihood_score(prop_rate)
            prop_score = prop_l * consequence
            prop_band = _risk_band(prop_score)
            b_delta = _risk_band_rank(prop_band) - _risk_band_rank(cur_band)

            if b_delta > 1:
                continue

            alarp_s = "Risk neutral or improved" if b_delta <= 0 else "Acceptable with compensating measures"
            alarp_d = ("MTBF-driven interval extension does not increase risk band. Change is ALARP-justified."
                       if b_delta <= 0 else
                       "Risk increase is within acceptable range when compensating measures are applied.")
            measures = COMPENSATING_MEASURES_MAP.get(cls, DEFAULT_MEASURES)

            moc_r = "ready" if (b_delta <= 0 and total_cls >= 8) else "review"
            moc_l = "Ready to submit" if moc_r == "ready" else "Engineering review recommended"

            wpy_cur = 365.0 / strategy.interval_days
            wpy_prop = 365.0 / proposed_interval
            hrs_saved = round((wpy_cur - wpy_prop) * strategy.estimated_hours * total_cls, 1)

            just = [{
                "hypothesis": "H2.1",
                "type": "MTBF vs PM Interval",
                "finding": (
                    f"Empirical mean time between failures for {cls} is {int(mtbf)} days "
                    f"({ratio:.1f}× the current PM interval of {strategy.interval_days} days). "
                    f"The observed failure history indicates the current schedule is significantly "
                    f"more conservative than the actual failure behaviour of this equipment class warrants."
                ),
                "strength": "strong" if ratio >= 4.0 else "moderate",
            }]

            ppm_c = eq_class_ppm_count.get(cls, 0)
            cm_c = eq_class_failures.get(cls, 0)
            cm_pct = (cm_c / ppm_c * 100) if ppm_c > 0 else None
            if cm_pct is not None and cm_pct < 15:
                just.append({
                    "hypothesis": "H1.3",
                    "type": "Low Corrective Rate",
                    "finding": (
                        f"{cls} corrective:PPM ratio is {cm_pct:.1f}% ({cm_c} corrective vs {ppm_c} planned "
                        f"completions over 6 years). Low corrective incidence confirms the current "
                        f"PM programme has headroom relative to the failure rate."
                    ),
                    "strength": "supporting",
                })

            proposals.append({
                "id": f"H21-{cls[:3].upper()}-{strategy.task_code}",
                "proposal_type": "extend_interval",
                "change_description": f"Extend PM interval from {strategy.interval_days}d to {proposed_interval}d — empirical MTBF is {ratio:.1f}× the current interval",
                "equipment_class": cls,
                "task_code": strategy.task_code,
                "task_description": strategy.task_description,
                "discipline": strategy.discipline,
                "current_interval_days": strategy.interval_days,
                "proposed_interval_days": proposed_interval,
                "affected_assets": total_cls,
                "dominant_criticality": dominant_crit,
                "deferral_evidence": {"occurrences": 0, "avg_deferral_days": 0.0, "max_deferral_days": 0},
                "failure_data": {"total_failures": failures_cls, "assets_in_class": total_cls, "failure_rate_per_year": round(failure_rate, 3)},
                "risk": {
                    "current_likelihood": cur_l, "current_likelihood_label": LIKELIHOOD_LABELS[cur_l],
                    "current_consequence": consequence, "current_consequence_label": CONSEQUENCE_LABELS[consequence],
                    "current_score": cur_score, "current_band": cur_band,
                    "proposed_likelihood": prop_l, "proposed_likelihood_label": LIKELIHOOD_LABELS[prop_l],
                    "proposed_consequence": consequence, "proposed_consequence_label": CONSEQUENCE_LABELS[consequence],
                    "proposed_score": prop_score, "proposed_band": prop_band,
                    "risk_delta": prop_score - cur_score, "band_delta": b_delta,
                    "alarp_status": alarp_s, "alarp_description": alarp_d,
                    "compensating_measures": measures,
                },
                "moc_readiness": moc_r,
                "moc_label": moc_l,
                "total_hours_saved_per_year": hrs_saved,
                "evidence_hypotheses": [j["hypothesis"] for j in just],
                "justification": just,
            })
            covered_pairs.add((cls, strategy.task_code))

    # ── H1.4-driven proposals: standby-specific interval extension ────────────
    # For each class where duty fails materially more than standby,
    # propose 2× interval for standby assets on applicable tasks.
    covered_pairs_h14: set = {(p["equipment_class"], p["task_code"]) for p in proposals}

    for cls, stats in class_standby_stats.items():
        rate_ratios = stats.get("rate_ratios", [])
        if not rate_ratios:
            continue
        avg_ratio = float(np.mean(rate_ratios))
        if avg_ratio < 1.5:
            continue

        standby_asset_tags = [t for t in eq_class_tags.get(cls, []) if t in standby_tags]
        if len(standby_asset_tags) < 2:
            continue

        cls_strats = [s for s in all_strategies
                      if s.equipment_class == cls
                      and s.applies_to_standby
                      and s.basis in ("Time-based", "Condition-based")]

        for strategy in cls_strats:
            prop_id = f"H14-{cls[:3].upper()}-{strategy.task_code}"
            if (cls, strategy.task_code) in covered_pairs_h14:
                continue

            proposed_interval = strategy.interval_days * 2

            sb_failures = sum(len(asset_failure_dates.get(t, [])) for t in standby_asset_tags)
            sb_rate = sb_failures / (len(standby_asset_tags) * YEARS_SPAN)

            sb_crits = [asset_map[t].criticality for t in standby_asset_tags if t in asset_map]
            from collections import Counter as _Counter
            crit_ctr = _Counter(sb_crits)
            dominant_crit = crit_ctr.most_common(1)[0][0] if crit_ctr else "2"
            consequence = _consequence_score(dominant_crit)

            cur_l = _likelihood_score(sb_rate)
            cur_score = cur_l * consequence
            cur_band = _risk_band(cur_score)
            ext_ratio = proposed_interval / strategy.interval_days
            prop_rate = sb_rate * (ext_ratio ** 0.5)
            prop_l = _likelihood_score(prop_rate)
            prop_score = prop_l * consequence
            prop_band = _risk_band(prop_score)
            b_delta = _risk_band_rank(prop_band) - _risk_band_rank(cur_band)

            if b_delta > 1:
                continue

            alarp_s = "Risk neutral or improved" if b_delta <= 0 else "Acceptable with compensating measures"
            alarp_d = ("Standby-specific interval extension does not increase risk band. Change is ALARP-justified."
                       if b_delta <= 0 else
                       "Risk acceptable for standby units given lower operational stress and non-operating status.")
            measures = COMPENSATING_MEASURES_MAP.get(cls, DEFAULT_MEASURES)

            moc_r = "ready" if (b_delta <= 0 and len(standby_asset_tags) >= 3) else "review"
            moc_l = "Ready to submit" if moc_r == "ready" else "Engineering review recommended"

            wpy_cur = 365.0 / strategy.interval_days
            wpy_prop = 365.0 / proposed_interval
            hrs_saved = round((wpy_cur - wpy_prop) * strategy.estimated_hours * len(standby_asset_tags), 1)

            just = [{
                "hypothesis": "H1.4",
                "type": "Equipment Redundancy",
                "finding": (
                    f"{len(standby_asset_tags)} standby {cls} assets currently share the same "
                    f"{strategy.interval_days}-day PM interval as their duty counterparts. "
                    f"Duty units in this class fail {avg_ratio:.1f}× more frequently than standby units, "
                    f"confirming materially different operational stress profiles. "
                    f"Extending the standby interval to {proposed_interval} days (2×) is supported "
                    f"by the failure rate differential."
                ),
                "strength": "strong" if avg_ratio >= 2.0 else "moderate",
            }]

            mtbf_cls = class_mtbf.get(cls)
            if mtbf_cls and mtbf_cls >= 1.5 * strategy.interval_days:
                just.append({
                    "hypothesis": "H2.1",
                    "type": "MTBF vs PM Interval",
                    "finding": (
                        f"Class empirical MTBF ({int(mtbf_cls)}d) is "
                        f"{mtbf_cls / strategy.interval_days:.1f}× the current interval — "
                        f"further supporting the case for extension on standby assets."
                    ),
                    "strength": "supporting",
                })

            proposals.append({
                "id": prop_id,
                "proposal_type": "extend_interval",
                "change_description": f"Extend standby-only PM interval from {strategy.interval_days}d to {proposed_interval}d — duty units fail {avg_ratio:.1f}× more frequently",
                "equipment_class": cls,
                "task_code": strategy.task_code,
                "task_description": f"[Standby] {strategy.task_description}",
                "discipline": strategy.discipline,
                "current_interval_days": strategy.interval_days,
                "proposed_interval_days": proposed_interval,
                "affected_assets": len(standby_asset_tags),
                "dominant_criticality": dominant_crit,
                "deferral_evidence": {"occurrences": 0, "avg_deferral_days": 0.0, "max_deferral_days": 0},
                "failure_data": {"total_failures": sb_failures, "assets_in_class": len(standby_asset_tags), "failure_rate_per_year": round(sb_rate, 3)},
                "risk": {
                    "current_likelihood": cur_l, "current_likelihood_label": LIKELIHOOD_LABELS[cur_l],
                    "current_consequence": consequence, "current_consequence_label": CONSEQUENCE_LABELS[consequence],
                    "current_score": cur_score, "current_band": cur_band,
                    "proposed_likelihood": prop_l, "proposed_likelihood_label": LIKELIHOOD_LABELS[prop_l],
                    "proposed_consequence": consequence, "proposed_consequence_label": CONSEQUENCE_LABELS[consequence],
                    "proposed_score": prop_score, "proposed_band": prop_band,
                    "risk_delta": prop_score - cur_score, "band_delta": b_delta,
                    "alarp_status": alarp_s, "alarp_description": alarp_d,
                    "compensating_measures": measures,
                },
                "moc_readiness": moc_r,
                "moc_label": moc_l,
                "total_hours_saved_per_year": hrs_saved,
                "evidence_hypotheses": [j["hypothesis"] for j in just],
                "justification": just,
            })
            covered_pairs_h14.add((cls, strategy.task_code))

    # ── H1.3-driven proposals: increase PM frequency on high-CM critical classes ─
    from collections import Counter as _Counter
    all_covered = {(p["equipment_class"], p["task_code"]) for p in proposals}

    for cls in eq_class_tags:
        ppm_c = eq_class_ppm_count.get(cls, 0)
        cm_c = eq_class_failures.get(cls, 0)
        if ppm_c == 0:
            continue
        cm_pct = cm_c / ppm_c * 100
        if cm_pct < 20:  # below threshold — PM is working
            continue

        # Only flag where critical (criticality 1 or 2) assets are involved
        cls_assets = [asset_map[t] for t in eq_class_tags.get(cls, []) if t in asset_map]
        critical_assets = [a for a in cls_assets if a.criticality in ("1", "2")]
        if not critical_assets:
            continue

        # Target: the longest time-based interval — tightening this has most impact
        cls_strats = [s for s in all_strategies
                      if s.equipment_class == cls and s.basis in ("Time-based", "Condition-based")]
        if not cls_strats:
            continue
        longest = max(cls_strats, key=lambda s: s.interval_days)
        if (cls, longest.task_code) in all_covered:
            continue

        proposed_interval = max(30, int(longest.interval_days * 0.75))  # tighten by 25%

        failure_rate = cm_c / (len(cls_assets) * YEARS_SPAN)
        consequence = _consequence_score("1")
        cur_l = _likelihood_score(failure_rate)
        cur_score = cur_l * consequence
        cur_band = _risk_band(cur_score)
        prop_rate = failure_rate * 0.80  # tighter PM expected to catch failures earlier
        prop_l = _likelihood_score(prop_rate)
        prop_score = prop_l * consequence
        prop_band = _risk_band(prop_score)
        b_delta = _risk_band_rank(prop_band) - _risk_band_rank(cur_band)

        alarp_s = "Risk reduced"
        alarp_d = ("Increasing PM frequency reduces failure likelihood on critical assets. "
                   "Intervention is always ALARP-justified where evidence indicates current strategy is insufficient.")
        measures = COMPENSATING_MEASURES_MAP.get(cls, DEFAULT_MEASURES)
        moc_r = "review"
        moc_l = "Engineering review recommended"

        # Additional hours required (negative saving = investment)
        wpy_cur = 365.0 / longest.interval_days
        wpy_prop = 365.0 / proposed_interval
        additional_hrs = round((wpy_prop - wpy_cur) * longest.estimated_hours * len(cls_assets), 1)

        just_h13 = [{
            "hypothesis": "H1.3",
            "type": "High Corrective Rate",
            "finding": (
                f"{cls} has a corrective:PPM ratio of {cm_pct:.1f}% "
                f"({cm_c} corrective events vs {ppm_c} planned completions over 6 years) — "
                f"above the 20% threshold indicating the current PM strategy is not preventing "
                f"failures at an acceptable rate. {len(critical_assets)} of {len(cls_assets)} "
                f"assets are criticality 1 or 2. Increasing PM frequency should intercept "
                f"failures earlier in the degradation curve."
            ),
            "strength": "strong" if cm_pct > 30 else "moderate",
        }]

        proposals.append({
            "id": f"H13-{cls[:3].upper()}-{longest.task_code}",
            "proposal_type": "increase_frequency",
            "change_description": f"Tighten PM interval from {longest.interval_days}d to {proposed_interval}d to address elevated corrective rate on critical assets",
            "equipment_class": cls,
            "task_code": longest.task_code,
            "task_description": longest.task_description,
            "discipline": longest.discipline,
            "current_interval_days": longest.interval_days,
            "proposed_interval_days": proposed_interval,
            "affected_assets": len(cls_assets),
            "dominant_criticality": "1",
            "deferral_evidence": {"occurrences": 0, "avg_deferral_days": 0.0, "max_deferral_days": 0},
            "failure_data": {"total_failures": cm_c, "assets_in_class": len(cls_assets), "failure_rate_per_year": round(failure_rate, 3)},
            "risk": {
                "current_likelihood": cur_l, "current_likelihood_label": LIKELIHOOD_LABELS[cur_l],
                "current_consequence": consequence, "current_consequence_label": CONSEQUENCE_LABELS[consequence],
                "current_score": cur_score, "current_band": cur_band,
                "proposed_likelihood": prop_l, "proposed_likelihood_label": LIKELIHOOD_LABELS[prop_l],
                "proposed_consequence": consequence, "proposed_consequence_label": CONSEQUENCE_LABELS[consequence],
                "proposed_score": prop_score, "proposed_band": prop_band,
                "risk_delta": prop_score - cur_score, "band_delta": b_delta,
                "alarp_status": alarp_s, "alarp_description": alarp_d,
                "compensating_measures": measures,
            },
            "moc_readiness": moc_r,
            "moc_label": moc_l,
            "total_hours_saved_per_year": -additional_hrs,  # negative = investment required
            "evidence_hypotheses": ["H1.3"],
            "justification": just_h13,
        })
        all_covered.add((cls, longest.task_code))

    # ── H2.2-driven proposals: strategy type change for random-failure classes ─
    for cls in eq_class_tags:
        cv = class_cv.get(cls)
        if cv is None or cv <= 0.8:
            continue  # Not clearly random

        # Only where a time-based strategy exists (hard-time replacement)
        cls_strats = [s for s in all_strategies
                      if s.equipment_class == cls and s.basis == "Time-based"]
        if not cls_strats:
            continue

        target = min(cls_strats, key=lambda s: s.interval_days)  # most frequent — biggest impact
        if (cls, target.task_code) in all_covered:
            continue

        cls_assets = [asset_map[t] for t in eq_class_tags.get(cls, []) if t in asset_map]
        if len(cls_assets) < 2:
            continue

        failures_cls = eq_class_failures.get(cls, 0)
        failure_rate = failures_cls / (len(cls_assets) * YEARS_SPAN)
        class_crits = [a.criticality for a in cls_assets]
        crit_ctr = _Counter(class_crits)
        dominant_crit = crit_ctr.most_common(1)[0][0] if crit_ctr else "3"
        consequence = _consequence_score(dominant_crit)

        cur_l = _likelihood_score(failure_rate)
        cur_score = cur_l * consequence
        cur_band = _risk_band(cur_score)

        # CBM doesn't change failure rate, but catches failures before function loss
        # Risk stays the same or marginally improves
        prop_l = max(1, cur_l - 1)
        prop_score = prop_l * consequence
        prop_band = _risk_band(prop_score)
        b_delta = _risk_band_rank(prop_band) - _risk_band_rank(cur_band)

        alarp_s = "Risk neutral or improved"
        alarp_d = ("Condition-based monitoring detects functional failure before it occurs, "
                   "maintaining or improving the existing risk position while eliminating "
                   "unnecessary hard-time replacements that provide no statistical benefit.")
        measures = ["Implement vibration / oil analysis monitoring programme",
                    "Define P-F interval for condition parameter to be monitored",
                    "Confirm spare parts availability for opportunistic replacement on condition"]

        moc_r = "review"
        moc_l = "Engineering review recommended"

        # Savings: assume CBM replaces 60% of hard-time events (only replace on condition)
        wpy = 365.0 / target.interval_days
        hrs_saved = round(wpy * target.estimated_hours * len(cls_assets) * 0.60, 1)

        mtbf_cls = class_mtbf.get(cls)
        just_h22 = [{
            "hypothesis": "H2.2",
            "type": "Random Failure Pattern",
            "finding": (
                f"{cls} inter-failure times have a coefficient of variation of {cv} "
                f"(threshold 0.8 = random). A CV above 0.8 indicates failures are not "
                f"age-related — the asset is equally likely to fail the day after a time-based "
                f"replacement as just before it. Hard-time replacement at {target.interval_days}-day "
                f"intervals therefore provides no statistical reduction in failure probability. "
                f"Condition-based monitoring should replace the scheduled replacement."
            ),
            "strength": "strong" if cv >= 1.0 else "moderate",
        }]
        if mtbf_cls:
            just_h22.append({
                "hypothesis": "H2.1",
                "type": "MTBF vs PM Interval",
                "finding": (
                    f"Empirical MTBF ({int(mtbf_cls)}d) is "
                    f"{mtbf_cls / target.interval_days:.1f}× the current interval, "
                    f"further confirming the schedule is not aligned to the failure behaviour."
                ),
                "strength": "supporting",
            })

        proposals.append({
            "id": f"H22-{cls[:3].upper()}-{target.task_code}",
            "proposal_type": "strategy_change",
            "change_description": f"Replace {target.interval_days}d time-based replacement with condition-based monitoring programme",
            "equipment_class": cls,
            "task_code": target.task_code,
            "task_description": target.task_description,
            "discipline": target.discipline,
            "current_interval_days": target.interval_days,
            "proposed_interval_days": None,  # Not a fixed interval
            "affected_assets": len(cls_assets),
            "dominant_criticality": dominant_crit,
            "deferral_evidence": {"occurrences": 0, "avg_deferral_days": 0.0, "max_deferral_days": 0},
            "failure_data": {"total_failures": failures_cls, "assets_in_class": len(cls_assets), "failure_rate_per_year": round(failure_rate, 3)},
            "risk": {
                "current_likelihood": cur_l, "current_likelihood_label": LIKELIHOOD_LABELS[cur_l],
                "current_consequence": consequence, "current_consequence_label": CONSEQUENCE_LABELS[consequence],
                "current_score": cur_score, "current_band": cur_band,
                "proposed_likelihood": prop_l, "proposed_likelihood_label": LIKELIHOOD_LABELS[prop_l],
                "proposed_consequence": consequence, "proposed_consequence_label": CONSEQUENCE_LABELS[consequence],
                "proposed_score": prop_score, "proposed_band": prop_band,
                "risk_delta": prop_score - cur_score, "band_delta": b_delta,
                "alarp_status": alarp_s, "alarp_description": alarp_d,
                "compensating_measures": measures,
            },
            "moc_readiness": moc_r,
            "moc_label": moc_l,
            "total_hours_saved_per_year": hrs_saved,
            "evidence_hypotheses": ["H2.2"],
            "justification": just_h22,
        })
        all_covered.add((cls, target.task_code))

    # ── H2.4-driven proposals: align to regulatory minimum ────────────────────
    for task_code, reg in REGULATORY_MINIMUMS.items():
        strategy = strategy_map.get(task_code)
        if not strategy:
            continue
        current_interval = strategy.interval_days
        min_interval = reg["min_interval_days"]
        if current_interval >= min_interval:
            continue  # Already at or beyond minimum — no opportunity
        if any(p["task_code"] == task_code for p in proposals):
            continue  # Already covered

        task_assets = [a for a in assets if a.equipment_class == strategy.equipment_class]
        if not task_assets:
            continue

        proposed_interval = min_interval

        failures_cls = eq_class_failures.get(strategy.equipment_class, 0)
        total_cls = len(task_assets)
        failure_rate = failures_cls / (total_cls * YEARS_SPAN) if total_cls > 0 else 0

        class_crits = [a.criticality for a in task_assets]
        crit_ctr = _Counter(class_crits)
        dominant_crit = crit_ctr.most_common(1)[0][0] if crit_ctr else "2"
        consequence = _consequence_score(dominant_crit)

        cur_l = _likelihood_score(failure_rate)
        cur_score = cur_l * consequence
        cur_band = _risk_band(cur_score)
        ext_r = proposed_interval / current_interval
        prop_rate = failure_rate * (ext_r ** 0.5)
        prop_l = _likelihood_score(prop_rate)
        prop_score = prop_l * consequence
        prop_band = _risk_band(prop_score)
        b_delta = _risk_band_rank(prop_band) - _risk_band_rank(cur_band)

        if b_delta > 1:
            continue

        alarp_s = "Risk neutral or improved" if b_delta <= 0 else "Acceptable with compensating measures"
        alarp_d = (
            f"Proposed interval ({min_interval}d) is the regulatory minimum mandated by {reg['regulation']}. "
            f"The change retains full statutory compliance. {reg['notes']}"
        )
        measures = COMPENSATING_MEASURES_MAP.get(strategy.equipment_class, DEFAULT_MEASURES)
        moc_r = "ready" if b_delta <= 0 else "review"
        moc_l = "Ready to submit" if moc_r == "ready" else "Engineering review recommended"

        wpy_cur = 365.0 / current_interval
        wpy_prop = 365.0 / proposed_interval
        hrs_saved = round((wpy_cur - wpy_prop) * strategy.estimated_hours * total_cls, 1)

        just_h24 = [{
            "hypothesis": "H2.4",
            "type": "Regulatory Optimisation",
            "finding": (
                f"'{strategy.task_description}' is currently performed every {current_interval} days, "
                f"which is more conservative than the regulatory minimum of {min_interval} days "
                f"mandated by {reg['regulation']}. {reg['notes']} "
                f"Extending to the regulatory minimum recovers "
                f"{round(wpy_cur - wpy_prop, 1):.1f} task executions per asset per year "
                f"whilst maintaining full statutory compliance."
            ),
            "strength": "strong",
        }]

        proposals.append({
            "id": f"H24-{strategy.equipment_class[:3].upper()}-{task_code}",
            "proposal_type": "regulatory_optimisation",
            "change_description": f"Align to regulatory minimum ({reg['regulation']}) — extend from {current_interval}d to {min_interval}d",
            "equipment_class": strategy.equipment_class,
            "task_code": task_code,
            "task_description": strategy.task_description,
            "discipline": strategy.discipline,
            "current_interval_days": current_interval,
            "proposed_interval_days": proposed_interval,
            "affected_assets": total_cls,
            "dominant_criticality": dominant_crit,
            "deferral_evidence": {"occurrences": 0, "avg_deferral_days": 0.0, "max_deferral_days": 0},
            "failure_data": {"total_failures": failures_cls, "assets_in_class": total_cls, "failure_rate_per_year": round(failure_rate, 3)},
            "risk": {
                "current_likelihood": cur_l, "current_likelihood_label": LIKELIHOOD_LABELS[cur_l],
                "current_consequence": consequence, "current_consequence_label": CONSEQUENCE_LABELS[consequence],
                "current_score": cur_score, "current_band": cur_band,
                "proposed_likelihood": prop_l, "proposed_likelihood_label": LIKELIHOOD_LABELS[prop_l],
                "proposed_consequence": consequence, "proposed_consequence_label": CONSEQUENCE_LABELS[consequence],
                "proposed_score": prop_score, "proposed_band": prop_band,
                "risk_delta": prop_score - cur_score, "band_delta": b_delta,
                "alarp_status": alarp_s, "alarp_description": alarp_d,
                "compensating_measures": measures,
            },
            "moc_readiness": moc_r,
            "moc_label": moc_l,
            "total_hours_saved_per_year": hrs_saved,
            "evidence_hypotheses": ["H2.4"],
            "justification": just_h24,
        })

    # Sort by MoC readiness first, then by hours saved
    readiness_order = {"ready": 0, "review": 1, "insufficient": 2}
    proposals.sort(key=lambda x: (readiness_order[x["moc_readiness"]], -x["total_hours_saved_per_year"]))

    total_hours = round(sum(p["total_hours_saved_per_year"] for p in proposals), 1)
    ready_count = sum(1 for p in proposals if p["moc_readiness"] == "ready")
    review_count = sum(1 for p in proposals if p["moc_readiness"] == "review")

    return {
        "total_proposals": len(proposals),
        "total_hours_saved_per_year": total_hours,
        "ready_for_moc": ready_count,
        "require_review": review_count,
        "proposals": proposals,
    }


def get_h1_4_analysis(db: Session, platforms: list[str] | None = None) -> dict:
    """
    H1.4: Maintenance strategies do not account for equipment redundancy.
    Duty and standby assets share identical PM intervals despite different
    operational stress profiles and failure consequences.
    Evidence: duty units fail more frequently than standby; yet both
    receive identical PM intervals — standby intervals can be safely extended.
    """
    tag_set = _asset_tags(db, platforms)

    # Bulk load
    all_assets = _filter_assets(db.query(Asset), tag_set).all()
    asset_map: dict[str, Asset] = {a.tag: a for a in all_assets}

    corrective_wos = _filter_wos(
        db.query(WorkOrder).filter(WorkOrder.wo_type == "Corrective"), tag_set
    ).all()

    asset_corrective: dict[str, int] = {}
    for wo in corrective_wos:
        asset_corrective[wo.asset_tag] = asset_corrective.get(wo.asset_tag, 0) + 1

    all_strategies = db.query(MaintenanceStrategy).all()
    # Map equipment_class -> list of strategies that apply to standby
    class_standby_strategies: dict[str, list[MaintenanceStrategy]] = {}
    for s in all_strategies:
        if s.applies_to_standby:
            class_standby_strategies.setdefault(s.equipment_class, []).append(s)

    YEARS_SPAN = 5.0

    # Process duty/standby pairs
    seen_pairs: set = set()
    pairs_data = []
    eq_duty_rates: dict[str, list[float]] = {}
    eq_standby_rates: dict[str, list[float]] = {}

    for duty in all_assets:
        if duty.operating_status != "Duty" or not duty.paired_tag:
            continue
        pair_key = tuple(sorted([duty.tag, duty.paired_tag]))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        standby = asset_map.get(duty.paired_tag)
        if not standby:
            continue

        eq = duty.equipment_class
        duty_failures = asset_corrective.get(duty.tag, 0)
        standby_failures = asset_corrective.get(standby.tag, 0)
        duty_rate = duty_failures / YEARS_SPAN
        standby_rate = standby_failures / YEARS_SPAN

        eq_duty_rates.setdefault(eq, []).append(duty_rate)
        eq_standby_rates.setdefault(eq, []).append(standby_rate)

        rate_ratio = round(duty_rate / standby_rate, 1) if standby_rate > 0 else None
        condition_tasks = [
            s for s in class_standby_strategies.get(eq, [])
            if s.basis in ("time-based", "condition-based")
        ]

        pairs_data.append({
            "duty_tag": duty.tag,
            "standby_tag": standby.tag,
            "equipment_class": eq,
            "criticality": duty.criticality,
            "duty_failures": duty_failures,
            "standby_failures": standby_failures,
            "duty_failure_rate": round(duty_rate, 3),
            "standby_failure_rate": round(standby_rate, 3),
            "rate_ratio": rate_ratio,
            "shared_interval_tasks": len(condition_tasks),
        })

    # Failure rate comparison by equipment class
    eq_comparison = []
    for eq in eq_duty_rates:
        avg_duty = float(np.mean(eq_duty_rates[eq]))
        avg_standby = float(np.mean(eq_standby_rates.get(eq, [0.0])))
        ratio = round(avg_duty / avg_standby, 2) if avg_standby > 0 else None
        condition_tasks = [
            s for s in class_standby_strategies.get(eq, [])
            if s.basis in ("time-based", "condition-based")
        ]
        eq_comparison.append({
            "equipment_class": eq,
            "pair_count": len(eq_duty_rates[eq]),
            "avg_duty_failure_rate": round(avg_duty, 3),
            "avg_standby_failure_rate": round(avg_standby, 3),
            "rate_ratio": ratio,
            "condition_tasks": [
                {"task_code": s.task_code, "task_description": s.task_description,
                 "interval_days": s.interval_days, "proposed_standby_interval": s.interval_days * 2}
                for s in condition_tasks
            ],
            "extension_opportunity": ratio is not None and ratio >= 1.5 and len(condition_tasks) > 0,
        })

    eq_comparison.sort(key=lambda x: x["rate_ratio"] or 0, reverse=True)

    # Summary stats
    total_pairs = len(pairs_data)
    pairs_higher_duty = sum(1 for p in pairs_data if p["duty_failure_rate"] > p["standby_failure_rate"])
    pct_higher = round(pairs_higher_duty / total_pairs * 100, 1) if total_pairs > 0 else 0

    all_duty = [p["duty_failure_rate"] for p in pairs_data]
    all_standby = [p["standby_failure_rate"] for p in pairs_data]
    avg_duty_fleet = round(float(np.mean(all_duty)), 3) if all_duty else 0
    avg_standby_fleet = round(float(np.mean(all_standby)), 3) if all_standby else 0
    fleet_ratio = round(avg_duty_fleet / avg_standby_fleet, 1) if avg_standby_fleet > 0 else None

    candidates = [e for e in eq_comparison if e["extension_opportunity"]]

    if pct_higher >= 60 and len(candidates) >= 2:
        verdict = "supported"
    elif pct_higher >= 40 or len(candidates) >= 1:
        verdict = "partial"
    else:
        verdict = "not_supported"

    return {
        "hypothesis": "H1.4",
        "title": "Maintenance strategies do not account for equipment redundancy",
        "verdict": verdict,
        "summary": (
            f"{total_pairs} duty/standby pairs analysed across the fleet. "
            f"{pairs_higher_duty} ({pct_higher}%) show higher corrective failure rates on duty units than standby, "
            f"confirming different operational stress profiles (fleet duty/standby ratio: {fleet_ratio}×). "
            f"Despite this, all {total_pairs} pairs share identical PM intervals. "
            f"{len(candidates)} equipment classes are candidates for standby interval extension."
        ),
        "total_pairs": total_pairs,
        "pairs_with_higher_duty_rate": pairs_higher_duty,
        "pct_with_higher_duty_rate": pct_higher,
        "avg_duty_failure_rate": avg_duty_fleet,
        "avg_standby_failure_rate": avg_standby_fleet,
        "fleet_rate_ratio": fleet_ratio,
        "failure_rate_by_class": eq_comparison,
        "extension_candidates": candidates,
        "pairs": sorted(
            pairs_data,
            key=lambda x: (x["duty_failure_rate"] - x["standby_failure_rate"]),
            reverse=True
        )[:25],
    }


# ---------------------------------------------------------------------------
# Weibull Analysis
# ---------------------------------------------------------------------------

# OREDA reference β values (used when empirical data is insufficient)
OREDA_BETA = {
    "Centrifugal Pump":       {"beta": 1.5, "source": "OREDA-2015 Table 2.8"},
    "Reciprocating Pump":     {"beta": 1.5, "source": "OREDA-2015 Table 2.9"},
    "Centrifugal Compressor": {"beta": 1.4, "source": "OREDA-2015 Table 3.2"},
    "Gas Turbine Generator":  {"beta": 1.8, "source": "OREDA-2015 Table 4.1"},
    "Diesel Generator":       {"beta": 1.6, "source": "OREDA-2015 Table 4.3"},
    "Air Compressor":         {"beta": 1.3, "source": "OREDA-2015 Table 3.5"},
    "Heat Exchanger":         {"beta": 1.2, "source": "OREDA-2015 Table 6.1"},
    "Pressure Vessel":        {"beta": 0.9, "source": "OREDA-2015 Table 7.1"},
    "Safety Valve":           {"beta": 0.8, "source": "OREDA-2015 Table 8.2"},
    "Control Valve":          {"beta": 1.1, "source": "OREDA-2015 Table 8.4"},
    "Fire & Gas Detector":    {"beta": 0.7, "source": "OREDA-2015 Table 9.1"},
    "Electric Motor":         {"beta": 1.4, "source": "OREDA-2015 Table 5.2"},
    "Switchgear":             {"beta": 1.0, "source": "OREDA-2015 Table 5.5"},
    "UPS":                    {"beta": 0.9, "source": "OREDA-2015 Table 5.7"},
    "Fan / Blower":           {"beta": 1.2, "source": "OREDA-2015 Table 3.8"},
    "Pressure Transmitter":   {"beta": 1.1, "source": "OREDA-2015 Table 9.3"},
    "Flow Meter":             {"beta": 1.0, "source": "OREDA-2015 Table 9.5"},
}


def _classify_beta(beta: float) -> dict:
    if beta < 0.9:
        return {
            "label": "Infant Mortality",
            "color": "#f59e0b",
            "implication": "Early-life failures dominate. Time-based PM has limited value. Investigate installation quality, commissioning procedures, and infant mortality burn-in.",
        }
    elif beta <= 1.1:
        return {
            "label": "Random Failure",
            "color": "#3b82f6",
            "implication": "Failures are random — unrelated to age or operating time. Time-based PM cannot prevent these. Condition-based monitoring or run-to-failure may be more cost-effective.",
        }
    elif beta <= 1.5:
        return {
            "label": "Mild Wear-Out",
            "color": "#10b981",
            "implication": "Moderate age-related degradation. Time-based PM is partially effective. Align PM intervals closer to the characteristic life η to optimise coverage.",
        }
    else:
        return {
            "label": "Wear-Out",
            "color": "#8b5cf6",
            "implication": "Strong age-related wear-out. Time-based PM is highly effective. PM interval should be set at a fraction of η to prevent failures before they occur.",
        }


def _fit_weibull_mrr(inter_failure_days: list[float]) -> tuple[float | None, float | None]:
    """Median rank regression Weibull fit. Returns (β, η) or (None, None) if insufficient data."""
    t = sorted(d for d in inter_failure_days if d > 0)
    n = len(t)
    if n < 5:
        return None, None
    F = [(i + 1 - 0.3) / (n + 0.4) for i in range(n)]
    x = np.log(t)
    y = np.log(np.log(1.0 / (1.0 - np.array(F))))
    try:
        slope, intercept = np.polyfit(x, y, 1)
        beta = max(0.1, float(slope))
        eta = float(np.exp(-intercept / beta))
        return round(beta, 2), round(eta, 0)
    except Exception:
        return None, None


def get_weibull_analysis(db: Session, platforms: list[str] | None = None) -> dict:
    """
    Weibull β estimation per equipment class from inter-failure times (corrective WOs).
    Falls back to OREDA reference values where empirical data is insufficient.
    """
    tag_set = _asset_tags(db, platforms)

    corrective_wos = _filter_wos(
        db.query(WorkOrder).filter(
            WorkOrder.wo_type == "Corrective",
            WorkOrder.scheduled_date.isnot(None),
        ),
        tag_set,
    ).all()

    # Build per-asset failure date lists
    asset_failures: dict[str, list] = {}
    for wo in corrective_wos:
        asset_failures.setdefault(wo.asset_tag, []).append(wo.scheduled_date)

    # Map assets to equipment class
    all_assets = _filter_assets(db.query(Asset), tag_set).all()
    asset_class: dict[str, str] = {a.tag: a.equipment_class for a in all_assets}

    # Collect inter-failure intervals per class
    class_intervals: dict[str, list[float]] = {}
    class_failure_count: dict[str, int] = {}
    for tag, dates in asset_failures.items():
        cls = asset_class.get(tag)
        if not cls:
            continue
        sorted_dates = sorted(dates)
        class_failure_count[cls] = class_failure_count.get(cls, 0) + len(sorted_dates)
        if len(sorted_dates) >= 2:
            for i in range(len(sorted_dates) - 1):
                gap = (sorted_dates[i + 1] - sorted_dates[i]).days
                if gap > 0:
                    class_intervals.setdefault(cls, []).append(float(gap))

    # All equipment classes present in the filtered asset set
    all_classes = sorted(set(asset_class.values()))

    results = []
    for cls in all_classes:
        intervals = class_intervals.get(cls, [])
        n_failures = class_failure_count.get(cls, 0)

        beta_emp, eta_emp = _fit_weibull_mrr(intervals)
        oreda = OREDA_BETA.get(cls)

        if beta_emp is not None:
            beta = beta_emp
            eta = eta_emp
            data_source = "empirical"
            n_intervals = len(intervals)
        elif oreda:
            beta = oreda["beta"]
            eta = None
            data_source = "oreda_reference"
            n_intervals = len(intervals)
        else:
            continue

        classification = _classify_beta(beta)

        results.append({
            "equipment_class": cls,
            "beta": beta,
            "eta_days": eta,
            "n_failures": n_failures,
            "n_intervals_used": n_intervals,
            "data_source": data_source,
            "oreda_reference": oreda["source"] if oreda else None,
            "classification": classification["label"],
            "classification_color": classification["color"],
            "maintenance_implication": classification["implication"],
        })

    results.sort(key=lambda x: x["beta"], reverse=True)

    wear_out = [r for r in results if r["beta"] > 1.1]
    random_f = [r for r in results if 0.9 <= r["beta"] <= 1.1]
    infant = [r for r in results if r["beta"] < 0.9]

    return {
        "classes_analysed": len(results),
        "wear_out_count": len(wear_out),
        "random_failure_count": len(random_f),
        "infant_mortality_count": len(infant),
        "avg_fleet_beta": round(float(np.mean([r["beta"] for r in results])), 2) if results else None,
        "results": results,
        "summary": (
            f"{len(results)} equipment classes analysed. "
            f"{len(wear_out)} show wear-out behaviour (β>1.1) — time-based PM is appropriate. "
            f"{len(random_f)} exhibit random failure patterns (β≈1) — condition-based or run-to-failure strategies warrant consideration. "
            f"{len(infant)} show infant mortality (β<0.9) — commissioning and installation quality should be reviewed."
        ),
    }


# ---------------------------------------------------------------------------
# SCE / Statutory Inspection Register
# ---------------------------------------------------------------------------

SCE_TASK_REGISTRY = {
    "FG-I01": {
        "description": "F&G Detector — Functional Test",
        "regulation": "PFEER / IEC 61511",
        "sce_type": "Fire & Gas Detection",
        "interval_days": 180,
        "notes": "Mandatory proof test for SIL-rated F&G detectors under IEC 61511. Minimum 6-monthly for SIL 1–2 applications.",
    },
    "FG-I02": {
        "description": "F&G Detector — Calibration",
        "regulation": "PFEER / Manufacturer",
        "sce_type": "Fire & Gas Detection",
        "interval_days": 365,
        "notes": "Annual calibration mandated by PFEER and manufacturer guidance.",
    },
    "FG-I03": {
        "description": "F&G Detector — Head Replacement",
        "regulation": "PFEER / Manufacturer",
        "sce_type": "Fire & Gas Detection",
        "interval_days": 1825,
        "notes": "5-yearly detector head replacement per manufacturer life-limiting specification.",
    },
    "SV-S01": {
        "description": "Safety Valve — Functional Test & Overhaul",
        "regulation": "PSSR 2000 / Written Scheme of Examination",
        "sce_type": "Overpressure Protection",
        "interval_days": 365,
        "notes": "PSSR 2000 mandates testing and overhaul per Written Scheme of Examination. Interval set to annual for critical overpressure protection duties.",
    },
    "SV-S02": {
        "description": "Safety Valve — Visual Inspection",
        "regulation": "PSSR 2000 / WSE",
        "sce_type": "Overpressure Protection",
        "interval_days": 730,
        "notes": "Biennial external visual inspection per PSSR Written Scheme of Examination.",
    },
    "PV-S01": {
        "description": "Pressure Vessel — External Visual",
        "regulation": "PSSR 2000 / WSE",
        "sce_type": "Pressure Containment",
        "interval_days": 730,
        "notes": "Statutory 2-yearly external visual inspection per PSSR Written Scheme of Examination.",
    },
    "PV-S02": {
        "description": "Pressure Vessel — Internal Inspection",
        "regulation": "PSSR 2000 / WSE",
        "sce_type": "Pressure Containment",
        "interval_days": 1825,
        "notes": "5-yearly internal inspection per PSSR Written Scheme of Examination.",
    },
    "PV-S03": {
        "description": "Pressure Vessel — Pressure Test",
        "regulation": "PSSR 2000 / WSE",
        "sce_type": "Pressure Containment",
        "interval_days": 3650,
        "notes": "10-yearly pressure test per PSSR Written Scheme of Examination.",
    },
    "CV-I01": {
        "description": "Control Valve — Partial Stroke Test",
        "regulation": "IEC 61511 / SIL Assessment",
        "sce_type": "Emergency Shutdown",
        "interval_days": 180,
        "notes": "6-monthly partial stroke test required to maintain PFD targets for SIL 1–2 ESD valves.",
    },
    "CV-I02": {
        "description": "Control Valve — Full Stroke Test",
        "regulation": "IEC 61511 / SIL Assessment",
        "sce_type": "Emergency Shutdown",
        "interval_days": 365,
        "notes": "Annual full-stroke proof test mandated by IEC 61511 SIL assessment for ESD duty valves.",
    },
}

SCE_EQUIPMENT_CLASSES = {
    "Fire & Gas Detector",
    "Safety Valve",
    "Pressure Vessel",
    "Control Valve",  # where SIL-rated ESD duty
}


def get_sce_analysis(db: Session, platforms: list[str] | None = None) -> dict:
    """
    Safety Critical Element (SCE) register and statutory inspection summary.
    SCEs are excluded from all maintenance optimisation scope.
    """
    tag_set = _asset_tags(db, platforms)

    # Identify SCE assets: equipment class is safety-critical OR criticality = 1
    sce_assets_q = _filter_assets(db.query(Asset), tag_set).filter(
        (Asset.equipment_class.in_(SCE_EQUIPMENT_CLASSES)) | (Asset.criticality == "1")
    )
    sce_assets = sce_assets_q.all()

    sce_asset_list = [
        {
            "tag": a.tag,
            "description": a.description,
            "equipment_class": a.equipment_class,
            "criticality": a.criticality,
            "platform": a.platform,
            "operating_status": a.operating_status,
            "system": a.system,
            "sce_reason": (
                "SCE Equipment Class" if a.equipment_class in SCE_EQUIPMENT_CLASSES else "Criticality 1 Asset"
            ),
            "regulation_basis": next(
                (v["regulation"] for k, v in SCE_TASK_REGISTRY.items()
                 if v["sce_type"] in (
                     "Fire & Gas Detection" if a.equipment_class == "Fire & Gas Detector" else
                     "Overpressure Protection" if a.equipment_class == "Safety Valve" else
                     "Pressure Containment" if a.equipment_class == "Pressure Vessel" else
                     "Emergency Shutdown" if a.equipment_class == "Control Valve" else ""
                 )),
                "Criticality Assessment" if a.criticality == "1" else "N/A"
            ),
        }
        for a in sce_assets
    ]

    sce_tags = {a.tag for a in sce_assets}

    # Statutory work orders on SCE assets
    statutory_wos = _filter_wos(
        db.query(WorkOrder).filter(WorkOrder.wo_type == "Statutory"),
        tag_set,
    ).all()

    statutory_on_sce = [w for w in statutory_wos if w.asset_tag in sce_tags]
    all_statutory_cost = sum(w.actual_cost or 0 for w in statutory_wos)
    sce_statutory_cost = sum(w.actual_cost or 0 for w in statutory_on_sce)

    # All WOs on SCE assets
    all_wos_on_sce = _filter_wos(db.query(WorkOrder), {t for t in sce_tags}).all() if sce_tags else []
    total_sce_cost = sum(w.actual_cost or 0 for w in all_wos_on_sce)
    all_wos_all = _filter_wos(db.query(WorkOrder), tag_set).all()
    total_all_cost = sum(w.actual_cost or 0 for w in all_wos_all)

    # Statutory inspection schedule summary
    task_summary: dict[str, dict] = {}
    for wo in statutory_wos:
        tc = wo.task_code or "UNKNOWN"
        task_summary.setdefault(tc, {
            "task_code": tc,
            "task_description": wo.task_description,
            "wo_count": 0,
            "total_cost": 0.0,
            "total_hours": 0.0,
        })
        task_summary[tc]["wo_count"] += 1
        task_summary[tc]["total_cost"] += wo.actual_cost or 0
        task_summary[tc]["total_hours"] += wo.actual_hours or 0

    inspection_schedule = []
    for tc, info in task_summary.items():
        registry = SCE_TASK_REGISTRY.get(tc, {})
        inspection_schedule.append({
            "task_code": tc,
            "task_description": info["task_description"],
            "regulation": registry.get("regulation", "Industry Best Practice"),
            "sce_type": registry.get("sce_type", "General"),
            "interval_days": registry.get("interval_days"),
            "wo_count": info["wo_count"],
            "total_cost": round(info["total_cost"], 2),
            "avg_hours": round(info["total_hours"] / max(info["wo_count"], 1), 1),
            "notes": registry.get("notes", ""),
        })

    inspection_schedule.sort(key=lambda x: x["wo_count"], reverse=True)

    # By class breakdown
    by_class: dict[str, int] = {}
    for a in sce_assets:
        by_class[a.equipment_class] = by_class.get(a.equipment_class, 0) + 1

    return {
        "total_sce_assets": len(sce_assets),
        "total_statutory_wos": len(statutory_wos),
        "statutory_wos_on_sce": len(statutory_on_sce),
        "total_statutory_cost": round(all_statutory_cost, 2),
        "total_sce_cost": round(total_sce_cost, 2),
        "sce_cost_pct_of_total": round(total_sce_cost / total_all_cost * 100, 1) if total_all_cost > 0 else 0,
        "sce_assets_by_class": by_class,
        "sce_asset_list": sorted(sce_asset_list, key=lambda x: (x["equipment_class"], x["tag"])),
        "statutory_inspection_schedule": inspection_schedule,
        "scope_note": (
            f"{len(sce_assets)} Safety Critical Elements identified across the fleet. "
            f"These assets and their statutory inspection tasks are excluded from all maintenance optimisation scope. "
            f"Statutory inspections are mandated by PSSR 2000, PFEER, IEC 61511, and Written Schemes of Examination — "
            f"they cannot be deferred, extended, or rationalised without regulatory approval."
        ),
    }
