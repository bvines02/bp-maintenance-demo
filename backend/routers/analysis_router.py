from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from analysis import (
    get_duty_standby_opportunities,
    get_deferral_opportunities,
    get_deferral_summary_by_task,
    get_cost_summary,
    get_corrective_summary,
    get_h1_1_analysis,
    get_h1_2_analysis,
    get_h1_3_analysis,
)

router = APIRouter(prefix="/analysis", tags=["analysis"])


def parse_platforms(platforms_raw: str | None) -> list[str] | None:
    if not platforms_raw:
        return None
    parsed = [p.strip() for p in platforms_raw.split(",") if p.strip()]
    return parsed if parsed else None


@router.get("/cost-summary")
def cost_summary(db: Session = Depends(get_db), platforms: str = Query(None)):
    return get_cost_summary(db, parse_platforms(platforms))


@router.get("/duty-standby")
def duty_standby(db: Session = Depends(get_db), platforms: str = Query(None)):
    return get_duty_standby_opportunities(db, parse_platforms(platforms))


@router.get("/deferral-opportunities")
def deferral_opportunities(
    db: Session = Depends(get_db),
    min_occurrences: int = 4,
    min_avg_deferral: int = 30,
    platforms: str = Query(None),
):
    return get_deferral_opportunities(db, min_occurrences, min_avg_deferral, parse_platforms(platforms))


@router.get("/deferral-summary")
def deferral_summary(db: Session = Depends(get_db), platforms: str = Query(None)):
    return get_deferral_summary_by_task(db, parse_platforms(platforms))


@router.get("/hypothesis/h1-1")
def hypothesis_h1_1(db: Session = Depends(get_db), platforms: str = Query(None)):
    return get_h1_1_analysis(db, parse_platforms(platforms))


@router.get("/hypothesis/h1-2")
def hypothesis_h1_2(db: Session = Depends(get_db), platforms: str = Query(None)):
    return get_h1_2_analysis(db, parse_platforms(platforms))


@router.get("/hypothesis/h1-3")
def hypothesis_h1_3(db: Session = Depends(get_db), platforms: str = Query(None)):
    return get_h1_3_analysis(db, parse_platforms(platforms))


@router.get("/corrective-summary")
def corrective_summary(db: Session = Depends(get_db), platforms: str = Query(None)):
    return get_corrective_summary(db, parse_platforms(platforms))


@router.get("/optimisation-opportunities")
def all_opportunities(db: Session = Depends(get_db), platforms: str = Query(None)):
    p = parse_platforms(platforms)
    ds = get_duty_standby_opportunities(db, p)
    def_opps = get_deferral_opportunities(db, platforms=p)
    all_opps = ds + def_opps
    all_opps.sort(key=lambda x: x["potential_annual_saving"], reverse=True)
    total_saving = sum(o["potential_annual_saving"] for o in all_opps)
    return {
        "total_opportunities": len(all_opps),
        "total_potential_annual_saving": round(total_saving, 2),
        "opportunities": all_opps,
    }
