from fastapi import APIRouter, Depends
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


@router.get("/cost-summary")
def cost_summary(db: Session = Depends(get_db)):
    return get_cost_summary(db)


@router.get("/duty-standby")
def duty_standby(db: Session = Depends(get_db)):
    return get_duty_standby_opportunities(db)


@router.get("/deferral-opportunities")
def deferral_opportunities(
    db: Session = Depends(get_db),
    min_occurrences: int = 4,
    min_avg_deferral: int = 30,
):
    return get_deferral_opportunities(db, min_occurrences, min_avg_deferral)


@router.get("/deferral-summary")
def deferral_summary(db: Session = Depends(get_db)):
    return get_deferral_summary_by_task(db)


@router.get("/hypothesis/h1-1")
def hypothesis_h1_1(db: Session = Depends(get_db)):
    return get_h1_1_analysis(db)


@router.get("/hypothesis/h1-2")
def hypothesis_h1_2(db: Session = Depends(get_db)):
    return get_h1_2_analysis(db)


@router.get("/hypothesis/h1-3")
def hypothesis_h1_3(db: Session = Depends(get_db)):
    return get_h1_3_analysis(db)


@router.get("/corrective-summary")
def corrective_summary(db: Session = Depends(get_db)):
    return get_corrective_summary(db)


@router.get("/optimisation-opportunities")
def all_opportunities(db: Session = Depends(get_db)):
    ds = get_duty_standby_opportunities(db)
    def_opps = get_deferral_opportunities(db)
    all_opps = ds + def_opps
    all_opps.sort(key=lambda x: x["potential_annual_saving"], reverse=True)
    total_saving = sum(o["potential_annual_saving"] for o in all_opps)
    return {
        "total_opportunities": len(all_opps),
        "total_potential_annual_saving": round(total_saving, 2),
        "opportunities": all_opps,
    }
