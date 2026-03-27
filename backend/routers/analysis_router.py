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
    get_h2_1_analysis,
    get_h2_2_analysis,
    get_h2_3_analysis,
    get_h2_4_analysis,
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
def hypothesis_h1_1(
    db: Session = Depends(get_db), platforms: str = Query(None),
    min_deferral_days: int = Query(14),
):
    return get_h1_1_analysis(db, parse_platforms(platforms), min_deferral_days=min_deferral_days)


@router.get("/hypothesis/h1-2")
def hypothesis_h1_2(db: Session = Depends(get_db), platforms: str = Query(None)):
    return get_h1_2_analysis(db, parse_platforms(platforms))


@router.get("/hypothesis/h1-3")
def hypothesis_h1_3(
    db: Session = Depends(get_db), platforms: str = Query(None),
    cm_ppm_threshold: float = Query(20.0),
    min_repeat_failures: int = Query(3),
):
    return get_h1_3_analysis(db, parse_platforms(platforms),
                             cm_ppm_threshold=cm_ppm_threshold,
                             min_repeat_failures=min_repeat_failures)


@router.get("/corrective-summary")
def corrective_summary(db: Session = Depends(get_db), platforms: str = Query(None)):
    return get_corrective_summary(db, parse_platforms(platforms))


@router.get("/hypothesis/h2-1")
def hypothesis_h2_1(
    db: Session = Depends(get_db), platforms: str = Query(None),
    over_conservative_threshold: float = Query(10.0),
    review_threshold: float = Query(5.0),
):
    return get_h2_1_analysis(db, parse_platforms(platforms),
                             over_conservative_threshold=over_conservative_threshold,
                             review_threshold=review_threshold)


@router.get("/hypothesis/h2-2")
def hypothesis_h2_2(
    db: Session = Depends(get_db), platforms: str = Query(None),
    random_cv_threshold: float = Query(0.8),
    wearout_cv_threshold: float = Query(0.5),
):
    return get_h2_2_analysis(db, parse_platforms(platforms),
                             random_cv_threshold=random_cv_threshold,
                             wearout_cv_threshold=wearout_cv_threshold)


@router.get("/hypothesis/h2-3")
def hypothesis_h2_3(
    db: Session = Depends(get_db), platforms: str = Query(None),
    min_corrective_events: int = Query(3),
):
    return get_h2_3_analysis(db, parse_platforms(platforms),
                             min_corrective_events=min_corrective_events)


@router.get("/hypothesis/h2-4")
def hypothesis_h2_4(db: Session = Depends(get_db), platforms: str = Query(None)):
    return get_h2_4_analysis(db, parse_platforms(platforms))


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
