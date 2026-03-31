"""
Demo data generator for BP Maintenance Demo.
Generates realistic offshore oil & gas platform maintenance data across 5 platforms.
"""
import random
import pandas as pd
import numpy as np
from datetime import date, timedelta
import os

random.seed(42)
np.random.seed(42)

START_DATE = date(2019, 1, 1)
END_DATE = date(2024, 12, 31)

# -------------------------------------------------------------------
# Five O&G platforms, each with distinct characteristics
# -------------------------------------------------------------------
PLATFORMS = [
    {
        "name": "Alpha",
        "code": "ALF",
        "description": "North Sea FPSO — mature asset base, baseline performance",
        "install_year_range": (2005, 2018),
        "criticality_weights": [0.40, 0.40, 0.20],   # A, B, C
        "mtbf_multiplier": 1.0,
        "deferral_rate": 0.80,   # fraction of deferred-task WOs that are actually late
        "count_overrides": {},
    },
    {
        "name": "Bravo",
        "code": "BRV",
        "description": "Norwegian fixed platform — newer equipment, best maintained fleet",
        "install_year_range": (2013, 2023),
        "criticality_weights": [0.30, 0.45, 0.25],
        "mtbf_multiplier": 1.5,   # more reliable
        "deferral_rate": 0.50,    # fewer deferrals — tighter maintenance discipline
        "count_overrides": {
            "Centrifugal Pump": 12,
            "Gas Turbine Generator": 2,
            "Centrifugal Compressor": 2,
            "Fire & Gas Detector": 18,
            "Safety Valve": 12,
        },
    },
    {
        "name": "Charlie",
        "code": "CHR",
        "description": "Gulf of Mexico deepwater FPSO — aging infrastructure, high CM burden",
        "install_year_range": (1999, 2013),
        "criticality_weights": [0.50, 0.35, 0.15],
        "mtbf_multiplier": 0.60,  # least reliable
        "deferral_rate": 0.75,
        "count_overrides": {
            "Pressure Vessel": 18,
            "Heat Exchanger": 14,
            "Control Valve": 22,
        },
    },
]

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

# Default counts per equipment class (Alpha baseline)
EQUIPMENT_CLASSES = {
    "Centrifugal Pump":       {"discipline": "Mechanical",       "has_standby": True,  "count": 16},
    "Reciprocating Pump":     {"discipline": "Mechanical",       "has_standby": True,  "count": 6},
    "Centrifugal Compressor": {"discipline": "Mechanical",       "has_standby": True,  "count": 4},
    "Gas Turbine Generator":  {"discipline": "Mechanical",       "has_standby": True,  "count": 3},
    "Electric Motor":         {"discipline": "Electrical",       "has_standby": False, "count": 12},
    "Pressure Vessel":        {"discipline": "Mechanical",       "has_standby": False, "count": 14},
    "Heat Exchanger":         {"discipline": "Mechanical",       "has_standby": False, "count": 10},
    "Control Valve":          {"discipline": "Instrumentation",  "has_standby": False, "count": 20},
    "Pressure Transmitter":   {"discipline": "Instrumentation",  "has_standby": False, "count": 18},
    "Flow Meter":             {"discipline": "Instrumentation",  "has_standby": False, "count": 12},
    "Fire & Gas Detector":    {"discipline": "Instrumentation",  "has_standby": False, "count": 24},
    "Switchgear Panel":       {"discipline": "Electrical",       "has_standby": False, "count": 8},
    "UPS":                    {"discipline": "Electrical",       "has_standby": True,  "count": 4},
    "Fan / Blower":           {"discipline": "Mechanical",       "has_standby": True,  "count": 8},
    "Safety Valve":           {"discipline": "Mechanical",       "has_standby": False, "count": 16},
}

MAINTENANCE_STRATEGIES = [
    # (task_code, description, interval_days, hours, basis, duty_only, standby_applies)
    ("CP-M01", "Lubrication oil check and top-up", 30, 0.5, "Time-based", False, True),
    ("CP-M02", "Vibration and temperature monitoring", 30, 1.0, "Condition-based", False, True),
    ("CP-M03", "Mechanical seal inspection", 90, 2.0, "Time-based", False, True),
    ("CP-M04", "Coupling inspection and alignment check", 180, 3.0, "Time-based", False, True),
    ("CP-M05", "Full overhaul - impeller, bearings, seals", 1825, 16.0, "Time-based", False, True),
    ("CP-E01", "Motor insulation resistance test", 365, 1.5, "Time-based", False, True),
    ("CP-E02", "Motor thermal imaging", 180, 1.0, "Condition-based", False, True),
    ("RP-M01", "Lubrication oil change", 90, 2.0, "Time-based", False, True),
    ("RP-M02", "Valve inspection and replacement", 180, 4.0, "Time-based", False, True),
    ("RP-M03", "Piston and liner inspection", 365, 8.0, "Time-based", False, True),
    ("RP-M04", "Full overhaul", 1825, 24.0, "Time-based", False, True),
    ("CC-M01", "Lube oil system check", 30, 1.0, "Time-based", False, True),
    ("CC-M02", "Vibration analysis", 30, 2.0, "Condition-based", False, True),
    ("CC-M03", "Dry gas seal monitoring", 90, 2.0, "Condition-based", False, True),
    ("CC-M04", "Coupling and alignment inspection", 180, 4.0, "Time-based", False, True),
    ("CC-M05", "Rotor dynamics check", 365, 8.0, "Time-based", False, True),
    ("CC-M06", "Major overhaul", 1825, 48.0, "Time-based", False, True),
    ("GT-M01", "Combustion inspection", 365, 40.0, "Time-based", False, False),
    ("GT-M02", "Hot section inspection", 730, 80.0, "Time-based", False, False),
    ("GT-M03", "Major overhaul", 2190, 160.0, "Time-based", False, False),
    ("GT-E01", "Generator insulation test", 365, 4.0, "Time-based", False, True),
    ("GT-E02", "Excitation system check", 180, 2.0, "Time-based", False, True),
    ("PV-S01", "External visual inspection", 365, 4.0, "Statutory", False, False),
    ("PV-S02", "Internal inspection (Written Scheme)", 730, 16.0, "Statutory", False, False),
    ("PV-S03", "Pressure test", 1825, 8.0, "Statutory", False, False),
    ("PV-M01", "Corrosion monitoring - UT thickness", 180, 3.0, "Condition-based", False, False),
    ("HX-M01", "Performance monitoring - dP and temperature", 90, 1.0, "Condition-based", False, False),
    ("HX-M02", "Tube bundle inspection and cleaning", 365, 8.0, "Time-based", False, False),
    ("HX-M03", "Pressure test", 1825, 4.0, "Statutory", False, False),
    ("CV-I01", "Partial stroke test", 180, 1.0, "Time-based", False, False),
    ("CV-I02", "Full stroke test and calibration", 365, 2.0, "Time-based", False, False),
    ("CV-I03", "Actuator and positioner overhaul", 1825, 6.0, "Time-based", False, False),
    ("PT-I01", "Calibration and loop check", 365, 1.5, "Time-based", False, False),
    ("PT-I02", "Impulse line check and blow-down", 180, 1.0, "Time-based", False, False),
    ("FM-I01", "Calibration verification", 365, 2.0, "Time-based", False, False),
    ("FM-I02", "Strainer check and cleaning", 180, 1.0, "Time-based", False, False),
    ("FG-I01", "Functional test", 90, 0.5, "Statutory", False, False),
    ("FG-I02", "Calibration check", 180, 1.0, "Statutory", False, False),
    ("FG-I03", "Detector head replacement", 1825, 0.5, "Time-based", False, False),
    ("SW-E01", "Thermal imaging", 365, 2.0, "Condition-based", False, False),
    ("SW-E02", "Contact resistance test", 730, 4.0, "Time-based", False, False),
    ("SW-E03", "Breaker maintenance and testing", 1825, 8.0, "Time-based", False, False),
    ("UP-E01", "Battery capacity test", 365, 3.0, "Time-based", False, True),
    ("UP-E02", "Battery visual inspection", 90, 1.0, "Time-based", False, True),
    ("UP-E03", "Full load transfer test", 180, 2.0, "Time-based", False, True),
    ("FB-M01", "Belt inspection and tension check", 90, 1.0, "Time-based", False, True),
    ("FB-M02", "Bearing lubrication", 90, 0.5, "Time-based", False, True),
    ("FB-M03", "Impeller inspection", 365, 3.0, "Time-based", False, True),
    ("FB-E01", "Motor insulation test", 365, 1.5, "Time-based", False, True),
    ("SV-S01", "Lift test and set pressure check", 730, 4.0, "Statutory", False, False),
    ("SV-S02", "Visual inspection", 365, 1.0, "Statutory", False, False),
    ("EM-E01", "Insulation resistance test", 365, 1.5, "Time-based", False, False),
    ("EM-E02", "Thermal imaging", 180, 1.0, "Condition-based", False, False),
    ("EM-M01", "Bearing lubrication", 90, 0.5, "Time-based", False, False),
]

CLASS_STRATEGY_MAP = {
    "Centrifugal Pump":       ["CP-M01","CP-M02","CP-M03","CP-M04","CP-M05","CP-E01","CP-E02"],
    "Reciprocating Pump":     ["RP-M01","RP-M02","RP-M03","RP-M04"],
    "Centrifugal Compressor": ["CC-M01","CC-M02","CC-M03","CC-M04","CC-M05","CC-M06"],
    "Gas Turbine Generator":  ["GT-M01","GT-M02","GT-M03","GT-E01","GT-E02"],
    "Pressure Vessel":        ["PV-S01","PV-S02","PV-S03","PV-M01"],
    "Heat Exchanger":         ["HX-M01","HX-M02","HX-M03"],
    "Control Valve":          ["CV-I01","CV-I02","CV-I03"],
    "Pressure Transmitter":   ["PT-I01","PT-I02"],
    "Flow Meter":             ["FM-I01","FM-I02"],
    "Fire & Gas Detector":    ["FG-I01","FG-I02","FG-I03"],
    "Switchgear Panel":       ["SW-E01","SW-E02","SW-E03"],
    "UPS":                    ["UP-E01","UP-E02","UP-E03"],
    "Fan / Blower":           ["FB-M01","FB-M02","FB-M03","FB-E01"],
    "Safety Valve":           ["SV-S01","SV-S02"],
    "Electric Motor":         ["EM-E01","EM-E02","EM-M01"],
}

STRATEGY_LOOKUP = {s[0]: s for s in MAINTENANCE_STRATEGIES}

CLASS_PREFIXES = {
    "Centrifugal Pump":       "CP",
    "Reciprocating Pump":     "RP",
    "Centrifugal Compressor": "CC",
    "Gas Turbine Generator":  "GTG",
    "Electric Motor":         "EM",
    "Pressure Vessel":        "PV",
    "Heat Exchanger":         "HX",
    "Control Valve":          "CV",
    "Pressure Transmitter":   "PT",
    "Flow Meter":             "FM",
    "Fire & Gas Detector":    "FGD",
    "Switchgear Panel":       "SW",
    "UPS":                    "UPS",
    "Fan / Blower":           "FB",
    "Safety Valve":           "SV",
}

MANUFACTURERS = {
    "Centrifugal Pump":       ["Flowserve", "Sulzer", "KSB", "Grundfos"],
    "Reciprocating Pump":     ["Gardner Denver", "Weir SPM", "Sundyne"],
    "Centrifugal Compressor": ["Solar Turbines", "GE Oil & Gas", "MAN Energy"],
    "Gas Turbine Generator":  ["GE", "Siemens", "Rolls-Royce"],
    "Electric Motor":         ["ABB", "Siemens", "WEG", "Nidec"],
    "Pressure Vessel":        ["Britannia", "Whessoe", "John Wood Group"],
    "Heat Exchanger":         ["Alfa Laval", "Tranter", "Kelvion"],
    "Control Valve":          ["Emerson", "Metso", "Flowserve"],
    "Pressure Transmitter":   ["Emerson Rosemount", "Honeywell", "Yokogawa"],
    "Flow Meter":             ["Emerson Rosemount", "Endress+Hauser", "ABB"],
    "Fire & Gas Detector":    ["MSA", "Honeywell", "Draeger", "Det-Tronics"],
    "Switchgear Panel":       ["ABB", "Schneider Electric", "Siemens"],
    "UPS":                    ["Eaton", "APC", "Vertiv"],
    "Fan / Blower":           ["Howden", "Dresser-Rand", "Aerovent"],
    "Safety Valve":           ["Emerson Crosby", "Leser", "Sempell"],
}

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

# ── H2.2: Failure distribution type per equipment class ──────────────────────
# "random"  → exponential inter-failure times (CV ≈ 1.0) — hard-time unjustified
# "wearout" → tight normal distribution (CV ≈ 0.15)      — hard-time justified
# "mixed"   → log-normal with moderate spread (CV ≈ 0.55) — CBM recommended
FAILURE_DISTRIBUTION = {
    "Control Valve":          "random",   # electronic/actuator faults: random
    "Pressure Transmitter":   "random",   # electronic sensor failure: random
    "Flow Meter":             "random",   # electronic failure: random
    "Fire & Gas Detector":    "random",   # electronic component: random
    "Switchgear Panel":       "random",   # electrical arcing/contact: random
    "Safety Valve":           "wearout",  # seat erosion / spring fatigue
    "Pressure Vessel":        "wearout",  # corrosion fatigue: age-related
    "Heat Exchanger":         "wearout",  # tube fatigue/fouling: wear-out
    "Electric Motor":         "wearout",  # insulation ageing: wear-out
    "UPS":                    "wearout",  # battery capacity degradation
    "Centrifugal Pump":       "mixed",    # multiple failure modes
    "Reciprocating Pump":     "mixed",    # mixed wear-out + random
    "Centrifugal Compressor": "mixed",    # mixed — seal random, bearing wear-out
    "Gas Turbine Generator":  "mixed",    # hot section wear + random faults
    "Fan / Blower":           "mixed",    # bearing wear + random belt failure
}

# ── H2.3: Major-effort tasks skipped for Criticality C assets ────────────────
# Crit C = non-safety-critical; run-to-failure or minimal PM is acceptable.
# Skipping major overhauls & thorough inspections exposes the PPM effort gap.
CRIT_C_SKIP_TASKS = {
    "CP-M05",   # Pump full overhaul
    "CP-E01",   # Motor insulation resistance test
    "CC-M05",   # Compressor rotor dynamics check
    "CC-M06",   # Compressor major overhaul
    "RP-M03",   # Recip pump piston & liner inspection
    "RP-M04",   # Recip pump full overhaul
    "GT-M02",   # Gas turbine hot section inspection
    "GT-M03",   # Gas turbine major overhaul
    "HX-M02",   # Heat exchanger tube bundle inspection
    "SW-E02",   # Switchgear contact resistance test
    "SW-E03",   # Switchgear breaker maintenance
    "EM-E01",   # Electric motor insulation test
    "FB-M03",   # Fan impeller inspection
    "SV-S01",   # Safety valve lift test (non-statutory basis for Crit C)
}

# Tasks with historically demonstrated deferral patterns
DEFERRED_TASK_CODES = {
    "CP-M04": (60, 120),    # Coupling inspection
    "CP-M05": (120, 240),   # Pump overhaul
    "HX-M02": (90, 150),    # Heat exchanger cleaning
    "PV-S01": (30, 90),     # Vessel external inspection
    "CC-M05": (60, 130),    # Compressor rotor dynamics
    "RP-M03": (60, 120),    # Recip pump piston inspection
    "FB-M03": (30, 90),     # Fan impeller inspection
    "SV-S02": (20, 60),     # Safety valve visual
}

# Asset-level MTBF in days (before platform multiplier)
# Calibrated against OREDA (Offshore Reliability Data) critical failure rates
ASSET_MTBF = {
    # Centrifugal Pump: OREDA 0.3–0.8/yr → target ~0.5/yr duty → 730d
    ("Centrifugal Pump",       "Duty"):    730,
    ("Centrifugal Pump",       "Standby"): 2920,
    ("Centrifugal Pump",       "Solo"):    730,
    # Reciprocating Pump: OREDA 0.5–1.5/yr → target ~0.75/yr → 487d
    ("Reciprocating Pump",     "Duty"):    487,
    ("Reciprocating Pump",     "Standby"): 1825,
    ("Reciprocating Pump",     "Solo"):    487,
    # Centrifugal Compressor: OREDA 0.2–0.5/yr → target ~0.3/yr → 1095d
    ("Centrifugal Compressor", "Duty"):    1095,
    ("Centrifugal Compressor", "Standby"): 3650,
    ("Centrifugal Compressor", "Solo"):    1095,
    # Gas Turbine Generator: OREDA 0.1–0.3/yr → target ~0.15/yr → 2190d
    ("Gas Turbine Generator",  "Duty"):    2190,
    ("Gas Turbine Generator",  "Standby"): 6570,
    ("Gas Turbine Generator",  "Solo"):    2190,
    # Electric Motor: OREDA 0.05–0.2/yr → target ~0.15/yr → 2190d
    ("Electric Motor",         "Solo"):    2190,
    # Pressure Vessel: OREDA 0.01–0.05/yr → target ~0.03/yr → 12000d
    ("Pressure Vessel",        "Solo"):    12000,
    # Heat Exchanger: OREDA 0.05–0.2/yr → target ~0.1/yr → 3650d
    ("Heat Exchanger",         "Solo"):    3650,
    # Control Valve: OREDA 0.1–0.5/yr → target ~0.3/yr → 1095d
    ("Control Valve",          "Solo"):    1095,
    # Pressure Transmitter: OREDA 0.05–0.2/yr → target ~0.1/yr → 3650d
    ("Pressure Transmitter",   "Solo"):    3650,
    # Flow Meter: OREDA 0.1–0.3/yr → target ~0.2/yr → 1825d
    ("Flow Meter",             "Solo"):    1825,
    # Fire & Gas Detector: OREDA 0.05–0.15/yr → target ~0.08/yr → 4380d
    ("Fire & Gas Detector",    "Solo"):    4380,
    # Switchgear Panel: OREDA 0.05–0.15/yr → target ~0.08/yr → 4380d
    ("Switchgear Panel",       "Solo"):    4380,
    # UPS: OREDA 0.05–0.15/yr → target ~0.1/yr → 3650d
    ("UPS",                    "Duty"):    3650,
    ("UPS",                    "Standby"): 7300,
    ("UPS",                    "Solo"):    3650,
    # Fan / Blower: OREDA 0.3–0.8/yr → target ~0.5/yr → 730d
    ("Fan / Blower",           "Duty"):    730,
    ("Fan / Blower",           "Standby"): 2920,
    ("Fan / Blower",           "Solo"):    730,
    # Safety Valve: OREDA 0.05–0.2/yr → target ~0.1/yr → 3650d
    ("Safety Valve",           "Solo"):    3650,
}


def generate_assets_for_platform(platform: dict) -> pd.DataFrame:
    assets = []
    tag_counter = {}
    pcode = platform["code"]
    yr_lo, yr_hi = platform["install_year_range"]
    crit_w = platform["criticality_weights"]

    for eq_class, cfg in EQUIPMENT_CLASSES.items():
        prefix = CLASS_PREFIXES[eq_class]
        count = platform["count_overrides"].get(eq_class, cfg["count"])
        has_standby = cfg["has_standby"]
        discipline = cfg["discipline"]

        # Ensure even count for paired classes
        if has_standby and count % 2 != 0:
            count = max(2, count - 1)

        pf_prefix = f"{pcode}-{prefix}"
        if pf_prefix not in tag_counter:
            tag_counter[pf_prefix] = 1

        i = 0
        while i < count:
            if has_standby and i + 1 < count:
                num_a = tag_counter[pf_prefix]
                num_b = tag_counter[pf_prefix] + 1
                tag_a = f"{pcode}-{prefix}-{num_a:03d}A"
                tag_b = f"{pcode}-{prefix}-{num_b:03d}B"
                tag_counter[pf_prefix] += 2

                system = random.choice(SYSTEMS)
                location = random.choice(LOCATIONS)
                manufacturer = random.choice(MANUFACTURERS[eq_class])
                model = f"Model-{random.randint(100,999)}"
                install_year = random.randint(yr_lo, yr_hi)
                criticality = random.choices(["A", "B", "C"], weights=crit_w)[0]
                service = f"{system} - {eq_class}"

                assets.append({
                    "tag": tag_a, "description": f"{eq_class} - {service}",
                    "equipment_class": eq_class, "system": system, "location": location,
                    "criticality": criticality, "operating_status": "Duty",
                    "paired_tag": tag_b, "manufacturer": manufacturer, "model": model,
                    "installation_year": install_year, "service_description": service,
                    "discipline": discipline, "platform": platform["name"],
                })
                assets.append({
                    "tag": tag_b, "description": f"{eq_class} - {service}",
                    "equipment_class": eq_class, "system": system, "location": location,
                    "criticality": criticality, "operating_status": "Standby",
                    "paired_tag": tag_a, "manufacturer": manufacturer, "model": model,
                    "installation_year": install_year, "service_description": service,
                    "discipline": discipline, "platform": platform["name"],
                })
                i += 2
            else:
                num = tag_counter[pf_prefix]
                tag = f"{pcode}-{prefix}-{num:03d}"
                tag_counter[pf_prefix] += 1

                system = random.choice(SYSTEMS)
                location = random.choice(LOCATIONS)
                manufacturer = random.choice(MANUFACTURERS[eq_class])
                model = f"Model-{random.randint(100,999)}"
                install_year = random.randint(yr_lo, yr_hi)
                criticality = random.choices(["A", "B", "C"], weights=crit_w)[0]
                service = f"{system} - {eq_class}"

                assets.append({
                    "tag": tag, "description": f"{eq_class} - {service}",
                    "equipment_class": eq_class, "system": system, "location": location,
                    "criticality": criticality, "operating_status": "Solo",
                    "paired_tag": None, "manufacturer": manufacturer, "model": model,
                    "installation_year": install_year, "service_description": service,
                    "discipline": discipline, "platform": platform["name"],
                })
                i += 1

    return pd.DataFrame(assets)


def generate_work_orders_for_platform(assets_df: pd.DataFrame, platform: dict, wo_counter: list) -> pd.DataFrame:
    work_orders = []
    deferral_rate = platform["deferral_rate"]

    for _, asset in assets_df.iterrows():
        eq_class = asset["equipment_class"]
        is_standby = asset["operating_status"] == "Standby"
        task_codes = CLASS_STRATEGY_MAP.get(eq_class, [])

        criticality = asset["criticality"]

        for task_code in task_codes:
            strat = STRATEGY_LOOKUP.get(task_code)
            if strat is None:
                continue

            (code, desc, interval_days, est_hours, basis, duty_only, standby_applies) = strat

            if is_standby and not standby_applies:
                continue

            # H2.3: Crit C assets skip major overhaul / thorough inspection tasks
            if criticality == "C" and task_code in CRIT_C_SKIP_TASKS:
                continue

            scheduled = START_DATE + timedelta(days=random.randint(0, interval_days))

            while scheduled <= END_DATE:
                wo_num = f"WO-{wo_counter[0]:07d}"
                wo_counter[0] += 1

                is_deferred_task = task_code in DEFERRED_TASK_CODES
                deferral_days = 0
                actual_date = None
                status = "Completed"

                if scheduled > date.today():
                    status = "Open"
                    actual_date = None
                    deferral_days = None
                elif is_deferred_task and random.random() < deferral_rate:
                    lo, hi = DEFERRED_TASK_CODES[task_code]
                    delay = random.randint(lo, hi)
                    deferral_days = delay
                    actual_date = scheduled + timedelta(days=delay)
                    status = "Completed"
                else:
                    noise = random.randint(-7, 14)
                    actual_date = scheduled + timedelta(days=max(0, noise))
                    deferral_days = max(0, noise)
                    status = "Completed"

                base_cost = est_hours * random.uniform(85, 120)
                if is_standby:
                    actual_cost_mult = random.uniform(0.7, 1.0)
                else:
                    actual_cost_mult = random.uniform(0.85, 1.25)

                actual_cost = round(base_cost * actual_cost_mult, 2) if actual_date else None
                actual_hrs = round(est_hours * actual_cost_mult, 2) if actual_date else None

                work_orders.append({
                    "wo_number": wo_num,
                    "asset_tag": asset["tag"],
                    "wo_type": "Statutory" if basis == "Statutory" else "PPM",
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


def generate_corrective_work_orders_for_platform(assets_df: pd.DataFrame, platform: dict, cm_counter: list) -> pd.DataFrame:
    corrective_wos = []
    mtbf_mult = platform["mtbf_multiplier"]

    for _, asset in assets_df.iterrows():
        eq_class = asset["equipment_class"]
        op_status = asset["operating_status"]
        failure_defs = FAILURE_MODES.get(eq_class, [])
        if not failure_defs:
            continue

        base_mtbf = ASSET_MTBF.get((eq_class, op_status))
        if base_mtbf is None:
            continue

        mtbf = int(base_mtbf * mtbf_mult)

        dist_type = FAILURE_DISTRIBUTION.get(eq_class, "mixed")
        failure_date = START_DATE + timedelta(days=random.randint(int(mtbf * 0.2), int(mtbf * 1.3)))

        while failure_date <= END_DATE:
            fm_def = random.choice(failure_defs)
            (failure_mode, description, _mtbf_d, _mtbf_s, repair_hours, cost_mult, fm_discipline) = fm_def

            wo_num = f"CM-{cm_counter[0]:07d}"
            cm_counter[0] += 1

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

            # H2.2: Use distribution type to generate inter-failure interval
            if dist_type == "random":
                # Exponential: memoryless random failures (CV ≈ 1.0)
                next_interval = max(30, int(np.random.exponential(mtbf)))
            elif dist_type == "wearout":
                # Tight normal: age-related wear-out (CV ≈ 0.15)
                next_interval = max(int(mtbf * 0.3), int(np.random.normal(mtbf, mtbf * 0.15)))
            else:
                # Log-normal: mixed failure modes (CV ≈ 0.55)
                sigma = 0.5
                mu = np.log(mtbf) - (sigma ** 2) / 2
                next_interval = max(30, int(np.random.lognormal(mu, sigma)))

            failure_date = failure_date + timedelta(days=next_interval)

    return pd.DataFrame(corrective_wos)


def generate_strategies():
    rows = []
    strat_id_counter = 1
    class_map = {
        "CP": "Centrifugal Pump", "RP": "Reciprocating Pump", "CC": "Centrifugal Compressor",
        "GT": "Gas Turbine Generator", "EM": "Electric Motor", "PV": "Pressure Vessel",
        "HX": "Heat Exchanger", "CV": "Control Valve", "PT": "Pressure Transmitter",
        "FM": "Flow Meter", "FG": "Fire & Gas Detector", "SW": "Switchgear Panel",
        "UP": "UPS", "FB": "Fan / Blower", "SV": "Safety Valve",
    }
    discipline_map = {
        "CP": "Mechanical", "RP": "Mechanical", "CC": "Mechanical", "GT": "Mechanical",
        "EM": "Electrical", "PV": "Mechanical", "HX": "Mechanical", "CV": "Instrumentation",
        "PT": "Instrumentation", "FM": "Instrumentation", "FG": "Instrumentation",
        "SW": "Electrical", "UP": "Electrical", "FB": "Mechanical", "SV": "Mechanical",
    }
    for code, desc, interval, hours, basis, duty_only, standby in MAINTENANCE_STRATEGIES:
        prefix = code.split("-")[0]
        rows.append({
            "strategy_id": f"STR-{strat_id_counter:04d}",
            "equipment_class": class_map.get(prefix, "General"),
            "task_code": code,
            "task_description": desc,
            "interval_days": interval,
            "estimated_hours": hours,
            "discipline": discipline_map.get(prefix, "Mechanical"),
            "basis": basis,
            "applies_to_duty": True,
            "applies_to_standby": standby,
            "notes": None,
        })
        strat_id_counter += 1
    return pd.DataFrame(rows)


def generate_all(output_dir: str):
    os.makedirs(output_dir, exist_ok=True)

    wo_counter = [1000000]
    cm_counter = [9000000]

    all_assets = []
    all_ppm = []
    all_corrective = []

    for platform in PLATFORMS:
        print(f"Generating {platform['name']} platform assets...")
        assets_df = generate_assets_for_platform(platform)
        all_assets.append(assets_df)

        print(f"  Generating PPM work orders for {platform['name']}...")
        ppm_df = generate_work_orders_for_platform(assets_df, platform, wo_counter)
        all_ppm.append(ppm_df)

        print(f"  Generating corrective work orders for {platform['name']}...")
        cm_df = generate_corrective_work_orders_for_platform(assets_df, platform, cm_counter)
        all_corrective.append(cm_df)

        print(f"  {platform['name']}: {len(assets_df)} assets, {len(ppm_df)} PPM WOs, {len(cm_df)} corrective WOs")

    assets_combined = pd.concat(all_assets, ignore_index=True)
    ppm_combined = pd.concat(all_ppm, ignore_index=True)
    corrective_combined = pd.concat(all_corrective, ignore_index=True)
    wo_combined = pd.concat([ppm_combined, corrective_combined], ignore_index=True)
    wo_combined = wo_combined.sort_values("scheduled_date").reset_index(drop=True)

    print("Generating maintenance strategies...")
    strat_df = generate_strategies()

    asset_path = os.path.join(output_dir, "asset_register.xlsx")
    wo_path = os.path.join(output_dir, "work_order_history.xlsx")
    strat_path = os.path.join(output_dir, "maintenance_strategies.xlsx")

    assets_combined.to_excel(asset_path, index=False)
    wo_combined.to_excel(wo_path, index=False)
    strat_df.to_excel(strat_path, index=False)

    print(f"\nTotal assets: {len(assets_combined)} across {len(PLATFORMS)} platforms")
    print(f"Total WOs: {len(wo_combined)} ({len(ppm_combined)} PPM/Statutory, {len(corrective_combined)} Corrective)")
    print(f"Strategies: {len(strat_df)} records")
