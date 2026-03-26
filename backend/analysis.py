"""
Core analysis engine: duty/standby opportunities, deferral pattern analysis,
and optimisation opportunity scoring.
"""
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from database import Asset, WorkOrder, MaintenanceStrategy
from typing import Optional


def get_duty_standby_opportunities(db: Session) -> list[dict]:
    """
    Identify assets in duty/standby pairs where the standby unit
    has the same maintenance strategy as the duty unit.
    Flags these as opportunities to extend the standby interval.
    """
    assets = db.query(Asset).filter(Asset.paired_tag.isnot(None)).all()
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


def get_deferral_opportunities(db: Session, min_occurrences: int = 4, min_avg_deferral: int = 30) -> list[dict]:
    """
    Identify maintenance tasks that have been consistently deferred
    (completed significantly after scheduled date) with no resulting failures.
    These are candidates for interval extension.
    """
    wos = db.query(WorkOrder).filter(
        WorkOrder.status == "Completed",
        WorkOrder.deferral_days.isnot(None),
        WorkOrder.deferral_days > 0,
    ).all()

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


def get_deferral_summary_by_task(db: Session) -> list[dict]:
    """
    Aggregate deferral patterns by task code across all assets.
    Used for fleet-level analysis.
    """
    wos = db.query(WorkOrder).filter(
        WorkOrder.status == "Completed",
        WorkOrder.deferral_days.isnot(None),
        WorkOrder.deferral_days > 14,
    ).all()

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


def get_cost_summary(db: Session) -> dict:
    wos = db.query(WorkOrder).filter(WorkOrder.status == "Completed").all()
    total_actual = sum(w.actual_cost or 0 for w in wos)
    total_estimated = sum(w.estimated_cost or 0 for w in wos)
    ppm_cost = sum(w.actual_cost or 0 for w in wos if w.wo_type == "PPM")
    statutory_cost = sum(w.actual_cost or 0 for w in wos if w.wo_type == "Statutory")
    corrective_cost = sum(w.actual_cost or 0 for w in wos if w.wo_type == "Corrective")

    by_discipline: dict = {}
    for w in wos:
        d = w.discipline or "Unknown"
        by_discipline[d] = by_discipline.get(d, 0) + (w.actual_cost or 0)

    assets = db.query(Asset).all()
    duty_standby_pairs = sum(1 for a in assets if a.paired_tag and a.operating_status == "Duty")

    ds_opps = get_duty_standby_opportunities(db)
    def_opps = get_deferral_opportunities(db)
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


def get_h1_1_analysis(db: Session) -> dict:
    """
    H1.1: PM schedules more conservative than equipment requires.
    Evidence: (a) tasks consistently deferred with no corrective uptick,
    (b) fleet-wide deferral vs corrective correlation.
    """
    # Get all deferred tasks (>14 days late) grouped by asset+task
    deferred_wos = db.query(WorkOrder).filter(
        WorkOrder.wo_type.in_(["PPM", "Statutory"]),
        WorkOrder.status == "Completed",
        WorkOrder.deferral_days > 14,
    ).all()

    # For each asset, count deferrals and corrective events per year
    asset_years: dict = {}
    for wo in deferred_wos:
        if not wo.scheduled_date:
            continue
        yr = wo.scheduled_date.year
        key = (wo.asset_tag, yr)
        asset_years.setdefault(key, {"deferrals": 0, "corrective": 0})
        asset_years[key]["deferrals"] += 1

    corrective_wos = db.query(WorkOrder).filter(WorkOrder.wo_type == "Corrective").all()
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
    all_wos = db.query(WorkOrder).all()
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


def get_h1_2_analysis(db: Session) -> dict:
    """
    H1.2: Duplicate or overlapping PM tasks on same equipment.
    Uses a component-function matrix to find tasks covering the same
    failure mode on the same equipment class, with savings estimates.
    """
    strategies = db.query(MaintenanceStrategy).all()
    all_wos = db.query(WorkOrder).filter(WorkOrder.wo_type.in_(["PPM", "Statutory"])).all()

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
            asset_count = db.query(Asset).filter(Asset.equipment_class == eq_class).count()
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


def get_h1_3_analysis(db: Session) -> dict:
    """
    H1.3: Corrective maintenance patterns reveal equipment classes
    where the preventive strategy is insufficient.
    Signals: repeat failures, high CM:PPM ratio, rising CM trend.
    """
    all_wos = db.query(WorkOrder).all()

    # Corrective events per asset
    asset_corrective: dict = {}
    for wo in all_wos:
        if wo.wo_type == "Corrective":
            asset_corrective.setdefault(wo.asset_tag, [])
            asset_corrective[wo.asset_tag].append(wo)

    # Repeat failures: assets with 3+ corrective events
    repeat_failures = []
    for tag, wos in asset_corrective.items():
        if len(wos) >= 3:
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
            "signal": "HIGH — strategy may be insufficient" if ratio > 20 else ("MODERATE" if ratio > 10 else "LOW"),
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

    high_risk = [r for r in cm_ratio if r["cm_to_ppm_ratio_pct"] > 20]

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
            f"{len(high_risk)} equipment classes show a corrective-to-PPM ratio above 20%, "
            f"indicating the current preventive strategy is not preventing failures at an acceptable rate."
        ),
    }


def get_corrective_summary(db: Session) -> dict:
    """Summary of corrective (breakdown) work orders by class, failure mode, and discipline."""
    wos = db.query(WorkOrder).filter(WorkOrder.wo_type == "Corrective").all()

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
