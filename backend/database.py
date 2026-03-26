from sqlalchemy import create_engine, Column, String, Integer, Float, Date, Boolean, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'maintenance.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Asset(Base):
    __tablename__ = "assets"
    tag = Column(String, primary_key=True)
    description = Column(String)
    equipment_class = Column(String)
    system = Column(String)
    location = Column(String)
    criticality = Column(String)
    operating_status = Column(String)  # duty, standby, spare
    paired_tag = Column(String, nullable=True)
    manufacturer = Column(String)
    model = Column(String)
    installation_year = Column(Integer)
    service_description = Column(String)
    discipline = Column(String)
    work_orders = relationship("WorkOrder", back_populates="asset")


class WorkOrder(Base):
    __tablename__ = "work_orders"
    wo_number = Column(String, primary_key=True)
    asset_tag = Column(String, ForeignKey("assets.tag"))
    wo_type = Column(String)  # PPM, corrective, statutory
    task_description = Column(String)
    task_code = Column(String)
    scheduled_date = Column(Date)
    actual_completion_date = Column(Date, nullable=True)
    status = Column(String)  # completed, deferred, cancelled, open
    estimated_hours = Column(Float)
    actual_hours = Column(Float, nullable=True)
    estimated_cost = Column(Float)
    actual_cost = Column(Float, nullable=True)
    discipline = Column(String)
    failure_mode = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    deferral_days = Column(Integer, nullable=True)
    asset = relationship("Asset", back_populates="work_orders")


class MaintenanceStrategy(Base):
    __tablename__ = "maintenance_strategies"
    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(String, unique=True)
    equipment_class = Column(String)
    task_code = Column(String)
    task_description = Column(String)
    interval_days = Column(Integer)
    estimated_hours = Column(Float)
    discipline = Column(String)
    basis = Column(String)  # time-based, condition-based, statutory
    applies_to_duty = Column(Boolean)
    applies_to_standby = Column(Boolean)
    notes = Column(Text, nullable=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
