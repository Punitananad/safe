from flask import Blueprint
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Create a minimal employee blueprint to satisfy the import
employee_bp = Blueprint('employee', __name__)

# Global variables for models
EmployeeDashboard = None
EmpRole = None
AuditLog = None

def create_employee_models(database):
    """Create employee models for PostgreSQL compatibility"""
    global EmployeeDashboard, EmpRole, AuditLog
    
    class EmpRole(database.Model):
        __tablename__ = 'emp_role'
        id = database.Column(database.Integer, primary_key=True)
        name = database.Column(database.String(50), unique=True, nullable=False)
        description = database.Column(database.Text)
        created_at = database.Column(database.DateTime, default=datetime.utcnow)
    
    class EmployeeDashboard(database.Model):
        __tablename__ = 'employee_dashboard'
        id = database.Column(database.Integer, primary_key=True)
        username = database.Column(database.String(80), unique=True, nullable=False)
        full_name = database.Column(database.String(120), nullable=False)
        password_hash = database.Column(database.String(128), nullable=False)
        role_id = database.Column(database.Integer, database.ForeignKey('emp_role.id'), nullable=False)
        is_active = database.Column(database.Boolean, default=True)
        can_login = database.Column(database.Boolean, default=True)
        created_by = database.Column(database.String(80), nullable=False)
        created_at = database.Column(database.DateTime, default=datetime.utcnow)
        
        role = database.relationship('EmpRole', backref='employees')
    
    class AuditLog(database.Model):
        __tablename__ = 'audit_log'
        id = database.Column(database.Integer, primary_key=True)
        actor_id = database.Column(database.Integer, database.ForeignKey('employee_dashboard.id'))
        action = database.Column(database.String(100), nullable=False)
        details = database.Column(database.Text)
        created_at = database.Column(database.DateTime, default=datetime.utcnow)
        
        actor = database.relationship('EmployeeDashboard', backref='audit_logs')
    
    return EmployeeDashboard, EmpRole, AuditLog

def init_employee_db(db):
    """Initialize employee database with PostgreSQL compatibility"""
    global EmployeeDashboard, EmpRole, AuditLog
    try:
        EmployeeDashboard, EmpRole, AuditLog = create_employee_models(db)
        db.create_all()
        
        # Create default employee role if it doesn't exist
        if not EmpRole.query.filter_by(name='employee').first():
            default_role = EmpRole(name='employee', description='Default employee role')
            db.session.add(default_role)
            db.session.commit()
        
        print("Employee database models created successfully")
    except Exception as e:
        print(f"Error creating employee models: {e}")

# Add a simple route to avoid empty blueprint
@employee_bp.route('/')
def employee_index():
    return "Employee Blueprint Loaded"