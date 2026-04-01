from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from app.dews.canary import seed_canaries
from app.routes.elis import router as elis_router

from app.database.db import engine, Base
from app.models import models

from app.routes import auth, worker, digital_twin, chatbot, dashboard, profile, alerts
from app.routes import analytics, shift_handover, nlp_parser

Base.metadata.create_all(bind=engine)
seed_canaries()

app = FastAPI(title="ConstructTwin", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static & Templates — uses app/ subfolder ─────────────────────────────────
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(worker.router)
app.include_router(digital_twin.router)
app.include_router(chatbot.router)
app.include_router(dashboard.router)
app.include_router(profile.router)
app.include_router(alerts.router)
app.include_router(analytics.router)
app.include_router(shift_handover.router)
app.include_router(nlp_parser.router)
app.include_router(elis_router)


# ── Page routes ───────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    return RedirectResponse("/login")

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request, error: str = ""):
    return templates.TemplateResponse("register.html", {"request": request, "error": error})

@app.get("/worker-dashboard", response_class=HTMLResponse)
def worker_dashboard(request: Request, user_id: int = 1):
    from app.database.db import SessionLocal
    db = SessionLocal()
    user       = db.query(models.User).filter(models.User.id == user_id).first()
    activities = db.query(models.Activity).all()
    db.close()
    return templates.TemplateResponse("worker_dashboard.html", {
        "request": request, "user": user, "activities": activities
    })

@app.get("/supervisor-dashboard", response_class=HTMLResponse)
def supervisor_dashboard(request: Request, user_id: int = 1):
    from app.database.db import SessionLocal
    db = SessionLocal()
    user = db.query(models.User).filter(models.User.id == user_id).first()
    db.close()
    return templates.TemplateResponse("supervisor_dashboard.html", {
        "request": request, "user": user
    })

@app.get("/update-work", response_class=HTMLResponse)
def update_work_page(request: Request, user_id: int = 1):
    from app.database.db import SessionLocal
    db = SessionLocal()
    user       = db.query(models.User).filter(models.User.id == user_id).first()
    activities = db.query(models.Activity).all()
    db.close()
    return templates.TemplateResponse("update_work.html", {
        "request": request, "user": user, "activities": activities
    })

@app.get("/monitor", response_class=HTMLResponse)
def monitor_page(request: Request, user_id: int = 1):
    from app.database.db import SessionLocal
    db = SessionLocal()
    user       = db.query(models.User).filter(models.User.id == user_id).first()
    activities = db.query(models.Activity).all()
    workers    = db.query(models.User).filter(models.User.role == "worker").all()
    db.close()
    return templates.TemplateResponse("monitor.html", {
        "request": request, "user": user,
        "activities": activities, "workers": workers
    })

@app.get("/digital-twin-page", response_class=HTMLResponse)
def twin_page(request: Request, user_id: int = 1):
    from app.database.db import SessionLocal
    db = SessionLocal()
    user       = db.query(models.User).filter(models.User.id == user_id).first()
    activities = db.query(models.Activity).all()
    db.close()
    return templates.TemplateResponse("digital_twin.html", {
        "request": request, "user": user, "activities": activities
    })

@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, user_id: int = 1):
    from app.database.db import SessionLocal
    db = SessionLocal()
    user    = db.query(models.User).filter(models.User.id == user_id).first()
    updates = db.query(models.WorkerUpdate).filter(
        models.WorkerUpdate.user_id == user_id
    ).order_by(models.WorkerUpdate.timestamp.desc()).all()
    db.close()
    return templates.TemplateResponse("profile.html", {
        "request": request, "user": user,
        "updates":      updates,
        "total_qty":    round(sum(u.quantity_done for u in updates), 2),
        "total_hrs":    round(sum(u.hours_worked  for u in updates), 1),
        "update_count": len(updates),
    })

@app.get("/logout")
def logout():
    return RedirectResponse("/login", status_code=302)

@app.get("/analytics", response_class=HTMLResponse)
def analytics_page(request: Request, user_id: int = 1):
    from app.database.db import SessionLocal
    db = SessionLocal()
    user       = db.query(models.User).filter(models.User.id == user_id).first()
    activities = db.query(models.Activity).all()
    db.close()
    return templates.TemplateResponse("analytics.html", {
        "request": request, "user": user, "activities": activities
    })

@app.get("/handover", response_class=HTMLResponse)
def handover_page(request: Request, user_id: int = 1):
    from app.database.db import SessionLocal
    db = SessionLocal()
    user       = db.query(models.User).filter(models.User.id == user_id).first()
    activities = db.query(models.Activity).all()
    db.close()
    return templates.TemplateResponse("handover.html", {
        "request": request, "user": user, "activities": activities
    })

@app.get("/smart-update", response_class=HTMLResponse)
def smart_update_page(request: Request, user_id: int = 1):
    from app.database.db import SessionLocal
    db = SessionLocal()
    user       = db.query(models.User).filter(models.User.id == user_id).first()
    activities = db.query(models.Activity).all()
    db.close()
    return templates.TemplateResponse("smart_update.html", {
        "request": request, "user": user, "activities": activities
    })

@app.get("/gantt", response_class=HTMLResponse)
def gantt_page(request: Request, user_id: int = 1):
    from app.database.db import SessionLocal
    db = SessionLocal()
    user = db.query(models.User).filter(models.User.id == user_id).first()
    db.close()
    return templates.TemplateResponse("gantt.html", {
        "request": request, "user": user
    })

@app.get("/command-center", response_class=HTMLResponse)
def command_center_page(request: Request, user_id: int = 1):
    from app.database.db import SessionLocal
    db = SessionLocal()
    user = db.query(models.User).filter(models.User.id == user_id).first()
    db.close()
    return templates.TemplateResponse("command_center.html", {
        "request": request, "user": user
    })
@app.get("/dews-dashboard", response_class=HTMLResponse)
def dews_dashboard(request: Request, user_id: int = 1):
    from app.database.db import SessionLocal
    db = SessionLocal()
    user = db.query(models.User).filter(models.User.id == user_id).first()
    db.close()
    return templates.TemplateResponse("dews_dashboard.html", {
        "request": request, "user": user
    })
@app.get("/elis", response_class=HTMLResponse)
def elis_dashboard(request: Request, user_id: int = 1):
    from app.database.db import SessionLocal
    db = SessionLocal()
    user = db.query(models.User).filter(models.User.id == user_id).first()
    db.close()
    return templates.TemplateResponse("elis_dashboard.html", {
        "request": request, "user": user
    })