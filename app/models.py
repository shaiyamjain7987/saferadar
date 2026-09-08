from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db

class Site(db.Model):
    __tablename__ = "sites"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    
    users = db.relationship("User", back_populates="site", lazy="dynamic")
    reports = db.relationship("Report", back_populates="site", lazy="dynamic")

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'worker', 'site_head', 'admin'
    
    site_id = db.Column(db.Integer, db.ForeignKey("sites.id"), nullable=False)
    site = db.relationship("Site", back_populates="users")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    reports = db.relationship("Report", back_populates="worker", lazy="dynamic", foreign_keys="Report.worker_id")
    actions_assigned = db.relationship("CorrectiveAction", back_populates="assignee", lazy="dynamic", foreign_keys="CorrectiveAction.assigned_to")

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_worker(self):
        return self.role == "worker"

    @property
    def is_site_head(self):
        return self.role in ("site_head", "admin")

class Report(db.Model):
    __tablename__ = "reports"
    id = db.Column(db.Integer, primary_key=True)
    
    worker_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    worker = db.relationship("User", back_populates="reports", foreign_keys=[worker_id])
    
    site_id = db.Column(db.Integer, db.ForeignKey("sites.id"), nullable=False)
    site = db.relationship("Site", back_populates="reports")
    
    report_date = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    area = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False)
    original_language = db.Column(db.String(20), default="en")
    
    # Media
    image_filename = db.Column(db.String(255), nullable=True)
    audio_record_id = db.Column(db.Integer, db.ForeignKey("audio_records.id"), nullable=True)
    audio_record = db.relationship("AudioRecord", backref="report", uselist=False)
    
    # NLP outputs
    sif_potential = db.Column(db.Boolean, default=False, nullable=False)
    sif_score = db.Column(db.Integer, nullable=True)
    risk_level = db.Column(db.String(20), nullable=True)  # LOW, MEDIUM, HIGH
    explanation = db.Column(db.Text, nullable=True)
    
    activity = db.Column(db.String(100), nullable=True)
    hazard = db.Column(db.String(100), nullable=True)
    precursor = db.Column(db.String(100), nullable=True)
    barrier_failure = db.Column(db.String(100), nullable=True)
    life_saving_rule = db.Column(db.String(100), nullable=True)
    
    status = db.Column(db.String(20), default="Open") # Open, Under Investigation, Closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AudioRecord(db.Model):
    __tablename__ = "audio_records"
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    transcript = db.Column(db.Text, nullable=True)
    translated_text = db.Column(db.Text, nullable=True)
    language_detected = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CorrectiveAction(db.Model):
    __tablename__ = "corrective_actions"
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey("reports.id"), nullable=False)
    report = db.relationship("Report", backref="corrective_actions")
    
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    assignee = db.relationship("User", back_populates="actions_assigned", foreign_keys=[assigned_to])
    
    description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), nullable=False) # Low, Medium, High
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default="Open") # Open, In Progress, Completed
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Alert(db.Model):
    __tablename__ = "alerts"
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey("sites.id"), nullable=False)
    site = db.relationship("Site", backref="alerts")
    
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    level = db.Column(db.String(20), nullable=False) # INFO, WARNING, CRITICAL
    is_acknowledged = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
