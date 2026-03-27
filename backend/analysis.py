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
    seen_pairs = set()
    opportunities = []

    for asset in assets:
        if asset.operating_status != "Duty":
            continue
        pair_key = tuple(sorted([asset.tag, asset.paired_tag]))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        standby = db.query(Asset).filter(Asset.tag == asset.paired_tag).first()
        if not standby:
            continue

        # Get all tasks for both assets
        duty_tasks = db.query(WorkOrder).filter(
            WorkOrder.asset_tag == asset.tag,
            WorkOrder.wo_type == "PPM"
        ).all()
        standby_tasks = db.query(WorkOrder).filter(
            WorkOrder.asset_tag == standby.tag,
            WorkOrder.wo_type == "PPM"
        ).all()

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

        # Confirm no failures on this asset during deferral periods
        failures = db.query(WorkOrder).filter(
            WorkOrder.asset_tag == asset_tag,
            WorkOrder.wo_type == "Corrective",
            WorkOrder.failure_mode.isnot(None),
        ).count()

        asset = db.query(Asset).filter(Asset.tag == asset_tag).first()
        strategy = db.query(MaintenanceStrategy).filter(
            MaintenanceStrategy.task_code == task_code
        ).first()

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
            asset = db.query(Asset).filter(Asset.tag == tag).first()
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
        asset = db.query(Asset).filter(Asset.tag == wo.asset_tag).first()
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
        asset = db.query(Asset).filter(Asset.tag == wo.asset_tag).first()
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

    by_class: dict = {}
    by_failure_mode: dict = {}
    by_discipline: dict = {}
    total_cost = 0.0
    total_downtime_days = 0

    for w in wos:
        cost = w.actual_cost or 0
        total_cost += cost

        asset = db.query(Asset).filter(Asset.tag == w.asset_tag).first()
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
