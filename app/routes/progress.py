from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import date

from app.database.db import SessionLocal
from app.models.models import DailyProgress, Activity

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 🔹 Get all activities (for dropdown)
@router.get("/activities")
def get_activities(db: Session = Depends(get_db)):
    activities = db.query(Activity).all()
    return [
        {"id": a.id, "name": a.name}
        for a in activities
    ]

# 🔹 Add daily progress
@router.post("/add-progress")
def add_progress(
    activity_id: int = Form(...),
    actual_quantity: float = Form(...),
    labor_count: int = Form(...),
    issues: str = Form(""),
    db: Session = Depends(get_db)
):
    progress = DailyProgress(
        activity_id=activity_id,
        date=date.today(),
        actual_quantity=actual_quantity,
        labor_count=labor_count,
        issues=issues
    )
    db.add(progress)
    db.commit()

    return RedirectResponse("/dashboard", status_code=302)
