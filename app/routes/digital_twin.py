from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database.db import get_db
from app.models.models import Activity, WorkerUpdate, RiskSnapshot
from datetime import datetime, timedelta, date

router = APIRouter()


def compute_twin(activity, updates):
    if not updates:
        return {
            "activity_id":      activity.id,
            "activity":         activity.name,
            "activity_type":    activity.activity_type or "General",
            "risk_score":       0,
            "status":           "NO DATA",
            "color":            "#6B7280",
            "insight":          "No worker updates submitted yet.",
            "advance_per_day":  0,
            "utilization":      0,
            "downtime_events":  0,
            "safety_incidents": 0,
            "total_qty":        0,
            "progress_pct":     0,
            "unit":             activity.unit or "m",
            "planned_qty":      activity.planned_quantity,
            "update_count":     0,
            "days_active":      0,
            "avg_crew":         0,
        }

    total_qty   = sum(u.quantity_done for u in updates)
    total_hours = sum(u.hours_worked  for u in updates)
    days        = len(set(u.timestamp.date() for u in updates)) or 1
    advance_per_day = round(total_qty / days, 2)
    utilization     = round(min((total_hours / (24 * days)) * 100, 100), 1)

    downtime_events  = sum(1 for u in updates
        if u.issue_type and ("equipment" in u.issue_type.lower() or u.hours_worked < 4))
    safety_incidents = sum(1 for u in updates
        if u.issue_type and "safety" in u.issue_type.lower())

    progress_pct = round((total_qty / activity.planned_quantity * 100), 1) \
        if activity.planned_quantity and activity.planned_quantity > 0 else 0

    risk = 0
    if utilization < 30:      risk += 35
    elif utilization < 55:    risk += 18
    if downtime_events > 3:   risk += 30
    elif downtime_events > 0: risk += 15
    if safety_incidents > 0:  risk += 25
    if progress_pct < 20:     risk += 25
    elif progress_pct < 45:   risk += 10
    recent = sorted(updates, key=lambda u: u.timestamp, reverse=True)[:3]
    if recent and all(u.issue_type and u.issue_type.lower() != "none" for u in recent):
        risk += 12
    risk = min(risk, 100)

    if   risk >= 65: status, color = "HIGH RISK",  "#EF4444"
    elif risk >= 35: status, color = "MEDIUM RISK", "#F59E0B"
    else:            status, color = "ON TRACK",    "#10B981"

    latest  = recent[0]
    insight = (
        f"Latest by {latest.worker_name}: {latest.quantity_done}{latest.quantity_unit} "
        f"in {latest.hours_worked}h. "
        + (f"⚠️ {latest.issue_type}"
           if latest.issue_type and latest.issue_type.lower() != "none"
           else "✅ No issues")
    )

    return {
        "activity_id":      activity.id,
        "activity":         activity.name,
        "activity_type":    activity.activity_type or "General",
        "risk_score":       risk,
        "status":           status,
        "color":            color,
        "insight":          insight,
        "advance_per_day":  advance_per_day,
        "utilization":      utilization,
        "downtime_events":  downtime_events,
        "safety_incidents": safety_incidents,
        "total_qty":        round(total_qty, 2),
        "progress_pct":     progress_pct,
        "unit":             activity.unit or "m",
        "planned_qty":      activity.planned_quantity,
        "update_count":     len(updates),
        "days_active":      days,
        "avg_crew":         round(sum(u.crew_size or 1 for u in updates) / len(updates)),
    }


def compute_daily_risk(activity, day_updates):
    """Compute risk score for a single day's updates independently."""
    if not day_updates:
        return None

    qty   = sum(u.quantity_done for u in day_updates)
    hours = sum(u.hours_worked  for u in day_updates)
    down  = sum(1 for u in day_updates
                if u.issue_type and (
                    "equipment" in u.issue_type.lower()
                    or u.hours_worked < 4))
    pct   = round(qty / activity.planned_quantity * 100, 1) \
            if activity.planned_quantity else 0
    util  = round(min(hours / (8 * len(day_updates)) * 100, 100), 1)

    risk = 0
    if util < 30:      risk += 35
    elif util < 55:    risk += 18
    if down > 3:       risk += 30
    elif down > 0:     risk += 15
    if pct  < 20:      risk += 25
    elif pct < 45:     risk += 10
    return min(risk, 100)


@router.get("/digital-twin")
def digital_twin(db: Session = Depends(get_db)):
    activities = db.query(Activity).all()
    result = []
    for a in activities:
        updates = db.query(WorkerUpdate).filter(
            WorkerUpdate.activity_id == a.id
        ).order_by(desc(WorkerUpdate.timestamp)).all()
        metrics = compute_twin(a, updates)
        result.append(metrics)
        snap = RiskSnapshot(
            activity_id = a.id,
            risk_score  = metrics["risk_score"],
            status      = metrics["status"],
            utilization = metrics["utilization"],
            downtime    = metrics["downtime_events"],
        )
        db.add(snap)
    db.commit()
    return result


@router.get("/digital-twin/{activity_id}")
def digital_twin_single(activity_id: int, db: Session = Depends(get_db)):
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        return {"error": "Not found"}
    updates = db.query(WorkerUpdate).filter(
        WorkerUpdate.activity_id == activity_id
    ).order_by(desc(WorkerUpdate.timestamp)).all()
    return compute_twin(activity, updates)


@router.get("/api/timeline/{activity_id}")
def get_timeline(activity_id: int, db: Session = Depends(get_db)):
    updates = (
        db.query(WorkerUpdate)
        .filter(WorkerUpdate.activity_id == activity_id)
        .order_by(WorkerUpdate.timestamp).all()
    )
    cumulative = 0
    result = []
    for u in updates:
        cumulative += u.quantity_done
        result.append({
            "date":       u.timestamp.strftime("%Y-%m-%d"),
            "daily":      u.quantity_done,
            "cumulative": round(cumulative, 2),
            "hours":      u.hours_worked,
            "issue":      u.issue_type,
        })
    return result


@router.get("/api/risk-trend/{activity_id}")
def risk_trend(activity_id: int, db: Session = Depends(get_db)):
    snaps = (
        db.query(RiskSnapshot)
        .filter(RiskSnapshot.activity_id == activity_id)
        .order_by(RiskSnapshot.recorded_at)
        .limit(30).all()
    )
    return [{"date": s.recorded_at.strftime("%Y-%m-%d %H:%M"),
             "risk_score": s.risk_score, "status": s.status}
            for s in snaps]


@router.get("/api/progress-summary")
def progress_summary(db: Session = Depends(get_db)):
    activities = db.query(Activity).all()
    result = []
    for a in activities:
        updates = db.query(WorkerUpdate).filter(WorkerUpdate.activity_id == a.id).all()
        total   = sum(u.quantity_done for u in updates)
        pct     = round(total / a.planned_quantity * 100, 1) if a.planned_quantity else 0
        result.append({
            "activity_id":        a.id,
            "activity_name":      a.name,
            "planned_quantity":   a.planned_quantity,
            "completed_quantity": round(total, 2),
            "unit":               a.unit or "m",
            "progress_pct":       pct,
            "update_count":       len(updates),
        })
    return result


@router.get("/api/activities")
def get_activities(db: Session = Depends(get_db)):
    activities = db.query(Activity).all()
    return [{"id": a.id, "name": a.name, "type": a.activity_type,
             "unit": a.unit, "project_id": a.project_id,
             "planned_quantity": a.planned_quantity,
             "planned_duration_days": a.planned_duration_days,
             "start_date": str(a.start_date) if a.start_date else None}
            for a in activities]


@router.get("/api/projects")
def get_projects(db: Session = Depends(get_db)):
    from app.models.models import Project
    projects = db.query(Project).all()
    return [{"id": p.id, "name": p.name,
             "type": p.project_type, "status": p.status}
            for p in projects]


@router.get("/api/risk-history")
def risk_history(db: Session = Depends(get_db)):
    """
    Computes REAL daily risk scores from actual worker updates per day.
    Each day's score is independently calculated — no padding with same value.
    Days with no submissions carry forward with slight drift toward 50.
    """
    activities  = db.query(Activity).all()
    all_updates = db.query(WorkerUpdate).all()
    today       = datetime.utcnow().date()
    result      = []

    for a in activities:
        act_updates  = [u for u in all_updates if u.activity_id == a.id]
        daily_scores = []
        last_known   = 50  # neutral starting point

        for day_offset in range(6, -1, -1):   # 6 days ago → today
            day         = today - timedelta(days=day_offset)
            day_updates = [u for u in act_updates
                           if u.timestamp.date() == day]

            score = compute_daily_risk(a, day_updates)
            if score is not None:
                last_known = score
                daily_scores.append(score)
            else:
                # Carry forward with slight drift — avoids flat identical line
                carried = round(last_known * 0.96 + 50 * 0.04, 1)
                last_known = carried
                daily_scores.append(carried)

        # Velocity = today minus yesterday
        velocity = round(daily_scores[-1] - daily_scores[-2], 1) \
                   if len(daily_scores) >= 2 else 0

        if   velocity > 10:  trend, color = "ACCELERATING",   "#EF4444"
        elif velocity > 3:   trend, color = "RISING",         "#F59E0B"
        elif velocity < -10: trend, color = "IMPROVING FAST", "#10B981"
        elif velocity < -3:  trend, color = "IMPROVING",      "#06B6D4"
        else:                trend, color = "STABLE",         "#71717A"

        result.append({
            "activity_id":  a.id,
            "activity":     a.name,
            "scores":       daily_scores,
            "current_risk": daily_scores[-1],
            "velocity":     velocity,
            "trend":        trend,
            "trend_color":  color,
        })

    return result


@router.get("/api/delay-forecast")
def delay_forecast(db: Session = Depends(get_db)):
    activities  = db.query(Activity).all()
    all_updates = db.query(WorkerUpdate).all()
    today       = datetime.utcnow().date()
    result      = []

    for a in activities:
        act_updates = [u for u in all_updates if u.activity_id == a.id]
        if not act_updates:
            continue

        total_qty  = sum(u.quantity_done for u in act_updates)
        days       = len(set(u.timestamp.date() for u in act_updates)) or 1
        daily_rate = total_qty / days if days > 0 else 0
        remaining  = max((a.planned_quantity or 0) - total_qty, 0)
        eta_days   = round(remaining / daily_rate) if daily_rate > 0 else 999

        planned_days_left = (a.end_date - today).days if a.end_date else 0
        delay_days = max(eta_days - planned_days_left, 0)

        result.append({
            "activity_id": a.id,
            "name":        a.name,
            "daily_rate":  round(daily_rate, 2),
            "remaining":   round(remaining, 1),
            "eta_days":    eta_days,
            "delay_days":  delay_days,
        })

    return result


@router.get("/api/site-health")
def site_health(db: Session = Depends(get_db)):
    activities  = db.query(Activity).all()
    all_updates = db.query(WorkerUpdate).all()

    if not all_updates:
        return {"health_score": 0, "grade": "F",
                "components": {}, "message": "No data yet"}

    total_updates = len(all_updates)
    issue_updates = sum(1 for u in all_updates
                        if u.issue_type and u.issue_type.lower() != "none")
    safety_issues = sum(1 for u in all_updates
                        if u.issue_type and "safety" in u.issue_type.lower())

    safety_score  = max(0, 100 - safety_issues * 15)
    quality_score = max(0, 100 - round(issue_updates / total_updates * 100))

    progress_scores = []
    for a in activities:
        au  = [u for u in all_updates if u.activity_id == a.id]
        qty = sum(u.quantity_done for u in au)
        pct = round(qty / a.planned_quantity * 100, 1) if a.planned_quantity else 0
        progress_scores.append(min(pct, 100))

    progress_score  = round(sum(progress_scores) / len(progress_scores)) \
                      if progress_scores else 0
    equipment_score = max(0, 100 - sum(
        1 for u in all_updates
        if u.issue_type and "equipment" in u.issue_type.lower()) * 8)

    health_score = round(
        safety_score    * 0.30 +
        quality_score   * 0.25 +
        progress_score  * 0.25 +
        equipment_score * 0.20
    )

    grade = "A" if health_score >= 85 else \
            "B" if health_score >= 70 else \
            "C" if health_score >= 55 else "D"

    return {
        "health_score": health_score,
        "grade":        grade,
        "components": {
            "safety":    safety_score,
            "quality":   quality_score,
            "progress":  progress_score,
            "equipment": equipment_score,
        }
    }