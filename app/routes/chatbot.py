"""
LLM Chatbot Route — powered by Groq (FREE)
───────────────────────────────────────────
Model  : llama-3.3-70b-versatile  (free tier, very fast)
API    : https://api.groq.com/openai/v1/chat/completions
Key    : get free key at https://console.groq.com  (no credit card needed)
"""

import os
from dotenv import load_dotenv
load_dotenv()

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.models.models import WorkerUpdate, Activity, Project, ChatLog, Alert
from datetime import datetime

router = APIRouter()

GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"

# ── Read key at request time so .env changes take effect without restart ──────
def get_groq_key() -> str:
    return os.getenv("GROQ_API_KEY", "")


SYSTEM_PROMPT = """\
You are SiteAI, an expert AI assistant embedded in ConstructTwin — a digital twin \
platform for infrastructure construction monitoring in India.

You have real-time access to the project database injected below: activities, \
risk scores, worker updates, downtime events, progress percentages, and active alerts.

Your expertise:
- TBM (Tunnel Boring Machine) operations and performance benchmarks
- Metro rail, dam, highway, and large civil works construction
- Critical path analysis, Earned Value Management (EVM)
- Construction risk assessment and mitigation strategies
- Worker productivity and safety compliance (IS codes)

Rules:
- Always cite specific numbers from the live data (e.g. "TBM Drive is at 45% with risk 62")
- Be direct and concise — 2-5 sentences unless a detailed answer is needed
- When risk is HIGH suggest 2-3 concrete mitigation actions
- Use **bold** for key figures, bullet points for lists
- If data is missing say "No data recorded yet" — never fabricate numbers
- Speak like a senior project manager, not a generic chatbot
"""


def build_site_context(db: Session) -> str:
    projects   = db.query(Project).all()
    activities = db.query(Activity).all()
    updates    = db.query(WorkerUpdate).order_by(
        WorkerUpdate.timestamp.desc()).limit(60).all()
    alerts     = db.query(Alert).filter(
        Alert.is_read == False).order_by(Alert.created_at.desc()).limit(8).all()

    lines = [
        f"TODAY: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
        "PROJECTS: " + ", ".join(f"{p.name} [{p.project_type}]" for p in projects),
        "",
    ]

    for a in activities:
        au    = [u for u in updates if u.activity_id == a.id]
        qty   = sum(u.quantity_done for u in au)
        hours = sum(u.hours_worked  for u in au)
        days  = len(set(u.timestamp.date() for u in au)) or 1
        util  = round(min(hours / (24 * days) * 100, 100), 1)
        down  = sum(1 for u in au if "equipment" in u.issue_type.lower() or u.hours_worked < 4)
        pct   = round(qty / a.planned_quantity * 100, 1) if a.planned_quantity else 0
        risk  = min(
            (35 if util < 30 else 18 if util < 55 else 0) +
            (30 if down > 3  else 15 if down > 0  else 0) +
            (25 if pct < 20  else 10 if pct < 45  else 0), 100
        )
        status = "HIGH RISK" if risk >= 65 else "MEDIUM RISK" if risk >= 35 else "ON TRACK"
        lines.append(
            f"ACTIVITY '{a.name}' ({a.activity_type}): "
            f"planned={a.planned_quantity}{a.unit}, done={round(qty,1)}{a.unit} ({pct}%), "
            f"utilization={util}%, downtime={down}, risk={risk}, status={status}, updates={len(au)}"
        )
        if au:
            l = au[0]
            lines.append(
                f"  └ Latest: {l.worker_name} {l.timestamp.strftime('%d %b %H:%M')} — "
                f"{l.quantity_done}{l.quantity_unit} in {l.hours_worked}h | Issue: {l.issue_type}"
            )

    if alerts:
        lines.append("\nUNREAD ALERTS:")
        for al in alerts:
            lines.append(f"  [{al.severity.upper()}] {al.alert_type}: {al.message[:100]}")

    return "\n".join(lines)


async def call_groq(messages: list, site_context: str) -> str:
    key = get_groq_key()
    system_with_context = SYSTEM_PROMPT + "\n\n=== LIVE SITE DATA ===\n" + site_context

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type":  "application/json",
            },
            json={
                "model":       GROQ_MODEL,
                "max_tokens":  700,
                "temperature": 0.4,
                "messages": [
                    {"role": "system", "content": system_with_context},
                    *messages,
                ],
            },
        )

    data = resp.json()
    if resp.status_code == 200 and data.get("choices"):
        return data["choices"][0]["message"]["content"]

    err = data.get("error", {}).get("message", f"HTTP {resp.status_code}")
    return f"⚠️ Groq error: {err}"


def keyword_fallback(message: str, db: Session) -> str:
    msg        = message.lower()
    updates    = db.query(WorkerUpdate).all()
    activities = db.query(Activity).all()

    if any(w in msg for w in ["risk", "danger", "critical", "alert"]):
        high = [
            a.name for a in activities
            if sum(1 for u in updates
                   if u.activity_id == a.id and "equipment" in u.issue_type.lower()) > 1
        ]
        if high:
            return f"⚠️ High-risk activities: **{', '.join(high)}**. Recommend immediate inspection and equipment audit."
        return "✅ No critical risks detected across all activities."

    if any(w in msg for w in ["progress", "advance", "complete", "percent", "done"]):
        lines = []
        for a in activities:
            au    = [u for u in updates if u.activity_id == a.id]
            total = sum(u.quantity_done for u in au)
            pct   = round(total / a.planned_quantity * 100, 1) if a.planned_quantity else 0
            lines.append(f"• **{a.name}**: {round(total,1)}{a.unit} / {a.planned_quantity}{a.unit} ({pct}%)")
        return "📊 Progress:\n" + "\n".join(lines) if lines else "No progress data yet."

    if any(w in msg for w in ["downtime", "breakdown", "equipment", "failure"]):
        total   = sum(1 for u in updates if "equipment" in u.issue_type.lower())
        low_hrs = sum(1 for u in updates if u.hours_worked < 4)
        return f"🔧 Equipment breakdowns: **{total}**. Low-hour shifts (<4h): **{low_hrs}**."

    if any(w in msg for w in ["worker", "crew", "staff", "labour"]):
        workers = list(set(u.worker_name for u in updates))
        return f"👷 Workers: **{', '.join(workers[:6])}** ({len(workers)} total). Updates: {len(updates)}."

    if any(w in msg for w in ["weather", "rain"]):
        wc = {}
        for u in updates:
            wc[u.weather_condition] = wc.get(u.weather_condition, 0) + 1
        if wc:
            top = max(wc, key=wc.get)
            return f"🌤️ Most common weather: **{top}** ({wc[top]} sessions). Rain days: {wc.get('Rain',0)+wc.get('Heavy Rain',0)}."
        return "No weather data recorded yet."

    if any(w in msg for w in ["safety", "incident", "accident"]):
        n = sum(1 for u in updates if "safety" in u.issue_type.lower())
        return f"⛑️ Safety incidents: **{n}**. {'Audit recommended.' if n > 0 else 'No incidents — compliant.'}"

    if any(w in msg for w in ["tbm", "tunnel", "boring"]):
        au  = [u for u in updates if "tbm" in u.work_type.lower() or "tunnel" in u.work_type.lower()]
        adv = sum(u.quantity_done for u in au)
        return f"🚇 TBM: **{len(au)}** updates, **{round(adv,1)}m** total advance."

    if any(w in msg for w in ["summary", "overview", "status", "report"]):
        qty    = sum(u.quantity_done for u in updates)
        issues = sum(1 for u in updates if u.issue_type.lower() != "none")
        return (
            f"📋 **Site Summary**\n"
            f"• Activities: {len(activities)}\n"
            f"• Total updates: {len(updates)}\n"
            f"• Quantity recorded: {round(qty,1)} units\n"
            f"• Issues reported: {issues}"
        )

    return (
        "Ask me about:\n"
        "• **Risk** — 'What's the current risk status?'\n"
        "• **Progress** — 'Show progress summary'\n"
        "• **Downtime** — 'Equipment breakdown count'\n"
        "• **Workers** — 'List active workers'\n"
        "• **Safety** — 'Any safety incidents?'\n"
        "• **TBM** — 'TBM advance status'"
    )


@router.post("/api/chat")
async def chat(request: Request, db: Session = Depends(get_db)):
    body       = await request.json()
    user_msg   = body.get("message", "").strip()
    user_id    = body.get("user_id")
    session_id = body.get("session_id", "default")
    history    = body.get("history", [])

    if not user_msg:
        return JSONResponse({"reply": "Please type a message."})

    db.add(ChatLog(user_id=user_id, role="user",
                   message=user_msg, session_id=session_id))
    db.commit()

    site_context = build_site_context(db)
    api_messages = [
        {"role": t["role"], "content": t["content"]}
        for t in history[-8:]
    ]
    api_messages.append({"role": "user", "content": user_msg})

    key = get_groq_key()
    if key:
        try:
            reply = await call_groq(api_messages, site_context)
        except Exception as e:
            reply  = keyword_fallback(user_msg, db)
            reply += f"\n\n_(Groq unavailable: {str(e)[:60]})_"
    else:
        reply  = keyword_fallback(user_msg, db)
        reply += (
            "\n\n_ℹ️ Enable full AI free: get key at "
            "[console.groq.com](https://console.groq.com) → set `GROQ_API_KEY=gsk_...`_"
        )

    db.add(ChatLog(user_id=user_id, role="assistant",
                   message=reply, session_id=session_id))
    db.commit()
    return JSONResponse({"reply": reply})


@router.get("/api/chat-history")
def chat_history(user_id: int, limit: int = 20, db: Session = Depends(get_db)):
    logs = (
        db.query(ChatLog)
        .filter(ChatLog.user_id == user_id)
        .order_by(ChatLog.timestamp.desc())
        .limit(limit).all()
    )
    return [
        {"role": l.role, "message": l.message,
         "timestamp": l.timestamp.isoformat()}
        for l in reversed(logs)
    ]