"""
worker.py — Field Update Routes
Integrated with DEWS Layer 1 (Watermark) and Layer 3 (Canary)
"""

from fastapi import APIRouter, Form, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime

from app.database.db import get_db
from app.models.models import WorkerUpdate, Alert, Activity

# ── DEWS imports ──────────────────────────────────────────────────────────────
from app.dews.watermark import compute_tag, inject_steg_salt, verify_steg_salt
from app.dews.canary    import is_canary, trigger_canary_alert

router = APIRouter()


@router.post("/worker-update")
def worker_update(
    request:          Request,
    user_id:          int   = Form(default=1),
    activity_id:      int   = Form(...),
    worker_name:      str   = Form(...),
    work_type:        str   = Form(...),
    work_description: str   = Form(default=""),
    quantity_done:    float = Form(...),
    quantity_unit:    str   = Form(...),
    hours_worked:     float = Form(...),
    issue_type:       str   = Form(default="None"),
    weather_condition:str   = Form(default="Clear"),
    crew_size:        int   = Form(default=5),
    safety_ok:        str   = Form(default=""),
    db: Session = Depends(get_db)
):
    # ── DEWS Layer 3: Canary check ────────────────────────────────────────────
    if is_canary(user_id):
        trigger_canary_alert(user_id, request_path="/worker-update")
        return RedirectResponse("/login?error=Access+denied", status_code=303)

    # ── DEWS Layer 1: Compute HMAC watermark tag ──────────────────────────────
    payload_for_tag = {
        "hours_worked":  hours_worked,
        "quantity_done": round(quantity_done, 2),
        "activity_id":   activity_id,
    }
    watermark_tag = compute_tag(user_id, payload_for_tag)

    # ── DEWS Layer 1: Inject steganographic salt into quantity ────────────────
    salted_quantity = inject_steg_salt(user_id, quantity_done)

    # ── DEWS Layer 2: Impossible delta check (Node-RED mirrors this) ──────────
    ids_verdict   = "PASS"
    breach_reasons = []

    if hours_worked > 18 or hours_worked < 0:
        ids_verdict = "BREACH"
        breach_reasons.append("impossible_hours")

    if quantity_done < 0:
        ids_verdict = "BREACH"
        breach_reasons.append("negative_quantity")

    # If BREACH — log alert but still store (for forensic audit trail)
    if ids_verdict == "BREACH":
        db.add(Alert(
            activity_id = activity_id,
            alert_type  = "IDS_BREACH",
            severity    = "high",
            message     = (
                f"⚠️ IDS flagged update from {worker_name} (ID:{user_id}). "
                f"Reasons: {', '.join(breach_reasons)}. "
                f"Watermark: {watermark_tag[:12]}..."
            ),
            is_read    = False,
            created_at = datetime.utcnow(),
        ))

    # ── Store the update with DEWS metadata ───────────────────────────────────
    update = WorkerUpdate(
        user_id          = user_id,
        activity_id      = activity_id,
        worker_name      = worker_name,
        work_type        = work_type,
        work_description = work_description,
        quantity_done    = salted_quantity,     # ← steganographic salt applied
        quantity_unit    = quantity_unit,
        hours_worked     = hours_worked,
        issue_type       = issue_type,
        weather_condition= weather_condition,
        crew_size        = crew_size,
        safety_ok        = (safety_ok == "true"),
    )
    db.add(update)

    # ── Auto-alerts for operational issues ───────────────────────────────────
    if issue_type in ["Equipment Breakdown", "Safety Concern"]:
        db.add(Alert(
            activity_id = activity_id,
            alert_type  = "HIGH_RISK" if issue_type == "Safety Concern" else "EQUIPMENT",
            message     = f"{worker_name} reported: {issue_type} during {work_type}.",
            severity    = "high" if issue_type == "Safety Concern" else "medium",
            is_read     = False,
            created_at  = datetime.utcnow(),
        ))

    if hours_worked < 4:
        db.add(Alert(
            activity_id = activity_id,
            alert_type  = "DELAY",
            message     = f"Low hours logged by {worker_name}: only {hours_worked}h on {work_type}.",
            severity    = "low",
            is_read     = False,
            created_at  = datetime.utcnow(),
        ))

    db.commit()
    return RedirectResponse(f"/worker-dashboard?user_id={user_id}&success=1", status_code=303)


@router.get("/api/updates")
def get_updates(
    activity_id:  int = None,
    worker_name:  str = None,
    limit:        int = 50,
    db: Session = Depends(get_db)
):
    q = db.query(WorkerUpdate)
    if activity_id:
        q = q.filter(WorkerUpdate.activity_id == activity_id)
    if worker_name:
        q = q.filter(WorkerUpdate.worker_name == worker_name)
    updates = q.order_by(WorkerUpdate.timestamp.desc()).limit(limit).all()
    return [
        {
            "id":               u.id,
            "worker_name":      u.worker_name,
            "work_type":        u.work_type,
            "work_description": u.work_description,
            "quantity_done":    u.quantity_done,
            "quantity_unit":    u.quantity_unit,
            "hours_worked":     u.hours_worked,
            "issue_type":       u.issue_type,
            "weather_condition":u.weather_condition,
            "crew_size":        u.crew_size,
            "safety_ok":        u.safety_ok,
            "timestamp":        u.timestamp.isoformat(),
            "activity_id":      u.activity_id,
        }
        for u in updates
    ]


@router.get("/api/worker-stats/{worker_name}")
def worker_stats(worker_name: str, db: Session = Depends(get_db)):
    updates = db.query(WorkerUpdate).filter(
        WorkerUpdate.worker_name == worker_name).all()
    if not updates:
        return {"error": "No data for this worker"}
    total_qty = sum(u.quantity_done for u in updates)
    total_hrs = sum(u.hours_worked  for u in updates)
    issues    = [u for u in updates if u.issue_type and u.issue_type.lower() != "none"]
    return {
        "worker_name":   worker_name,
        "total_updates": len(updates),
        "total_quantity":round(total_qty, 2),
        "total_hours":   round(total_hrs, 1),
        "issue_count":   len(issues),
        "efficiency":    round(total_qty / total_hrs, 2) if total_hrs > 0 else 0,
    }


# ── DEWS Verification API ─────────────────────────────────────────────────────

@router.get("/api/dews/verify/{update_id}")
def verify_update_integrity(update_id: int, db: Session = Depends(get_db)):
    """
    Forensic endpoint — verifies the steganographic salt of a stored update.
    Used by supervisor to audit any suspicious submission.
    """
    update = db.query(WorkerUpdate).filter(WorkerUpdate.id == update_id).first()
    if not update:
        return {"error": "Update not found"}

    salt_valid = verify_steg_salt(update.user_id, update.quantity_done)

    return {
        "update_id":    update_id,
        "worker_id":    update.user_id,
        "worker_name":  update.worker_name,
        "quantity":     update.quantity_done,
        "salt_valid":   salt_valid,
        "verdict":      "AUTHENTIC" if salt_valid else "TAMPERED — salt mismatch",
        "risk":         "LOW" if salt_valid else "HIGH — possible data forgery",
    }


@router.get("/api/dews/audit")
def dews_audit_log(limit: int = 20, db: Session = Depends(get_db)):
    """
    Returns all DEWS-related alerts (IDS breaches, canary triggers).
    """
    alerts = db.query(Alert).filter(
        Alert.alert_type.in_(["IDS_BREACH", "CANARY_TRIGGERED"])
    ).order_by(Alert.created_at.desc()).limit(limit).all()

    return [
        {
            "id":         a.id,
            "type":       a.alert_type,
            "severity":   a.severity,
            "message":    a.message,
            "created_at": a.created_at.isoformat(),
        }
        for a in alerts
    ]