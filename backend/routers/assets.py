from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db, Asset

router = APIRouter(prefix="/assets", tags=["assets"])


def _apply_platform_filter(q, platforms_raw: str | None):
    if platforms_raw:
        names = [p.strip() for p in platforms_raw.split(",") if p.strip()]
        if names:
            q = q.filter(Asset.platform.in_(names))
    return q


@router.get("/")
def list_assets(
    db: Session = Depends(get_db),
    equipment_class: str = Query(None),
    system: str = Query(None),
    criticality: str = Query(None),
    operating_status: str = Query(None),
    platforms: str = Query(None),
    skip: int = 0,
    limit: int = 1000,
):
    q = db.query(Asset)
    q = _apply_platform_filter(q, platforms)
    if equipment_class:
        q = q.filter(Asset.equipment_class == equipment_class)
    if system:
        q = q.filter(Asset.system == system)
    if criticality:
        q = q.filter(Asset.criticality == criticality)
    if operating_status:
        q = q.filter(Asset.operating_status == operating_status)
    total = q.count()
    assets = q.offset(skip).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "tag": a.tag,
                "description": a.description,
                "equipment_class": a.equipment_class,
                "system": a.system,
                "location": a.location,
                "criticality": a.criticality,
                "operating_status": a.operating_status,
                "paired_tag": a.paired_tag,
                "manufacturer": a.manufacturer,
                "model": a.model,
                "installation_year": a.installation_year,
                "service_description": a.service_description,
                "discipline": a.discipline,
                "platform": a.platform,
            }
            for a in assets
        ],
    }


@router.get("/summary")
def asset_summary(db: Session = Depends(get_db), platforms: str = Query(None)):
    q = db.query(Asset)
    q = _apply_platform_filter(q, platforms)
    assets = q.all()
    by_class: dict = {}
    by_criticality: dict = {}
    by_status: dict = {}
    pairs = 0
    for a in assets:
        by_class[a.equipment_class] = by_class.get(a.equipment_class, 0) + 1
        by_criticality[a.criticality] = by_criticality.get(a.criticality, 0) + 1
        by_status[a.operating_status] = by_status.get(a.operating_status, 0) + 1
        if a.paired_tag and a.operating_status == "Duty":
            pairs += 1
    return {
        "total": len(assets),
        "by_equipment_class": by_class,
        "by_criticality": by_criticality,
        "by_operating_status": by_status,
        "duty_standby_pairs": pairs,
    }


@router.get("/{tag}")
def get_asset(tag: str, db: Session = Depends(get_db)):
    a = db.query(Asset).filter(Asset.tag == tag).first()
    if not a:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Asset not found")
    return {
        "tag": a.tag,
        "description": a.description,
        "equipment_class": a.equipment_class,
        "system": a.system,
        "location": a.location,
        "criticality": a.criticality,
        "operating_status": a.operating_status,
        "paired_tag": a.paired_tag,
        "manufacturer": a.manufacturer,
        "model": a.model,
        "installation_year": a.installation_year,
        "service_description": a.service_description,
        "discipline": a.discipline,
    }
