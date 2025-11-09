from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import os
import secrets
import hashlib
from datetime import timedelta

# Create blueprint
admin_bp = Blueprint('admin', __name__)

# Import db - will be set when blueprint is registered
db = None
AdminUser = None
Coupon = None
AdminOTP = None
MentorPayments = None

# Try to import db from main app if available
try:
    from journal import db as main_db
    if main_db is not None:
        db = main_db
except ImportError:
    pass

def ensure_db():
    """Ensure database is available"""
    global db
    if db is None:
        try:
            from journal import db as main_db
            db = main_db
        except ImportError:
            pass
    return db

# Models will be created when init_admin_db is called
def create_models(database):
    global AdminUser, Coupon, AdminOTP, MentorPayments
    
    class AdminUser(database.Model):
        __tablename__ = 'admin_user'
        id = database.Column(database.Integer, primary_key=True)
        username = database.Column(database.String(80), unique=True, nullable=False)
        password_hash = database.Column(database.String(120), nullable=False)
        role = database.Column(database.String(20), nullable=False, default='admin')
        created_at = database.Column(database.DateTime, default=datetime.utcnow)

    class Coupon(database.Model):
        __tablename__ = 'coupon'
        id = database.Column(database.Integer, primary_key=True)
        code = database.Column(database.String(50), unique=True, nullable=False)
        discount_percent = database.Column(database.Integer, nullable=False)
        created_by = database.Column(database.String(80), nullable=False)
        active = database.Column(database.Boolean, default=True)
        mentor_id = database.Column(database.Integer, nullable=True)  # For mentor assignment
        created_at = database.Column(database.DateTime, default=datetime.utcnow)
    
    class AdminOTP(database.Model):
        __tablename__ = 'admin_otp'
        id = database.Column(database.Integer, primary_key=True)
        otp_hash = database.Column(database.String(128), nullable=False)
        salt = database.Column(database.String(64), nullable=False)
        expires_at = database.Column(database.DateTime, nullable=False)
        used = database.Column(database.Boolean, default=False)
        created_at = database.Column(database.DateTime, default=datetime.utcnow)
    
    class MentorPayments(database.Model):
        __tablename__ = 'mentor_payments'
        id = database.Column(database.Integer, primary_key=True)
        mentor_id = database.Column(database.Integer, nullable=False)
        amount = database.Column(database.Integer, nullable=False)  # Amount in paise
        payment_date = database.Column(database.DateTime, nullable=False)
        payment_method = database.Column(database.String(50), nullable=False, default='Manual')
        reference_number = database.Column(database.String(100), nullable=True)
        period_start = database.Column(database.Date, nullable=True)
        period_end = database.Column(database.Date, nullable=True)
        commission_count = database.Column(database.Integer, nullable=False, default=0)
        notes = database.Column(database.Text, nullable=True)
        paid_by = database.Column(database.String(80), nullable=False)
        created_at = database.Column(database.DateTime, default=datetime.utcnow)
    
    return AdminUser, Coupon, AdminOTP, MentorPayments

def init_admin_db(app_db):
    """Initialize admin database with PostgreSQL"""
    global db, AdminUser, Coupon, AdminOTP, MentorPayments
    db = app_db
    try:
        AdminUser, Coupon, AdminOTP, MentorPayments = create_models(db)
        db.create_all()
        print("Admin PostgreSQL database models created successfully")
    except Exception as e:
        print(f"Error creating admin models: {e}")

# Admin credentials
ADMIN_PASSWORD = "welcometocnt"
ADMIN_EMAIL = "punitanand571@gmail.com"

# Centralized mentor functions for PostgreSQL compatibility
def get_mentor_count():
    """Get total mentor count using PostgreSQL-compatible query"""
    try:
        from sqlalchemy import text
        result = db.session.execute(text("SELECT COUNT(*) FROM mentor")).fetchone()
        return result[0] if result else 0
    except Exception as e:
        print(f"Error getting mentor count: {e}")
        return 0

def get_all_mentors_with_stats():
    """Get all mentors with statistics using PostgreSQL-compatible queries"""
    try:
        from sqlalchemy import text
        mentors_data = db.session.execute(
            text("""
                SELECT m.id, m.mentor_id, m.name, m.email, m.active, m.created_at,
                       COALESCE(m.commission_pct, 40.0) as commission_pct,
                       COUNT(DISTINCT cu.id) as total_usage,
                       COUNT(DISTINCT cu.user_id) as student_count,
                       COALESCE(SUM(cu.commission_amount), 0) as total_commission
                FROM mentor m
                LEFT JOIN coupon_usage cu ON m.id = cu.mentor_id
                GROUP BY m.id, m.mentor_id, m.name, m.email, m.active, m.created_at, m.commission_pct
                ORDER BY m.created_at DESC
            """)
        ).fetchall()
        
        mentors = []
        for row in mentors_data:
            mentors.append({
                'id': row[0],
                'mentor_id': row[1],
                'name': row[2],
                'email': row[3],
                'active': row[4],
                'created_at': row[5],
                'commission_pct': row[6],
                'total_usage': row[7],
                'student_count': row[8],
                'total_commission': row[9],
                'commission_owed': row[9]  # Same as total_commission for template compatibility
            })
        
        return mentors
    except Exception as e:
        print(f"Error getting mentors with stats: {e}")
        return []

# Decorators
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@admin_bp.route('/')
def admin_root():
    """Root admin route - redirect to login if not authenticated, dashboard if authenticated"""
    if session.get('admin_logged_in'):
        return redirect(url_for('admin.dashboard'))
    else:
        return redirect(url_for('admin.login'))

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    try:
        # Ensure db is available
        ensure_db()
        
        # Simple count query to avoid model conflicts
        from sqlalchemy import text
        result = db.session.execute(text("SELECT COUNT(*) FROM users")).fetchone()
        user_count = result[0] if result else 0
        users = []  # Don't load all users for dashboard, just count
        print(f"Dashboard: Found {user_count} users")
    except Exception as e:
        print(f"Error fetching user count in dashboard: {e}")
        users = []
        user_count = 0
    
    try:
        import employee_dashboard_bp
        if hasattr(employee_dashboard_bp, 'EmployeeDashboard') and employee_dashboard_bp.EmployeeDashboard:
            employees = employee_dashboard_bp.EmployeeDashboard.query.all()
            employee_count = len(employees)
        else:
            employees = []
            employee_count = 0
    except:
        employees = []
        employee_count = 0
    
    # Use centralized mentor count function
    mentor_count = get_mentor_count()
    mentors = []  # Don't load all mentors for dashboard, just count
    
    try:
        # Use direct SQL query to avoid model conflicts
        from sqlalchemy import text
        result = db.session.execute(text("SELECT COUNT(*) FROM coupon")).fetchone()
        coupon_count = result[0] if result else 0
        coupons = []
    except Exception as e:
        print(f"Error fetching coupon count: {e}")
        coupons = []
        coupon_count = 0
    # Get admin count with proper model initialization
    try:
        if not AdminUser:
            AdminUser, Coupon, AdminOTP, MentorPayments = create_models(db)
        admin_count = AdminUser.query.count() if AdminUser else 0
    except Exception as e:
        print(f"Error getting admin count: {e}")
        admin_count = 0
    
    # Get subscription stats
    try:
        from subscription_models import get_subscription_stats
        subscription_stats = get_subscription_stats()
    except Exception as e:
        print(f"Error fetching subscription stats: {e}")
        subscription_stats = {'total_active': 0}
    
    return render_template('admin/dashboard.html', 
                         users=users,
                         employees=employees,
                         mentors=mentors,
                         coupons=coupons,
                         user_count=user_count,
                         employee_count=employee_count,
                         mentor_count=mentor_count,
                         coupon_count=coupon_count,
                         admin_count=admin_count,
                         subscription_stats=subscription_stats)

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        
        if password == ADMIN_PASSWORD:
            # Send OTP to admin email
            send_admin_otp()
            session['admin_password_verified'] = True
            flash('OTP sent to admin email. Please check your email.')
            return redirect(url_for('admin.verify_otp'))
        else:
            flash('Invalid admin password')
    
    return render_template('admin/login.html')



@admin_bp.route('/coupons')
@admin_required
def coupons():
    """Display all coupons with PostgreSQL compatibility"""
    try:
        # Ensure db is available
        ensure_db()
        
        from sqlalchemy import text
        coupon_rows = db.session.execute(
            text("""
                SELECT c.id, c.code, c.discount_percent, c.active, c.created_at, c.created_by,
                       m.name as mentor_name, m.mentor_id
                FROM coupon c
                LEFT JOIN mentor m ON c.mentor_id = m.id
                ORDER BY c.created_at DESC
            """)
        ).fetchall()
        
        coupons_list = []
        for row in coupon_rows:
            # Handle datetime objects properly
            created_at = row[4]
            if created_at and hasattr(created_at, 'strftime'):
                created_at_str = created_at.strftime('%Y-%m-%d %H:%M')
            else:
                created_at_str = str(created_at) if created_at else None
            
            coupons_list.append({
                'id': row[0],
                'code': row[1],
                'discount_percent': row[2],
                'active': bool(row[3]) if row[3] is not None else False,
                'created_at': created_at_str,
                'created_by': row[5],
                'mentor_name': row[6],
                'mentor_id': row[7]
            })
        
    except Exception as e:
        print(f"Error fetching coupons: {e}")
        import traceback
        traceback.print_exc()
        coupons_list = []
    
    return render_template('admin/coupons.html', coupons=coupons_list)

@admin_bp.route('/create-coupon', methods=['GET', 'POST'])
@admin_required
def create_coupon():
    """Create new coupon with PostgreSQL compatibility"""
    if request.method == 'POST':
        try:
            # Ensure db is available
            ensure_db()
            
            code = request.form['code'].strip().upper()
            discount_percent = int(request.form['discount_percent'])
            mentor_id = request.form.get('mentor_id') or None
            
            # Check if coupon already exists
            from sqlalchemy import text
            existing = db.session.execute(
                text("SELECT id FROM coupon WHERE code = :code"),
                {'code': code}
            ).fetchone()
            
            if existing:
                flash('Coupon code already exists')
                mentors = get_mentors_for_select()
                return render_template('admin/create_coupon.html', mentors=mentors)
            
            # Create new coupon with mentor assignment
            db.session.execute(
                text("""
                    INSERT INTO coupon (code, discount_percent, created_by, active, mentor_id, created_at)
                    VALUES (:code, :discount_percent, :created_by, :active, :mentor_id, :created_at)
                """),
                {
                    'code': code,
                    'discount_percent': discount_percent,
                    'created_by': session.get('admin_username', 'admin'),
                    'active': True,
                    'mentor_id': mentor_id,
                    'created_at': datetime.utcnow()
                }
            )
            db.session.commit()
            
            flash(f'Coupon {code} created successfully with {discount_percent}% discount')
            return redirect(url_for('admin.coupons'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating coupon: {str(e)}')
    
    # Get mentors for the dropdown
    mentors = get_mentors_for_select()
    return render_template('admin/create_coupon.html', mentors=mentors)

@admin_bp.route('/users')
@admin_required
def users():
    """Display all users with PostgreSQL compatibility"""
    try:
        from sqlalchemy import text
        users_data = db.session.execute(
            text("""
                SELECT id, email, name, verified, subscription_active, 
                       subscription_expires, registered_on, coupon_code
                FROM users
                ORDER BY registered_on DESC
            """)
        ).fetchall()
        
        users_list = []
        for row in users_data:
            # Handle datetime objects properly
            subscription_expires = row[5]
            if subscription_expires and hasattr(subscription_expires, 'strftime'):
                subscription_expires_str = subscription_expires.strftime('%Y-%m-%d %H:%M')
            else:
                subscription_expires_str = str(subscription_expires) if subscription_expires else None
            
            registered_on = row[6]
            if registered_on and hasattr(registered_on, 'strftime'):
                registered_on_str = registered_on.strftime('%Y-%m-%d %H:%M')
            else:
                registered_on_str = str(registered_on) if registered_on else None
            
            users_list.append({
                'id': row[0],
                'email': row[1],
                'name': row[2],
                'verified': bool(row[3]) if row[3] is not None else False,
                'subscription_active': bool(row[4]) if row[4] is not None else False,
                'subscription_expires': subscription_expires_str,
                'registered_on': registered_on_str,
                'coupon_code': row[7]
            })
        
    except Exception as e:
        print(f"Error fetching users: {e}")
        import traceback
        traceback.print_exc()
        users_list = []
    
    return render_template('admin/users.html', users=users_list)

@admin_bp.route('/create-employee', methods=['GET', 'POST'])
@admin_required
def admin_create_employee():
    if request.method == 'POST':
        try:
            # Import employee dashboard blueprint
            import employee_dashboard_bp
            if hasattr(employee_dashboard_bp, 'EmployeeDashboard') and employee_dashboard_bp.EmployeeDashboard:
                username = request.form['username']
                password = request.form['password']
                full_name = request.form['full_name']
                
                existing = employee_dashboard_bp.EmployeeDashboard.query.filter_by(username=username).first()
                if existing:
                    flash('Employee username already exists')
                    return render_template('admin/admin_create_employee.html')
                
                # Get employee role (assuming role_id 3 is for employees)
                employee_role = employee_dashboard_bp.EmpRole.query.filter_by(name='employee').first()
                if not employee_role:
                    flash('Employee role not found')
                    return render_template('admin/admin_create_employee.html')
                
                employee = employee_dashboard_bp.EmployeeDashboard(
                    username=username,
                    full_name=full_name,
                    password_hash=generate_password_hash(password),
                    role_id=employee_role.id,
                    is_active=True,
                    can_login=True,
                    created_by='admin'
                )
                db.session.add(employee)
                db.session.commit()
                
                flash(f'Employee created: {username}')
                return redirect(url_for('admin.dashboard'))
            else:
                flash('Employee model not available')
        except Exception as e:
            flash(f'Error creating employee: {str(e)}')
    
    return render_template('admin/admin_create_employee.html')











@admin_bp.route('/coupons/<int:coupon_id>/toggle', methods=['POST'])
@admin_required
def toggle_coupon(coupon_id):
    try:
        # Get current coupon status
        from sqlalchemy import text
        result = db.session.execute(
            text("SELECT active, code FROM coupon WHERE id = :coupon_id"), {'coupon_id': coupon_id}
        ).fetchone()
        
        if result:
            current_active = bool(result[0])
            code = result[1]
            new_active = not current_active
            
            # Update coupon status
            from sqlalchemy import text
            db.session.execute(
                text("UPDATE coupon SET active = :active WHERE id = :coupon_id"), 
                {'active': new_active, 'coupon_id': coupon_id}
            )
            db.session.commit()
            
            status = "activated" if new_active else "deactivated"
            flash(f'Coupon {code} {status}')
        else:
            flash('Coupon not found')
    except Exception as e:
        flash(f'Error updating coupon: {str(e)}')
    
    return redirect(url_for('admin.coupons'))

@admin_bp.route('/coupons/<int:coupon_id>/delete', methods=['POST'])
@admin_required
def delete_coupon(coupon_id):
    try:
        from sqlalchemy import text
        
        # Get coupon info
        result = db.session.execute(
            text("SELECT active, code FROM coupon WHERE id = :coupon_id"), 
            {'coupon_id': coupon_id}
        ).fetchone()
        
        if not result:
            flash('Coupon not found')
            return redirect(url_for('admin.coupons'))
        
        active, code = result
        
        # Only allow deletion if coupon is inactive
        if active:
            flash('Cannot delete active coupon. Please deactivate first.')
            return redirect(url_for('admin.coupons'))
        
        # Delete coupon usage records first
        db.session.execute(
            text("DELETE FROM coupon_usage WHERE coupon_code = :code"),
            {'code': code}
        )
        
        # Delete the coupon
        db.session.execute(
            text("DELETE FROM coupon WHERE id = :coupon_id"),
            {'coupon_id': coupon_id}
        )
        
        db.session.commit()
        flash(f'Coupon {code} deleted successfully')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting coupon: {str(e)}')
    
    return redirect(url_for('admin.coupons'))

# Mentor Management Routes
@admin_bp.route('/mentors')
@admin_required
def mentors():
    # Use centralized mentor function
    all_mentors = get_all_mentors_with_stats()
    return render_template('admin/mentors.html', mentors=all_mentors)

@admin_bp.route('/create-mentor', methods=['GET', 'POST'])
@admin_required
def create_mentor():
    if request.method == 'POST':
        try:
            # Import mentor functions and check if db is initialized
            from mentor import generate_mentor_id, generate_mentor_password
            
            if not db:
                flash('Database not initialized. Please contact administrator.')
                return render_template('admin/create_mentor.html')
            
            # Import mentor model from mentor module
            import mentor
            if not hasattr(mentor, 'Mentor') or not mentor.Mentor:
                flash('Mentor model not available. Please contact administrator.')
                return render_template('admin/create_mentor.html')
            
            name = request.form['name'].strip()
            email = request.form['email'].strip()
            commission = float(request.form.get('commission', 40.0))
            
            # Generate unique mentor ID and password
            mentor_id = generate_mentor_id()
            password = generate_mentor_password()
            
            # Ensure commission_pct column exists
            try:
                from sqlalchemy import text
                # Test if column exists by trying to select it
                db.session.execute(text("SELECT commission_pct FROM mentor LIMIT 1"))
                print("commission_pct column exists")
            except Exception as e:
                print(f"commission_pct column issue: {e}")
                # Try to add the column
                try:
                    db.session.execute(text("ALTER TABLE mentor ADD COLUMN commission_pct REAL DEFAULT 40.0"))
                    db.session.commit()
                    print("Added commission_pct column to mentor table")
                except Exception as add_error:
                    print(f"Error adding commission_pct column: {add_error}")
                    db.session.rollback()
                    # Continue without the column for now
                    commission = 40.0  # Use default value
            
            # Try to create mentor with commission_pct
            try:
                new_mentor = mentor.Mentor(
                    mentor_id=mentor_id,
                    password_hash=generate_password_hash(password),
                    name=name,
                    email=email,
                    commission_pct=commission,
                    created_by_admin_id=1,  # Assuming admin ID 1
                    active=True
                )
                
                db.session.add(new_mentor)
                db.session.commit()
            except Exception as model_error:
                print(f"SQLAlchemy model error: {model_error}")
                db.session.rollback()
                
                # Fallback: Create mentor using raw SQL
                from sqlalchemy import text
                db.session.execute(
                    text("""
                        INSERT INTO mentor (mentor_id, password_hash, name, email, commission_pct, created_by_admin_id, active, created_at)
                        VALUES (:mentor_id, :password_hash, :name, :email, :commission_pct, :created_by_admin_id, :active, :created_at)
                    """),
                    {
                        'mentor_id': mentor_id,
                        'password_hash': generate_password_hash(password),
                        'name': name,
                        'email': email,
                        'commission_pct': commission,
                        'created_by_admin_id': 1,
                        'active': True,
                        'created_at': datetime.utcnow()
                    }
                )
                db.session.commit()
                print("Mentor created using raw SQL fallback")
            
            # Show generated credentials once
            flash(f'Mentor created successfully! Mentor ID: {mentor_id}, Password: {password}, Commission: {commission}% (Save this - it won\'t be shown again!)')
            return redirect(url_for('admin.mentors'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Final error creating mentor: {e}")
            flash(f'Error creating mentor: {str(e)}')
    
    return render_template('admin/create_mentor.html')

@admin_bp.route('/mentor/<int:mentor_id>/reset-password', methods=['POST'])
@admin_required
def reset_mentor_password(mentor_id):
    try:
        from mentor import generate_mentor_password
        import mentor
        
        if not hasattr(mentor, 'Mentor') or not mentor.Mentor:
            flash('Mentor model not available')
            return redirect(url_for('admin.mentors'))
        
        mentor_obj = mentor.Mentor.query.get_or_404(mentor_id)
        new_password = generate_mentor_password()
        mentor_obj.password_hash = generate_password_hash(new_password)
        
        db.session.commit()
        
        flash(f'Password reset for {mentor_obj.name}. New password: {new_password} (Save this - it won\'t be shown again!)')
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting password: {str(e)}')
    
    return redirect(url_for('admin.mentors'))

@admin_bp.route('/mentor/<int:mentor_id>/details')
@admin_required
def mentor_details(mentor_id):
    try:
        from sqlalchemy import text
        
        # Get mentor basic info
        mentor_info = db.session.execute(
            text("SELECT id, mentor_id, name, email, active, created_at, COALESCE(commission_pct, 40.0) as commission_pct FROM mentor WHERE id = :mentor_id"),
            {"mentor_id": mentor_id}
        ).fetchone()
        
        if not mentor_info:
            flash('Mentor not found')
            return redirect(url_for('admin.mentors'))
        
        print(f"[MENTOR_DETAILS] Found mentor: {mentor_info[2]} (ID: {mentor_info[0]})")
        
        # Get detailed analytics
        analytics = db.session.execute(
            text("""
                SELECT 
                    COUNT(DISTINCT cu.id) as total_usage,
                    COUNT(DISTINCT cu.user_id) as unique_students,
                    COALESCE(SUM(cu.commission_amount), 0) as total_commission,
                    COALESCE(SUM(cu.discount_amount), 0) as total_discount,
                    COUNT(DISTINCT c.id) as total_coupons,
                    COALESCE(MAX(m.commission_pct), 40.0) as avg_commission_pct
                FROM mentor m
                LEFT JOIN coupon_usage cu ON m.id = cu.mentor_id
                LEFT JOIN coupon c ON m.id = c.mentor_id
                WHERE m.id = :mentor_id
            """),
            {"mentor_id": mentor_id}
        ).fetchone()
        
        # Get assigned coupons (remove non-existent columns)
        coupons = db.session.execute(
            text("""
                SELECT c.code, c.discount_percent, 100 as max_uses, 0 as uses, c.active, c.created_at
                FROM coupon c
                WHERE c.mentor_id = :mentor_id
                ORDER BY c.created_at DESC
            """),
            {"mentor_id": mentor_id}
        ).fetchall()
        
        # Get recent students
        students = db.session.execute(
            text("""
                SELECT u.email, u.name, cu.coupon_code, cu.used_at, cu.commission_amount, cu.discount_amount
                FROM coupon_usage cu
                JOIN users u ON cu.user_id = u.id
                WHERE cu.mentor_id = :mentor_id
                ORDER BY cu.used_at DESC
                LIMIT 20
            """),
            {"mentor_id": mentor_id}
        ).fetchall()
        
        mentor_data = {
            'id': mentor_info[0],
            'mentor_id': mentor_info[1],
            'name': mentor_info[2],
            'email': mentor_info[3],
            'active': mentor_info[4],
            'created_at': mentor_info[5]
        }
        
        return render_template('admin/mentor_details_comprehensive.html', 
                             mentor=mentor_data, 
                             analytics=analytics, 
                             coupons=coupons, 
                             students=students)
        
    except Exception as e:
        flash(f'Error fetching mentor details: {str(e)}')
        return redirect(url_for('admin.mentors'))

@admin_bp.route('/mentor/<int:mentor_id>/toggle', methods=['POST'])
@admin_required
def toggle_mentor(mentor_id):
    try:
        import mentor
        
        if not hasattr(mentor, 'Mentor') or not mentor.Mentor:
            flash('Mentor model not available')
            return redirect(url_for('admin.mentors'))
        
        mentor_obj = mentor.Mentor.query.get_or_404(mentor_id)
        mentor_obj.active = not mentor_obj.active
        db.session.commit()
        
        status = "activated" if mentor_obj.active else "deactivated"
        flash(f'Mentor {mentor_obj.name} {status}')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating mentor: {str(e)}')
    
    return redirect(url_for('admin.mentors'))

@admin_bp.route('/mentor/<int:mentor_id>/delete', methods=['POST'])
@admin_required
def delete_mentor(mentor_id):
    try:
        import mentor
        
        if not hasattr(mentor, 'Mentor') or not mentor.Mentor:
            flash('Mentor model not available')
            return redirect(url_for('admin.mentors'))
        
        mentor_obj = mentor.Mentor.query.get_or_404(mentor_id)
        
        # Only allow deletion if mentor is inactive
        if mentor_obj.active:
            flash('Cannot delete active mentor. Please deactivate first.')
            return redirect(url_for('admin.mentors'))
        
        mentor_name = mentor_obj.name
        
        # Remove mentor assignment from coupons
        from sqlalchemy import text
        db.session.execute(
            text("UPDATE coupon SET mentor_id = NULL WHERE mentor_id = :mentor_id"),
            {"mentor_id": mentor_id}
        )
        
        # Delete the mentor
        db.session.delete(mentor_obj)
        db.session.commit()
        
        flash(f'Mentor {mentor_name} deleted successfully')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting mentor: {str(e)}')
    
    return redirect(url_for('admin.mentors'))

@admin_bp.route('/mentor/<int:mentor_id>/payments')
@admin_required
def mentor_payments(mentor_id):
    try:
        from sqlalchemy import text
        
        # Skip commission_paid column operations since it doesn't exist
        
        # Get mentor info
        mentor_info = db.session.execute(
            text("SELECT id, mentor_id, name, email FROM mentor WHERE id = :mentor_id"),
            {"mentor_id": mentor_id}
        ).fetchone()
        
        print(f"[MENTOR_PAYMENTS] Processing mentor ID: {mentor_id}")
        if mentor_info:
            print(f"[MENTOR_PAYMENTS] Found mentor: {mentor_info[2]}")
        else:
            print(f"[MENTOR_PAYMENTS] Mentor not found in database")
        
        if not mentor_info:
            flash('Mentor not found')
            return redirect(url_for('admin.mentors'))
        
        # Get current pending commission (all commissions since commission_paid column doesn't exist)
        pending_commission = db.session.execute(
            text("""
                SELECT 
                    COALESCE(SUM(cu.commission_amount), 0) as total_pending,
                    COUNT(cu.id) as usage_count
                FROM coupon_usage cu
                WHERE cu.mentor_id = :mentor_id
            """),
            {"mentor_id": mentor_id}
        ).fetchone()
        
        # Get payment history
        payment_history_raw = db.session.execute(
            text("""
                SELECT id, amount, payment_date, payment_method, reference_number,
                       period_start, period_end, commission_count, notes, paid_by
                FROM mentor_payments
                WHERE mentor_id = :mentor_id
                ORDER BY payment_date DESC
            """),
            {"mentor_id": mentor_id}
        ).fetchall()
        
        # Convert to proper format with datetime handling
        payment_history = []
        for row in payment_history_raw:
            payment_date = row[2]
            if isinstance(payment_date, str):
                try:
                    from datetime import datetime
                    payment_date = datetime.fromisoformat(payment_date.replace('Z', '+00:00'))
                except:
                    payment_date = None
            
            payment_history.append([
                row[0],  # id
                row[1],  # amount
                payment_date,  # payment_date (converted)
                row[3],  # payment_method
                row[4],  # reference_number
                row[5],  # period_start
                row[6],  # period_end
                row[7],  # commission_count
                row[8],  # notes
                row[9]   # paid_by
            ])
        
        # Get recent commissions (all since commission_paid column doesn't exist)
        unpaid_commissions_raw = db.session.execute(
            text("""
                SELECT u.email, cu.coupon_code, cu.used_at, cu.commission_amount, cu.discount_amount
                FROM coupon_usage cu
                JOIN users u ON cu.user_id = u.id
                WHERE cu.mentor_id = :mentor_id
                ORDER BY cu.used_at DESC
                LIMIT 20
            """),
            {"mentor_id": mentor_id}
        ).fetchall()
        
        # Convert to proper format with datetime handling
        unpaid_commissions = []
        for row in unpaid_commissions_raw:
            used_at = row[2]
            if isinstance(used_at, str):
                try:
                    from datetime import datetime
                    used_at = datetime.fromisoformat(used_at.replace('Z', '+00:00'))
                except:
                    used_at = None
            
            unpaid_commissions.append([
                row[0],  # email
                row[1],  # coupon_code
                used_at,  # used_at (converted)
                row[3],  # commission_amount
                row[4]   # discount_amount
            ])
        
        mentor_data = {
            'id': mentor_info[0],
            'mentor_id': mentor_info[1],
            'name': mentor_info[2],
            'email': mentor_info[3]
        }
        
        return render_template('admin/mentor_payments.html',
                             mentor=mentor_data,
                             pending_commission=pending_commission,
                             payment_history=payment_history,
                             unpaid_commissions=unpaid_commissions)
        
    except Exception as e:
        flash(f'Error fetching payment data: {str(e)}')
        return redirect(url_for('admin.mentors'))

@admin_bp.route('/mentor/<int:mentor_id>/make-payment', methods=['POST'])
@admin_required
def make_mentor_payment(mentor_id):
    try:
        from sqlalchemy import text
        from datetime import datetime
        
        # Get form data
        amount = int(float(request.form.get('amount', 0)) * 100)  # Convert to paise
        payment_method = request.form.get('payment_method', 'Manual')
        reference_number = request.form.get('reference_number', '')
        notes = request.form.get('notes', '')
        timeframe = request.form.get('timeframe', '')
        commission_count = int(request.form.get('commission_count', 0))
        payment_date_str = request.form.get('payment_date', '')
        
        # Validation
        if amount <= 0:
            flash('Invalid payment amount', 'error')
            return redirect(url_for('admin.mentor_payments', mentor_id=mentor_id))
        
        if not payment_method:
            flash('Payment method is required', 'error')
            return redirect(url_for('admin.mentor_payments', mentor_id=mentor_id))
        
        if not timeframe:
            flash('Payment period is required', 'error')
            return redirect(url_for('admin.mentor_payments', mentor_id=mentor_id))
        
        # Parse payment date
        payment_date = datetime.now()
        if payment_date_str:
            try:
                payment_date = datetime.fromisoformat(payment_date_str)
            except:
                pass  # Use current time if parsing fails
        
        # Build comprehensive notes
        payment_notes = []
        if timeframe:
            payment_notes.append(f"Period: {timeframe}")
        if commission_count > 0:
            payment_notes.append(f"Covers {commission_count} referrals")
        if notes:
            payment_notes.append(f"Notes: {notes}")
        
        final_notes = " | ".join(payment_notes)
        
        # Get mentor name for success message
        mentor_info = db.session.execute(
            text("SELECT name FROM mentor WHERE id = :mentor_id"),
            {"mentor_id": mentor_id}
        ).fetchone()
        mentor_name = mentor_info[0] if mentor_info else "Unknown"
        
        # Record payment with all fields
        db.session.execute(
            text("""
                INSERT INTO mentor_payments 
                (mentor_id, amount, payment_date, payment_method, reference_number, 
                 commission_count, notes, paid_by, created_at)
                VALUES (:mentor_id, :amount, :payment_date, :payment_method, :reference_number, 
                        :commission_count, :notes, :paid_by, :created_at)
            """),
            {
                "mentor_id": mentor_id,
                "amount": amount,
                "payment_date": payment_date,
                "payment_method": payment_method,
                "reference_number": reference_number,
                "commission_count": commission_count,
                "notes": final_notes,
                "paid_by": session.get('admin_username', 'admin'),
                "created_at": datetime.now()
            }
        )
        
        # Note: commission_paid column doesn't exist, so we can't mark commissions as paid
        # This functionality would need the commission_paid column to be added to the database
        
        db.session.commit()
        
        # Success message with details
        success_msg = f'Payment of ₹{amount/100:.2f} recorded successfully for {mentor_name}'
        if timeframe:
            success_msg += f' (Period: {timeframe})'
        if reference_number:
            success_msg += f' (Ref: {reference_number})'
        
        flash(success_msg, 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error recording payment: {str(e)}', 'error')
        import traceback
        print(f"Payment error: {traceback.format_exc()}")
    
    return redirect(url_for('admin.mentor_payments', mentor_id=mentor_id))

@admin_bp.route('/mentor/<int:mentor_id>/export-payments')
@admin_required
def export_mentor_payments(mentor_id):
    try:
        from sqlalchemy import text
        from flask import make_response
        import csv
        from io import StringIO
        
        # Get mentor info
        mentor_info = db.session.execute(
            text("SELECT mentor_id, name, email FROM mentor WHERE id = :mentor_id"),
            {"mentor_id": mentor_id}
        ).fetchone()
        
        if not mentor_info:
            flash('Mentor not found')
            return redirect(url_for('admin.mentors'))
        
        # Get all payment data
        payments = db.session.execute(
            text("""
                SELECT payment_date, amount, payment_method, reference_number,
                       commission_count, notes, paid_by
                FROM mentor_payments
                WHERE mentor_id = :mentor_id
                ORDER BY payment_date DESC
            """),
            {"mentor_id": mentor_id}
        ).fetchall()
        
        # Create CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['PAYMENT STATEMENT'])
        writer.writerow(['Mentor:', mentor_info[1]])
        writer.writerow(['Mentor ID:', mentor_info[0]])
        writer.writerow(['Email:', mentor_info[2]])
        writer.writerow(['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow([])
        
        # Payment data header
        writer.writerow(['Date', 'Amount (₹)', 'Method', 'Reference', 'Referrals', 'Notes', 'Paid By'])
        
        total_amount = 0
        for payment in payments:
            amount = (payment[1] or 0) / 100
            total_amount += amount
            payment_date = payment[0]
            if isinstance(payment_date, str):
                try:
                    payment_date = datetime.fromisoformat(payment_date.replace('Z', '+00:00'))
                    date_str = payment_date.strftime('%Y-%m-%d %H:%M')
                except:
                    date_str = payment_date
            elif payment_date:
                date_str = payment_date.strftime('%Y-%m-%d %H:%M')
            else:
                date_str = 'N/A'
                
            writer.writerow([
                date_str,
                f'{amount:.2f}',
                payment[2] or 'Manual',
                payment[3] or 'N/A',
                payment[4] or 0,
                payment[5] or '-',
                payment[6] or 'admin'
            ])
        
        writer.writerow([])
        writer.writerow(['TOTAL PAID:', f'₹{total_amount:.2f}'])
        
        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=payment_statement_{mentor_info[0]}.csv'
        
        return response
        
    except Exception as e:
        flash(f'Error exporting payments: {str(e)}')
        return redirect(url_for('admin.mentor_payments', mentor_id=mentor_id))

@admin_bp.route('/assign-coupon-to-mentor', methods=['GET', 'POST'])
@admin_required
def assign_coupon_to_mentor():
    if request.method == 'POST':
        try:
            coupon_id = request.form['coupon_id']
            mentor_id = request.form['mentor_id']
            
            # Get coupon and mentor info
            from sqlalchemy import text
            coupon_result = db.session.execute(
                text("SELECT code FROM coupon WHERE id = :coupon_id"), {'coupon_id': coupon_id}
            ).fetchone()
            
            mentor_result = db.session.execute(
                text("SELECT name FROM mentor WHERE id = :mentor_id"), {'mentor_id': mentor_id}
            ).fetchone()
            
            if coupon_result and mentor_result:
                # Update coupon with mentor_id
                from sqlalchemy import text
                db.session.execute(
                    text("UPDATE coupon SET mentor_id = :mentor_id WHERE id = :coupon_id"), 
                    {'mentor_id': mentor_id, 'coupon_id': coupon_id}
                )
                db.session.commit()
                
                flash(f'Coupon {coupon_result[0]} assigned to mentor {mentor_result[0]}')
                return redirect(url_for('admin.coupons'))
            else:
                flash('Coupon or mentor not found')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error assigning coupon: {str(e)}')
    
    try:
        # Get active mentors
        from sqlalchemy import text
        mentor_result = db.session.execute(
            text("SELECT id, name FROM mentor WHERE active = true")
        )
        mentors = [{'id': row[0], 'name': row[1]} for row in mentor_result]
        
        # Get unassigned active coupons
        coupon_result = db.session.execute(
            text("SELECT id, code FROM coupon WHERE active = true AND (mentor_id IS NULL OR mentor_id = '')")
        )
        coupons = [{'id': row[0], 'code': row[1]} for row in coupon_result]
        
    except Exception as e:
        print(f"Error fetching mentors/coupons: {e}")
        mentors = []
        coupons = []
    
    return render_template('admin/assign_coupon.html', mentors=mentors, coupons=coupons)

# Employee Management Routes
@admin_bp.route('/employees')
@admin_required
def employees():
    try:
        # Import the employee dashboard blueprint to get the EmployeeDashboard model
        import employee_dashboard_bp
        if hasattr(employee_dashboard_bp, 'EmployeeDashboard') and employee_dashboard_bp.EmployeeDashboard:
            all_employees = employee_dashboard_bp.EmployeeDashboard.query.order_by(employee_dashboard_bp.EmployeeDashboard.created_at.desc()).all()
        else:
            all_employees = []
    except Exception as e:
        print(f"Error fetching employees: {e}")
        all_employees = []
    return render_template('admin/employees.html', employees=all_employees)

@admin_bp.route('/employee/<int:employee_id>/toggle', methods=['POST'])
@admin_required
def toggle_employee(employee_id):
    try:
        import employee_dashboard_bp
        if hasattr(employee_dashboard_bp, 'EmployeeDashboard') and employee_dashboard_bp.EmployeeDashboard:
            employee = employee_dashboard_bp.EmployeeDashboard.query.get_or_404(employee_id)
            employee.is_active = not employee.is_active
            db.session.commit()
            status = 'active' if employee.is_active else 'inactive'
            flash(f'Employee {employee.username} {status}')
        else:
            flash('Employee model not available')
    except Exception as e:
        flash(f'Error updating employee: {str(e)}')
    
    return redirect(url_for('admin.employees'))

@admin_bp.route('/employee/<int:employee_id>/delete', methods=['POST'])
@admin_required
def delete_employee(employee_id):
    try:
        import employee_dashboard_bp
        if hasattr(employee_dashboard_bp, 'EmployeeDashboard') and employee_dashboard_bp.EmployeeDashboard:
            employee = employee_dashboard_bp.EmployeeDashboard.query.get_or_404(employee_id)
            username = employee.username
            
            # Delete related audit logs first to avoid foreign key constraint
            if hasattr(employee_dashboard_bp, 'AuditLog') and employee_dashboard_bp.AuditLog:
                employee_dashboard_bp.AuditLog.query.filter_by(actor_id=employee_id).delete()
            
            db.session.delete(employee)
            db.session.commit()
            flash(f'Employee {username} deleted successfully')
        else:
            flash('Employee model not available')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting employee: {str(e)}')
    
    return redirect(url_for('admin.employees'))

def send_admin_otp():
    """Send OTP to admin email using the same method as main app"""
    try:
        # Ensure database and models are available
        ensure_db()
        
        # Initialize models if not already done
        global AdminUser, Coupon, AdminOTP, MentorPayments
        if not AdminOTP:
            print("AdminOTP model not initialized, initializing now...")
            try:
                AdminUser, Coupon, AdminOTP, MentorPayments = create_models(db)
                print("AdminOTP model initialized successfully")
            except Exception as e:
                print(f"Failed to initialize AdminOTP model: {e}")
                return
            
        # Clear any existing unused OTPs
        try:
            AdminOTP.query.filter_by(used=False).delete()
            db.session.commit()
        except Exception as e:
            print(f"Error clearing existing OTPs: {e}")
            db.session.rollback()
        
        # Generate OTP
        otp = f"{secrets.randbelow(1_000_000):06d}"
        salt = os.urandom(16)
        otp_hash = hashlib.sha256(salt + otp.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(minutes=5)
        
        # Save OTP to database - ensure we're using the correct AdminOTP model
        admin_otp = AdminOTP(
            otp_hash=otp_hash,
            salt=salt.hex(),
            expires_at=expires_at
        )
        db.session.add(admin_otp)
        db.session.commit()
        
        # Import and use the exact same email setup as main app
        from flask_mail import Mail, Message
        from flask import current_app
        
        # Get mail instance from current app
        mail = Mail(current_app)
        
        subject = "Admin Login OTP - CalculatenTrade"
        html = f"""
        <h2>Admin Login OTP</h2>
        <p>Your OTP for admin login is:</p>
        <h1 style="color: #007bff; letter-spacing: 3px;">{otp}</h1>
        <p>This OTP will expire in 5 minutes.</p>
        <p>If you didn't request this, please ignore this email.</p>
        """
        
        # Create and send message using the same method as main app
        msg = Message(subject=subject, recipients=[ADMIN_EMAIL], html=html)
        mail.send(msg)
        print(f"Admin OTP sent to {ADMIN_EMAIL}: {otp}")
        
    except Exception as e:
        print(f"Error sending admin OTP: {e}")
        import traceback
        traceback.print_exc()

@admin_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if not session.get('admin_password_verified'):
        return redirect(url_for('admin.login'))
    
    if request.method == 'POST':
        otp_input = request.form['otp']
        
        # Ensure database and models are available
        ensure_db()
        
        # Initialize models if not already done
        global AdminUser, Coupon, AdminOTP, MentorPayments
        if not AdminOTP:
            print("AdminOTP model not initialized, initializing now...")
            try:
                AdminUser, Coupon, AdminOTP, MentorPayments = create_models(db)
                print("AdminOTP model initialized successfully")
            except Exception as e:
                print(f"Failed to initialize AdminOTP model: {e}")
                flash('System error. Please contact administrator.')
                return redirect(url_for('admin.login'))
        
        # Get latest unused OTP
        try:
            admin_otp = AdminOTP.query.filter_by(used=False).order_by(AdminOTP.id.desc()).first()
        except Exception as e:
            print(f"Error querying AdminOTP: {e}")
            flash('Database error. Please contact administrator.')
            return redirect(url_for('admin.login'))
        
        if not admin_otp:
            flash('No valid OTP found. Please request a new one.')
            return redirect(url_for('admin.login'))
        
        # Check if OTP is expired
        if datetime.utcnow() > admin_otp.expires_at:
            flash('OTP has expired. Please request a new one.')
            return redirect(url_for('admin.login'))
        
        # Verify OTP
        salt = bytes.fromhex(admin_otp.salt)
        otp_hash = hashlib.sha256(salt + otp_input.encode()).hexdigest()
        
        if otp_hash == admin_otp.otp_hash:
            # Mark OTP as used
            admin_otp.used = True
            db.session.commit()
            
            # Set admin session
            session['admin_logged_in'] = True
            session['admin_username'] = 'admin'
            session['admin_role'] = 'owner'
            session.pop('admin_password_verified', None)
            
            flash('Login successful!')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Invalid OTP. Please try again.')
    
    return render_template('admin/admin_verify_otp.html')

@admin_bp.route('/debug-mentors')
@admin_required
def debug_mentors():
    """Debug route to check mentor data consistency"""
    try:
        from sqlalchemy import text
        
        # Check if mentor table exists
        tables_result = db.session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='mentor'")
        ).fetchall()
        
        debug_info = {
            'mentor_table_exists': len(tables_result) > 0,
            'mentor_count': 0,
            'mentors': [],
            'coupon_usage_count': 0,
            'commission_paid_column_exists': False
        }
        
        if debug_info['mentor_table_exists']:
            # Get mentor count
            count_result = db.session.execute(text("SELECT COUNT(*) FROM mentor")).fetchone()
            debug_info['mentor_count'] = count_result[0] if count_result else 0
            
            # Get all mentors
            mentors_result = db.session.execute(
                text("SELECT id, mentor_id, name, email, active FROM mentor")
            ).fetchall()
            
            for row in mentors_result:
                debug_info['mentors'].append({
                    'id': row[0],
                    'mentor_id': row[1],
                    'name': row[2],
                    'email': row[3],
                    'active': bool(row[4])
                })
        
        # Check coupon_usage table
        try:
            usage_result = db.session.execute(text("SELECT COUNT(*) FROM coupon_usage")).fetchone()
            debug_info['coupon_usage_count'] = usage_result[0] if usage_result else 0
            
            # Check if commission_paid column exists
            db.session.execute(text("SELECT commission_paid FROM coupon_usage LIMIT 1"))
            debug_info['commission_paid_column_exists'] = True
        except:
            debug_info['commission_paid_column_exists'] = False
        
        return f"<pre>{str(debug_info)}</pre>"
        
    except Exception as e:
        return f"<pre>Error: {str(e)}</pre>"

@admin_bp.route('/logout')
def logout():
    """Admin logout route"""
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    session.pop('admin_role', None)
    session.pop('admin_password_verified', None)
    flash('You have been logged out successfully.')
    return redirect(url_for('admin.login'))

def get_mentors_for_select():
    """Get mentors for select dropdown"""
    try:
        from sqlalchemy import text
        result = db.session.execute(
            text("SELECT id, name, COALESCE(commission_pct, 40.0) as commission_pct FROM mentor WHERE active = true ORDER BY name")
        )
        mentors = [{'id': row[0], 'name': row[1], 'commission_pct': row[2]} for row in result]
        print(f"Found {len(mentors)} active mentors for dropdown")
        return mentors
    except Exception as e:
        print(f"Error fetching mentors for select: {e}")
        import traceback
        traceback.print_exc()
        return []

@admin_bp.route('/create-user', methods=['GET', 'POST'])
@admin_required
def create_user():
    if session.get('admin_role') != 'owner':
        flash('Access denied. Owner privileges required.')
        return redirect(url_for('admin.dashboard'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form.get('role', 'admin')
        
        # Initialize models if not already done
        global AdminUser, Coupon, AdminOTP, MentorPayments
        if not AdminUser:
            AdminUser, Coupon, AdminOTP, MentorPayments = create_models(db)
        
        existing = AdminUser.query.filter_by(username=username).first() if AdminUser else None
        if existing:
            flash('Username already exists')
            return render_template('admin/create_user.html')
        
        admin_user = AdminUser(
            username=username,
            password_hash=generate_password_hash(password),
            role=role
        )
        db.session.add(admin_user)
        db.session.commit()
        
        flash(f'Admin user created: {username}')
        return redirect(url_for('admin.dashboard'))
    
    return render_template('admin/create_user.html')

@admin_bp.route('/user/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user(user_id):
    try:
        # Get current user status
        from sqlalchemy import text
        result = db.session.execute(
            text("SELECT verified, email FROM users WHERE id = :user_id"), {'user_id': user_id}
        ).fetchone()
        
        if result:
            current_verified = bool(result[0]) if result[0] is not None else False
            email = result[1]
            new_verified = not current_verified
            
            # Update user status
            db.session.execute(
                text("UPDATE users SET verified = :verified WHERE id = :user_id"), 
                {'verified': new_verified, 'user_id': user_id}
            )
            db.session.commit()
            
            status = "activated" if new_verified else "deactivated"
            flash(f'User {email} {status}')
        else:
            flash('User not found')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating user: {str(e)}')
        print(f"Error in toggle_user: {e}")
        import traceback
        traceback.print_exc()
    
    return redirect(url_for('admin.users'))

@admin_bp.route('/owner-password', methods=['GET', 'POST'])
@admin_required
def owner_password():
    if session.get('admin_role') != 'owner':
        flash('Access denied. Owner privileges required.')
        return redirect(url_for('admin.dashboard'))
    
    if request.method == 'POST':
        # This would update owner password - implement as needed
        flash('Owner password updated')
        return redirect(url_for('admin.dashboard'))
    
    return render_template('admin/owner_password.html')

# Initialize tables when blueprint is imported
def init_admin_db_final(app_db):
    """Call this from main app after db is initialized"""
    global db, AdminUser, Coupon, AdminOTP, MentorPayments
    db = app_db
    AdminUser, Coupon, AdminOTP, MentorPayments = create_models(db)
    # Tables will be created in the current app context
    db.create_all()