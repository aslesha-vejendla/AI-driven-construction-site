"""
seed.py — Run from project ROOT:
  cd D:\Construction_Digital_Twin
  python seed.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import date, datetime, timedelta
import random

from app.database.db import SessionLocal, engine, Base
from app.models.models import (
    Project, Activity, DailyProgress, WorkerUpdate,
    User, RiskSnapshot, Alert, EarnedValue, SiteHealthLog
)
from passlib.hash import bcrypt

# ── Wipe & recreate ───────────────────────────────────────────────────────────
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
db = SessionLocal()

print("🌱 Seeding ConstructTwin database...")

# ── Users ─────────────────────────────────────────────────────────────────────
users = [
    User(name="Rajesh Kumar",  email="rajesh@ctwin.in", password=bcrypt.hash("pass123"),
         role="supervisor", designation="Project Manager",   company="L&T Construction",
         phone="+91 98200 11111", avatar_color="#F5A623"),
    User(name="Amit Sharma",   email="amit@ctwin.in",   password=bcrypt.hash("pass123"),
         role="supervisor", designation="Site Engineer",     company="L&T Construction",
         phone="+91 98200 22222", avatar_color="#3B82F6"),
    User(name="Ramesh Patil",  email="ramesh@ctwin.in", password=bcrypt.hash("pass123"),
         role="worker", designation="TBM Operator",          company="L&T Construction",
         phone="+91 98200 33333", avatar_color="#10B981"),
    User(name="Suresh Verma",  email="suresh@ctwin.in", password=bcrypt.hash("pass123"),
         role="worker", designation="Concrete Foreman",      company="Afcons Infrastructure",
         phone="+91 98200 44444", avatar_color="#8B5CF6"),
    User(name="Arjun Singh",   email="arjun@ctwin.in",  password=bcrypt.hash("pass123"),
         role="worker", designation="Rebar Fitter",          company="Afcons Infrastructure",
         phone="+91 98200 55555", avatar_color="#EF4444"),
    User(name="Priya Nair",    email="priya@ctwin.in",  password=bcrypt.hash("pass123"),
         role="worker", designation="Survey Engineer",       company="L&T Construction",
         phone="+91 98200 66666", avatar_color="#06B6D4"),
    User(name="Kiran Desai",   email="kiran@ctwin.in",  password=bcrypt.hash("pass123"),
         role="worker", designation="Safety Officer",        company="L&T Construction",
         phone="+91 98200 77777", avatar_color="#F59E0B"),
    User(name="Vijay Mehta",   email="vijay@ctwin.in",  password=bcrypt.hash("pass123"),
         role="worker", designation="Pile Rig Operator",     company="Tata Projects",
         phone="+91 98200 88888", avatar_color="#EC4899"),
]
db.add_all(users)
db.commit()
print(f"  ✓ {len(users)} users")

# ── Projects ──────────────────────────────────────────────────────────────────
projects = [
    Project(name="Mumbai Metro Line 3",          project_type="Metro Rail",
            status="Active",   start_date=date(2024,1,15), end_date=date(2026,12,31)),
    Project(name="Pune Ring Road Phase 2",        project_type="Highway",
            status="Active",   start_date=date(2024,3,1),  end_date=date(2026,8,30)),
    Project(name="Navi Mumbai Elevated Corridor", project_type="Elevated Road",
            status="On Hold",  start_date=date(2024,6,1),  end_date=date(2027,3,31)),
]
db.add_all(projects)
db.commit()
print(f"  ✓ {len(projects)} projects")

# ── Activities ────────────────────────────────────────────────────────────────
activities = [
    Activity(project_id=1, name="TBM Tunneling - East Drive",   activity_type="Tunneling",
             unit="m",  planned_quantity=2400,  planned_days=180, planned_duration_days=180,
             start_date=date(2024,1,15), end_date=date(2024,10,15), budget=85000000),
    Activity(project_id=1, name="Station Box Excavation - CST", activity_type="Excavation",
             unit="m3", planned_quantity=15000, planned_days=90,  planned_duration_days=90,
             start_date=date(2024,2,1),  end_date=date(2024,8,1),   budget=22000000),
    Activity(project_id=1, name="Concourse Slab Casting",       activity_type="Concrete",
             unit="m3", planned_quantity=8000,  planned_days=60,  planned_duration_days=60,
             start_date=date(2024,5,1),  end_date=date(2024,10,1),  budget=18000000),
    Activity(project_id=1, name="Rebar Fixing - Platform Level",activity_type="Rebar",
             unit="MT", planned_quantity=1200,  planned_days=45,  planned_duration_days=45,
             start_date=date(2024,6,1),  end_date=date(2024,9,15),  budget=9500000),
    Activity(project_id=2, name="Pile Foundation - Stretch A",  activity_type="Piling",
             unit="no", planned_quantity=320,   planned_days=75,  planned_duration_days=75,
             start_date=date(2024,3,1),  end_date=date(2024,8,15),  budget=32000000),
    Activity(project_id=2, name="Pier Cap Casting - Zone B",    activity_type="Concrete",
             unit="m3", planned_quantity=5500,  planned_days=50,  planned_duration_days=50,
             start_date=date(2024,5,15), end_date=date(2024,9,1),   budget=14000000),
    Activity(project_id=2, name="Precast Girder Launching",     activity_type="Structural",
             unit="no", planned_quantity=180,   planned_days=90,  planned_duration_days=90,
             start_date=date(2024,4,1),  end_date=date(2024,10,1),  budget=41000000),
    Activity(project_id=3, name="Soil Investigation & Survey",  activity_type="Survey",
             unit="km", planned_quantity=12,    planned_days=30,  planned_duration_days=30,
             start_date=date(2024,6,1),  end_date=date(2024,9,1),   budget=3500000),
]
db.add_all(activities)
db.commit()
print(f"  ✓ {len(activities)} activities")

# ── Worker Updates ────────────────────────────────────────────────────────────
worker_users = [u for u in users if u.role == "worker"]
issue_types  = ["None","None","None","Equipment Breakdown","Material Delay",
                "Weather","Labour Shortage","Safety Concern"]
work_types   = ["TBM Advance","Excavation","Concrete Pouring","Rebar Fixing",
                "Pile Boring","Shuttering","Survey","Inspection"]
weathers     = ["Clear","Clear","Cloudy","Rain","Extreme Heat","Fog"]
today        = date.today()
updates_list = []

for act in activities[:6]:
    for day_offset in range(60, 0, -1):
        work_date = today - timedelta(days=day_offset)
        if work_date.weekday() == 6:
            continue
        for wu in random.sample(worker_users, random.randint(1, min(3, len(worker_users)))):
            qty   = round(random.uniform(0.5, act.planned_quantity / act.planned_days * 1.3), 2)
            hours = round(random.uniform(5.5, 10.5), 1)
            issue = random.choice(issue_types)
            updates_list.append(WorkerUpdate(
                user_id          = wu.id,
                activity_id      = act.id,
                worker_name      = wu.name,
                work_type        = random.choice(work_types),
                work_description = f"{wu.designation} on {act.name}",
                quantity_done    = qty,
                quantity_unit    = act.unit,
                hours_worked     = hours,
                crew_size        = random.randint(4, 18),
                issue_type       = issue,
                weather_condition= random.choice(weathers),
                safety_ok        = (issue == "None"),
                timestamp        = datetime.combine(work_date, datetime.min.time())
                                   + timedelta(hours=random.randint(7, 16)),
            ))

db.add_all(updates_list)
db.commit()
print(f"  ✓ {len(updates_list)} worker updates")

# ── Daily Progress ────────────────────────────────────────────────────────────
dp_list = []
for act in activities[:6]:
    for day_offset in range(60, 0, -1):
        d = today - timedelta(days=day_offset)
        if d.weekday() == 6:
            continue
        dp_list.append(DailyProgress(
            activity_id     = act.id,
            date            = d,
            actual_quantity = round(random.uniform(
                act.planned_quantity / act.planned_days * 0.7,
                act.planned_quantity / act.planned_days * 1.2), 2),
            labor_count     = random.randint(8, 25),
            issues          = "" if random.random() > 0.2 else random.choice(
                ["Minor delay", "Material shortage", "Equipment issue"]),
        ))
db.add_all(dp_list)
db.commit()
print(f"  ✓ {len(dp_list)} daily progress records")

# ── Risk Snapshots ────────────────────────────────────────────────────────────
risk_list = []
for act in activities:
    for day_offset in range(14, 0, -1):
        score = random.randint(20, 85)
        risk_list.append(RiskSnapshot(
            activity_id = act.id,
            risk_score  = score,
            status      = "HIGH RISK" if score >= 65 else "MEDIUM RISK" if score >= 40 else "ON TRACK",
            utilization = round(random.uniform(55, 95), 1),
            downtime    = random.randint(0, 3),
            recorded_at = datetime.now() - timedelta(days=day_offset),
        ))
db.add_all(risk_list)
db.commit()
print(f"  ✓ {len(risk_list)} risk snapshots")

# ── Alerts ────────────────────────────────────────────────────────────────────
alerts_list = [
    Alert(activity_id=1, alert_type="Risk",     severity="high",
          message="TBM utilization dropped below 60% — check cutter head",
          is_read=False, created_at=datetime.now()-timedelta(hours=2)),
    Alert(activity_id=2, alert_type="Delay",    severity="medium",
          message="Excavation 12% behind plan — night shift labour shortage",
          is_read=False, created_at=datetime.now()-timedelta(hours=5)),
    Alert(activity_id=5, alert_type="Safety",   severity="high",
          message="Safety concern on Pile Foundation Stretch A",
          is_read=False, created_at=datetime.now()-timedelta(hours=1)),
    Alert(activity_id=3, alert_type="Material", severity="low",
          message="Cement stock below threshold — reorder within 3 days",
          is_read=True,  created_at=datetime.now()-timedelta(days=1)),
    Alert(activity_id=6, alert_type="Weather",  severity="medium",
          message="Heavy rain forecast 48h — secure Pier Cap formwork",
          is_read=False, created_at=datetime.now()-timedelta(hours=8)),
]
db.add_all(alerts_list)
db.commit()
print(f"  ✓ {len(alerts_list)} alerts")

# ── Earned Value ──────────────────────────────────────────────────────────────
ev_list = []
for act in activities[:6]:
    for day_offset in range(14, 0, -1):
        pv = round(random.uniform(0.4, 0.9), 3)
        ev = round(pv * random.uniform(0.75, 1.15), 3)
        ac = round(ev  * random.uniform(0.85, 1.20), 3)
        ev_list.append(EarnedValue(
            activity_id = act.id,
            pv=pv, ev=ev, ac=ac,
            spi = round(ev / pv, 3) if pv else 1.0,
            cpi = round(ev / ac, 3) if ac else 1.0,
            recorded_at = datetime.now() - timedelta(days=day_offset),
        ))
db.add_all(ev_list)
db.commit()
print(f"  ✓ {len(ev_list)} earned value records")

# ── Site Health Logs ──────────────────────────────────────────────────────────
health_list = []
for day_offset in range(14, 0, -1):
    score = random.randint(62, 91)
    health_list.append(SiteHealthLog(
        health_score = score,
        grade        = "A" if score >= 85 else "B" if score >= 70 else "C",
        components   = '{"safety":90,"progress":75,"quality":82,"equipment":68}',
        recorded_at  = datetime.now() - timedelta(days=day_offset),
    ))
db.add_all(health_list)
db.commit()
print(f"  ✓ {len(health_list)} site health logs")

db.close()
print("\n✅ Seeding complete!")
print("─────────────────────────────────")
print("  Supervisor → rajesh@ctwin.in / pass123")
print("  Worker     → ramesh@ctwin.in / pass123")
print("─────────────────────────────────")
print("  Next: uvicorn main:app --reload")