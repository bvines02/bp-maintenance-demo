"""
Demo data generator for BP Maintenance Demo.
Generates realistic offshore oil & gas platform maintenance data.
"""
import random
import pandas as pd
import numpy as np
from datetime import date, timedelta
import os

random.seed(42)
np.random.seed(42)

PLATFORM_NAME = "Alpha Platform"
START_DATE = date(2019, 1, 1)
END_DATE = date(2024, 12, 31)

SYSTEMS = [
    "Produced Water Treatment",
    "Seawater Lift",
    "Gas Compression",
    "Crude Oil Export",
    "Utilities - Power Generation",
    "Utilities - HVAC",
    "Fire & Gas",
    "Process Safety",
    "Subsea",
    "Flare & Vent",
]

LOCATIONS = ["Module A", "Module B", "Module C", "Cellar Deck", "Main Deck", "Mezzanine Deck", "Utilities Room"]

EQUIPMENT_CLASSES = {
    "Centrifugal Pump": {"discipline": "Mechanical", "has_standby": True, "count": 16},
    "Reciprocating Pump": {"discipline": "Mechanical", "has_standby": True, "count": 6},
    "Centrifugal Compressor": {"discipline": "Mechanical", "has_standby": True, "count": 4},
    "Gas Turbine Generator": {"discipline": "Mechanical", "has_standby": True, "count": 3},
    "Electric Motor": {"discipline": "Electrical", "has_standby": False, "count": 12},
    "Pressure Vessel": {"discipline": "Mechanical", "has_standby": False, "count": 14},
    "Heat Exchanger": {"discipline": "Mechanical", "has_standby": False, "count": 10},
    "Control Valve": {"discipline": "Instrumentation", "has_standby": False, "count": 20},
    "Pressure Transmitter": {"discipline": "Instrumentation", "has_standby": False, "count": 18},
    "Flow Meter": {"discipline": "Instrumentation", "has_standby": False, "count": 12},
    "Fire & Gas Detector": {"discipline": "Instrumentation", "has_standby": False, "count": 24},
    "Switchgear Panel": {"discipline": "Electrical", "has_standby": False, "count": 8},
    "UPS": {"discipline": "Electrical", "has_standby": True, "count": 4},
    "Fan / Blower": {"discipline": "Mechanical", "has_standby": True, "count": 8},
    "Safety Valve": {"discipline": "Mechanical", "has_standby": False, "count": 16},
}

MAINTENANCE_STRATEGIES = [
    # (task_code, description, interval_days, hours, basis, duty_only, standby_applies)
    # Centrifugal Pump
    ("CP-M01", "Lubrication oil check and top-up", 30, 0.5, "Time-based", False, True),
    ("CP-M02", "Vibration and temperature monitoring", 30, 1.0, "Condition-based", False, True),
    ("CP-M03", "Mechanical seal inspection", 90, 2.0, "Time-based", False, True),
    ("CP-M04", "Coupling inspection and alignment check", 180, 3.0, "Time-based", False, True),
    ("CP-M05", "Full overhaul - impeller, bearings, seals", 1825, 16.0, "Time-based", False, True),
    ("CP-E01", "Motor insulation resistance test", 365, 1.5, "Time-based", False, True),
    ("CP-E02", "Motor thermal imaging", 180, 1.0, "Condition-based", False, True),
    # Reciprocating Pump
    ("RP-M01", "Lubrication oil change", 90, 2.0, "Time-based", False, True),
    ("RP-M02", "Valve inspection and replacement", 180, 4.0, "Time-based", False, True),
    ("RP-M03", "Piston and liner inspection", 365, 8.0, "Time-based", False, True),
    ("RP-M04", "Full overhaul", 1825, 24.0, "Time-based", False, True),
    # Centrifugal Compressor
    ("CC-M01", "Lube oil system check", 30, 1.0, "Time-based", False, True),
    ("CC-M02", "Vibration analysis", 30, 2.0, "Condition-based", False, True),
    ("CC-M03", "Dry gas seal monitoring", 90, 2.0, "Condition-based", False, True),
    ("CC-M04", "Coupling and alignment inspection", 180, 4.0, "Time-based", False, True),
    ("CC-M05", "Rotor dynamics check", 365, 8.0, "Time-based", False, True),
    ("CC-M06", "Major overhaul", 1825, 48.0, "Time-based", False, True),
    # Gas Turbine Generator
    ("GT-M01", "Combustion inspection", 365, 40.0, "Time-based", False, False),
    ("GT-M02", "Hot section inspection", 730, 80.0, "Time-based", False, False),
    ("GT-M03", "Major overhaul", 2190, 160.0, "Time-based", False, False),
    ("GT-E01", "Generator insulation test", 365, 4.0, "Time-based", False, True),
    ("GT-E02", "Excitation system check", 180, 2.0, "Time-based", False, True),
    # Pressure Vessel
    ("PV-S01", "External visual inspection", 365, 4.0, "Statutory", False, False),
    ("PV-S02", "Internal inspection (Written Scheme)", 730, 16.0, "Statutory", False, False),
    ("PV-S03", "Pressure test", 1825, 8.0, "Statutory", False, False),
    ("PV-M01", "Corrosion monitoring - UT thickness", 180, 3.0, "Condition-based", False, False),
    # Heat Exchanger
    ("HX-M01", "Performance monitoring - dP and temperature", 90, 1.0, "Condition-based", False, False),
    ("HX-M02", "Tube bundle inspection and cleaning", 365, 8.0, "Time-based", False, False),
    ("HX-M03", "Pressure test", 1825, 4.0, "Statutory", False, False),
    # Control Valve
    ("CV-I01", "Partial stroke test", 180, 1.0, "Time-based", False, False),
    ("CV-I02", "Full stroke test and calibration", 365, 2.0, "Time-based", False, False),
    ("CV-I03", "Actuator and positioner overhaul", 1825, 6.0, "Time-based", False, False),
    # Pressure Transmitter
    ("PT-I01", "Calibration and loop check", 365, 1.5, "Time-based", False, False),
    ("PT-I02", "Impulse line check and blow-down", 180, 1.0, "Time-based", False, False),
    # Flow Meter
    ("FM-I01", "Calibration verification", 365, 2.0, "Time-based", False, False),
    ("FM-I02", "Strainer check and cleaning", 180, 1.0, "Time-based", False, False),
    # Fire & Gas Detector
    ("FG-I01", "Functional test", 90, 0.5, "Statutory", False, False),
    ("FG-I02", "Calibration check", 180, 1.0, "Statutory", False, False),
    ("FG-I03", "Detector head replacement", 1825, 0.5, "Time-based", False, False),
    # Switchgear
    ("SW-E01", "Thermal imaging", 365, 2.0, "Condition-based", False, False),
    ("SW-E02", "Contact resistance test", 730, 4.0, "Time-based", False, False),
    ("SW-E03", "Breaker maintenance and testing", 1825, 8.0, "Time-based", False, False),
    # UPS
    ("UP-E01", "Battery capacity test", 365, 3.0, "Time-based", False, True),
    ("UP-E02", "Battery visual inspection", 90, 1.0, "Time-based", False, True),
    ("UP-E03", "Full load transfer test", 180, 2.0, "Time-based", False, True),
    # Fan / Blower
    ("FB-M01", "Belt inspection and tension check", 90, 1.0, "Time-based", False, True),
    ("FB-M02", "Bearing lubrication", 90, 0.5, "Time-based", False, True),
    ("FB-M03", "Impeller inspection", 365, 3.0, "Time-based", False, True),
    ("FB-E01", "Motor insulation test", 365, 1.5, "Time-based", False, True),
    # Safety Valve
    ("SV-S01", "Lift test and set pressure check", 730, 4.0, "Statutory", False, False),
    ("SV-S02", "Visual inspection", 365, 1.0, "Statutory", False, False),
    # Electric Motor (standalone)
    ("EM-E01", "Insulation resistance test", 365, 1.5, "Time-based", False, False),
    ("EM-E02", "Thermal imaging", 180, 1.0, "Condition-based", False, False),
    ("EM-M01", "Bearing lubrication", 90, 0.5, "Time-based", False, False),
]

CLASS_STRATEGY_MAP = {
    "Centrifugal Pump": ["CP-M01","CP-M02","CP-M03","CP-M04","CP-M05","CP-E01","CP-E02"],
    "Reciprocating Pump": ["RP-M01","RP-M02","RP-M03","RP-M04"],
    "Centrifugal Compressor": ["CC-M01","CC-M02","CC-M03","CC-M04","CC-M05","CC-M06"],
    "Gas Turbine Generator": ["GT-M01","GT-M02","GT-M03","GT-E01","GT-E02"],
    "Pressure Vessel": ["PV-S01","PV-S02","PV-S03","PV-M01"],
    "Heat Exchanger": ["HX-M01","HX-M02","HX-M03"],
    "Control Valve": ["CV-I01","CV-I02","CV-I03"],
    "Pressure Transmitter": ["PT-I01","PT-I02"],
    "Flow Meter": ["FM-I01","FM-I02"],
    "Fire & Gas Detector": ["FG-I01","FG-I02","FG-I03"],
    "Switchgear Panel": ["SW-E01","SW-E02","SW-E03"],
    "UPS": ["UP-E01","UP-E02","UP-E03"],
    "Fan / Blower": ["FB-M01","FB-M02","FB-M03","FB-E01"],
    "Safety Valve": ["SV-S01","SV-S02"],
    "Electric Motor": ["EM-E01","EM-E02","EM-M01"],
}

STRATEGY_LOOKUP = {s[0]: s for s in MAINTENANCE_STRATEGIES}

CLASS_PREFIXES = {
    "Centrifugal Pump": "CP",
    "Reciprocating Pump": "RP",
    "Centrifugal Compressor": "CC",
    "Gas Turbine Generator": "GTG",
    "Electric Motor": "EM",
    "Pressure Vessel": "PV",
    "Heat Exchanger": "HX",
    "Control Valve": "CV",
    "Pressure Transmitter": "PT",
    "Flow Meter": "FM",
    "Fire & Gas Detector": "FGD",
    "Switchgear Panel": "SW",
    "UPS": "UPS",
    "Fan / Blower": "FB",
    "Safety Valve": "SV",
}

MANUFACTURERS = {
    "Centrifugal Pump": ["Flowserve", "Sulzer", "KSB", "Grundfos"],
    "Reciprocating Pump": ["Gardner Denver", "Weir SPM", "Sundyne"],
    "Centrifugal Compressor": ["Solar Turbines", "GE Oil & Gas", "MAN Energy"],
    "Gas Turbine Generator": ["GE", "Siemens", "Rolls-Royce"],
    "Electric Motor": ["ABB", "Siemens", "WEG", "Nidec"],
    "Pressure Vessel": ["Britannia", "Whessoe", "John Wood Group"],
    "Heat Exchanger": ["Alfa Laval", "Tranter", "Kelvion"],
    "Control Valve": ["Emerson", "Metso", "Flowserve"],
    "Pressure Transmitter": ["Emerson Rosemount", "Honeywell", "Yokogawa"],
    "Flow Meter": ["Emerson Rosemount", "Endress+Hauser", "ABB"],
    "Fire & Gas Detector": ["MSA", "Honeywell", "Draeger", "Det-Tronics"],
    "Switchgear Panel": ["ABB", "Schneider Electric", "Siemens"],
    "UPS": ["Eaton", "APC", "Vertiv"],
    "Fan / Blower": ["Howden", "Dresser-Rand", "Aerovent"],
    "Safety Valve": ["Emerson Crosby", "Leser", "Sempell"],
}

# Corrective maintenance: failure modes, MTBF (days), repair hours, cost multiplier vs PPM
# Format: (failure_mode, description, mtbf_duty, mtbf_standby, repair_hours, cost_mult, discipline)
FAILURE_MODES = {
    "Centrifugal Pump": [
        ("Mechanical seal failure", "Emergency repair - mechanical seal leak", 300, 900, 6.0, 3.5, "Mechanical"),
        ("Bearing failure", "Unplanned replacement - bearing failure on pump", 420, 1200, 8.0, 4.0, "Mechanical"),
        ("Impeller wear/cavitation", "Corrective overhaul - impeller cavitation damage", 730, 2000, 12.0, 5.0, "Mechanical"),
        ("Coupling failure", "Emergency repair - coupling shear", 600, 1500, 4.0, 2.5, "Mechanical"),
        ("Motor winding failure", "Electrical fault - motor winding breakdown", 900, 1800, 10.0, 6.0, "Electrical"),
    ],
    "Reciprocating Pump": [
        ("Valve plate failure", "Emergency repair - suction/discharge valve failure", 240, 720, 8.0, 4.0, "Mechanical"),
        ("Piston rod seal leak", "Corrective repair - piston rod packing failure", 360, 900, 6.0, 3.0, "Mechanical"),
        ("Crankshaft bearing failure", "Major repair - crankshaft bearing seizure", 730, 1800, 20.0, 8.0, "Mechanical"),
    ],
    "Centrifugal Compressor": [
        ("Dry gas seal degradation", "Emergency repair - dry gas seal failure", 540, 1500, 16.0, 7.0, "Mechanical"),
        ("Lube oil system fault", "Corrective repair - lube oil pressure low / filter blockage", 365, 1000, 6.0, 3.0, "Mechanical"),
        ("Vibration trip - imbalance", "Unplanned shutdown - high vibration trip, imbalance found", 600, 1500, 12.0, 5.0, "Mechanical"),
        ("Intercooler tube leak", "Corrective repair - intercooler tube leak", 900, 2500, 10.0, 4.5, "Mechanical"),
    ],
    "Gas Turbine Generator": [
        ("Fuel control valve fault", "Emergency repair - fuel control valve failure", 400, 1000, 12.0, 6.0, "Mechanical"),
        ("Combustion liner cracking", "Unplanned outage - hot section cracking found", 730, 2000, 40.0, 15.0, "Mechanical"),
        ("Generator excitation fault", "Electrical fault - excitation system failure", 600, 1500, 8.0, 5.0, "Electrical"),
        ("Lube oil leak", "Emergency repair - lube oil system leak", 365, 900, 4.0, 2.5, "Mechanical"),
    ],
    "Electric Motor": [
        ("Winding insulation breakdown", "Emergency rewind - motor insulation failure", 730, None, 16.0, 8.0, "Electrical"),
        ("Bearing failure", "Corrective replacement - motor bearing failure", 540, None, 4.0, 3.0, "Mechanical"),
        ("Terminal box fault", "Electrical fault - terminal box damage / tracking", 900, None, 3.0, 2.0, "Electrical"),
    ],
    "Pressure Vessel": [
        ("Internal corrosion pitting", "Corrective repair - corrosion pitting found at inspection", 1095, None, 24.0, 10.0, "Mechanical"),
        ("Nozzle weld crack", "Emergency repair - nozzle weld cracking discovered", 1460, None, 32.0, 14.0, "Mechanical"),
    ],
    "Heat Exchanger": [
        ("Tube bundle fouling", "Corrective cleaning - severe tube fouling / blockage", 365, None, 12.0, 4.0, "Mechanical"),
        ("Tube leak", "Emergency repair - tube bundle leak detected", 540, None, 16.0, 6.0, "Mechanical"),
        ("Gasket failure", "Corrective repair - shell/tube gasket leak", 730, None, 6.0, 3.0, "Mechanical"),
    ],
    "Control Valve": [
        ("Actuator failure", "Emergency repair - actuator failure, valve stuck", 365, None, 4.0, 3.0, "Instrumentation"),
        ("Positioner fault", "Corrective repair - positioner calibration drift / failure", 300, None, 2.0, 2.0, "Instrumentation"),
        ("Seat/plug erosion", "Corrective overhaul - erosion damage to seat and plug", 540, None, 8.0, 4.0, "Instrumentation"),
    ],
    "Pressure Transmitter": [
        ("Impulse line blockage", "Corrective repair - impulse line blocked", 180, None, 2.0, 1.5, "Instrumentation"),
        ("Transmitter drift / failure", "Replacement - pressure transmitter out of range", 365, None, 1.5, 2.0, "Instrumentation"),
    ],
    "Flow Meter": [
        ("Sensor fouling", "Corrective cleaning - flow meter sensor fouled", 270, None, 3.0, 2.0, "Instrumentation"),
        ("Electronics failure", "Replacement - flow meter electronics failure", 540, None, 4.0, 3.0, "Instrumentation"),
    ],
    "Fire & Gas Detector": [
        ("Detector head failure", "Corrective replacement - detector head failed self-test", 540, None, 1.0, 1.5, "Instrumentation"),
        ("Wiring/connection fault", "Corrective repair - wiring fault causing spurious alarm", 365, None, 2.0, 1.5, "Instrumentation"),
    ],
    "Switchgear Panel": [
        ("Breaker contact failure", "Emergency repair - breaker contact wear / failure", 1095, None, 8.0, 6.0, "Electrical"),
        ("Busbar overheating", "Emergency repair - busbar joint overheating detected", 1460, None, 12.0, 8.0, "Electrical"),
    ],
    "UPS": [
        ("Battery cell failure", "Corrective replacement - battery cell degraded below capacity", 365, 730, 4.0, 3.0, "Electrical"),
        ("Inverter fault", "Emergency repair - inverter module failure", 730, 1500, 6.0, 5.0, "Electrical"),
    ],
    "Fan / Blower": [
        ("Belt failure", "Emergency repair - drive belt failure", 270, 720, 2.0, 2.0, "Mechanical"),
        ("Bearing seizure", "Corrective repair - fan bearing seizure", 365, 900, 4.0, 3.0, "Mechanical"),
        ("Impeller imbalance", "Corrective repair - impeller imbalance causing vibration", 540, 1200, 6.0, 3.5, "Mechanical"),
    ],
    "Safety Valve": [
        ("Valve seat leak", "Corrective repair - safety valve seat leak found on test", 730, None, 4.0, 3.0, "Mechanical"),
        ("Stuck open/closed", "Emergency repair - safety valve failed to reseat", 900, None, 6.0, 4.0, "Mechanical"),
    ],
}

# Tasks with historically demonstrated deferral (these will show consistent ~3-6 month deferrals)
DEFERRED_TASK_CODES = {
    "CP-M04",  # Coupling inspection - routinely deferred ~90 days
    "CP-M05",  # Pump overhaul - routinely deferred ~180 days
    "HX-M02",  # Heat exchanger cleaning - routinely deferred ~120 days
    "PV-S01",  # Vessel external inspection - deferred ~60 days
    "CC-M05",  # Compressor rotor dynamics - deferred ~90 days
    "RP-M03",  # Recip pump piston inspection - deferred ~90 days
    "FB-M03",  # Fan impeller inspection - deferred ~60 days
    "SV-S02",  # Safety valve visual - deferred ~45 days
}


def generate_assets():
    assets = []
    tag_counter = {}

    for eq_class, cfg in EQUIPMENT_CLASSES.items():
        prefix = CLASS_PREFIXES[eq_class]
        count = cfg["count"]
        has_standby = cfg["has_standby"]
        discipline = cfg["discipline"]

        if prefix not in tag_counter:
            tag_counter[prefix] = 1

        i = 0
        while i < count:
            if has_standby and i + 1 < count:
                # Create duty/standby pair
                num_a = tag_counter[prefix]
                num_b = tag_counter[prefix] + 1
                tag_a = f"{prefix}-{num_a:03d}A"
                tag_b = f"{prefix}-{num_b:03d}B"
                tag_counter[prefix] += 2

                system = random.choice(SYSTEMS)
                location = random.choice(LOCATIONS)
                manufacturer = random.choice(MANUFACTURERS[eq_class])
                model = f"Model-{random.randint(100,999)}"
                install_year = random.randint(2005, 2018)
                criticality = random.choices(["A", "B", "C"], weights=[0.4, 0.4, 0.2])[0]
                service = f"{system} - {eq_class}"

                assets.append({
                    "tag": tag_a,
                    "description": f"{eq_class} - {service}",
                    "equipment_class": eq_class,
                    "system": system,
                    "location": location,
                    "criticality": criticality,
                    "operating_status": "Duty",
                    "paired_tag": tag_b,
                    "manufacturer": manufacturer,
                    "model": model,
                    "installation_year": install_year,
                    "service_description": service,
                    "discipline": discipline,
                })
                assets.append({
                    "tag": tag_b,
                    "description": f"{eq_class} - {service}",
                    "equipment_class": eq_class,
                    "system": system,
                    "location": location,
                    "criticality": criticality,
                    "operating_status": "Standby",
                    "paired_tag": tag_a,
                    "manufacturer": manufacturer,
                    "model": model,
                    "installation_year": install_year,
                    "service_description": service,
                    "discipline": discipline,
                })
                i += 2
            else:
                num = tag_counter[prefix]
                tag = f"{prefix}-{num:03d}"
                tag_counter[prefix] += 1

                system = random.choice(SYSTEMS)
                location = random.choice(LOCATIONS)
                manufacturer = random.choice(MANUFACTURERS[eq_class])
                model = f"Model-{random.randint(100,999)}"
                install_year = random.randint(2005, 2018)
                criticality = random.choices(["A", "B", "C"], weights=[0.3, 0.45, 0.25])[0]
                service = f"{system} - {eq_class}"

                assets.append({
                    "tag": tag,
                    "description": f"{eq_class} - {service}",
                    "equipment_class": eq_class,
                    "system": system,
                    "location": location,
                    "criticality": criticality,
                    "operating_status": "Solo",
                    "paired_tag": None,
                    "manufacturer": manufacturer,
                    "model": model,
                    "installation_year": install_year,
                    "service_description": service,
                    "discipline": discipline,
                })
                i += 1

    return pd.DataFrame(assets)


def generate_work_orders(assets_df):
    work_orders = []
    wo_counter = [10000]

    for _, asset in assets_df.iterrows():
        eq_class = asset["equipment_class"]
        is_standby = asset["operating_status"] == "Standby"
        task_codes = CLASS_STRATEGY_MAP.get(eq_class, [])

        for task_code in task_codes:
            strat = STRATEGY_LOOKUP.get(task_code)
            if strat is None:
                continue

            (code, desc, interval_days, est_hours, basis, duty_only, standby_applies) = strat

            # Skip tasks not applicable to standby
            if is_standby and not standby_applies:
                continue

            # Generate WO history from START_DATE to END_DATE
            scheduled = START_DATE + timedelta(days=random.randint(0, interval_days))

            while scheduled <= END_DATE:
                wo_num = f"WO-{wo_counter[0]:06d}"
                wo_counter[0] += 1

                # Is this a task with a known deferral pattern?
                is_deferred_task = task_code in DEFERRED_TASK_CODES
                deferral_days = 0
                actual_date = None
                status = "Completed"

                if scheduled > date.today():
                    status = "Open"
                    actual_date = None
                    deferral_days = None
                elif is_deferred_task and random.random() < 0.80:
                    # Consistently deferred - 80% of occurrences are late
                    if task_code == "CP-M04":
                        delay = random.randint(60, 120)
                    elif task_code == "CP-M05":
                        delay = random.randint(120, 240)
                    elif task_code == "HX-M02":
                        delay = random.randint(90, 150)
                    elif task_code == "PV-S01":
                        delay = random.randint(30, 90)
                    elif task_code == "CC-M05":
                        delay = random.randint(60, 130)
                    elif task_code == "RP-M03":
                        delay = random.randint(60, 120)
                    elif task_code == "FB-M03":
                        delay = random.randint(30, 90)
                    elif task_code == "SV-S02":
                        delay = random.randint(20, 60)
                    else:
                        delay = random.randint(30, 60)
                    deferral_days = delay
                    actual_date = scheduled + timedelta(days=delay)
                    status = "Completed"
                else:
                    # On time or slightly early/late (within tolerance)
                    noise = random.randint(-7, 14)
                    actual_date = scheduled + timedelta(days=max(0, noise))
                    deferral_days = max(0, noise)
                    status = "Completed"

                # Cost: standby gets same estimate but actual sometimes lower (less wear)
                base_cost = est_hours * random.uniform(85, 120)  # £ per hour blended rate
                if is_standby:
                    actual_cost_mult = random.uniform(0.7, 1.0)
                else:
                    actual_cost_mult = random.uniform(0.85, 1.25)

                actual_cost = round(base_cost * actual_cost_mult, 2) if actual_date else None
                actual_hrs = round(est_hours * actual_cost_mult, 2) if actual_date else None

                work_orders.append({
                    "wo_number": wo_num,
                    "asset_tag": asset["tag"],
                    "wo_type": "Statutory" if basis == "Statutory" else ("PPM" if basis in ("Time-based", "Condition-based") else "PPM"),
                    "task_description": desc,
                    "task_code": task_code,
                    "scheduled_date": scheduled,
                    "actual_completion_date": actual_date,
                    "status": status,
                    "estimated_hours": round(est_hours, 2),
                    "actual_hours": actual_hrs,
                    "estimated_cost": round(base_cost, 2),
                    "actual_cost": actual_cost,
                    "discipline": asset["discipline"],
                    "failure_mode": None,
                    "notes": f"Deferred {deferral_days} days past schedule" if deferral_days and deferral_days > 14 else None,
                    "deferral_days": deferral_days,
                })

                scheduled += timedelta(days=interval_days)

    return pd.DataFrame(work_orders)


def generate_corrective_work_orders(assets_df):
    """
    Generate corrective (breakdown) work orders using a single per-asset MTBF.
    Each failure event then randomly draws a failure mode from the class library.
    This avoids the multiple-timeline inflation that occurs when each failure mode
    generates its own independent timeline.

    Target rates (corrective events per asset per year):
      Centrifugal Pump (duty): ~0.8   Standby: ~0.2
      Reciprocating Pump:      ~0.8
      Centrifugal Compressor:  ~0.6
      Gas Turbine Generator:   ~1.0
      Electric Motor:          ~0.2
      Pressure Vessel:         ~0.08
      Heat Exchanger:          ~0.5
      Control Valve:           ~0.4
      Pressure Transmitter:    ~0.25
      Flow Meter:              ~0.3
      Fire & Gas Detector:     ~0.15
      Switchgear Panel:        ~0.15
      UPS:                     ~0.2
      Fan / Blower (duty):     ~0.7   Standby: ~0.2
      Safety Valve:            ~0.15
    """

    # Asset-level MTBF in days, keyed by (equipment_class, operating_status)
    # operating_status values: "Duty", "Standby", "Solo"
    ASSET_MTBF = {
        ("Centrifugal Pump",       "Duty"):    450,
        ("Centrifugal Pump",       "Standby"): 1825,
        ("Centrifugal Pump",       "Solo"):    450,
        ("Reciprocating Pump",     "Duty"):    450,
        ("Reciprocating Pump",     "Standby"): 1460,
        ("Reciprocating Pump",     "Solo"):    450,
        ("Centrifugal Compressor", "Duty"):    600,
        ("Centrifugal Compressor", "Standby"): 1825,
        ("Centrifugal Compressor", "Solo"):    600,
        ("Gas Turbine Generator",  "Duty"):    365,
        ("Gas Turbine Generator",  "Standby"): 1095,
        ("Gas Turbine Generator",  "Solo"):    365,
        ("Electric Motor",         "Solo"):    1825,
        ("Pressure Vessel",        "Solo"):    4380,
        ("Heat Exchanger",         "Solo"):    730,
        ("Control Valve",          "Solo"):    900,
        ("Pressure Transmitter",   "Solo"):    1460,
        ("Flow Meter",             "Solo"):    1095,
        ("Fire & Gas Detector",    "Solo"):    2190,
        ("Switchgear Panel",       "Solo"):    2190,
        ("UPS",                    "Duty"):    1825,
        ("UPS",                    "Standby"): 3650,
        ("UPS",                    "Solo"):    1825,
        ("Fan / Blower",           "Duty"):    520,
        ("Fan / Blower",           "Standby"): 1825,
        ("Fan / Blower",           "Solo"):    520,
        ("Safety Valve",           "Solo"):    2190,
    }

    corrective_wos = []
    wo_counter = [90000]

    for _, asset in assets_df.iterrows():
        eq_class = asset["equipment_class"]
        op_status = asset["operating_status"]
        failure_defs = FAILURE_MODES.get(eq_class, [])
        if not failure_defs:
            continue

        mtbf = ASSET_MTBF.get((eq_class, op_status))
        if mtbf is None:
            continue

        # Scatter first failure within first MTBF window
        failure_date = START_DATE + timedelta(days=random.randint(int(mtbf * 0.2), int(mtbf * 1.3)))

        while failure_date <= END_DATE:
            # Pick a failure mode at random, weighted by inverse MTBF (more common modes more likely)
            # Use uniform weighting for simplicity — all modes equally likely
            fm_def = random.choice(failure_defs)
            (failure_mode, description, _mtbf_d, _mtbf_s, repair_hours, cost_mult, fm_discipline) = fm_def

            wo_num = f"CM-{wo_counter[0]:06d}"
            wo_counter[0] += 1

            repair_days = random.randint(0, 3)
            completion_date = min(failure_date + timedelta(days=repair_days), END_DATE)

            base_rate = random.uniform(110, 160)
            est_cost = round(repair_hours * base_rate * cost_mult, 2)
            actual_cost = round(est_cost * random.uniform(0.85, 1.30), 2)
            actual_hours = round(repair_hours * random.uniform(0.8, 1.4), 2)

            deferred_link = None
            if op_status == "Duty" and random.random() < 0.12:
                deferred_link = "Failure may be associated with deferred maintenance — review PPM history"

            corrective_wos.append({
                "wo_number": wo_num,
                "asset_tag": asset["tag"],
                "wo_type": "Corrective",
                "task_description": description,
                "task_code": f"CM-{eq_class[:3].upper().replace(' ','')}",
                "scheduled_date": failure_date,
                "actual_completion_date": completion_date,
                "status": "Completed",
                "estimated_hours": round(repair_hours, 2),
                "actual_hours": actual_hours,
                "estimated_cost": est_cost,
                "actual_cost": actual_cost,
                "discipline": fm_discipline,
                "failure_mode": failure_mode,
                "notes": deferred_link,
                "deferral_days": None,
            })

            # Next failure: MTBF ±40% scatter
            next_interval = int(mtbf * random.uniform(0.6, 1.4))
            failure_date = failure_date + timedelta(days=next_interval)

    return pd.DataFrame(corrective_wos)


def generate_strategies():
    rows = []
    strat_id_counter = 1
    for code, desc, interval, hours, basis, duty_only, standby in MAINTENANCE_STRATEGIES:
        # Determine equipment class from prefix
        prefix = code.split("-")[0]
        class_map = {
            "CP": "Centrifugal Pump",
            "RP": "Reciprocating Pump",
            "CC": "Centrifugal Compressor",
            "GT": "Gas Turbine Generator",
            "EM": "Electric Motor",
            "PV": "Pressure Vessel",
            "HX": "Heat Exchanger",
            "CV": "Control Valve",
            "PT": "Pressure Transmitter",
            "FM": "Flow Meter",
            "FG": "Fire & Gas Detector",
            "SW": "Switchgear Panel",
            "UP": "UPS",
            "FB": "Fan / Blower",
            "SV": "Safety Valve",
        }
        eq_class = class_map.get(prefix, "General")
        discipline_map = {
            "CP": "Mechanical", "RP": "Mechanical", "CC": "Mechanical",
            "GT": "Mechanical", "EM": "Electrical", "PV": "Mechanical",
            "HX": "Mechanical", "CV": "Instrumentation", "PT": "Instrumentation",
            "FM": "Instrumentation", "FG": "Instrumentation", "SW": "Electrical",
            "UP": "Electrical", "FB": "Mechanical", "SV": "Mechanical",
        }
        disc = discipline_map.get(prefix, "Mechanical")
        rows.append({
            "strategy_id": f"STR-{strat_id_counter:04d}",
            "equipment_class": eq_class,
            "task_code": code,
            "task_description": desc,
            "interval_days": interval,
            "estimated_hours": hours,
            "discipline": disc,
            "basis": basis,
            "applies_to_duty": True,
            "applies_to_standby": standby,
            "notes": None,
        })
        strat_id_counter += 1
    return pd.DataFrame(rows)


def generate_all(output_dir: str):
    os.makedirs(output_dir, exist_ok=True)

    print("Generating assets...")
    assets_df = generate_assets()

    print("Generating PPM work orders (this may take a moment)...")
    ppm_df = generate_work_orders(assets_df)

    print("Generating corrective (breakdown) work orders...")
    corrective_df = generate_corrective_work_orders(assets_df)

    wo_df = pd.concat([ppm_df, corrective_df], ignore_index=True)
    wo_df = wo_df.sort_values("scheduled_date").reset_index(drop=True)

    print("Generating maintenance strategies...")
    strat_df = generate_strategies()

    # Write to Excel
    asset_path = os.path.join(output_dir, "asset_register.xlsx")
    wo_path = os.path.join(output_dir, "work_order_history.xlsx")
    strat_path = os.path.join(output_dir, "maintenance_strategies.xlsx")

    assets_df.to_excel(asset_path, index=False)
    wo_df.to_excel(wo_path, index=False)
    strat_df.to_excel(strat_path, index=False)

    ppm_count = len(ppm_df)
    corrective_count = len(corrective_df)
    print(f"Assets: {len(assets_df)} records -> {asset_path}")
    print(f"Work Orders: {len(wo_df)} total ({ppm_count} PPM/Statutory, {corrective_count} Corrective) -> {wo_path}")
    print(f"Strategies: {len(strat_df)} records -> {strat_path}")

    return assets_df, wo_df, strat_df


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "../demo_data"
    generate_all(out)
