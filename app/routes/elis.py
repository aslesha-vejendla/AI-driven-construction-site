import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from pydantic import BaseModel

from app.models.models import ELISEvent
from app.database.db import get_db
from app.elis.classifier import elis_classifier
from app.elis.logger import log_event

router = APIRouter(prefix="/api/elis", tags=["ELIS"])


# ── Pydantic schema ───────────────────────────────────────────────────────────
class ELISEventCreate(BaseModel):
    event_type: str
    message: str
    worker_id: Optional[int] = None
    extra_data: Optional[dict] = {}


# ── GET /api/elis/events ──────────────────────────────────────────────────────
@router.get("/events")
def get_events(limit: int = 100, severity: str = None, db: Session = Depends(get_db)):
    q = db.query(ELISEvent).order_by(ELISEvent.timestamp.desc())
    if severity:
        q = q.filter(ELISEvent.severity == severity)
    return q.limit(limit).all()


# ── POST /api/elis/events ─────────────────────────────────────────────────────
@router.post("/events")
def create_event(payload: ELISEventCreate, db: Session = Depends(get_db)):
    ml_result = elis_classifier.classify({
        "message":   payload.message,
        "worker_id": payload.worker_id or 0,
        "severity":  "",
    })

    event = log_event(
        db=db,
        event_type=payload.event_type,
        message=payload.message,
        worker_id=payload.worker_id,
        extra_data=payload.extra_data,
        ml_class=ml_result["class"] if elis_classifier.trained else None,
        ml_confidence=ml_result["confidence"] if elis_classifier.trained else None,
    )

    # ── Wire to Node-RED ──────────────────────────────────────────────────────
    try:
        httpx.post(
            "http://127.0.0.1:1880/elis-webhook",
            json={
                "event_id":   event.id,
                "event_type": event.event_type,
                "severity":   event.severity,
                "category":   event.category,
                "message":    event.message,
                "ml_class":   event.ml_class,
                "ml_confidence": event.ml_confidence,
            },
            timeout=2.0
        )
    except Exception:
        pass  # Node-RED being down should never break the API

    return event


# ── GET /api/elis/stats ───────────────────────────────────────────────────────
@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total   = db.query(func.count(ELISEvent.id)).scalar()
    by_sev  = db.query(ELISEvent.severity,   func.count()).group_by(ELISEvent.severity).all()
    by_type = db.query(ELISEvent.event_type, func.count()).group_by(ELISEvent.event_type).all()
    by_ml   = db.query(ELISEvent.ml_class,   func.count()).group_by(ELISEvent.ml_class).all()
    return {
        "total":         total,
        "by_severity":   dict(by_sev),
        "by_event_type": dict(by_type),
        "by_ml_class":   dict(by_ml),
    }


# ── GET /api/elis/worker-risk ─────────────────────────────────────────────────
@router.get("/worker-risk")
def get_worker_risk(db: Session = Depends(get_db)):
    from sqlalchemy import Integer as SAInteger, cast
    rows = db.query(
        ELISEvent.worker_id,
        func.count().label("total_events"),
        func.sum(cast(ELISEvent.event_type == "IDS_BREACH",       SAInteger)).label("breaches"),
        func.sum(cast(ELISEvent.event_type == "ANOMALY_DETECTED", SAInteger)).label("anomalies"),
    ).filter(ELISEvent.worker_id != None).group_by(ELISEvent.worker_id).all()

    def risk(b, a):
        score = (b or 0) * 3 + (a or 0)
        return "HIGH" if score > 6 else "ELEVATED" if score > 3 else "MEDIUM" if score > 0 else "LOW"

    return [
        {
            "worker_id":    r.worker_id,
            "total_events": r.total_events,
            "breaches":     r.breaches or 0,
            "anomalies":    r.anomalies or 0,
            "risk_level":   risk(r.breaches, r.anomalies),
        }
        for r in rows
    ]


# ── POST /api/elis/train ──────────────────────────────────────────────────────
@router.post("/train")
def train_model(db: Session = Depends(get_db)):
    events = db.query(ELISEvent).all()
    if len(events) < 10:
        return {"error": f"Need 10+ events to train, you have {len(events)}"}

    def label(e):
        if e.event_type in ("CANARY_TRIGGERED", "SALT_MISMATCH"): return 2
        if e.event_type in ("IDS_BREACH", "RISK_ESCALATION"):     return 1
        if e.event_type == "ANOMALY_DETECTED":                     return 1
        return 0

    dicts  = [{"message": e.message, "worker_id": e.worker_id or 0, "severity": e.severity} for e in events]
    labels = [label(e) for e in events]
    elis_classifier.train(dicts, labels)
    return {"status": "trained", "events_used": len(events)}