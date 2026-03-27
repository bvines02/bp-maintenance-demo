from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db, WorkOrder, Asset

router = APIRouter(prefix="/workorders", tags=["workorders"])


def _platform_tag_set(db: Session, platforms_raw: str | None):
    if not platforms_raw:
        return None
    names = [p.strip() for p in platforms_raw.split(",") if p.strip()]
    if not names:
        return None
    rows = db.query(Asset.tag).filter(Asset.platform.in_(names)).all()
    return {r[0] for r in rows}


@router.get("/")
def list_work_orders(
    db: Session = Depends(get_db),
    asset_tag: str = Query(None),
    task_code: str = Query(None),
    wo_type: str = Query(None),
    status: str = Query(None),
    platforms: str = Query(None),
    skip: int = 0,
    limit: int = 200,
):
    q = db.query(WorkOrder)
    tag_set = _platform_tag_set(db, platforms)
    if tag_set is not None:
        q = q.filter(WorkOrder.asset_tag.in_(tag_set))
    if asset_tag:
        q = q.filter(WorkOrder.asset_tag == asset_tag)
    if task_code:
        q = q.filter(WorkOrder.task_code == task_code)
    if wo_type:
        q = q.filter(WorkOrder.wo_type == wo_type)
    if status:
        q = q.filter(WorkOrder.status == status)
    total = q.count()
    wos = q.order_by(WorkOrder.scheduled_date.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "items": [_wo_dict(w) for w in wos],
    }


@router.get("/summary")
def work_order_summary(db: Session = Depends(get_db), platforms: str = Query(None)):
    tag_set = _platform_tag_set(db, platforms)
    q = db.query(WorkOrder)
    if tag_set is not None:
        q = q.filter(WorkOrder.asset_tag.in_(tag_set))
    wos = q.all()
    by_type: dict = {}
    by_status: dict = {}
    by_discipline: dict = {}
    deferred_count = 0
    total_cost = 0.0
    for w in wos:
        by_type[w.wo_type] = by_type.get(w.wo_type, 0) + 1
        by_status[w.status] = by_status.get(w.status, 0) + 1
        by_discipline[w.discipline] = by_discipline.get(w.discipline, 0) + 1
        if w.deferral_days and w.deferral_days > 14:
            deferred_count += 1
        total_cost += w.actual_cost or 0
    return {
        "total": len(wos),
        "by_type": by_type,
        "by_status": by_status,
        "by_discipline": by_discipline,
        "deferred_count": deferred_count,
        "total_cost": round(total_cost, 2),
    }


def _wo_dict(w: WorkOrder) -> dict:
    return {
        "wo_number": w.wo_number,
        "asset_tag": w.asset_tag,
        "wo_type": w.wo_type,
        "task_description": w.task_description,
        "task_code": w.task_code,
        "scheduled_date": str(w.scheduled_date) if w.scheduled_date else None,
        "actual_completion_date": str(w.actual_completion_date) if w.actual_completion_date else None,
        "status": w.status,
        "estimated_hours": w.estimated_hours,
        "actual_hours": w.actual_hours,
        "estimated_cost": w.estimated_cost,
        "actual_cost": w.actual_cost,
        "discipline": w.discipline,
        "deferral_days": w.deferral_days,
        "notes": w.notes,
    }
