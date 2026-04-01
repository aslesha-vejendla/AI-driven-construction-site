from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import ELISEvent

SEVERITY_MAP = {
    "WATERMARK_APPLIED":  "INFO",
    "WATERMARK_VERIFIED": "INFO",
    "IDS_BREACH":         "CRITICAL",
    "SALT_MISMATCH":      "CRITICAL",
    "CANARY_TRIGGERED":   "CRITICAL",
    "RISK_ESCALATION":    "WARNING",
    "ANOMALY_DETECTED":   "WARNING",
    "AUTH_FAILURE":       "WARNING",
    "REPORT_GENERATED":   "INFO",
}

CATEGORY_MAP = {
    "WATERMARK_APPLIED":  "INTEGRITY",
    "WATERMARK_VERIFIED": "INTEGRITY",
    "IDS_BREACH":         "SECURITY",
    "SALT_MISMATCH":      "SECURITY",
    "CANARY_TRIGGERED":   "SECURITY",
    "RISK_ESCALATION":    "SECURITY",
    "ANOMALY_DETECTED":   "OPERATIONAL",
    "AUTH_FAILURE":       "SECURITY",
    "REPORT_GENERATED":   "OPERATIONAL",
}

SOURCE_MAP = {
    "WATERMARK_APPLIED":  "WORKER",
    "WATERMARK_VERIFIED": "SYSTEM",
    "IDS_BREACH":         "IDS",
    "SALT_MISMATCH":      "IDS",
    "CANARY_TRIGGERED":   "CANARY",
    "RISK_ESCALATION":    "SYSTEM",
    "ANOMALY_DETECTED":   "SYSTEM",
    "AUTH_FAILURE":       "WORKER",
    "REPORT_GENERATED":   "AI",
}

def log_event(
    db: Session,
    event_type: str,
    message: str,
    worker_id: int = None,
    extra_data: dict = None,
    ml_class: str = None,
    ml_confidence: float = None,
):
    event = ELISEvent(
        event_type    = event_type,
        severity      = SEVERITY_MAP.get(event_type, "INFO"),
        category      = CATEGORY_MAP.get(event_type, "OPERATIONAL"),
        source        = SOURCE_MAP.get(event_type, "SYSTEM"),
        worker_id     = worker_id,
        message       = message,
        extra_data    = extra_data or {},
        ml_class      = ml_class,
        ml_confidence = ml_confidence,
        timestamp     = datetime.utcnow(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event