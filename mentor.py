from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import secrets
import string

# Create blueprint
mentor_bp = Blueprint('mentor', __name__)

# Import db - will be set when blueprint is registered
db = None
Mentor = None
Student = None
Coupon = None

# Models will be created when init_mentor_db is called
def create_models(database):
    global Mentor, Student, Coupon
    
    class Mentor(database.Model):
        __tablename__ = 'mentor'
        __table_args__ = {'extend_existing': True}  # Allow table extension
        id = database.Column(database.Integer, primary_key=True)
        mentor_id = database.Column(database.String(50), unique=True, nullable=False)
        password_hash = database.Column(database.String(128), nullable=False)
        name = database.Column(database.String(100), nullable=False)
        email = database.Column(database.String(120), nullable=False)
        commission_pct = database.Column(database.Float, nullable=True, default=40.0)  # Make nullable to avoid issues
        created_by_admin_id = database.Column(database.Integer, nullable=False)
        active = database.Column(database.Boolean, default=True)
        created_at = database.Column(database.DateTime, default=datetime.utcnow)
    
    class Student(database.Model):
        __tablename__ = 'student'
        id = database.Column(database.Integer, primary_key=True)
        name = database.Column(database.String(100), nullable=False)
        email = database.Column(database.String(120), nullable=False)
        coupon_code_used = database.Column(database.String(50), nullable=True)
        registered_at = database.Column(database.DateTime, default=datetime.utcnow)
    
    # Update existing Coupon model to include mentor_id and student_id
    class MentorCoupon(database.Model):
        __tablename__ = 'mentor_coupon'
        id = database.Column(database.Integer, primary_key=True)
        code = database.Column(database.String(50), unique=True, nullable=False)
        mentor_id = database.Column(database.Integer, nullable=True)  # Remove FK constraint to avoid conflicts
        student_id = database.Column(database.Integer, nullable=True)  # Remove FK constraint to avoid conflicts
        used_at = database.Column(database.DateTime, nullable=True)
        created_at = database.Column(database.DateTime, default=datetime.utcnow)
        discount_percent = database.Column(database.Integer, nullable=False, default=10)
        active = database.Column(database.Boolean, default=True)
    
    # Set global reference for easier access
    Coupon = MentorCoupon
    return Mentor, Student, MentorCoupon

# Decorators
def mentor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('mentor_logged_in'):
            return redirect(url_for('mentor.login'))
        
        # Check if mentor is still active
        mentor = Mentor.query.filter_by(mentor_id=session.get('mentor_id')).first()
        if not mentor or not mentor.active:
            session.clear()
            flash('Your mentor account has been deactivated. Please contact admin.')
            return redirect(url_for('mentor.login'))
        
        return f(*args, **kwargs)
    return decorated_function

# Routes
@mentor_bp.route('/')
def index():
    if session.get('mentor_logged_in'):
        return redirect(url_for('mentor.dashboard'))
    return redirect(url_for('mentor.login'))

@mentor_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        mentor_id = request.form['mentor_id'].strip()
        password = request.form['password'].strip()
        
        mentor = Mentor.query.filter_by(mentor_id=mentor_id).first()
        
        if mentor and mentor.active and check_password_hash(mentor.password_hash, password):
            session.permanent = True  # Make session permanent (30 days)
            session['mentor_logged_in'] = True
            session['mentor_id'] = mentor.mentor_id
            session['mentor_name'] = mentor.name
            flash(f'Welcome back, {mentor.name}!')
            return redirect(url_for('mentor.dashboard'))
        else:
            flash('Invalid mentor ID or password.')
    
    return render_template('mentor/mentor_login.html')

@mentor_bp.route('/dashboard')
@mentor_required
def dashboard():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    
    mentor = Mentor.query.filter_by(mentor_id=session['mentor_id']).first()
    
    # Get students who used coupons assigned to this mentor from coupon_usage table
    from sqlalchemy import text
    
    # Build search condition
    search_condition = ""
    params = {"mentor_id": mentor.id}
    
    if search:
        search_condition = "AND (u.email LIKE :search OR u.name LIKE :search)"
        params["search"] = f"%{search}%"
    
    # Get students with pagination - fix commission calculation
    offset = (page - 1) * 10
    students_query = f"""
        SELECT u.email, u.name, cu.coupon_code, cu.used_at, 
               p.amount as student_paid,
               (p.amount * COALESCE(m.commission_pct, 40.0) / 100) as commission_amount
        FROM coupon_usage cu
        JOIN users u ON cu.user_id = u.id
        JOIN payments p ON cu.payment_id = p.id
        JOIN mentor m ON cu.mentor_id = m.id
        WHERE cu.mentor_id = :mentor_id {search_condition}
        ORDER BY cu.used_at DESC
        LIMIT 10 OFFSET :offset
    """
    
    params["offset"] = offset
    students_data = db.session.execute(text(students_query), params).fetchall()
    
    # Get total count for pagination
    count_query = f"""
        SELECT COUNT(*)
        FROM coupon_usage cu
        JOIN users u ON cu.user_id = u.id
        WHERE cu.mentor_id = :mentor_id {search_condition}
    """
    total_students = db.session.execute(text(count_query), {k: v for k, v in params.items() if k != "offset"}).fetchone()[0]
    
    # Get coupon statistics from main coupon table
    total_coupons = db.session.execute(
        text("SELECT COUNT(*) FROM coupon WHERE mentor_id = :mentor_id"),
        {"mentor_id": mentor.id}
    ).fetchone()[0]
    
    used_coupons = db.session.execute(
        text("SELECT COUNT(DISTINCT coupon_code) FROM coupon_usage WHERE mentor_id = :mentor_id"),
        {"mentor_id": mentor.id}
    ).fetchone()[0]
    
    # Create pagination object manually
    class SimplePagination:
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
        
        def iter_pages(self):
            for i in range(1, self.pages + 1):
                yield i
    
    students = SimplePagination(students_data, page, 10, total_students)
    
    # Calculate total commission
    total_commission_query = f"""
        SELECT COALESCE(SUM(p.amount * COALESCE(m.commission_pct, 40.0) / 100), 0) as total_commission
        FROM coupon_usage cu
        JOIN payments p ON cu.payment_id = p.id
        JOIN mentor m ON cu.mentor_id = m.id
        WHERE cu.mentor_id = :mentor_id
    """
    
    total_commission_result = db.session.execute(text(total_commission_query), {"mentor_id": mentor.id}).fetchone()
    total_commission = total_commission_result[0] if total_commission_result else 0
    
    return render_template('mentor/themed_mentor_dashboard.html',
                         students=students,
                         search=search,
                         total_coupons=total_coupons,
                         used_coupons=used_coupons,
                         total_commission=total_commission,
                         mentor=mentor)

@mentor_bp.route('/profile')
@mentor_required
def profile():
    mentor = Mentor.query.filter_by(mentor_id=session['mentor_id']).first()
    
    # Get mentor statistics
    from sqlalchemy import text
    stats = db.session.execute(
        text("""
            SELECT 
                COUNT(DISTINCT cu.id) as total_usage,
                COALESCE(SUM(cu.commission_amount), 0) as total_commission,
                COALESCE(SUM(cu.discount_amount), 0) as total_discount,
                COUNT(DISTINCT cu.user_id) as unique_users
            FROM coupon_usage cu
            WHERE cu.mentor_id = :mentor_id
        """),
        {"mentor_id": mentor.id}
    ).fetchone()
    
    return render_template('mentor/profile.html', mentor=mentor, stats=stats)

@mentor_bp.route('/coupons')
@mentor_required
def coupons():
    mentor = Mentor.query.filter_by(mentor_id=session['mentor_id']).first()
    
    # Get assigned coupons
    from sqlalchemy import text
    coupon_rows = db.session.execute(
        text("""
            SELECT c.code, c.discount_percent, c.max_uses, c.uses, c.active, c.created_at
            FROM coupon c
            WHERE c.mentor_id = :mentor_id
            ORDER BY c.created_at DESC
        """),
        {"mentor_id": mentor.id}
    ).fetchall()
    
    # Convert to list of dicts for easier template handling
    assigned_coupons = []
    for row in coupon_rows:
        assigned_coupons.append({
            'code': row[0],
            'discount_percent': row[1],
            'max_uses': row[2],
            'uses': row[3],
            'active': row[4],
            'created_at': row[5]
        })
    
    return render_template('mentor/coupons.html', coupons=assigned_coupons, mentor=mentor)

@mentor_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('mentor.login'))

# Utility functions
def generate_mentor_id():
    """Generate unique mentor ID"""
    while True:
        mentor_id = 'MNT' + ''.join(secrets.choice(string.digits) for _ in range(6))
        if not Mentor.query.filter_by(mentor_id=mentor_id).first():
            return mentor_id

def generate_mentor_password():
    """Generate secure password for mentor"""
    chars = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(chars) for _ in range(12))

def create_simple_models(database):
    """Fallback to create simple models without relationships"""
    global Mentor, Student, MentorCoupon, Coupon
    
    class Mentor(database.Model):
        __tablename__ = 'mentor_simple'
        id = database.Column(database.Integer, primary_key=True)
        mentor_id = database.Column(database.String(50), unique=True, nullable=False)
        password_hash = database.Column(database.String(128), nullable=False)
        name = database.Column(database.String(100), nullable=False)
        email = database.Column(database.String(120), nullable=False)
        created_by_admin_id = database.Column(database.Integer, nullable=False)
        active = database.Column(database.Boolean, default=True)
        created_at = database.Column(database.DateTime, default=datetime.utcnow)
    
    class Student(database.Model):
        __tablename__ = 'student_simple'
        id = database.Column(database.Integer, primary_key=True)
        name = database.Column(database.String(100), nullable=False)
        email = database.Column(database.String(120), nullable=False)
        coupon_code_used = database.Column(database.String(50), nullable=True)
        registered_at = database.Column(database.DateTime, default=datetime.utcnow)
    
    class MentorCoupon(database.Model):
        __tablename__ = 'mentor_coupon_simple'
        id = database.Column(database.Integer, primary_key=True)
        code = database.Column(database.String(50), unique=True, nullable=False)
        mentor_id = database.Column(database.Integer, nullable=True)
        student_id = database.Column(database.Integer, nullable=True)
        used_at = database.Column(database.DateTime, nullable=True)
        created_at = database.Column(database.DateTime, default=datetime.utcnow)
        discount_percent = database.Column(database.Integer, nullable=False, default=10)
        active = database.Column(database.Boolean, default=True)
    
    Coupon = MentorCoupon
    database.create_all()
    print("Simple mentor models created successfully")
    return Mentor, Student, MentorCoupon

# Initialize tables when blueprint is imported
def init_mentor_db(app_db):
    """Call this from main app after db is initialized"""
    global db, Mentor, Student, MentorCoupon, Coupon
    db = app_db
    try:
        Mentor, Student, MentorCoupon = create_models(db)
        Coupon = MentorCoupon  # Alias for compatibility
        # Tables will be created in the current app context
        db.create_all()
        print("Mentor database models created successfully")
    except Exception as e:
        print(f"Error creating mentor models: {e}")
        # Create simplified models without relationships if there are conflicts
        create_simple_models(db)