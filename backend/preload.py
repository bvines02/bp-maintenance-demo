"""Run during Docker build to pre-populate the SQLite database."""
import os
import pandas as pd
from database import init_db, SessionLocal, Asset, WorkOrder, MaintenanceStrategy

DEMO_DIR = os.path.join(os.path.dirname(__file__), "..", "demo_data")

init_db()
db = SessionLocal()

if db.query(Asset).count() > 0:
    print("Database already populated, skipping.")
    db.close()
    exit(0)

print("Loading assets...")
assets_df = pd.read_excel(os.path.join(DEMO_DIR, "asset_register.xlsx"))
for _, row in assets_df.iterrows():
    db.add(Asset(
        tag=row["tag"], description=row["description"],
        equipment_class=row["equipment_class"], system=row["system"],
        location=row["location"], criticality=row["criticality"],
        operating_status=row["operating_status"],
        paired_tag=row["paired_tag"] if pd.notna(row.get("paired_tag")) else None,
        manufacturer=row["manufacturer"], model=row["model"],
        installation_year=int(row["installation_year"]),
        service_description=row["service_description"],
        discipline=row["discipline"],
        platform=row["platform"] if pd.notna(row.get("platform")) else None,
    ))
db.commit()

print("Loading maintenance strategies...")
strat_df = pd.read_excel(os.path.join(DEMO_DIR, "maintenance_strategies.xlsx"))
for _, row in strat_df.iterrows():
    db.add(MaintenanceStrategy(
        strategy_id=row["strategy_id"], equipment_class=row["equipment_class"],
        task_code=row["task_code"], task_description=row["task_description"],
        interval_days=int(row["interval_days"]), estimated_hours=float(row["estimated_hours"]),
        discipline=row["discipline"], basis=row["basis"],
        applies_to_duty=bool(row["applies_to_duty"]),
        applies_to_standby=bool(row["applies_to_standby"]),
        notes=row["notes"] if pd.notna(row.get("notes")) else None,
    ))
db.commit()

print("Loading work orders...")
wo_df = pd.read_excel(os.path.join(DEMO_DIR, "work_order_history.xlsx"))
batch = []
for i, row in wo_df.iterrows():
    scheduled = row["scheduled_date"]
    actual = row["actual_completion_date"]
    if pd.isna(scheduled):
        continue
    if hasattr(scheduled, "date"):
        scheduled = scheduled.date()
    if pd.notna(actual) and hasattr(actual, "date"):
        actual = actual.date()
    elif pd.isna(actual):
        actual = None
    batch.append(WorkOrder(
        wo_number=row["wo_number"], asset_tag=row["asset_tag"],
        wo_type=row["wo_type"], task_description=row["task_description"],
        task_code=row["task_code"], scheduled_date=scheduled,
        actual_completion_date=actual, status=row["status"],
        estimated_hours=float(row["estimated_hours"]),
        actual_hours=float(row["actual_hours"]) if pd.notna(row.get("actual_hours")) else None,
        estimated_cost=float(row["estimated_cost"]),
        actual_cost=float(row["actual_cost"]) if pd.notna(row.get("actual_cost")) else None,
        discipline=row["discipline"],
        failure_mode=row["failure_mode"] if pd.notna(row.get("failure_mode")) else None,
        notes=row["notes"] if pd.notna(row.get("notes")) else None,
        deferral_days=int(row["deferral_days"]) if pd.notna(row.get("deferral_days")) else None,
    ))
    if len(batch) >= 500:
        db.bulk_save_objects(batch)
        db.commit()
        batch = []
        print(f"  {i + 1} work orders loaded...")

if batch:
    db.bulk_save_objects(batch)
    db.commit()

db.close()
print("Done. Database pre-loaded successfully.")
