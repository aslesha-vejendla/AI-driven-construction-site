"""
analytics.py — Three innovative analytical engines:

1. AI Delay Predictor
   Uses linear regression on cumulative progress data to predict
   estimated completion date and flag delay risk.
   Formula: at current advance_per_day, days_remaining = remaining_qty / advance_per_day

2. Earned Value Management (EVM)
   PV  = Budget × (elapsed_days / planned_days)
   EV  = Budget × (completed_qty / planned_qty)
   AC  = crew_size × hours × assumed_daily_rate (₹2500/person/day)
   SPI = EV / PV   → <1 behind schedule, >1 ahead
   CPI = EV / AC   → <1 over budget, >1 under budget

3. Site Health Score
   Composite 0–100 score across all activities, weighted by:
   - Progress velocity     (30%)
   - Risk score (inverted) (25%)
   - Utilization           (20%)
   - Safety compliance     (15%)
   - Issue frequency       (10%)
   Graded: A+ ≥90, A ≥80, B ≥70, C ≥60, D ≥50, F <50
"""

import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database.db import get_db
from app.models.models import Activity, WorkerUpdate, Project, SiteHealthLog

router = APIRouter(prefix="/api")

DAILY_LABOUR_RATE = 2500   # ₹ per person per day (assumption for EVM AC)


# ─────────────────────────────────────────────────────────────────────────────
# 1.  AI DELAY PREDICTOR
# ─────────────────────────────────────────────────────────────────────────────

def _linear_regression(x: list, y: list):
    """Simple least-squares slope and intercept."""
    n = len(x)
    if n < 2:
        return 0, 0
    sx  = sum(x)
    sy  = sum(y)
    sxy = sum(xi * yi for xi, yi in zip(x, y))
    sxx = sum(xi * xi for xi in x)
    denom = n * sxx - sx * sx
    if denom == 0:
        return 0, 0
    slope     = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return slope, intercept


def _predict_activity(activity: Activity, updates: list) -> dict:
    if not updates:
        return {"activity_id": activity.id, "name": activity.name,
                "status": "NO DATA", "confidence": 0}

    # Build daily cumulative series
    daily = {}
    for u in sorted(updates, key=lambda u: u.timestamp):
        d = u.timestamp.date()
        daily[d] = daily.get(d, 0) + u.quantity_done

    dates_sorted = sorted(daily)
    origin       = dates_sorted[0]
    xs = [(d - origin).days for d in dates_sorted]
    ys_cum = []
    cum = 0
    for d in dates_sorted:
        cum += daily[d]
        ys_cum.append(cum)

    slope, intercept = _linear_regression(xs, ys_cum)  # qty per day (linear trend)

    total_qty    = ys_cum[-1]
    remaining    = max(activity.planned_quantity - total_qty, 0)
    progress_pct = round(total_qty / activity.planned_quantity * 100, 1) if activity.planned_quantity else 0

    # Estimated days to complete at current slope
    if slope > 0:
        days_to_finish = remaining / slope
    else:
        days_to_finish = 9999

    today          = datetime.utcnow().date()
    eta            = today + timedelta(days=int(days_to_finish))
    planned_end    = (origin + timedelta(days=activity.planned_duration_days))
    delay_days     = max((eta - planned_end).days, 0)
    on_time        = eta <= planned_end

    # Confidence: more data points → higher confidence (caps at 90%)
    n_days   = len(dates_sorted)
    confidence = min(round(50 + n_days * 2.5), 90)

    # Forecast: next 7 days of projected advance
    forecast = []
    last_x   = xs[-1]
    for i in range(1, 8):
        proj_cum = slope * (last_x + i) + intercept
        proj_cum = max(proj_cum, total_qty)  # don't go backwards
        forecast.append({
            "date": (today + timedelta(days=i)).isoformat(),
            "projected_cumulative": round(min(proj_cum, activity.planned_quantity), 2),
        })

    return {
        "activity_id":    activity.id,
        "name":           activity.name,
        "progress_pct":   progress_pct,
        "total_qty":      round(total_qty, 2),
        "planned_qty":    activity.planned_quantity,
        "unit":           activity.unit,
        "advance_per_day": round(slope, 2),
        "days_to_finish": round(days_to_finish) if days_to_finish < 9999 else None,
        "eta":            eta.isoformat(),
        "planned_end":    planned_end.isoformat(),
        "delay_days":     delay_days,
        "on_time":        on_time,
        "confidence":     confidence,
        "forecast_7d":    forecast,
        "delay_label":    "ON TIME" if on_time else f"DELAYED +{delay_days}d",
        "delay_color":    "#10B981" if on_time else ("#F59E0B" if delay_days < 15 else "#EF4444"),
    }


@router.get("/delay-forecast")
def delay_forecast(db: Session = Depends(get_db)):
    activities = db.query(Activity).all()
    result = []
    for a in activities:
        updates = db.query(WorkerUpdate).filter(
            WorkerUpdate.activity_id == a.id
        ).order_by(WorkerUpdate.timestamp).all()
        result.append(_predict_activity(a, updates))
    return result


@router.get("/delay-forecast/{activity_id}")
def delay_forecast_single(activity_id: int, db: Session = Depends(get_db)):
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        return {"error": "Not found"}
    updates = db.query(WorkerUpdate).filter(
        WorkerUpdate.activity_id == activity_id
    ).order_by(WorkerUpdate.timestamp).all()
    return _predict_activity(activity, updates)


# ─────────────────────────────────────────────────────────────────────────────
# 2.  EARNED VALUE MANAGEMENT (EVM)
# ─────────────────────────────────────────────────────────────────────────────

def _evm_activity(activity: Activity, updates: list, budget: float) -> dict:
    if not updates or budget <= 0:
        return {
            "activity_id": activity.id, "name": activity.name,
            "pv": 0, "ev": 0, "ac": 0, "spi": 0, "cpi": 0,
            "spi_label": "N/A", "cpi_label": "N/A",
            "cost_variance": 0, "schedule_variance": 0,
            "eac": 0,   # Estimate at Completion
        }

    from datetime import date as date_type
    today          = datetime.utcnow().date()
    start_date_str = activity.start_date or ""
    try:
        start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except Exception:
        start = (min(u.timestamp for u in updates)).date()

    planned_days  = activity.planned_duration_days or 1
    elapsed_days  = max((today - start).days, 0)

    # PV: budget × fraction of planned time elapsed
    pv_pct = min(elapsed_days / planned_days, 1.0)
    pv     = round(budget * pv_pct, 0)

    # EV: budget × fraction of scope completed
    total_qty = sum(u.quantity_done for u in updates)
    ev_pct    = min(total_qty / activity.planned_quantity, 1.0) if activity.planned_quantity else 0
    ev        = round(budget * ev_pct, 0)

    # AC: actual cost estimate (crew × hours × rate)
    total_crew_days = sum(u.crew_size * (u.hours_worked / 8) for u in updates)
    ac = round(total_crew_days * DAILY_LABOUR_RATE, 0)

    spi = round(ev / pv,  3) if pv  > 0 else 0
    cpi = round(ev / ac,  3) if ac  > 0 else 0

    sv  = round(ev - pv, 0)   # Schedule Variance (₹)
    cv  = round(ev - ac, 0)   # Cost Variance (₹)

    # EAC: Estimate at Completion = AC + (BAC - EV) / CPI
    eac = round(ac + (budget - ev) / cpi, 0) if cpi > 0 else budget * 2

    def spi_label(s):
        if s == 0:   return "N/A"
        if s >= 1.0: return f"✅ Ahead ({s})"
        if s >= 0.8: return f"⚠️ Slightly Behind ({s})"
        return       f"🚨 Behind ({s})"

    def cpi_label(c):
        if c == 0:   return "N/A"
        if c >= 1.0: return f"✅ Under Budget ({c})"
        if c >= 0.8: return f"⚠️ Near Budget ({c})"
        return       f"🚨 Over Budget ({c})"

    return {
        "activity_id":       activity.id,
        "name":              activity.name,
        "budget":            budget,
        "pv":                pv,
        "ev":                ev,
        "ac":                ac,
        "spi":               spi,
        "cpi":               cpi,
        "sv":                sv,
        "cv":                cv,
        "eac":               eac,
        "spi_label":         spi_label(spi),
        "cpi_label":         cpi_label(cpi),
        "progress_pct":      round(ev_pct * 100, 1),
        "elapsed_days":      elapsed_days,
        "planned_days":      planned_days,
    }


@router.get("/evm")
def earned_value(db: Session = Depends(get_db)):
    activities = db.query(Activity).all()
    projects   = {p.id: p for p in db.query(Project).all()}
    result     = []
    for a in activities:
        updates = db.query(WorkerUpdate).filter(WorkerUpdate.activity_id == a.id).all()
        proj    = projects.get(a.project_id)
        # Distribute project budget equally across activities (simplified)
        proj_acts = [x for x in activities if x.project_id == a.project_id]
        budget_cr = (proj.budget_cr if proj else 0)
        per_act_budget = (budget_cr * 1e7 / len(proj_acts)) if proj_acts else 0   # crore → rupees
        result.append(_evm_activity(a, updates, per_act_budget))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 3.  SITE HEALTH SCORE
# ─────────────────────────────────────────────────────────────────────────────

def _compute_health(db: Session) -> dict:
    activities = db.query(Activity).all()
    if not activities:
        return {"health_score": 0, "grade": "F", "components": {}}

    scores = []
    for a in activities:
        updates = db.query(WorkerUpdate).filter(WorkerUpdate.activity_id == a.id).all()
        if not updates:
            scores.append({"progress": 0, "risk_inv": 50, "utilization": 0, "safety": 100, "issue_rate": 100})
            continue

        total_qty    = sum(u.quantity_done for u in updates)
        total_hours  = sum(u.hours_worked for u in updates)
        days         = len(set(u.timestamp.date() for u in updates)) or 1
        utilization  = min((total_hours / (24 * days)) * 100, 100)
        progress_pct = min(total_qty / a.planned_quantity * 100, 100) if a.planned_quantity else 0

        downtime     = sum(1 for u in updates if "equipment" in u.issue_type.lower() or u.hours_worked < 4)
        safety_inc   = sum(1 for u in updates if "safety" in u.issue_type.lower())
        issue_count  = sum(1 for u in updates if u.issue_type.lower() != "none")

        # Risk (inverted)
        risk = 0
        if utilization < 30:   risk += 35
        elif utilization < 55: risk += 18
        if downtime > 3:       risk += 30
        elif downtime > 0:     risk += 15
        if safety_inc > 0:     risk += 25
        if progress_pct < 20:  risk += 25
        risk = min(risk, 100)
        risk_inv = 100 - risk

        safety_score = max(100 - safety_inc * 30 - (0 if updates[-1].safety_ok else 20), 0)
        issue_rate   = max(100 - (issue_count / len(updates)) * 100, 0)

        scores.append({
            "progress":    progress_pct,
            "risk_inv":    risk_inv,
            "utilization": utilization,
            "safety":      safety_score,
            "issue_rate":  issue_rate,
        })

    n = len(scores)
    avg = lambda key: sum(s[key] for s in scores) / n

    components = {
        "progress_velocity": round(avg("progress"), 1),
        "risk_health":       round(avg("risk_inv"), 1),
        "utilization":       round(avg("utilization"), 1),
        "safety":            round(avg("safety"), 1),
        "issue_free_rate":   round(avg("issue_rate"), 1),
    }

    # Weighted composite
    health = (
        components["progress_velocity"] * 0.30 +
        components["risk_health"]        * 0.25 +
        components["utilization"]        * 0.20 +
        components["safety"]             * 0.15 +
        components["issue_free_rate"]    * 0.10
    )
    health = round(health, 1)

    grade = (
        "A+" if health >= 90 else
        "A"  if health >= 80 else
        "B"  if health >= 70 else
        "C"  if health >= 60 else
        "D"  if health >= 50 else "F"
    )

    # Persist snapshot
    log = SiteHealthLog(
        health_score=health,
        grade=grade,
        components=json.dumps(components)
    )
    db.add(log)
    db.commit()

    return {"health_score": health, "grade": grade, "components": components}


@router.get("/site-health")
def site_health(db: Session = Depends(get_db)):
    return _compute_health(db)


@router.get("/site-health-trend")
def site_health_trend(db: Session = Depends(get_db)):
    logs = (
        db.query(SiteHealthLog)
        .order_by(SiteHealthLog.recorded_at.desc())
        .limit(30).all()
    )
    return [
        {
            "date": l.recorded_at.strftime("%Y-%m-%d %H:%M"),
            "health_score": l.health_score,
            "grade": l.grade,
            "components": json.loads(l.components or "{}"),
        }
        for l in reversed(logs)
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 4.  PRODUCTIVITY HEATMAP DATA  (hour-of-day × day-of-week)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/productivity-heatmap")
def productivity_heatmap(db: Session = Depends(get_db)):
    """
    Returns a 7×24 grid: for each (weekday, hour), avg quantity completed per update.
    Frontend uses this to render a GitHub-style heatmap.
    """
    updates = db.query(WorkerUpdate).all()
    grid = [[0.0] * 24 for _ in range(7)]
    count = [[0]   * 24 for _ in range(7)]

    for u in updates:
        wd = u.timestamp.weekday()   # 0=Mon, 6=Sun
        hr = u.timestamp.hour
        grid[wd][hr]  += u.quantity_done
        count[wd][hr] += 1

    result = []
    days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    for wd in range(7):
        for hr in range(24):
            avg = round(grid[wd][hr] / count[wd][hr], 2) if count[wd][hr] > 0 else 0
            result.append({"day": days[wd], "day_idx": wd, "hour": hr, "avg_qty": avg, "count": count[wd][hr]})
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 5.  WEATHER IMPACT ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/weather-impact")
def weather_impact(db: Session = Depends(get_db)):
    """Compare average productivity (qty/hour) by weather condition."""
    updates = db.query(WorkerUpdate).all()
    by_weather: dict = {}
    for u in updates:
        w = u.weather_condition or "Unknown"
        if w not in by_weather:
            by_weather[w] = {"total_qty": 0, "total_hours": 0, "count": 0, "issues": 0}
        by_weather[w]["total_qty"]   += u.quantity_done
        by_weather[w]["total_hours"] += u.hours_worked
        by_weather[w]["count"]       += 1
        if u.issue_type.lower() != "none":
            by_weather[w]["issues"]  += 1

    result = []
    for w, v in by_weather.items():
        result.append({
            "weather":         w,
            "avg_qty_per_hr":  round(v["total_qty"] / v["total_hours"], 2) if v["total_hours"] > 0 else 0,
            "avg_qty_per_day": round(v["total_qty"] / v["count"], 2) if v["count"] > 0 else 0,
            "update_count":    v["count"],
            "issue_rate_pct":  round(v["issues"] / v["count"] * 100, 1) if v["count"] > 0 else 0,
        })
    result.sort(key=lambda x: x["avg_qty_per_hr"], reverse=True)
    return result