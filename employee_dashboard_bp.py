from flask import Blueprint, render_template, request, jsonify, abort, flash, session, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import json

# Create blueprint
employee_dashboard_bp = Blueprint('employee_dashboard', __name__, url_prefix='/employee', template_folder='templates/employee_dashboard')

# Global variables - set when blueprint is registered
db = None
User = None
EmployeeDashboard = None
EmpRole = None
AuditLog = None
UserSession = None

def create_employee_dashboard_models(database):
    global User, EmployeeDashboard, EmpRole, AuditLog, UserSession
    
    class EmpRole(database.Model):
        __tablename__ = 'emp_role'
        __table_args__ = {'extend_existing': True}
        id = database.Column(database.Integer, primary_key=True)
        name = database.Column(database.String(50), unique=True, nullable=False)  # owner, admin, employee, user
        description = database.Column(database.String(200))
        created_at = database.Column(database.DateTime, default=datetime.utcnow)

    class EmployeeDashboard(database.Model):
        __tablename__ = 'emp_dashboard_employee'
        __table_args__ = {'extend_existing': True}
        id = database.Column(database.Integer, primary_key=True)
        username = database.Column(database.String(80), unique=True, nullable=False)
        full_name = database.Column(database.String(100), nullable=False)
        password_hash = database.Column(database.String(255), nullable=False)
        role_id = database.Column(database.Integer, database.ForeignKey('emp_role.id'), nullable=False)
        is_active = database.Column(database.Boolean, default=True)
        can_login = database.Column(database.Boolean, default=True)
        last_login = database.Column(database.DateTime)
        created_at = database.Column(database.DateTime, default=datetime.utcnow)
        created_by = database.Column(database.String(80), default='admin')
        
        role = database.relationship('EmpRole', backref='employees')

    class AuditLog(database.Model):
        __tablename__ = 'emp_audit_log'
        __table_args__ = {'extend_existing': True}
        id = database.Column(database.Integer, primary_key=True)
        actor_id = database.Column(database.Integer, database.ForeignKey('emp_dashboard_employee.id'), nullable=False)
        action = database.Column(database.String(100), nullable=False)
        target_type = database.Column(database.String(50), nullable=False)
        target_id = database.Column(database.Integer, nullable=False)
        meta = database.Column(database.JSON)
        ip_address = database.Column(database.String(45))
        timestamp = database.Column(database.DateTime, default=datetime.utcnow)
        
        actor = database.relationship('EmployeeDashboard', backref='audit_logs')

    class UserSession(database.Model):
        __tablename__ = 'emp_user_session'
        __table_args__ = {'extend_existing': True}
        id = database.Column(database.Integer, primary_key=True)
        user_id = database.Column(database.Integer, database.ForeignKey('users.id'), nullable=False)
        session_token = database.Column(database.String(255), unique=True, nullable=False)
        ip_address = database.Column(database.String(45))
        user_agent = database.Column(database.String(500))
        is_active = database.Column(database.Boolean, default=True)
        created_at = database.Column(database.DateTime, default=datetime.utcnow)
        last_activity = database.Column(database.DateTime, default=datetime.utcnow)
    
    # Get existing User model from the database registry
    try:
        # Access User model from the database registry to avoid circular imports
        User = database.Model.registry._class_registry.get('User')
    except:
        User = None
    
    return User, EmployeeDashboard, EmpRole, AuditLog, UserSession

# Rate limiting storage (in production, use Redis)
rate_limit_store = {}

def check_rate_limit(employee_id, action, limit=30, window=60):
    """Check if employee has exceeded rate limit"""
    now = datetime.utcnow()
    key = f"{employee_id}:{action}"
    
    if key not in rate_limit_store:
        rate_limit_store[key] = []
    
    # Clean old entries
    rate_limit_store[key] = [
        timestamp for timestamp in rate_limit_store[key]
        if now - timestamp < timedelta(seconds=window)
    ]
    
    if len(rate_limit_store[key]) >= limit:
        return False
    
    rate_limit_store[key].append(now)
    return True

def require_employee_role(*roles):
    """Decorator to check employee role permissions"""
    def wrapper(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not session.get('employee_logged_in'):
                return redirect(url_for('employee_dashboard.employee_login'))
            
            employee_id = session.get('employee_id')
            if EmployeeDashboard:
                employee = EmployeeDashboard.query.get(employee_id)
                if not employee or not employee.is_active or not employee.can_login:
                    flash('Account disabled', 'error')
                    return redirect(url_for('employee_dashboard.employee_login'))
                
                if employee.role.name not in roles:
                    flash('Insufficient permissions', 'error')
                    return redirect(url_for('employee_dashboard.dashboard'))
            
            return f(*args, **kwargs)
        return wrapped
    return wrapper

def log_audit(action, target_type, target_id, meta=None):
    """Log employee action to audit trail"""
    if not session.get('employee_id'):
        return
    
    audit = AuditLog(
        actor_id=session.get('employee_id'),
        action=action,
        target_type=target_type,
        target_id=target_id,
        meta=meta or {},
        ip_address=request.remote_addr
    )
    db.session.add(audit)
    db.session.commit()

# Authentication Routes
@employee_dashboard_bp.route('/login', methods=['GET', 'POST'])
def employee_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        employee = EmployeeDashboard.query.filter_by(username=username).first() if EmployeeDashboard else None
        
        if employee and employee.is_active and employee.can_login and \
           check_password_hash(employee.password_hash, password):
            
            session['employee_logged_in'] = True
            session['employee_id'] = employee.id
            session['employee_name'] = employee.full_name
            session['employee_role'] = employee.role.name
            
            employee.last_login = datetime.utcnow()
            db.session.commit()
            
            log_audit('employee_login', 'employee', employee.id)
            return redirect(url_for('employee_dashboard.dashboard'))
        else:
            flash('Invalid credentials or account disabled', 'error')
    
    return render_template('employee_login.html')

@employee_dashboard_bp.route('/logout')
def employee_logout():
    if session.get('employee_id'):
        log_audit('employee_logout', 'employee', session.get('employee_id'))
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('employee_dashboard.employee_login'))

# Dashboard Routes
@employee_dashboard_bp.route('/')
@require_employee_role('employee', 'admin', 'owner')
def dashboard():
    try:
        # Use direct SQL queries to get user counts
        from sqlalchemy import text
        
        # Get total users
        result = db.session.execute(text("SELECT COUNT(*) FROM user")).fetchone()
        total_users = result[0] if result else 0
        
        # Get active users (verified)
        result = db.session.execute(text("SELECT COUNT(*) FROM user WHERE verified = 1")).fetchone()
        active_users = result[0] if result else 0
        
        # Get inactive users
        inactive_users = total_users - active_users
        
        # Get recent users for display
        result = db.session.execute(
            text("SELECT id, email, name, verified, registered_on FROM user ORDER BY registered_on DESC LIMIT 10")
        )
        recent_users = []
        for row in result:
            user_dict = {
                'id': row[0],
                'email': row[1],
                'name': row[2],
                'verified': bool(row[3]),
                'registered_on': row[4]
            }
            recent_users.append(user_dict)
        
    except Exception as e:
        print(f"Error fetching user data: {e}")
        total_users = 0
        active_users = 0
        inactive_users = 0
        recent_users = []
    
    return render_template('employee_dashboard.html',
                         total_users=total_users,
                         active_users=active_users,
                         inactive_users=inactive_users,
                         recent_users=recent_users)

@employee_dashboard_bp.route('/users')
@require_employee_role('employee', 'admin', 'owner')
def users_list():
    try:
        from sqlalchemy import text
        search = request.args.get('q', '')
        
        if search:
            result = db.session.execute(
                text("SELECT id, email, name, verified, subscription_active, registered_on FROM user WHERE email LIKE :search ORDER BY registered_on DESC"),
                {'search': f'%{search}%'}
            )
        else:
            result = db.session.execute(
                text("SELECT id, email, name, verified, subscription_active, registered_on FROM user ORDER BY registered_on DESC")
            )
        
        users = []
        for row in result:
            user_dict = {
                'id': row[0],
                'email': row[1],
                'name': row[2],
                'verified': bool(row[3]),
                'subscription_active': bool(row[4]),
                'registered_on': row[5]
            }
            users.append(user_dict)
            
    except Exception as e:
        print(f"Error fetching users: {e}")
        users = []
    
    return render_template('employee_users_simple.html', users=users, search=search)

@employee_dashboard_bp.route('/manage/<int:user_id>')
@require_employee_role('employee', 'admin', 'owner')
def manage_user(user_id):
    return redirect(url_for('employee_dashboard.user_detail', user_id=user_id))

@employee_dashboard_bp.route('/user/<int:user_id>')
@require_employee_role('employee', 'admin', 'owner')
def user_detail(user_id):
    try:
        from sqlalchemy import text
        
        # Get user details
        result = db.session.execute(
            text("SELECT id, email, name, verified, subscription_active, registered_on FROM user WHERE id = :user_id"),
            {'user_id': user_id}
        ).fetchone()
        
        if not result:
            abort(404)
        
        user = {
            'id': result[0],
            'email': result[1],
            'name': result[2],
            'verified': bool(result[3]),
            'subscription_active': bool(result[4]),
            'registered_on': result[5]
        }
        
        # Get user sessions if UserSession table exists
        sessions = []
        try:
            session_result = db.session.execute(
                text("SELECT session_token, ip_address, user_agent, is_active, created_at, last_activity FROM emp_user_session WHERE user_id = :user_id ORDER BY last_activity DESC LIMIT 5"),
                {'user_id': user_id}
            )
            for row in session_result:
                session_dict = {
                    'session_token': row[0],
                    'ip_address': row[1],
                    'user_agent': row[2],
                    'is_active': bool(row[3]),
                    'created_at': row[4],
                    'last_activity': row[5]
                }
                sessions.append(session_dict)
        except:
            sessions = []
        
    except Exception as e:
        print(f"Error fetching user details: {e}")
        abort(404)
    
    return render_template('employee_user_detail.html', user=user, sessions=sessions)

# AJAX API Routes
@employee_dashboard_bp.route('/api/user/<int:user_id>/toggle', methods=['POST'])
@require_employee_role('employee', 'admin', 'owner')
def api_toggle_user(user_id):
    try:
        from sqlalchemy import text
        
        # Get current user status
        result = db.session.execute(
            text("SELECT verified, email FROM user WHERE id = :user_id"), 
            {'user_id': user_id}
        ).fetchone()
        
        if not result:
            return jsonify({'error': 'User not found'}), 404
        
        current_verified = bool(result[0])
        email = result[1]
        new_verified = not current_verified
        
        # Update user status
        db.session.execute(
            text("UPDATE user SET verified = :verified WHERE id = :user_id"),
            {'verified': new_verified, 'user_id': user_id}
        )
        db.session.commit()
        
        return jsonify({
            'success': True,
            'is_active': new_verified,
            'message': f'User {email} {"activated" if new_verified else "deactivated"}'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@employee_dashboard_bp.route('/api/user/<int:user_id>/disable-login', methods=['POST'])
@require_employee_role('employee', 'admin', 'owner')
def api_disable_login(user_id):
    if not check_rate_limit(session.get('employee_id'), 'disable_login'):
        return jsonify({'error': 'Rate limit exceeded'}), 429
    
    try:
        from sqlalchemy import text
        
        # Get user email for logging
        result = db.session.execute(
            text("SELECT email FROM user WHERE id = :user_id"),
            {'user_id': user_id}
        ).fetchone()
        
        if not result:
            return jsonify({'error': 'User not found'}), 404
        
        user_email = result[0]
        
        # Disable user login by setting verified to False
        db.session.execute(
            text("UPDATE user SET verified = 0 WHERE id = :user_id"),
            {'user_id': user_id}
        )
        db.session.commit()
        
        log_audit('disable_user_login', 'user', user_id, {
            'user_email': user_email
        })
        
        return jsonify({
            'success': True,
            'message': 'User login disabled'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@employee_dashboard_bp.route('/sessions')
@require_employee_role('employee', 'admin', 'owner')
def active_sessions():
    try:
        from sqlalchemy import text
        result = db.session.execute(
            text("SELECT session_token, user_id, ip_address, user_agent, is_active, created_at, last_activity FROM emp_user_session WHERE is_active = 1 ORDER BY last_activity DESC")
        )
        sessions = []
        for row in result:
            session_dict = {
                'session_token': row[0],
                'user_id': row[1],
                'ip_address': row[2],
                'user_agent': row[3],
                'is_active': bool(row[4]),
                'created_at': row[5],
                'last_activity': row[6]
            }
            sessions.append(session_dict)
    except Exception as e:
        print(f"Error fetching sessions: {e}")
        sessions = []
    
    return render_template('employee_sessions.html', sessions=sessions)

@employee_dashboard_bp.route('/audit')
@require_employee_role('admin', 'owner')  # Only admin and owner can view full audit
def audit_log():
    try:
        from sqlalchemy import text
        page = request.args.get('page', 1, type=int)
        actor_filter = request.args.get('actor', '')
        action_filter = request.args.get('action', '')
        per_page = 50
        offset = (page - 1) * per_page
        
        # Build query with filters
        where_conditions = []
        params = {'limit': per_page, 'offset': offset}
        
        if actor_filter:
            where_conditions.append("e.full_name LIKE :actor_filter")
            params['actor_filter'] = f'%{actor_filter}%'
        
        if action_filter:
            where_conditions.append("a.action LIKE :action_filter")
            params['action_filter'] = f'%{action_filter}%'
        
        where_clause = ' AND '.join(where_conditions)
        if where_clause:
            where_clause = 'WHERE ' + where_clause
        
        # Get audit logs
        query = f"""
            SELECT a.id, a.actor_id, a.action, a.target_type, a.target_id, a.meta, a.ip_address, a.timestamp, e.full_name
            FROM emp_audit_log a
            LEFT JOIN emp_dashboard_employee e ON a.actor_id = e.id
            {where_clause}
            ORDER BY a.timestamp DESC
            LIMIT :limit OFFSET :offset
        """
        
        result = db.session.execute(text(query), params)
        audits = []
        for row in result:
            audit_dict = {
                'id': row[0],
                'actor_id': row[1],
                'action': row[2],
                'target_type': row[3],
                'target_id': row[4],
                'meta': row[5],
                'ip_address': row[6],
                'timestamp': row[7],
                'actor_name': row[8]
            }
            audits.append(audit_dict)
        
        # Get total count for pagination
        count_query = f"""
            SELECT COUNT(*)
            FROM emp_audit_log a
            LEFT JOIN emp_dashboard_employee e ON a.actor_id = e.id
            {where_clause}
        """
        total = db.session.execute(text(count_query), {k: v for k, v in params.items() if k not in ['limit', 'offset']}).fetchone()[0]
        
        # Create pagination object-like structure
        class PaginationMock:
            def __init__(self, items, page, per_page, total):
                self.items = items
                self.page = page
                self.per_page = per_page
                self.total = total
                self.pages = (total + per_page - 1) // per_page
                self.has_prev = page > 1
                self.has_next = page < self.pages
                self.prev_num = page - 1 if self.has_prev else None
                self.next_num = page + 1 if self.has_next else None
        
        audits_paginated = PaginationMock(audits, page, per_page, total)
        
    except Exception as e:
        print(f"Error fetching audit logs: {e}")
        audits_paginated = None
    
    return render_template('employee_audit.html', audits=audits_paginated, actor_filter=actor_filter, action_filter=action_filter)

def init_employee_dashboard_db(app_db):
    """Initialize employee dashboard database models"""
    global db, User, EmployeeDashboard, EmpRole, AuditLog, UserSession
    db = app_db
    User, EmployeeDashboard, EmpRole, AuditLog, UserSession = create_employee_dashboard_models(db)
    
    # Create tables (already in app context)
    db.create_all()
    
    # Create default roles if they don't exist
    if EmpRole.query.count() == 0:
        roles = [
            EmpRole(name='owner', description='System Owner - Full Access'),
            EmpRole(name='admin', description='Administrator - Manage Employees & Users'),
            EmpRole(name='employee', description='Employee - User Management Only'),
            EmpRole(name='user', description='Regular User')
        ]
        for role in roles:
            db.session.add(role)
        db.session.commit()
        print("Default roles created")