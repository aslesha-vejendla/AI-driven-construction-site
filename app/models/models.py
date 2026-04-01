from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, DateTime, Boolean, Text, JSON
from datetime import datetime
from app.database.db import Base


class Project(Base):
    __tablename__ = "projects"

    id           = Column(Integer, primary_key=True, index=True)
    name         = Column(String)
    project_type = Column(String, default="Infrastructure")
    status       = Column(String, default="Active")
    start_date   = Column(Date)
    end_date     = Column(Date)


class Activity(Base):
    __tablename__ = "activities"

    id                    = Column(Integer, primary_key=True, index=True)
    project_id            = Column(Integer, ForeignKey("projects.id"))
    name                  = Column(String)
    activity_type         = Column(String, default="General")
    unit                  = Column(String, default="m")
    planned_quantity      = Column(Float)
    planned_days          = Column(Integer)
    planned_duration_days = Column(Integer)
    start_date            = Column(Date)
    end_date              = Column(Date)
    budget                = Column(Float, default=0)


class DailyProgress(Base):
    __tablename__ = "daily_progress"

    id              = Column(Integer, primary_key=True, index=True)
    activity_id     = Column(Integer, ForeignKey("activities.id"))
    date            = Column(Date)
    actual_quantity = Column(Float)
    labor_count     = Column(Integer)
    issues          = Column(String)


class WorkerUpdate(Base):
    __tablename__ = "worker_updates"

    id               = Column(Integer, primary_key=True, index=True)
    user_id          = Column(Integer, ForeignKey("users.id"), nullable=True)
    activity_id      = Column(Integer, ForeignKey("activities.id"))
    worker_name      = Column(String)
    work_type        = Column(String)
    work_description = Column(String)
    quantity_done    = Column(Float)
    quantity_unit    = Column(String)
    hours_worked     = Column(Float)
    crew_size        = Column(Integer, default=1)
    issue_type       = Column(String, default="None")
    weather_condition= Column(String, default="Clear")
    safety_ok        = Column(Boolean, default=True)
    timestamp        = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id           = Column(Integer, primary_key=True, index=True)
    name         = Column(String)
    email        = Column(String, unique=True, index=True)
    password     = Column(String)
    role         = Column(String)
    designation  = Column(String, default="")
    company      = Column(String, default="")
    phone        = Column(String, default="")
    avatar_color = Column(String, default="#F59E0B")


class RiskSnapshot(Base):
    __tablename__ = "risk_snapshots"

    id          = Column(Integer, primary_key=True, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id"))
    risk_score  = Column(Float)
    status      = Column(String)
    utilization = Column(Float, default=0)
    downtime    = Column(Integer, default=0)
    recorded_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id          = Column(Integer, primary_key=True, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id"), nullable=True)
    alert_type  = Column(String)
    severity    = Column(String)
    message     = Column(Text)
    is_read     = Column(Boolean, default=False)
    created_at  = Column(DateTime, default=datetime.utcnow)


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String)
    role       = Column(String)
    message    = Column(Text)
    timestamp  = Column(DateTime, default=datetime.utcnow)


class ShiftHandover(Base):
    __tablename__ = "shift_handovers"

    id               = Column(Integer, primary_key=True, index=True)
    activity_id      = Column(Integer, ForeignKey("activities.id"))
    outgoing_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    outgoing_name    = Column(String)
    shift            = Column(String)
    qty_completed    = Column(Float, default=0)
    unit             = Column(String, default="m")
    pending_tasks    = Column(Text)
    safety_notes     = Column(Text)
    equipment_status = Column(Text)
    issues_left      = Column(Text)
    priority_next    = Column(Text)
    ai_briefing      = Column(Text)
    timestamp        = Column(DateTime, default=datetime.utcnow)


class EarnedValue(Base):
    __tablename__ = "earned_value"

    id          = Column(Integer, primary_key=True, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id"))
    pv          = Column(Float, default=0)
    ev          = Column(Float, default=0)
    ac          = Column(Float, default=0)
    spi         = Column(Float, default=1)
    cpi         = Column(Float, default=1)
    recorded_at = Column(DateTime, default=datetime.utcnow)


class SiteHealthLog(Base):
    __tablename__ = "site_health_logs"

    id           = Column(Integer, primary_key=True, index=True)
    health_score = Column(Float)
    grade        = Column(String)
    components   = Column(Text)
    recorded_at  = Column(DateTime, default=datetime.utcnow)

# In models.py — add alongside your existing tables

class ELISEvent(Base):
    __tablename__ = "elis_events"

    id         = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, nullable=False)   # WATERMARK_APPLIED, CANARY_TRIGGERED etc.
    severity   = Column(String, nullable=False)   # INFO | WARNING | CRITICAL
    category   = Column(String, nullable=False)   # INTEGRITY | SECURITY | OPERATIONAL
    source     = Column(String, nullable=False)   # WORKER | SYSTEM | AI | IDS | CANARY
    worker_id  = Column(Integer, nullable=True)
    message    = Column(String, nullable=False)
    extra_data = Column(JSON, nullable=True)      # any extra fields
    ml_class   = Column(String, nullable=True)    # NORMAL | SUSPICIOUS | CRITICAL_BREACH
    ml_confidence = Column(Float, nullable=True)
    timestamp  = Column(DateTime, default=datetime.utcnow)