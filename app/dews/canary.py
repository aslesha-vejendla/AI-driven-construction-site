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
    {"id": 9991, "name": "_canary_alpha", "email": "canary_a@internal.sys"},
    {"id": 9992, "name": "_canary_beta",  "email": "canary_b@internal.sys"},
    {"id": 9993, "name": "_canary_gamma", "email": "canary_g@internal.sys"},
]


def seed_canaries():
    """
    Run once on startup — inserts fake canary workers.
    Fully idempotent: checks BOTH id AND email before inserting.
    Safe to call on every server restart.
    """
    db = SessionLocal()
    try:
        for profile in CANARY_PROFILES:
            # Check by ID first
            existing_by_id = db.query(User).filter(User.id == profile["id"]).first()
            if existing_by_id:
                continue  # Already seeded — skip cleanly

            # Check by email as secondary guard (handles partial/corrupt states)
            existing_by_email = db.query(User).filter(User.email == profile["email"]).first()
            if existing_by_email:
                continue  # Email taken — skip cleanly

            canary_user = User(
                id           = profile["id"],   # ← Force the honeypot ID explicitly
                name         = profile["name"],
                email        = profile["email"],
                password     = "CANARY_LOCKED_NO_LOGIN",
                role         = "worker",
                designation  = "CANARY",
                company      = "SYSTEM",
                phone        = "",
                avatar_color = "#FF0000",
            )
            db.add(canary_user)

        db.commit()
        print("[DEWS] Canary records verified.")
    except Exception as e:
        db.rollback()
        print(f"[DEWS] Canary seed error: {e}")
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
            activity_id = 1,
            alert_type  = "CANARY_TRIGGERED",
            severity    = "high",
            message     = (
                f"HONEYPOT TRIGGERED — Worker ID {worker_id} is a canary record. "
                f"Possible insider threat, API fuzzing, or direct DB access detected. "
                f"Path: {request_path}"
            ),
            is_read    = False,
            created_at = datetime.utcnow(),
        )
        db.add(alert)
        db.commit()
        print(f"[DEWS] CANARY TRIGGERED: worker_id={worker_id}  path={request_path}")
    except Exception as e:
        db.rollback()
        print(f"[DEWS] Canary alert error: {e}")
    finally:
        db.close()