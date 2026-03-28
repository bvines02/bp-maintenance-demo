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
    get_strategy_proposals,
)

router = APIRouter(prefix="/analysis", tags=["analysis"])

# Simple in-memory cache — data never changes during a process lifetime
_cache: dict = {}


def _cached(key: str, fn):
    if key not in _cache:
        _cache[key] = fn()
    return _cache[key]


def parse_platforms(platforms_raw: str | None) -> list[str] | None:
    if not platforms_raw:
        return None
    parsed = [p.strip() for p in platforms_raw.split(",") if p.strip()]
    return parsed if parsed else None


@router.get("/cost-summary")
def cost_summary(db: Session = Depends(get_db), platforms: str = Query(None)):
    return _cached(f"cost-summary:{platforms}", lambda: get_cost_summary(db, parse_platforms(platforms)))


@router.get("/duty-standby")
def duty_standby(db: Session = Depends(get_db), platforms: str = Query(None)):
    return _cached(f"duty-standby:{platforms}", lambda: get_duty_standby_opportunities(db, parse_platforms(platforms)))


@router.get("/deferral-opportunities")
def deferral_opportunities(
    db: Session = Depends(get_db),
    min_occurrences: int = 4,
    min_avg_deferral: int = 30,
    platforms: str = Query(None),
):
    key = f"deferral-opps:{platforms}:{min_occurrences}:{min_avg_deferral}"
    return _cached(key, lambda: get_deferral_opportunities(db, min_occurrences, min_avg_deferral, parse_platforms(platforms)))


@router.get("/deferral-summary")
def deferral_summary(db: Session = Depends(get_db), platforms: str = Query(None)):
    return _cached(f"deferral-summary:{platforms}", lambda: get_deferral_summary_by_task(db, parse_platforms(platforms)))


@router.get("/hypothesis/h1-1")
def hypothesis_h1_1(
    db: Session = Depends(get_db), platforms: str = Query(None),
    min_deferral_days: int = Query(14),
):
    key = f"h1-1:{platforms}:{min_deferral_days}"
    return _cached(key, lambda: get_h1_1_analysis(db, parse_platforms(platforms), min_deferral_days=min_deferral_days))


@router.get("/hypothesis/h1-2")
def hypothesis_h1_2(db: Session = Depends(get_db), platforms: str = Query(None)):
    return _cached(f"h1-2:{platforms}", lambda: get_h1_2_analysis(db, parse_platforms(platforms)))


@router.get("/hypothesis/h1-3")
def hypothesis_h1_3(
    db: Session = Depends(get_db), platforms: str = Query(None),
    cm_ppm_threshold: float = Query(20.0),
    min_repeat_failures: int = Query(3),
):
    key = f"h1-3:{platforms}:{cm_ppm_threshold}:{min_repeat_failures}"
    return _cached(key, lambda: get_h1_3_analysis(db, parse_platforms(platforms),
                                                   cm_ppm_threshold=cm_ppm_threshold,
                                                   min_repeat_failures=min_repeat_failures))


@router.get("/corrective-summary")
def corrective_summary(db: Session = Depends(get_db), platforms: str = Query(None)):
    return _cached(f"corrective-summary:{platforms}", lambda: get_corrective_summary(db, parse_platforms(platforms)))


@router.get("/hypothesis/h2-1")
def hypothesis_h2_1(
    db: Session = Depends(get_db), platforms: str = Query(None),
    over_conservative_threshold: float = Query(10.0),
    review_threshold: float = Query(5.0),
):
    key = f"h2-1:{platforms}:{over_conservative_threshold}:{review_threshold}"
    return _cached(key, lambda: get_h2_1_analysis(db, parse_platforms(platforms),
                                                   over_conservative_threshold=over_conservative_threshold,
                                                   review_threshold=review_threshold))


@router.get("/hypothesis/h2-2")
def hypothesis_h2_2(
    db: Session = Depends(get_db), platforms: str = Query(None),
    random_cv_threshold: float = Query(0.8),
    wearout_cv_threshold: float = Query(0.5),
):
    key = f"h2-2:{platforms}:{random_cv_threshold}:{wearout_cv_threshold}"
    return _cached(key, lambda: get_h2_2_analysis(db, parse_platforms(platforms),
                                                   random_cv_threshold=random_cv_threshold,
                                                   wearout_cv_threshold=wearout_cv_threshold))


@router.get("/hypothesis/h2-3")
def hypothesis_h2_3(
    db: Session = Depends(get_db), platforms: str = Query(None),
    min_corrective_events: int = Query(3),
):
    key = f"h2-3:{platforms}:{min_corrective_events}"
    return _cached(key, lambda: get_h2_3_analysis(db, parse_platforms(platforms),
                                                   min_corrective_events=min_corrective_events))


@router.get("/hypothesis/h2-4")
def hypothesis_h2_4(db: Session = Depends(get_db), platforms: str = Query(None)):
    return _cached(f"h2-4:{platforms}", lambda: get_h2_4_analysis(db, parse_platforms(platforms)))


@router.get("/optimisation-opportunities")
def all_opportunities(db: Session = Depends(get_db), platforms: str = Query(None)):
    p = parse_platforms(platforms)

    def compute():
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

    return _cached(f"all-opps:{platforms}", compute)


@router.get("/strategy-proposals")
def strategy_proposals(db: Session = Depends(get_db), platforms: str = Query(None)):
    return _cached(f"strategy-proposals:{platforms}", lambda: get_strategy_proposals(db, parse_platforms(platforms)))
