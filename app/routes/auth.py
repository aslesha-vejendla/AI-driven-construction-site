import random
from fastapi import APIRouter, Form, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from passlib.hash import bcrypt

from app.database.db import get_db
from app.models.models import User

router = APIRouter()

AVATAR_COLORS = ["#F59E0B","#3B82F6","#10B981","#8B5CF6","#EF4444","#06B6D4","#EC4899"]


@router.post("/login")
def login(
    email:    str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user:
        return RedirectResponse("/login?error=User+not+found", status_code=303)

    # Verify bcrypt hash
    try:
        pwd_ok = bcrypt.verify(password, user.password)
    except Exception:
        pwd_ok = False

    if not pwd_ok:
        return RedirectResponse("/login?error=Wrong+password", status_code=303)

    if user.role == "supervisor":
        return RedirectResponse(f"/supervisor-dashboard?user_id={user.id}", status_code=303)
    return RedirectResponse(f"/worker-dashboard?user_id={user.id}", status_code=303)


@router.post("/register")
def register(
    name:        str = Form(...),
    email:       str = Form(...),
    password:    str = Form(...),
    role:        str = Form(...),
    designation: str = Form(default=""),
    company:     str = Form(default=""),
    phone:       str = Form(default=""),
    db: Session = Depends(get_db)
):
    email = email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        return RedirectResponse("/register?error=Email+already+registered", status_code=303)

    user = User(
        name=name, email=email,
        password=bcrypt.hash(password),   # ← hash on register too
        role=role, designation=designation,
        company=company, phone=phone,
        avatar_color=random.choice(AVATAR_COLORS)
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if role == "supervisor":
        return RedirectResponse(f"/supervisor-dashboard?user_id={user.id}", status_code=303)
    return RedirectResponse(f"/worker-dashboard?user_id={user.id}", status_code=303)


@router.post("/profile/update")
def update_profile(
    user_id:     int = Form(...),
    name:        str = Form(...),
    designation: str = Form(default=""),
    phone:       str = Form(default=""),
    company:     str = Form(default=""),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.name        = name
        user.designation = designation
        user.phone       = phone
        user.company     = company
        db.commit()
    return RedirectResponse(f"/profile?user_id={user_id}&saved=1", status_code=303)