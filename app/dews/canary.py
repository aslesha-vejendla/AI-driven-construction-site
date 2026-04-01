"""
DEWS — Data Event Watermarking System
======================================
Layer 3: Canary Record Honeypots

Fake worker IDs seeded into the database that:
- Never appear in the UI
- Are never assigned to real workers
- Are never referenced in any report

The ONLY way they get touched is if someone is:
- Directly querying the database
- Fuzzing the API with sequential IDs
- Running insider threat operations

The moment a canary is triggered → CRITICAL alert fires immediately.
"""

from app.database.db import SessionLocal
from app.models.models import User, Alert
from datetime import datetime


# ── Canary IDs — never assign these to real users ────────────────────────────
CANARY_WORKER_IDS = {9991, 9992, 9993}

CANARY_PROFILES = [
    {"id": 9991, "name": "_canary_alpha",   "email": "canary_a@internal.sys"},
    {"id": 9992, "name": "_canary_beta",    "email": "canary_b@internal.sys"},
    {"id": 9993, "name": "_canary_gamma",   "email": "canary_g@internal.sys"},
]


def seed_canaries():
    """
    Run once on startup — inserts fake canary workers.
    Safe to call multiple times (idempotent).
    """
    db = SessionLocal()
    try:
        for profile in CANARY_PROFILES:
            existing = db.query(User).filter(User.id == profile["id"]).first()
            if not existing:
                canary_user = User(
                    name         = profile["name"],
                    email        = profile["email"],
                    password     = "CANARY_LOCKED_NO_LOGIN",
                    role         = "worker",
                    designation  = "CANARY",
                    company      = "SYSTEM",
                    avatar_color = "#FF0000",
                )
                db.add(canary_user)
        db.commit()
        print("✓ DEWS canary records seeded")
    except Exception as e:
        print(f"⚠ Canary seed error: {e}")
        db.rollback()
    finally:
        db.close()


def is_canary(worker_id: int) -> bool:
    """Returns True if the worker_id is a canary honeypot."""
    return worker_id in CANARY_WORKER_IDS


def trigger_canary_alert(worker_id: int, request_path: str = ""):
    """
    Called when a canary ID is accessed.
    Creates a CRITICAL alert and logs to ELIS.
    """
    db = SessionLocal()
    try:
        alert = Alert(
            activity_id = 1,   # attach to first activity as placeholder
            alert_type  = "CANARY_TRIGGERED",
            severity    = "high",
            message     = (
                f"🚨 HONEYPOT TRIGGERED — Worker ID {worker_id} is a canary record. "
                f"Possible insider threat, API fuzzing, or direct DB access detected. "
                f"Path: {request_path}"
            ),
            is_read     = False,
            created_at  = datetime.utcnow(),
        )
        db.add(alert)
        db.commit()
        print(f"🚨 DEWS CANARY TRIGGERED: worker_id={worker_id} path={request_path}")
    except Exception as e:
        print(f"⚠ Canary alert error: {e}")
        db.rollback()
    finally:
        db.close()