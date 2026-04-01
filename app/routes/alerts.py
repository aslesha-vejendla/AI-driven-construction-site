from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.models.models import Alert

router = APIRouter()


@router.get("/api/alerts")
def get_alerts(unread_only: bool = False, db: Session = Depends(get_db)):
    q = db.query(Alert)
    if unread_only:
        q = q.filter(Alert.is_read == False)
    alerts = q.order_by(Alert.created_at.desc()).limit(20).all()
    return [
        {
            "id":         a.id,
            "alert_type": a.alert_type,
            "message":    a.message,
            "severity":   a.severity,
            "is_read":    a.is_read,
            "created_at": a.created_at.isoformat(),
        }
        for a in alerts
    ]


@router.post("/api/alerts/{alert_id}/read")
def mark_read(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if alert:
        alert.is_read = True
        db.commit()
    return {"ok": True}


@router.post("/api/alerts/read-all")
def mark_all_read(db: Session = Depends(get_db)):
    db.query(Alert).update({"is_read": True})
    db.commit()
    return {"ok": True}