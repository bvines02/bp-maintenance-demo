from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import pandas as pd
import io
import os
from datetime import datetime

from database import init_db, SessionLocal, Asset, WorkOrder, MaintenanceStrategy
from routers import assets, workorders, analysis_router, chat
from data_generator import generate_all

app = FastAPI(title="BP Maintenance Optimisation", version="1.0.0")

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    *[o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()],
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assets.router)
app.include_router(workorders.router)
app.include_router(analysis_router.router)
app.include_router(chat.router)


@app.on_event("startup")
def startup():
    init_db()
    # Auto-load demo data if DB is empty
    db = SessionLocal()
    try:
        if db.query(Asset).count() == 0:
            _load_demo_data(db)
    finally:
        db.close()


def _load_demo_data(db: Session):
    demo_dir = os.path.join(os.path.dirname(__file__), "..", "demo_data")
    asset_path = os.path.join(demo_dir, "asset_register.xlsx")
    wo_path = os.path.join(demo_dir, "work_order_history.xlsx")
    strat_path = os.path.join(demo_dir, "maintenance_strategies.xlsx")

    # Generate if not present
    if not os.path.exists(asset_path):
        print("Generating demo data...")
        generate_all(demo_dir)

    print("Loading assets...")
    assets_df = pd.read_excel(asset_path)
    for _, row in assets_df.iterrows():
        db.add(Asset(
            tag=row["tag"],
            description=row["description"],
            equipment_class=row["equipment_class"],
            system=row["system"],
            location=row["location"],
            criticality=row["criticality"],
            operating_status=row["operating_status"],
            paired_tag=row["paired_tag"] if pd.notna(row.get("paired_tag")) else None,
            manufacturer=row["manufacturer"],
            model=row["model"],
            installation_year=int(row["installation_year"]),
            service_description=row["service_description"],
            discipline=row["discipline"],
        ))
    db.commit()

    print("Loading maintenance strategies...")
    strat_df = pd.read_excel(strat_path)
    for _, row in strat_df.iterrows():
        db.add(MaintenanceStrategy(
            strategy_id=row["strategy_id"],
            equipment_class=row["equipment_class"],
            task_code=row["task_code"],
            task_description=row["task_description"],
            interval_days=int(row["interval_days"]),
            estimated_hours=float(row["estimated_hours"]),
            discipline=row["discipline"],
            basis=row["basis"],
            applies_to_duty=bool(row["applies_to_duty"]),
            applies_to_standby=bool(row["applies_to_standby"]),
            notes=row["notes"] if pd.notna(row.get("notes")) else None,
        ))
    db.commit()

    print("Loading work orders (this will take a moment)...")
    wo_df = pd.read_excel(wo_path)
    batch = []
    for i, row in wo_df.iterrows():
        scheduled = row["scheduled_date"]
        actual = row["actual_completion_date"]
        if pd.isna(scheduled):
            continue
        if hasattr(scheduled, 'date'):
            scheduled = scheduled.date()
        if pd.notna(actual) and hasattr(actual, 'date'):
            actual = actual.date()
        elif pd.isna(actual):
            actual = None

        batch.append(WorkOrder(
            wo_number=row["wo_number"],
            asset_tag=row["asset_tag"],
            wo_type=row["wo_type"],
            task_description=row["task_description"],
            task_code=row["task_code"],
            scheduled_date=scheduled,
            actual_completion_date=actual,
            status=row["status"],
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
            print(f"  Loaded {i+1} work orders...")

    if batch:
        db.bulk_save_objects(batch)
        db.commit()

    print("Demo data loaded successfully.")


@app.get("/")
def root():
    return {"message": "BP Maintenance Optimisation API", "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}
