"""
shift_handover.py — powered by Groq (FREE)
──────────────────────────────────────────
End-of-shift handover: worker fills form → Groq llama-3.3-70b generates
a professional briefing paragraph for the incoming crew.
"""

import os
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.models.models import ShiftHandover, Activity
from fastapi import Depends

router = APIRouter()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = "llama-3.3-70b-versatile"
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"


async def generate_briefing(h: ShiftHandover, activity_name: str) -> str:
    prompt = f"""Write a professional shift handover briefing for the INCOMING construction crew.

Activity: {activity_name}
Outgoing crew lead: {h.outgoing_name}
Shift: {h.shift}
Quantity completed: {h.qty_completed} {h.unit}
Pending tasks: {h.pending_tasks or 'None specified'}
Equipment status: {h.equipment_status or 'All operational'}
Safety notes: {h.safety_notes or 'No special notes'}
Unresolved issues: {h.issues_left or 'None'}
Priority for next crew: {h.priority_next or 'Continue as planned'}

Write exactly 3 short paragraphs (no headers, no bullets):
1. What was accomplished this shift and current site state
2. Critical safety/equipment notes the incoming crew must know immediately
3. Specific targets and first actions for this shift

Be concise, practical, and construction-domain specific. Max 130 words total."""

    if not GROQ_API_KEY:
        return (
            f"Shift {h.shift} handover from {h.outgoing_name}. "
            f"Completed {h.qty_completed}{h.unit} this shift. "
            f"Pending: {h.pending_tasks or 'None'}. "
            f"Equipment: {h.equipment_status or 'All OK'}. "
            f"Priority for next shift: {h.priority_next or 'Continue as planned'}.\n\n"
            "_Set GROQ_API_KEY for AI-generated briefings._"
        )

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model":       GROQ_MODEL,
                    "max_tokens":  250,
                    "temperature": 0.5,
                    "messages": [
                        {"role": "system", "content": "You write concise, professional construction site shift handover briefings."},
                        {"role": "user",   "content": prompt},
                    ],
                },
            )
        data = resp.json()
        if resp.status_code == 200 and data.get("choices"):
            return data["choices"][0]["message"]["content"]
        raise ValueError(data.get("error", {}).get("message", "Groq error"))

    except Exception as e:
        return (
            f"Handover from {h.outgoing_name} ({h.shift} shift): "
            f"{h.qty_completed}{h.unit} completed. "
            f"Pending: {h.pending_tasks or 'None'}. "
            f"Equipment: {h.equipment_status or 'OK'}. "
            f"Next priority: {h.priority_next or 'Continue work'}."
            f"\n\n_(AI briefing failed: {str(e)[:60]})_"
        )


@router.get("/api/handovers")
def get_handovers(activity_id: int = None, limit: int = 20,
                  db: Session = Depends(get_db)):
    q = db.query(ShiftHandover)
    if activity_id:
        q = q.filter(ShiftHandover.activity_id == activity_id)
    items = q.order_by(ShiftHandover.timestamp.desc()).limit(limit).all()
    return [
        {
            "id":               h.id,
            "activity_id":      h.activity_id,
            "outgoing_name":    h.outgoing_name,
            "shift":            h.shift,
            "qty_completed":    h.qty_completed,
            "unit":             h.unit,
            "pending_tasks":    h.pending_tasks,
            "safety_notes":     h.safety_notes,
            "equipment_status": h.equipment_status,
            "issues_left":      h.issues_left,
            "priority_next":    h.priority_next,
            "ai_briefing":      h.ai_briefing,
            "timestamp":        h.timestamp.isoformat(),
        }
        for h in items
    ]


@router.get("/api/handovers/latest/{activity_id}")
def latest_handover(activity_id: int, db: Session = Depends(get_db)):
    h = (
        db.query(ShiftHandover)
        .filter(ShiftHandover.activity_id == activity_id)
        .order_by(ShiftHandover.timestamp.desc())
        .first()
    )
    if not h:
        return {"message": "No handover yet for this activity"}
    return {
        "outgoing_name": h.outgoing_name, "shift": h.shift,
        "qty_completed": h.qty_completed, "unit": h.unit,
        "pending_tasks": h.pending_tasks, "safety_notes": h.safety_notes,
        "equipment_status": h.equipment_status, "priority_next": h.priority_next,
        "ai_briefing": h.ai_briefing,
        "timestamp": h.timestamp.isoformat(),
    }


@router.post("/api/handover/submit")
async def submit_handover(request: Request, db: Session = Depends(get_db)):
    body = await request.json()

    activity = db.query(Activity).filter(
        Activity.id == body.get("activity_id")).first()
    activity_name = activity.name if activity else "Unknown Activity"

    h = ShiftHandover(
        activity_id      = body.get("activity_id"),
        outgoing_user_id = body.get("user_id"),
        outgoing_name    = body.get("outgoing_name", ""),
        shift            = body.get("shift", "Day"),
        qty_completed    = float(body.get("qty_completed", 0)),
        unit             = body.get("unit", "m"),
        pending_tasks    = body.get("pending_tasks", ""),
        safety_notes     = body.get("safety_notes", ""),
        equipment_status = body.get("equipment_status", ""),
        issues_left      = body.get("issues_left", ""),
        priority_next    = body.get("priority_next", ""),
    )
    db.add(h)
    db.flush()

    h.ai_briefing = await generate_briefing(h, activity_name)
    db.commit()

    return JSONResponse({"ok": True, "handover_id": h.id, "ai_briefing": h.ai_briefing})