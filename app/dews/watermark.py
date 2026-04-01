"""
DEWS — Data Event Watermarking System
======================================
Layer 1: Watermark Injector

Two mechanisms per worker update:
1. HMAC-SHA256 tag — cryptographically binds worker identity to payload
2. Steganographic salt — invisible numeric perturbation unique to each worker_id

If someone copies another worker's data and re-submits it:
- The steg salt won't match their identity → BREACH detected
- The HMAC tag won't match the new worker_id → BREACH detected
"""

import hmac
import hashlib
import json
import os


SECRET_KEY = os.environ.get("WATERMARK_SECRET", "constructionease-dews-secret-v3")


# ── HMAC Tag ──────────────────────────────────────────────────────────────────

def compute_tag(worker_id: int, payload: dict) -> str:
    """
    HMAC-SHA256 tag binding worker identity to the exact payload.
    Canonical form: sorted JSON of key fields + worker_id.
    """
    canonical = json.dumps({
        "worker_id":   worker_id,
        "hours":       payload.get("hours_worked",   payload.get("hours", 0)),
        "quantity":    round(float(payload.get("quantity_done", payload.get("quantity", 0))), 2),
        "activity_id": payload.get("activity_id", 0),
    }, sort_keys=True)
    return hmac.new(
        SECRET_KEY.encode(),
        canonical.encode(),
        hashlib.sha256
    ).hexdigest()


def verify_tag(worker_id: int, payload: dict, submitted_tag: str) -> bool:
    """Re-derive tag and compare using constant-time digest."""
    expected = compute_tag(worker_id, payload)
    return hmac.compare_digest(expected, submitted_tag)


# ── Steganographic Salt ───────────────────────────────────────────────────────

def inject_steg_salt(worker_id: int, quantity: float) -> float:
    """
    Embeds a deterministic, invisible perturbation at the 4th decimal place.
    Same worker_id always produces the same salt — detectable by code, invisible to humans.

    Formula: salt = (worker_id × 7919) mod 9 × 0.0001
    e.g. worker_id=3 → salt_basis=6 → perturbation=+0.0006
    """
    salt_basis    = (worker_id * 7919) % 9
    perturbation  = salt_basis * 0.0001
    return round(quantity + perturbation, 4)


def verify_steg_salt(worker_id: int, quantity: float) -> bool:
    """Extract 4th decimal from stored quantity and check it matches worker's expected salt."""
    expected_salt = (worker_id * 7919) % 9
    observed_salt = round((quantity * 10000) % 10)
    return observed_salt == expected_salt


def extract_salt_owner(quantity: float) -> list:
    """
    Forensic: given a quantity value, returns list of worker_ids whose salt matches.
    Useful when a breach is detected — find who originally submitted this value.
    """
    observed_salt = round((quantity * 10000) % 10)
    matches = []
    for worker_id in range(1, 10000):
        if (worker_id * 7919) % 9 == observed_salt:
            matches.append(worker_id)
            if len(matches) >= 5:   # cap at 5 candidates
                break
    return matches