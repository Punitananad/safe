import os
import secrets
import hashlib
import time
import logging
import sqlite3

# Configure logging
logging.basicConfig(level=logging.INFO)
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Tuple
from difflib import get_close_matches
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from toast_utils import ToastManager, toast_success, toast_error, toast_warning, toast_info
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, logout_user, current_user, login_required, UserMixin
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from authlib.integrations.flask_client import OAuth
from google_auth_oauthlib.flow import Flow
from dotenv import load_dotenv
import requests
import json

import pytz
from datetime import datetime, timedelta, timezone
import razorpay

# Import blueprints at top
from journal import calculatentrade_bp, db
from admin_blueprint import admin_bp, init_admin_db
from employee_dashboard_bp import employee_dashboard_bp, init_employee_dashboard_db
from mentor import mentor_bp, init_mentor_db
from subscription_admin import subscription_admin_bp
from subscription_models import init_subscription_plans, get_user_active_subscription, create_user_subscription

load_dotenv()

# ------------------------------------------------------------------------------
# App & DB setup
# ------------------------------------------------------------------------------
app = Flask(__name__)
# Template configuration to prevent encoding issues




app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True
app.jinja_env.cache = {}


# Session stability - use stable secret key from env
app.secret_key = os.getenv('FLASK_SECRET', 'dev-secret-change-this')

# Database configuration
from database_config import get_database_url, get_postgres_url

# Use PostgreSQL if DATABASE_TYPE is set to 'postgres'
if os.getenv('DATABASE_TYPE') == 'postgres':
    app.config["SQLALCHEMY_DATABASE_URI"] = get_postgres_url()
    print("Using PostgreSQL database")
else:
    db_location = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'calculatentrade.db')
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_location}"
    print("Using SQLite database")


app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Session cookie configuration for local dev
app.config.update(
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=30)  # 30 days for mentor sessions
)

# Apply ProxyFix for production deployment behind proxy/nginx
if os.getenv('FLASK_ENV') == 'production':
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE='None'
    )



db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = "login"   # route name of your login view
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return None

# Add hasattr to Jinja2 globals
app.jinja_env.globals['hasattr'] = hasattr

# Add subscription function to Jinja2 globals
app.jinja_env.globals['get_user_active_subscription'] = get_user_active_subscription

# Blueprint registration will be done after models are defined

# Database initialization is handled by init_db.py
# This ensures proper application context management

def init_app_database():
    """Initialize database with proper application context - called by init_db.py"""
    with app.app_context():
        db.create_all()
        print("Database tables created successfully")
        
        # Initialize blueprint databases
        try:
            init_admin_db(db)
            print("Admin blueprint database initialized")
        except Exception as e:
            print(f"Error initializing admin blueprint: {e}")
        
        try:
            init_employee_dashboard_db(db)
            print("Employee dashboard blueprint database initialized")
        except Exception as e:
            print(f"Error initializing employee dashboard blueprint: {e}")
        
        try:
            init_mentor_db(db)
            print("Mentor blueprint database initialized")
        except Exception as e:
            print(f"Error creating mentor models: {e}")
        
        try:
            init_subscription_plans()
            print("Subscription plans initialized")
        except Exception as e:
            print(f"Error initializing subscription plans: {e}")

migrate = Migrate(app, db)

# ------------------------------------------------------------------------------
# Dhan API configuration
# ------------------------------------------------------------------------------
DHAN_ACCESS_TOKEN = os.environ.get("DHAN_ACCESS_TOKEN")
DHAN_CLIENT_ID = os.environ.get("DHAN_CLIENT_ID")

DHAN_BASE_URL = "https://api.dhan.co"

# Timezone setup with error handling
try:
    IST = pytz.timezone("Asia/Kolkata")
except Exception as e:
    print(f"Warning: Failed to initialize timezone: {e}")
    # Fallback to UTC if IST fails
    IST = pytz.UTC

# ------------------------------------------------------------------------------
# Mail (Gmail SMTP) configuration
# ------------------------------------------------------------------------------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = (os.environ.get('MAIL_SENDER_NAME', 'Support'),
                                     os.environ.get('MAIL_USERNAME'))

mail = Mail(app)

# Razorpay Configuration
razorpay_client = razorpay.Client(auth=(os.environ.get('RAZORPAY_KEY_ID'), os.environ.get('RAZORPAY_KEY_SECRET')))

# Google OAuth Configuration
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    access_token_url='https://www.googleapis.com/oauth2/v4/token',
    userinfo_endpoint='https://www.googleapis.com/oauth2/v2/userinfo',
    client_kwargs={'scope': 'openid email profile'}
)

# Google OAuth 2.0 Flow Configuration
def get_redirect_uri():
    """Auto-detect redirect URI based on environment"""
    flask_env = os.getenv('FLASK_ENV', 'development')
    if flask_env == 'production':
        return 'https://calculatentrade.com/auth/google/callback'
    else:
        return 'http://localhost:5000/auth/google/callback'

def create_flow(state=None):
    """Create Google OAuth flow"""
    import os
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # Allow HTTP for development
    
    redirect_uri = get_redirect_uri()
    
    # Get the absolute path to client_secret.json
    client_secret_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'client_secret.json')
    
    flow = Flow.from_client_secrets_file(
        client_secret_path,
        scopes=['https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile', 'openid'],
        redirect_uri=redirect_uri
    )
    flow.redirect_uri = redirect_uri
    
    # Set state if provided (for callback)
    if state:
        flow.state = state
    
    return flow

# ------------------------------------------------------------------------------
# Models
# ------------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)  # Allow null for OAuth users
    coupon_code = db.Column(db.String(50), nullable=True)
    registered_on = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    verified = db.Column(db.Boolean, nullable=False, default=False)  # email verified
    google_id = db.Column(db.String(100), nullable=True, unique=True)  # Google OAuth ID
    profile_pic = db.Column(db.String(200), nullable=True)  # Profile picture URL
    name = db.Column(db.String(100), nullable=True)  # Full name from Google
    
    # Subscription fields
    subscription_active = db.Column(db.Boolean, nullable=False, default=False)
    subscription_expires = db.Column(db.DateTime, nullable=True)
    subscription_type = db.Column(db.String(20), nullable=True)  # 'monthly' or 'yearly'

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def has_active_subscription(self) -> bool:
        if not self.subscription_active:
            return False
        if self.subscription_expires:
            now = datetime.now(timezone.utc)
            # Ensure both datetimes are timezone-aware for comparison
            if self.subscription_expires.tzinfo is None:
                expires_at = self.subscription_expires.replace(tzinfo=timezone.utc)
            else:
                expires_at = self.subscription_expires
            if now > expires_at:
                return False
        return True


class ResetOTP(db.Model):
    __tablename__ = "reset_otp"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), index=True, nullable=False)
    otp_hash = db.Column(db.String(128), nullable=False)
    salt = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def is_expired(self) -> bool:
        now = datetime.now(timezone.utc)
        # Ensure both datetimes are timezone-aware for comparison
        if self.expires_at.tzinfo is None:
            expires_at = self.expires_at.replace(tzinfo=timezone.utc)
        else:
            expires_at = self.expires_at
        return now > expires_at


class EmailVerifyOTP(db.Model):
    __tablename__ = "email_verify_otp"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), index=True, nullable=False)
    otp_hash = db.Column(db.String(128), nullable=False)
    salt = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def is_expired(self) -> bool:
        now = datetime.now(timezone.utc)
        # Ensure both datetimes are timezone-aware for comparison
        if self.expires_at.tzinfo is None:
            expires_at = self.expires_at.replace(tzinfo=timezone.utc)
        else:
            expires_at = self.expires_at
        return now > expires_at


class UserSettings(db.Model):
    __tablename__ = "user_settings"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    email_notifications = db.Column(db.Boolean, default=True)
    theme = db.Column(db.String(20), default='light')
    timezone = db.Column(db.String(50), default='Asia/Kolkata')
    default_calculator = db.Column(db.String(20), default='intraday')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = db.relationship('User', backref=db.backref('settings', uselist=False))


# Base Trade Model for all calculator types
class BaseTrade(db.Model):
    __abstract__ = True
    id = db.Column(db.Integer, primary_key=True)
    trade_type = db.Column(db.String(10), nullable=False, default="buy")
    avg_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    expected_return = db.Column(db.Float, nullable=True)
    risk_percent = db.Column(db.Float, nullable=True)
    capital_used = db.Column(db.Float, nullable=True)
    target_price = db.Column(db.Float, nullable=True)
    stop_loss_price = db.Column(db.Float, nullable=True)
    total_reward = db.Column(db.Float, nullable=True)
    total_risk = db.Column(db.Float, nullable=True)
    rr_ratio = db.Column(db.Float, nullable=True)
    symbol = db.Column(db.String(50), nullable=True)
    comment = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="open")
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

class IntradayTrade(BaseTrade):
    __tablename__ = "intraday_trades"
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    leverage = db.Column(db.Float, nullable=True)
    lot_size = db.Column(db.Integer, nullable=True)
    derivative_name = db.Column(db.String(100), nullable=True)

class DeliveryTrade(BaseTrade):
    __tablename__ = "delivery_trades"
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

class SwingTrade(BaseTrade):
    __tablename__ = "swing_trades"
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

class MTFTrade(BaseTrade):
    __tablename__ = "mtf_trades"
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

class FOTrade(BaseTrade):
    __tablename__ = "fo_trades"
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    strike_price = db.Column(db.Float, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True)
    option_type = db.Column(db.String(10), nullable=True)  # CE/PE

class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    razorpay_order_id = db.Column(db.String(100), nullable=False)
    razorpay_payment_id = db.Column(db.String(100), nullable=True)
    amount = db.Column(db.Integer, nullable=False)  # Amount in paise
    original_amount = db.Column(db.Integer, nullable=False)  # Original amount before discount
    discount_amount = db.Column(db.Integer, nullable=False, default=0)  # Discount in paise
    coupon_code = db.Column(db.String(50), nullable=True)  # Applied coupon code
    currency = db.Column(db.String(10), nullable=False, default='INR')
    plan_type = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='created')  # created, paid, failed
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    paid_at = db.Column(db.DateTime, nullable=True)
    
    user = db.relationship('User', backref=db.backref('payments', lazy=True))

class CouponUsage(db.Model):
    __tablename__ = "coupon_usage"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    coupon_id = db.Column(db.Integer, nullable=True)
    coupon_code = db.Column(db.String(50), nullable=False)
    mentor_id = db.Column(db.Integer, nullable=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=True)
    discount_amount = db.Column(db.Integer, nullable=False)  # Discount in paise
    commission_amount = db.Column(db.Integer, nullable=False, default=0)  # Commission in paise
    order_id = db.Column(db.String(100), nullable=True)
    used_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    
    user = db.relationship('User', backref=db.backref('coupon_usages', lazy=True))
    payment = db.relationship('Payment', backref=db.backref('coupon_usage', uselist=False))

class TradeSplit(db.Model):
    __tablename__ = "trade_splits"
    id = db.Column(db.Integer, primary_key=True)
    trade_id = db.Column(db.Integer, nullable=False)
    trade_type = db.Column(db.String(20), nullable=False)  # intraday, delivery, etc.
    preview = db.Column(db.String(100), nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    sl_price = db.Column(db.Float, nullable=False)
    target_price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

# ------------------------------------------------------------------------------
# Dhan API Helper Functions
# ------------------------------------------------------------------------------
def get_dhan_headers():
    """Get headers for Dhan API requests"""
    return {
        "access-token": DHAN_ACCESS_TOKEN,
        "Content-Type": "application/json"
    }

def fetch_all_symbols():
    """Fetch all available symbols from Dhan API"""
    try:
        # Connect to the local SQLite database for Dhan symbols (keep this)
        DB_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'dhan_master.db')
        
        conn = sqlite3.connect(DB_PATH)
        
        c = conn.cursor()
        c.execute("""
            SELECT SYMBOL_NAME, DISPLAY_NAME, SECURITY_ID
            FROM instruments
            WHERE EXCH_ID = 'NSE' AND SEGMENT = 'E'
        """)
        rows = c.fetchall()
        conn.close()

        symbol_map = {}
        for sym, disp, sec_id in rows:
            if sec_id and sym:  # Only process if we have both symbol and security ID
                clean_sym = sym.strip().upper()
                symbol_map[clean_sym] = (sym, disp, str(sec_id))
                
                # Add display name mapping if different
                if disp and disp.strip().upper() != clean_sym:
                    clean_disp = disp.strip().upper()
                    symbol_map[clean_disp] = (sym, disp, str(sec_id))
                
                # Add common variations
                variations = []
                if ' LTD' in clean_sym:
                    variations.append(clean_sym.replace(' LTD', ''))
                if ' LIMITED' in clean_sym:
                    variations.append(clean_sym.replace(' LIMITED', ''))
                if ' ' in clean_sym:
                    variations.append(clean_sym.replace(' ', ''))
                
                for variation in variations:
                    if variation and variation not in symbol_map:
                        symbol_map[variation] = (sym, disp, str(sec_id))
        
        print(f"[SYMBOLS] Loaded {len(symbol_map)} symbol mappings")
        return symbol_map
    
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return {}
    except Exception as e:
        print(f"Unexpected error fetching symbols: {e}")
        return {}
import re

EQUITY_SYMBOL_RE = re.compile(r"^[A-Z]{1,15}$")  # only letters, typical NSE equity tickers

# Common option/derivative tokens often found in symbols
DERIV_TOKENS = (
    "CE", "PE", "FUT", "PERP", "W",  # options/futures/warrants generic
)

def is_equity_stock_symbol(sym: str) -> bool:
    """
    Heuristic filter to allow only plain equity stock symbols like HDFC, MRF, TCS.
    Excludes anything with digits, separators, or common derivatives markers.
    """
    if not sym:
        return False
    s = sym.strip().upper()

    # Quick rejects: contains separators or spaces
    if any(ch in s for ch in (" ", "-", "_", "/", ".", "@", "#")):
        return False

    # Reject if contains any digits (often present in options expiries/strikes)
    if any(ch.isdigit() for ch in s):
        return False

    # Reject if ends with or contains common derivative tokens
    # Keep strict: if token appears anywhere, exclude
    for tok in DERIV_TOKENS:
        if tok in s:
            return False

    # Accept only pure A–Z up to 15 chars (typical equity symbol lengths)
    if not EQUITY_SYMBOL_RE.fullmatch(s):
        return False

    return True


DB_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'dhan_master.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/search-equity-symbols', methods=['GET'])
def search_equity_symbols():
    search_query = (request.args.get('query') or '').strip()
    if not search_query:
        return jsonify([])

    try:
        conn = get_db()
        c = conn.cursor()
        q_upper = search_query.upper()

        # Get symbol matches: exact > startswith > substring
        sql = """
        SELECT
            SYMBOL_NAME,
            DISPLAY_NAME,
            CASE
                WHEN UPPER(SYMBOL_NAME) = ? THEN 300
                WHEN UPPER(SYMBOL_NAME) LIKE ? THEN 200
                WHEN UPPER(DISPLAY_NAME) LIKE ? THEN 100
                WHEN UPPER(SYMBOL_NAME) LIKE ? THEN 80
                WHEN UPPER(DISPLAY_NAME) LIKE ? THEN 50
                ELSE 0
            END AS score
        FROM instruments
        WHERE SEGMENT = 'E' AND EXCH_ID = 'NSE'
          AND (
            UPPER(SYMBOL_NAME) LIKE ?
            OR UPPER(DISPLAY_NAME) LIKE ?
          )
        ORDER BY score DESC, LENGTH(SYMBOL_NAME) ASC, SYMBOL_NAME ASC
        LIMIT 10
        """

        params = (
            q_upper,                # exact match
            q_upper + '%',          # startswith symbol
            q_upper + '%',          # startswith name
            '%' + q_upper + '%',    # substring symbol
            '%' + q_upper + '%',    # substring name
            '%' + q_upper + '%',    # filter symbol
            '%' + q_upper + '%',    # filter name
        )
        rows = c.execute(sql, params).fetchall()
        conn.close()

        # Prepare result
        result = [
            {
                "symbol": str(r["SYMBOL_NAME"]).strip().upper(),
                "name": str(r["DISPLAY_NAME"]).strip()
            }
            for r in rows
            if r["SYMBOL_NAME"]  
        ]
        return jsonify(result)

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "Error fetching symbols"}), 500


def resolve_input(symbol_input):
    """Resolve to NSE cash-equity symbol and security_id robustly."""
    try:
        DB_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'dhan_master.db')
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        key = (symbol_input or "").strip().upper()
        print(f"[RESOLVE] Looking for: '{key}'")

        # 1) Exact symbol match (strongest)
        row = c.execute("""
            SELECT SYMBOL_NAME, DISPLAY_NAME, SECURITY_ID, EXCH_ID, SEGMENT
            FROM instruments
            WHERE EXCH_ID='NSE' AND SEGMENT='E' AND UPPER(SYMBOL_NAME)=?
            LIMIT 1
        """, (key,)).fetchone()
        if not row and " " in key:
            # Try without spaces (HDFC BANK -> HDFCBANK)
            key_nospace = key.replace(" ", "")
            row = c.execute("""
                SELECT SYMBOL_NAME, DISPLAY_NAME, SECURITY_ID, EXCH_ID, SEGMENT
                FROM instruments
                WHERE EXCH_ID='NSE' AND SEGMENT='E' AND UPPER(SYMBOL_NAME)=?
                LIMIT 1
            """, (key_nospace,)).fetchone()

        # 2) Loose display-name match if symbol failed
        if not row:
            like_key = f"{key.split()[0]}%"  # prefix match helps (HDFC%)
            row = c.execute("""
                SELECT SYMBOL_NAME, DISPLAY_NAME, SECURITY_ID, EXCH_ID, SEGMENT
                FROM instruments
                WHERE EXCH_ID='NSE' AND SEGMENT='E'
                  AND (UPPER(DISPLAY_NAME) LIKE ? OR UPPER(DISPLAY_NAME)=?)
                ORDER BY LENGTH(DISPLAY_NAME) ASC
                LIMIT 1
            """, (like_key, key)).fetchone()

        conn.close()
        if not row:
            print(f"[RESOLVE] No match found for: {key}")
            return None

        sym, disp, sec_id, exch, segment = row
        result = {
            "security_id": int(sec_id),
            "segment": "NSE_EQ",  # map SEGMENT='E' to Dhan segment key
            "symbol": sym,
            "display_name": disp,
            "exchange": exch
        }
        print(f"[RESOLVE] {key} -> {result}")
        return result
    except Exception as e:
        print(f"[RESOLVE] Error: {e}")
        return None

def _headers():
    """Get headers for Dhan API requests with mandatory client-id"""
    if not DHAN_ACCESS_TOKEN:
        raise RuntimeError("DHAN_ACCESS_TOKEN not set")
    if not DHAN_CLIENT_ID:
        raise RuntimeError("DHAN_CLIENT_ID not set")
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "access-token": DHAN_ACCESS_TOKEN,
        "client-id": DHAN_CLIENT_ID,
    }

def get_ltp_batch(payload):
    """Get LTP using the faster /marketfeed/ltp endpoint"""
    url = "https://api.dhan.co/v2/marketfeed/ltp"
    try:
        h = _headers()
        r = requests.post(url, headers=h, json=payload, timeout=10)
        if r.status_code != 200:
            return {"error": f"API {r.status_code}: {r.text}"}
        return r.json() or {}
    except Exception as e:
        return {"error": f"LTP exception: {e}"}

def get_market_depth(security_id, segment_hint):
    """Fetch real-time market depth from Dhan API"""
    url = "https://api.dhan.co/v2/marketfeed/quote"
    try:
        h = _headers()
        payload = {segment_hint: [int(security_id)]}
        print(f"[API] quote payload={payload}")
        r = requests.post(url, headers=h, json=payload, timeout=10)
        print(f"[API] status={r.status_code}, body={r.text[:500]}")
        if r.status_code != 200:
            return {"error": f"API {r.status_code}: {r.text}"}
        data = r.json() or {}
        buckets = (data.get("data") or {})
        snap = None
        found_segment = None
        for seg_key, seg_map in buckets.items():
            snap = (seg_map or {}).get(str(security_id)) or (seg_map or {}).get(int(security_id))
            if snap:
                found_segment = seg_key
                break
        if not snap:
            return {"error": f"No data for security ID {security_id} (hint={segment_hint})"}
        return {
            "last_price": snap.get("last_price"),
            "best_bid": snap.get("best_bid_price"),
            "best_ask": snap.get("best_ask_price"),
            "volume": snap.get("volume") or snap.get("volume_traded_today"),
            "segment_used": found_segment,
            "raw": snap
        }
    except Exception as e:
        return {"error": f"API Exception: {e}"}

def is_market_open():
    """Check if market is currently open"""
    now = datetime.now(IST)
    
    # Check if weekend
    if now.weekday() >= 5:
        return False
    
    # Check if holiday (you should define MARKET_HOLIDAYS)
    MARKET_HOLIDAYS = set()  # Define your holidays here
    if now.strftime("%Y-%m-%d") in MARKET_HOLIDAYS:
        return False
    
    # Market hours (9:15 AM to 3:30 PM IST)
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    return market_open <= now <= market_close

def get_live_price(symbol):
    """Get live price for a symbol from Dhan API"""
    try:
        resolved = resolve_input(symbol)
        if not resolved:
            return {"error": f"Symbol {symbol} not found"}
        sec_id = resolved['security_id']
        segment = resolved['segment']  # e.g., "NSE_EQ"
        print(f"[PRICE] {symbol} -> id={sec_id}, segment={segment}")

        # Fast path: LTP API
        ltp_res = get_ltp_batch({segment: [int(sec_id)]})
        if 'error' in ltp_res:
            return ltp_res
        ltp = ((ltp_res.get("data") or {}).get(segment) or {}).get(str(sec_id), {}).get("last_price")
        if ltp is None:
            # Fallback to Quote API
            md = get_market_depth(sec_id, segment)
            if 'error' in md:
                return md
            ltp = md.get('last_price')

        if ltp is None:
            return {"error": f"No price data for {symbol} ({segment})"}

        return {
            "symbol": symbol,
            "price": ltp,
            "change": 0,
            "change_percent": 0,
            "segment": segment,
            "last_updated": datetime.now().strftime("%H:%M:%S")
        }
    except Exception as e:
        return {"error": f"Price fetch failed: {e}"}

@app.route('/get-price/<symbol>', methods=['GET'])
def get_price_route(symbol):
    """API endpoint to get live price for a symbol"""
    try:
        import urllib.parse
        decoded_symbol = urllib.parse.unquote(symbol)
        print(f"\n=== PRICE REQUEST ===")
        print(f"Original: {symbol}")
        print(f"Decoded: {decoded_symbol}")
        
        price_data = get_live_price(decoded_symbol)
        print(f"Final result: {price_data}")
        print(f"=== END REQUEST ===\n")
        
        if 'error' in price_data:
            return jsonify(price_data), 400
        
        return jsonify(price_data)
    except Exception as e:
        error_msg = f"Route exception: {str(e)}"
        print(f"[ERROR] {error_msg}")
        return jsonify({"error": error_msg}), 500

# ------------------------------------------------------------------------------
# Calculator Configuration
# ------------------------------------------------------------------------------
CALCULATOR_CONFIG = {
    'intraday': {
        'leverage': 5.0,
        'model': IntradayTrade,
        'template': 'intraday_calculator.html',
        'saved_template': 'saved.html',
        'detail_template': 'detail_calc.html'
    },
    'delivery': {
        'leverage': 1.0,  # No leverage
        'model': DeliveryTrade,
        'template': 'delivery_calculator.html',
        'saved_template': 'saved_delivery.html',
        'detail_template': 'detail_delivery.html'
    },
    'swing': {
        'leverage': 2.0,
        'model': SwingTrade,
        'template': 'swing_calculator.html',
        'saved_template': 'saved_swing.html',
        'detail_template': 'detail_swing.html'
    },
    'mtf': {
        'leverage': 4.0,
        'model': MTFTrade,
        'template': 'mtf_calculator.html',
        'saved_template': 'saved_mtf.html',
        'detail_template': 'detail_mtf.html'
    },
    'fo': {
        'leverage': 1.0,  # No leverage for F&O
        'model': IntradayTrade,
        'template': 'fo_calculator.html',
        'saved_template': 'saved_fno.html',
        'detail_template': 'detail_fno.html'
    }
}

def calculate_trade_metrics(avg_price, quantity, expected_return, risk_percent, trade_type, leverage):
    """Universal calculation function for all trade types"""
    capital_used = (avg_price * quantity) / leverage
    reward_per_share = (expected_return / 100.0) * avg_price
    risk_per_share = (risk_percent / 100.0) * avg_price
    
    if trade_type == "buy":
        target_price = avg_price + reward_per_share
        stop_loss_price = avg_price - risk_per_share
    else:  # sell
        target_price = avg_price - reward_per_share
        stop_loss_price = avg_price + risk_per_share
    
    total_reward = reward_per_share * quantity
    total_risk = risk_per_share * quantity
    rr_ratio = (reward_per_share / risk_per_share) if risk_per_share != 0 else 0.0
    
    return {
        "trade_type": trade_type,
        "avg_price": avg_price,
        "quantity": quantity,
        "expected_return": expected_return,
        "risk_percent": risk_percent,
        "capital_used": round(capital_used, 2),
        "target_price": round(target_price, 2),
        "stop_loss_price": round(stop_loss_price, 2),
        "total_reward": round(total_reward, 2),
        "total_risk": round(total_risk, 2),
        "rr_ratio": round(rr_ratio, 2),
        "leverage": leverage
    }

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "email" not in session:
            toast_error(template_key='session_expired')
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def subscription_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "email" not in session:
            toast_error(template_key='session_expired')
            return redirect(url_for("login"))
        
        # Check subscription using new system
        active_sub = get_user_active_subscription(current_user.id)
        if not active_sub:
            toast_warning(template_key='subscription_required')
            return redirect(url_for("subscription"))
        
        return f(*args, **kwargs)
    return decorated_function


def password_policy_ok(pw: str) -> bool:
    if len(pw) < 8:
        return False
    has_u = any(c.isupper() for c in pw)
    has_l = any(c.islower() for c in pw)
    has_d = any(c.isdigit() for c in pw)
    has_s = any(not c.isalnum() for c in pw)
    return has_u and has_l and has_d and has_s


def send_email(to: str, subject: str, html: str, body: str = None) -> None:
    try:
        # Check if email credentials are properly configured
        mail_username = app.config.get('MAIL_USERNAME')
        mail_password = app.config.get('MAIL_PASSWORD')
        
        if not mail_username or not mail_password or mail_username == 'your-actual-gmail@gmail.com' or mail_password == 'your-actual-app-password':
            print(f"[EMAIL] Email credentials not configured properly, skipping email to: {to}")
            return  # Skip sending email if credentials are not configured
        
        print(f"[EMAIL] Attempting to send email to: {to}")
        print(f"[EMAIL] MAIL_USERNAME configured: {mail_username}")
        print(f"[EMAIL] MAIL_PASSWORD configured: {'Yes' if mail_password else 'No'}")
        
        msg = Message(subject=subject, recipients=[to], html=html, body=body)
        mail.send(msg)
        print(f"[EMAIL] Successfully sent email to: {to}")
    except Exception as e:
        print(f"[EMAIL] Failed to send email to {to}: {str(e)}")
        # Don't raise the exception, just log it for development
        print(f"[EMAIL] Continuing without sending email...")

# ----- OTP utils (Reset Password) -----
def issue_reset_otp(email: str) -> None:
    try:
        ResetOTP.query.filter_by(email=email, used=False).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()

    otp = f"{secrets.randbelow(1_000_000):06d}"
    salt = os.urandom(16)
    digest = hashlib.sha256(salt + otp.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    rec = ResetOTP(
        email=email,
        otp_hash=digest,
        salt=salt.hex(),
        expires_at=expires_at,
        attempts=0,
        used=False
    )
    db.session.add(rec)
    db.session.commit()

    subject = "Your password reset code"
    html = f"""
      <p>Use this code to reset your password:</p>
      <h2 style="letter-spacing:2px">{otp}</h2>
      <p>This code will expire in 5 minutes (at {expires_at.strftime('%H:%M UTC')}).</p>
      <p>If you did not request this, you can ignore this email.</p>
    """
    try:
        send_email(to=email, subject=subject, html=html)
        print(f"[RESET-OTP][EMAIL] Sent code to {email}")
    except Exception as e:
        print("[RESET-OTP][EMAIL][ERROR]", e)


def verify_reset_otp(email: str, otp_input: str) -> Tuple[bool, str, Optional[ResetOTP]]:
    rec = ResetOTP.query.filter_by(email=email, used=False).order_by(ResetOTP.id.desc()).first()
    if not rec:
        return False, "Invalid or used code.", None
    if rec.attempts >= 5:
        return False, "Too many attempts. Request a new code.", rec
    if rec.is_expired():
        return False, "Code expired. Request a new code.", rec

    salt = bytes.fromhex(rec.salt)
    calc = hashlib.sha256(salt + otp_input.encode()).hexdigest()
    if calc != rec.otp_hash:
        rec.attempts += 1
        db.session.commit()
        return False, "Incorrect code.", rec
    return True, "Verified.", rec

# ----- OTP utils (Email Verification) -----
def issue_signup_otp(email: str) -> None:
    try:
        EmailVerifyOTP.query.filter_by(email=email, used=False).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()

    otp = f"{secrets.randbelow(1_000_000):06d}"
    salt = os.urandom(16)
    digest = hashlib.sha256(salt + otp.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    rec = EmailVerifyOTP(
        email=email,
        otp_hash=digest,
        salt=salt.hex(),
        expires_at=expires_at,
        attempts=0,
        used=False
    )
    db.session.add(rec)
    db.session.commit()

    subject = "Verify your email"
    html = f"""
      <p>Welcome! Please verify your email using this code:</p>
      <h2 style="letter-spacing:2px">{otp}</h2>
      <p>This code expires in 5 minutes (at {expires_at.strftime('%H:%M UTC')}).</p>
      <p>If you didn't sign up, ignore this message.</p>
    """
    try:
        send_email(to=email, subject=subject, html=html)
        print(f"[SIGNUP-OTP][EMAIL] Sent verify code to {email}")
    except Exception as e:
        print("[SIGNUP-OTP][EMAIL][ERROR]", e)


def verify_signup_otp(email: str, otp_input: str) -> Tuple[bool, str, Optional[EmailVerifyOTP]]:
    rec = EmailVerifyOTP.query.filter_by(email=email, used=False).order_by(EmailVerifyOTP.id.desc()).first()
    if not rec:
        return False, "Invalid or used code.", None
    if rec.attempts >= 5:
        return False, "Too many attempts. Request a new code.", rec
    if rec.is_expired():
        return False, "Code expired. Request a new code.", rec

    salt = bytes.fromhex(rec.salt)
    calc = hashlib.sha256(salt + otp_input.encode()).hexdigest()
    if calc != rec.otp_hash:
        rec.attempts += 1
        db.session.commit()
        return False, "Incorrect code.", rec
    return True, "Verified.", rec

# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/employee-portal")
def employee_portal():
    return redirect(url_for('employee_dashboard.employee_login'))

# Registration
@app.route("/register", methods=["GET", "POST"])
def register():
    def is_ajax():
        return request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = (request.form.get("password") or "").strip()
        confirm = (request.form.get("confirm_password") or "").strip()

        if not email or not password:
            msg = "Email and password are required."
            if is_ajax(): return jsonify({"ok": False, "error": msg}), 200
            toast_error(msg); return redirect(url_for("register"))

        if not email.endswith("@gmail.com"):
            msg = "Please use a Gmail address."
            if is_ajax(): return jsonify({"ok": False, "error": msg}), 200
            toast_error(msg); return redirect(url_for("register"))

        if password != confirm:
            msg = "Passwords do not match."
            if is_ajax(): return jsonify({"ok": False, "error": msg}), 200
            toast_error(msg); return redirect(url_for("register"))

        if not password_policy_ok(password):
            msg = "Password must be 8+ chars with upper, lower, digit, and special."
            if is_ajax(): return jsonify({"ok": False, "error": msg}), 200
            toast_error(msg); return redirect(url_for("register"))

        try:
            if User.query.filter_by(email=email).first():
                msg = "User already exists with this email."
                if is_ajax(): return jsonify({"ok": False, "error": msg, "errorCode": "EMAIL_EXISTS"}), 200
                toast_error(template_key='email_exists')
                return redirect(url_for("register"))

            user = User(email=email, verified=True)  # Auto-verify for development
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            # Skip email verification for development
            # issue_signup_otp(email)

            if is_ajax():
                return jsonify({"ok": True, "redirect": "/login"}), 200

            toast_success(template_key='register_success')
            return redirect(url_for("login"))

        except Exception as e:
            print('\n\nerror ==>', e, '\n\n')
            db.session.rollback()
            print("[REGISTER][ERROR]", e)
            msg = "Registration failed. Please try again."
            if is_ajax(): return jsonify({"ok": False, "error": msg}), 200
            toast_error(template_key='register_failed')
            return redirect(url_for("register"))

    return render_template("register.html")

# Email verification
@app.route("/verify-email", methods=["GET", "POST"])
def verify_email_route():
    email = (request.args.get("email") or request.form.get("email") or "").strip().lower()
    if request.method == "POST":
        otp_input = (request.form.get("otp") or "").strip()
        try:
            ok, msg, rec = verify_signup_otp(email, otp_input)
            if not ok:
                flash(msg, "error")
                return render_template("verify_email.html", email=email)

            user = User.query.filter_by(email=email).first()
            if not user:
                flash("Account not found.", "error")
                return render_template("verify_email.html", email=email)

            user.verified = True
            db.session.add(user)
            if rec:
                rec.used = True
                db.session.add(rec)
            db.session.commit()

            toast_success("Email verified successfully! You can now log in.")
            return redirect(url_for("login"))

        except Exception as e:
            db.session.rollback()
            print("[VERIFY-EMAIL][ERROR]", e)
            toast_error(template_key='verification_failed')
            return render_template("verify_email.html", email=email)
    return render_template("verify_email.html", email=email)

@app.route("/verify-email/resend", methods=["POST"])
def resend_verify_email():
    email = (request.form.get("email") or "").strip().lower()
    try:
        if User.query.filter_by(email=email).first():
            issue_signup_otp(email)
        flash("If the account exists, a new code has been sent.", "info")
    except Exception as e:
        print("[VERIFY-EMAIL-RESEND][ERROR]", e)
        flash("Could not send a new code. Try again later.", "error")
    return redirect(url_for("verify_email_route", email=email))

# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = (request.form.get("password") or "").strip()

        try:
            user = User.query.filter_by(email=email).first()
            # Skip email verification check for development
            # if user and not user.verified:
            #     flash("Please verify your email first. A code has been sent.", "error")
            #     issue_signup_otp(email)
            #     return redirect(url_for("verify_email_route", email=email))

            if user and user.google_id and not user.password_hash:
                toast_info("This account uses Google sign-in. Please use 'Continue with Google' button.")
                return render_template("login.html")

            if user and user.check_password(password):
                # mark user as authenticated for flask-login
                login_user(user, remember=False)          # set remember=True if you want persistent login cookie
                # keep session entry if other parts of your app rely on it
                session["email"] = user.email
                toast_success(template_key='login_success')
                # respect 'next' param so protected pages redirect correctly after login
                next_page = request.args.get("next")
                return redirect(next_page or url_for("home"))

            toast_error(template_key='login_failed')
        except Exception as e:
            toast_error("Login error. Please try again.")
            print("[LOGIN][ERROR]", e)

    return render_template("login.html")

@app.route("/logout")
def logout():
    logout_user()
    session.pop("email", None)
    toast_success(template_key='logout_success')
    return redirect(url_for("login"))

# Subscription routes
@app.route("/subscription")
@login_required
def subscription():
    user = User.query.filter_by(email=session["email"]).first()
    
    # Get current subscription from new system
    active_sub = get_user_active_subscription(user.id)
    
    return render_template("subscription.html", user=user, active_subscription=active_sub)

@app.route("/api/check-email")
def check_email():
    email = request.args.get("email", "").strip().lower()
    if not email:
        return jsonify({"exists": False})
    
    try:
        user = User.query.filter_by(email=email).first()
        return jsonify({"exists": bool(user)})
    except Exception as e:
        print(f"Database error in check_email: {e}")
        return jsonify({"exists": False, "error": "Database error"}), 500

@app.route("/api/apply-coupon", methods=["POST"])
def apply_coupon():
    """Validate coupon and return discount metadata"""
    # Check if user is logged in for AJAX requests
    if not current_user.is_authenticated:
        return jsonify({"success": False, "error": "Please log in to apply coupon"}), 401
    
    try:
        data = request.get_json()
        coupon_code = (data.get("coupon_code") or "").strip().upper()
        plan_type = data.get("plan_type")
        
        if not coupon_code:
            return jsonify({"success": False, "error": "Coupon code is required"}), 400
        
        if plan_type not in ["monthly", "yearly"]:
            return jsonify({"success": False, "error": "Invalid plan type"}), 400
        
        # Get original amount (base prices for coupon calculation)
        original_amount = 30000 if plan_type == "monthly" else 79900  # Amount in paise (₹300 and ₹799)
        
        # Check if coupon exists and is active
        from sqlalchemy import text
        coupon_result = db.session.execute(
            text("SELECT id, code, discount_percent, active, mentor_id, max_uses, uses FROM coupon WHERE UPPER(TRIM(code)) = :code"),
            {"code": coupon_code}
        ).fetchone()
        
        if not coupon_result:
            return jsonify({"success": False, "error": "Invalid coupon code"}), 400
        
        coupon_id, code, discount_percent, active, mentor_id, max_uses, uses = coupon_result
        
        if not active:
            return jsonify({"success": False, "error": "Coupon code has expired"}), 400
        
        if max_uses and uses >= max_uses:
            return jsonify({"success": False, "error": "Coupon usage limit reached"}), 400
        
        # Check if user has already used this coupon (single-use validation)
        existing_usage = CouponUsage.query.filter_by(
            user_id=current_user.id,
            coupon_code=coupon_code
        ).first()
        
        if existing_usage:
            return jsonify({"success": False, "error": "Coupon code has already been used"}), 400
        
        # Calculate discount
        discount_amount = int((original_amount * discount_percent) / 100)
        final_amount = original_amount - discount_amount
        
        # Ensure minimum amount
        min_amount = 100  # ₹1 minimum
        if final_amount < min_amount:
            final_amount = min_amount
            discount_amount = original_amount - final_amount
        
        return jsonify({
            "success": True,
            "coupon_code": coupon_code,
            "discount_percent": discount_percent,
            "original_amount": original_amount,
            "discount_amount": discount_amount,
            "final_amount": final_amount,
            "savings": discount_amount
        })
        
    except Exception as e:
        print(f"Error applying coupon: {e}")
        return jsonify({"success": False, "error": "Failed to apply coupon"}), 500

@app.route("/create_order", methods=["POST"])
@login_required
def create_order():
    try:
        data = request.get_json()
        plan_type = data.get("plan_type")
        coupon_code = (data.get("coupon_code") or "").strip().upper()
        
        if plan_type not in ["monthly", "yearly"]:
            return jsonify({"error": "Invalid plan type"}), 400
        
        # Get original amount (base prices for coupon calculation)
        original_amount = 30000 if plan_type == "monthly" else 79900  # Amount in paise (₹300 and ₹799)
        final_amount = original_amount
        discount_amount = 0
        
        # Apply coupon if provided
        if coupon_code:
            # Validate coupon server-side
            from sqlalchemy import text
            coupon_result = db.session.execute(
                text("SELECT id, code, discount_percent, active, mentor_id, max_uses, uses FROM coupon WHERE UPPER(TRIM(code)) = :code"),
                {"code": coupon_code}
            ).fetchone()
            
            if not coupon_result:
                return jsonify({"error": "Invalid coupon code"}), 400
            
            coupon_id, code, discount_percent, active, mentor_id, max_uses, uses = coupon_result
            
            if not active:
                return jsonify({"error": "Coupon code has expired"}), 400
            
            if max_uses and uses >= max_uses:
                return jsonify({"error": "Coupon usage limit reached"}), 400
            
            # Check if user has already used this coupon
            existing_usage = CouponUsage.query.filter_by(
                user_id=current_user.id,
                coupon_code=coupon_code
            ).first()
            
            if existing_usage:
                return jsonify({"error": "Coupon code has already been used"}), 400
            
            # Calculate discount
            discount_amount = int((original_amount * discount_percent) / 100)
            final_amount = original_amount - discount_amount
            
            # Ensure minimum amount
            min_amount = 100  # ₹1 minimum
            if final_amount < min_amount:
                final_amount = min_amount
                discount_amount = original_amount - final_amount
        
        order_data = {
            "amount": final_amount,
            "currency": "INR",
            "receipt": f"order_{current_user.id}_{int(time.time())}",
            "notes": {
                "plan_type": plan_type,
                "user_id": current_user.id,
                "coupon_code": coupon_code if coupon_code else None,
                "original_amount": original_amount,
                "discount_amount": discount_amount
            }
        }
        
        order = razorpay_client.order.create(data=order_data)
        
        # Save payment record with coupon info
        payment = Payment(
            user_id=current_user.id,
            razorpay_order_id=order["id"],
            amount=final_amount,
            original_amount=original_amount,
            discount_amount=discount_amount,
            coupon_code=coupon_code if coupon_code else None,
            plan_type=plan_type,
            status='created'
        )
        db.session.add(payment)
        db.session.commit()
        
        return jsonify({
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "key": os.environ.get('RAZORPAY_KEY_ID'),
            "coupon_applied": bool(coupon_code),
            "discount_amount": discount_amount,
            "original_amount": original_amount
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/mentor/dashboard-data")
def get_mentor_dashboard_data():
    """Get real-time dashboard data for mentor"""
    try:
        # Simulate real-time data
        import random
        from datetime import datetime, timedelta
        
        # Generate sample performance data
        performance_data = {
            'coupon_usage': [random.randint(8, 25) for _ in range(7)],
            'commission': [random.randint(500, 1800) for _ in range(7)],
            'conversion_rate': random.randint(65, 85),
            'total_clicks': random.randint(1000, 1500),
            'total_conversions': random.randint(700, 1200)
        }
        
        # Generate recent activities
        activities = [
            {
                'type': 'student_registered',
                'message': 'New student registered',
                'details': 'John Doe used coupon SAV30',
                'time': '2 min ago',
                'badge': 'success'
            },
            {
                'type': 'commission_earned',
                'message': 'Commission earned',
                'details': f'₹{random.randint(200, 500)} from MENTOR20 usage',
                'time': '1 hour ago',
                'badge': 'warning'
            },
            {
                'type': 'coupon_shared',
                'message': 'Coupon shared',
                'details': 'SAV30 shared via WhatsApp',
                'time': '3 hours ago',
                'badge': 'info'
            }
        ]
        
        return jsonify({
            'success': True,
            'data': {
                'performance': performance_data,
                'activities': activities,
                'portfolio_value': f"₹{random.randint(10000, 15000):,}.{random.randint(10, 99)}",
                'portfolio_change': f"+{random.uniform(2.5, 4.5):.1f}%",
                'last_updated': datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/api/generate-coupon-url")
def generate_coupon_url():
    """Generate proper coupon URL with HTTPS for production"""
    coupon_code = request.args.get('coupon', '').strip().upper()
    if not coupon_code:
        return jsonify({"error": "Coupon code required"}), 400
    
    # Determine base URL based on environment
    if request.headers.get('Host', '').startswith('localhost'):
        base_url = f"http://{request.headers.get('Host')}"
    else:
        # Production - always use HTTPS with calculatentrade.com
        base_url = "https://calculatentrade.com"
    
    subscription_url = f"{base_url}/subscription?coupon={coupon_code}&auto_apply=true"
    
    return jsonify({
        "success": True,
        "url": subscription_url,
        "coupon_code": coupon_code
    })

@app.route("/verify_payment", methods=["POST"])
@login_required
def verify_payment():
    try:
        payment_id = request.json.get("razorpay_payment_id")
        order_id = request.json.get("razorpay_order_id")
        signature = request.json.get("razorpay_signature")
        
        # Verify payment signature
        params_dict = {
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature
        }
        
        razorpay_client.utility.verify_payment_signature(params_dict)
        
        # Get payment record
        payment = Payment.query.filter_by(razorpay_order_id=order_id).first()
        if not payment:
            return jsonify({"error": "Payment record not found"}), 400
        
        # Update payment record
        payment.razorpay_payment_id = payment_id
        payment.status = 'paid'
        payment.paid_at = datetime.now(timezone.utc)
        
        # Record coupon usage if coupon was applied
        if payment.coupon_code:
            # Get coupon details for mentor attribution
            from sqlalchemy import text
            coupon_result = db.session.execute(
                text("SELECT id, mentor_id, mentor_commission_pct FROM coupon WHERE UPPER(TRIM(code)) = :code"),
                {"code": payment.coupon_code}
            ).fetchone()
            
            if coupon_result:
                coupon_id, mentor_id, commission_pct = coupon_result
                
                # Calculate commission if mentor assigned
                commission_amount = 0
                if mentor_id and commission_pct:
                    commission_amount = int((payment.amount * commission_pct) / 100)
                
                # Atomically increment usage count
                db.session.execute(
                    text("UPDATE coupon SET uses = uses + 1 WHERE id = :coupon_id"),
                    {"coupon_id": coupon_id}
                )
                
                # Create usage record
                coupon_usage = CouponUsage(
                    user_id=current_user.id,
                    coupon_id=coupon_id,
                    coupon_code=payment.coupon_code,
                    mentor_id=mentor_id,
                    payment_id=payment.id,
                    discount_amount=payment.discount_amount,
                    commission_amount=commission_amount,
                    order_id=order_id
                )
                db.session.add(coupon_usage)
        
        # Create subscription using new system
        subscription = create_user_subscription(
            user_id=current_user.id,
            plan_name=payment.plan_type,
            payment_id=payment.id,
            amount_paid=payment.amount
        )
        
        # Update legacy user fields for backward compatibility
        user = current_user
        user.subscription_active = True
        user.subscription_type = payment.plan_type
        
        if payment.plan_type == "monthly":
            user.subscription_expires = datetime.now(timezone.utc) + timedelta(days=30)
        else:
            user.subscription_expires = datetime.now(timezone.utc) + timedelta(days=365)
        
        db.session.commit()
        
        success_message = f"Successfully purchased {payment.plan_type} subscription!"
        if payment.coupon_code:
            success_message += f" Coupon {payment.coupon_code} applied - You saved ₹{payment.discount_amount/100:.2f}!"
        
        return jsonify({"status": "success", "message": success_message})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/purchase_subscription", methods=["POST"])
@login_required
def purchase_subscription():
    plan_type = request.form.get("plan_type")
    
    if plan_type not in ["monthly", "yearly"]:
        flash("Invalid plan type.", "error")
        return redirect(url_for("subscription"))
    
    try:
        # Create subscription using new system
        subscription = create_user_subscription(
            user_id=current_user.id,
            plan_name=plan_type,
            amount_paid=0  # Free for testing
        )
        
        # Update legacy user fields for backward compatibility
        user = User.query.filter_by(email=session["email"]).first()
        user.subscription_active = True
        user.subscription_type = plan_type
        
        if plan_type == "monthly":
            user.subscription_expires = datetime.now(timezone.utc) + timedelta(days=30)
        else:  # yearly
            user.subscription_expires = datetime.now(timezone.utc) + timedelta(days=365)
        
        db.session.commit()
        
        flash(f"Successfully purchased {plan_type} subscription!", "success")
        return redirect(url_for("home"))
    except Exception as e:
        flash(f"Error creating subscription: {str(e)}", "error")
        return redirect(url_for("subscription"))

@app.route("/admin/mentor-report/<int:mentor_id>")
def mentor_report(mentor_id):
    """Get mentor coupon usage report"""
    try:
        from sqlalchemy import text, func
        
        # Get mentor details
        mentor_result = db.session.execute(
            text("SELECT display_name FROM mentor WHERE id = :mentor_id"),
            {"mentor_id": mentor_id}
        ).fetchone()
        
        if not mentor_result:
            return jsonify({"error": "Mentor not found"}), 404
        
        mentor_name = mentor_result[0]
        
        # Get aggregated metrics
        usage_stats = db.session.execute(
            text("""
                SELECT 
                    COUNT(*) as total_uses,
                    SUM(p.amount) as total_revenue_impact,
                    SUM(cu.discount_amount) as total_discount,
                    SUM(cu.commission_amount) as total_commission_owed
                FROM coupon_usage cu
                JOIN payments p ON cu.payment_id = p.id
                WHERE cu.mentor_id = :mentor_id AND p.status = 'paid'
            """),
            {"mentor_id": mentor_id}
        ).fetchone()
        
        # Get top coupons
        top_coupons = db.session.execute(
            text("""
                SELECT 
                    cu.coupon_code,
                    COUNT(*) as usage_count,
                    SUM(cu.discount_amount) as total_discount,
                    SUM(cu.commission_amount) as total_commission
                FROM coupon_usage cu
                JOIN payments p ON cu.payment_id = p.id
                WHERE cu.mentor_id = :mentor_id AND p.status = 'paid'
                GROUP BY cu.coupon_code
                ORDER BY usage_count DESC
                LIMIT 10
            """),
            {"mentor_id": mentor_id}
        ).fetchall()
        
        return jsonify({
            "mentor_id": mentor_id,
            "mentor_name": mentor_name,
            "total_uses": usage_stats[0] or 0,
            "total_revenue_impact": (usage_stats[1] or 0) / 100,  # Convert to rupees
            "total_discount": (usage_stats[2] or 0) / 100,
            "total_commission_owed": (usage_stats[3] or 0) / 100,
            "top_coupons": [{
                "code": row[0],
                "usage_count": row[1],
                "total_discount": row[2] / 100,
                "total_commission": row[3] / 100
            } for row in top_coupons]
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/subscription/status")
@login_required
def subscription_status():
    """Get current user's subscription status"""
    try:
        active_sub = get_user_active_subscription(current_user.id)
        
        if active_sub:
            return jsonify({
                'success': True,
                'has_subscription': True,
                'plan_name': active_sub.plan.display_name,
                'status': active_sub.status,
                'start_date': active_sub.start_date.isoformat(),
                'end_date': active_sub.end_date.isoformat(),
                'days_remaining': active_sub.days_remaining(),
                'is_active': active_sub.is_active()
            })
        else:
            return jsonify({
                'success': True,
                'has_subscription': False,
                'message': 'No active subscription found'
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/privacy-policy")
def privacy_policy():
    return render_template("privacy_policy.html")

@app.route("/refund-policy")
def refund_policy():
    return render_template("refund_policy.html")


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user_settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not user_settings:
        user_settings = UserSettings(user_id=current_user.id)
        db.session.add(user_settings)
        db.session.commit()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_settings':
            user_settings.email_notifications = 'email_notifications' in request.form
            user_settings.theme = request.form.get('theme', 'light')
            user_settings.timezone = request.form.get('timezone', 'Asia/Kolkata')
            user_settings.default_calculator = request.form.get('default_calculator', 'intraday')
            user_settings.updated_at = datetime.now(timezone.utc)
            
            db.session.commit()
            flash('Settings updated successfully!', 'success')
            return redirect(url_for('settings'))
    
    return render_template('settings.html', settings=user_settings)


# Delete Account OTP Model
class DeleteAccountOTP(db.Model):
    __tablename__ = "delete_account_otp"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), index=True, nullable=False)
    otp_hash = db.Column(db.String(128), nullable=False)
    salt = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def is_expired(self) -> bool:
        now = datetime.now(timezone.utc)
        if self.expires_at.tzinfo is None:
            expires_at = self.expires_at.replace(tzinfo=timezone.utc)
        else:
            expires_at = self.expires_at
        return now > expires_at

# Delete Account OTP utils
def issue_delete_account_otp(email: str) -> None:
    try:
        DeleteAccountOTP.query.filter_by(email=email, used=False).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()

    otp = f"{secrets.randbelow(1_000_000):06d}"
    salt = os.urandom(16)
    digest = hashlib.sha256(salt + otp.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    rec = DeleteAccountOTP(
        email=email,
        otp_hash=digest,
        salt=salt.hex(),
        expires_at=expires_at,
        attempts=0,
        used=False
    )
    db.session.add(rec)
    db.session.commit()

    subject = "Account Deletion Verification"
    html = f"""
      <p><strong>IMPORTANT:</strong> You have requested to delete your account.</p>
      <p>Use this code to confirm account deletion:</p>
      <h2 style="letter-spacing:2px; color: red;">{otp}</h2>
      <p>This code will expire in 10 minutes.</p>
      <p><strong>WARNING:</strong> This action cannot be undone. All your data will be permanently deleted.</p>
      <p>If you did not request this, please ignore this email and change your password immediately.</p>
    """
    try:
        send_email(to=email, subject=subject, html=html)
        print(f"[DELETE-ACCOUNT-OTP][EMAIL] Sent code to {email}")
    except Exception as e:
        print("[DELETE-ACCOUNT-OTP][EMAIL][ERROR]", e)

def verify_delete_account_otp(email: str, otp_input: str) -> Tuple[bool, str, Optional['DeleteAccountOTP']]:
    rec = DeleteAccountOTP.query.filter_by(email=email, used=False).order_by(DeleteAccountOTP.id.desc()).first()
    if not rec:
        return False, "Invalid or used code.", None
    if rec.attempts >= 3:
        return False, "Too many attempts. Request a new code.", rec
    if rec.is_expired():
        return False, "Code expired. Request a new code.", rec

    salt = bytes.fromhex(rec.salt)
    calc = hashlib.sha256(salt + otp_input.encode()).hexdigest()
    if calc != rec.otp_hash:
        rec.attempts += 1
        db.session.commit()
        return False, "Incorrect code.", rec
    return True, "Verified.", rec

@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    action = request.form.get('action', 'request')
    
    if action == 'request':
        # Step 1: Request deletion (send OTP for Google users, verify password for regular users)
        if current_user.google_id and not current_user.password_hash:
            # Google OAuth user - send OTP
            try:
                issue_delete_account_otp(current_user.email)
                flash('A verification code has been sent to your email. Please check your inbox.', 'info')
                return render_template('delete_account_otp.html', email=current_user.email)
            except Exception as e:
                flash('Error sending verification code. Please try again.', 'error')
                return redirect(url_for('settings'))
        else:
            # Regular user - verify password
            password = request.form.get('password')
            if not password or not current_user.check_password(password):
                flash('Incorrect password. Account deletion cancelled.', 'error')
                return redirect(url_for('settings'))
            
            # Show confirmation page
            return render_template('delete_account_confirm.html')
    
    elif action == 'verify_otp':
        # Step 2: Verify OTP for Google users
        otp_input = request.form.get('otp', '').strip()
        email = request.form.get('email', '').strip().lower()
        
        if email != current_user.email:
            flash('Invalid request.', 'error')
            return redirect(url_for('settings'))
        
        try:
            ok, msg, rec = verify_delete_account_otp(email, otp_input)
            if not ok:
                flash(msg, 'error')
                return render_template('delete_account_otp.html', email=email)
            
            # Mark OTP as used
            if rec:
                rec.used = True
                db.session.commit()
            
            # Show final confirmation
            return render_template('delete_account_confirm.html')
            
        except Exception as e:
            flash('Error verifying code. Please try again.', 'error')
            return render_template('delete_account_otp.html', email=email)
    
    elif action == 'confirm':
        # Step 3: Final confirmation and deletion
        confirm_text = request.form.get('confirm_text', '').strip()
        
        if confirm_text != 'DELETE MY ACCOUNT':
            flash('Confirmation text incorrect. Account deletion cancelled.', 'error')
            return render_template('delete_account_confirm.html')
        
        try:
            user_id = current_user.id
            user_email = current_user.email
            
            # Delete all user-related data in proper order to avoid foreign key issues
            try:
                UserSettings.query.filter_by(user_id=user_id).delete()
            except Exception as e:
                print(f"Error deleting user settings: {e}")
            
            try:
                ResetOTP.query.filter_by(email=user_email).delete()
            except Exception as e:
                print(f"Error deleting reset OTP: {e}")
            
            try:
                EmailVerifyOTP.query.filter_by(email=user_email).delete()
            except Exception as e:
                print(f"Error deleting email verify OTP: {e}")
            
            try:
                DeleteAccountOTP.query.filter_by(email=user_email).delete()
            except Exception as e:
                print(f"Error deleting delete account OTP: {e}")
            
            # Delete calculator trades and related data
            try:
                user_trades = IntradayTrade.query.filter_by(user_id=user_id).all()
                trade_ids = [trade.id for trade in user_trades]
                
                if trade_ids:
                    TradeSplit.query.filter(TradeSplit.trade_id.in_(trade_ids)).delete(synchronize_session=False)
                
                IntradayTrade.query.filter_by(user_id=user_id).delete()
            except Exception as e:
                print(f"Error deleting intraday trades: {e}")
            
            try:
                DeliveryTrade.query.filter_by(user_id=user_id).delete()
            except Exception as e:
                print(f"Error deleting delivery trades: {e}")
            
            try:
                SwingTrade.query.filter_by(user_id=user_id).delete()
            except Exception as e:
                print(f"Error deleting swing trades: {e}")
            
            try:
                MTFTrade.query.filter_by(user_id=user_id).delete()
            except Exception as e:
                print(f"Error deleting MTF trades: {e}")
            
            try:
                FOTrade.query.filter_by(user_id=user_id).delete()
            except Exception as e:
                print(f"Error deleting FO trades: {e}")
            
            # Delete templates
            try:
                PreviewTemplate.query.filter_by(user_id=user_id).delete()
            except Exception as e:
                print(f"Error deleting preview templates: {e}")
            
            try:
                AIPlanTemplate.query.filter_by(user_id=user_id).delete()
            except Exception as e:
                print(f"Error deleting AI plan templates: {e}")
            
            # Delete subscription history first
            try:
                from subscription_models import SubscriptionHistory
                SubscriptionHistory.query.filter_by(user_id=user_id).delete()
            except Exception as e:
                print(f"Error deleting subscription history: {e}")
            
            # Delete user subscriptions
            try:
                from subscription_models import UserSubscription
                UserSubscription.query.filter_by(user_id=user_id).delete()
            except Exception as e:
                print(f"Error deleting user subscriptions: {e}")
            
            # Delete payments
            try:
                Payment.query.filter_by(user_id=user_id).delete()
            except Exception as e:
                print(f"Error deleting payments: {e}")
            
            # Delete journal trades if they exist
            try:
                from journal import Trade
                # Journal trades don't have user_id, skip this step
                pass
            except Exception as e:
                print(f"Error deleting journal trades: {e}")
            
            # Delete user account
            db.session.delete(current_user)
            db.session.commit()
            
            # Logout user
            logout_user()
            session.clear()
            
            flash('Account successfully deleted. All your data has been permanently removed.', 'success')
            return redirect(url_for('home'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Error in account deletion: {e}")
            flash(f'Error deleting account: {str(e)}. Please try again or contact support.', 'error')
            return redirect(url_for('settings'))
    
    else:
        flash('Invalid request.', 'error')
        return redirect(url_for('settings'))

# Google OAuth Routes (using google_auth_oauthlib.flow)
@app.route('/oauth/login')
def oauth_login():
    """Start Google OAuth flow"""
    try:
        flow = create_flow()
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        session['oauth_state'] = state  # Use different key to avoid conflicts
        app.logger.info(f"Starting OAuth flow with state: {state[:10]}...")
        return redirect(authorization_url)
    except Exception as e:
        app.logger.error(f"OAuth login error: {e}")
        flash('Failed to start Google login. Please try again.', 'error')
        return redirect(url_for('login'))

@app.route('/auth/google/callback')
def oauth_callback():
    """Handle OAuth callback"""
    try:
        # Get states
        session_state = session.get('oauth_state')
        returned_state = request.args.get('state')
        
        app.logger.info(f"OAuth callback - Session state: {session_state[:10] if session_state else 'None'}..., Returned: {returned_state[:10] if returned_state else 'None'}...")
        
        # Check for error in callback
        error = request.args.get('error')
        if error:
            app.logger.error(f"OAuth error from Google: {error}")
            flash('Google authentication was cancelled or failed.', 'error')
            return redirect(url_for('login'))
        
        # Verify state parameter
        if not session_state or session_state != returned_state:
            app.logger.error(f"State mismatch: session={session_state}, returned={returned_state}")
            flash('Security check failed. Please try logging in again.', 'error')
            return redirect(url_for('login'))
        
        # Create flow and fetch token
        flow = create_flow()
        flow.fetch_token(authorization_response=request.url)
        
        # Get user info from Google
        credentials = flow.credentials
        user_info_response = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {credentials.token}'},
            timeout=10
        )
        
        if user_info_response.status_code != 200:
            app.logger.error(f"Failed to get user info: {user_info_response.status_code}")
            flash('Failed to get user information from Google.', 'error')
            return redirect(url_for('login'))
        
        user_info = user_info_response.json()
        email = user_info.get('email')
        
        if not email:
            app.logger.error("No email in Google response")
            flash('Failed to get email from Google.', 'error')
            return redirect(url_for('login'))
        
        # Check if user exists
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Update existing user with Google info if needed
            if not user.google_id:
                user.google_id = user_info.get('id')
                user.name = user_info.get('name', '')
                user.profile_pic = user_info.get('picture', '')
                user.verified = True
                db.session.commit()
            
            login_user(user, remember=False)
            session["email"] = user.email
            session.pop('oauth_state', None)  # Clean up
            
            app.logger.info(f"User {email} logged in via Google")
            flash('Successfully logged in with Google!', 'success')
            return redirect(url_for('home'))
        else:
            # Create new user
            new_user = User(
                email=email,
                google_id=user_info.get('id'),
                name=user_info.get('name', ''),
                profile_pic=user_info.get('picture', ''),
                verified=True,
                password_hash=None
            )
            
            db.session.add(new_user)
            db.session.commit()
            
            login_user(new_user, remember=False)
            session["email"] = new_user.email
            session.pop('oauth_state', None)  # Clean up
            
            app.logger.info(f"New user {email} created via Google")
            flash('Account created and logged in with Google!', 'success')
            return redirect(url_for('home'))
            
    except Exception as e:
        app.logger.error(f"OAuth callback error: {e}")
        session.pop('oauth_state', None)  # Clean up on error
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('login'))

# Keep existing Google OAuth routes for backward compatibility
@app.route('/auth/google')
def google_login():
    """Initiate Google OAuth login (legacy) - redirects to new OAuth flow"""
    return redirect(url_for('oauth_login'))


# Forgot password
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        try:
            if email and User.query.filter_by(email=email).first():
                issue_reset_otp(email)
        except Exception as e:
            print("[FORGOT][ERROR]", e)

        flash("If that email exists, a reset code has been sent.", "info")
        return redirect(url_for("verify_otp_route", email=email))
    return render_template("forgot_password.html")

# Verify reset OTP
@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp_route():
    email = (request.args.get("email") or request.form.get("email") or "").strip().lower()

    if request.method == "POST":
        otp_input = (request.form.get("otp") or "").strip()
        new_pw = request.form.get("password") or ""
        confirm_pw = request.form.get("confirm_password") or ""

        try:
            ok, msg, rec = verify_reset_otp(email, otp_input)
            if not ok:
                flash(msg, "error")
                return render_template("verify_otp.html", email=email)

            if new_pw != confirm_pw:
                flash("Passwords do not match.", "error")
                return render_template("verify_otp.html", email=email)

            if not password_policy_ok(new_pw):
                flash("Password must be 8+ chars with upper, lower, digit, and special.", "error")
                return render_template("verify_otp.html", email=email)

            user = User.query.filter_by(email=email).first()
            if not user:
                flash("Account not found.", "error")
                return render_template("verify_otp.html", email=email)

            user.set_password(new_pw)
            db.session.add(user)
            if rec:
                rec.used = True
                db.session.add(rec)
            db.session.commit()

            flash("Password reset successful. Please log in.", "success")
            return redirect(url_for("login"))

        except Exception as e:
            db.session.rollback()
            flash("Could not reset password. Please try again.", "error")
            print("[VERIFY-OTP][ERROR]", e)
            return render_template("verify_otp.html", email=email)

    return render_template("verify_otp.html", email=email)

# ------------------------------------------------------------------------------
# Intraday calculator + related routes
# ------------------------------------------------------------------------------
@app.route("/calculator")
@subscription_required
def calculator():
    return render_template("calculator.html")

# Universal calculator route
@app.route("/<calc_type>_calculator", methods=["GET", "POST"])
@subscription_required
def universal_calculator(calc_type):
    if calc_type not in CALCULATOR_CONFIG:
        return redirect(url_for('calculator'))
    
    config = CALCULATOR_CONFIG[calc_type]
    
    if request.method == "POST":
        try:
            avg_price = float(request.form["avgPrice"])
            quantity = int(request.form["quantity"])
            expected_return = float(request.form["expectedReturn"])
            risk_percent = float(request.form["riskPercent"])
            comment = request.form.get("comment", "").strip()
            trade_type = request.form.get("trade_type", "buy").strip().lower()
            if trade_type not in ("buy", "sell"):
                trade_type = "buy"

            result = calculate_trade_metrics(
                avg_price, quantity, expected_return, risk_percent, 
                trade_type, config['leverage']
            )
            result["comment"] = comment
            result["calc_type"] = calc_type

            return render_template(config['template'], result=result)
        except Exception as e:
            app.logger.exception(f"Error in {calc_type} calculation")
            return jsonify({"error": str(e)}), 500

    return render_template(config['template'])

# Keep original intraday route for backward compatibility
@app.route("/intraday_calculator", methods=["GET", "POST"])
@subscription_required
def intraday():
    return universal_calculator('intraday')

# Universal save route
@app.route("/save_<calc_type>_result", methods=["POST"])
@subscription_required
def save_universal_result(calc_type):
    if calc_type not in CALCULATOR_CONFIG:
        return jsonify({"error": "Invalid calculator type"}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data received"}), 400
    
    try:
        config = CALCULATOR_CONFIG[calc_type]
        model = config['model']
        
        # Ensure symbol is properly set
        symbol = (data.get("symbol") or "").strip()
        comment = (data.get("comment") or "").strip()
        
        # Extract symbol from comment if not provided
        if not symbol and comment:
            for word in comment.split():
                if word.isupper() and 2 <= len(word) <= 10 and word.isalpha():
                    symbol = word
                    break
        
        # Create trade instance with null checks
        trade_data = {
            "user_id": current_user.id,  # Associate trade with current user
            "trade_type": data.get("trade_type", "buy"),
            "avg_price": float(data.get("avg_price", 0)),
            "quantity": int(data.get("quantity", 0)),
            "expected_return": float(data.get("expected_return", 0)),
            "risk_percent": float(data.get("risk_percent", 0)),
            "capital_used": float(data.get("capital_used", 0)),
            "target_price": float(data.get("target_price", 0)) if data.get("target_price") is not None else 0,
            "stop_loss_price": float(data.get("stop_loss_price", 0)) if data.get("stop_loss_price") is not None else 0,
            "total_reward": float(data.get("total_reward", 0)),
            "total_risk": float(data.get("total_risk", 0)),
            "rr_ratio": float(data.get("rr_ratio", 0)),
            "symbol": symbol or None,
            "comment": comment,
            "timestamp": datetime.now(timezone.utc),
        }
        
        # Add F&O specific fields if applicable
        if calc_type == 'fo':
            trade_data.update({
                "strike_price": float(data.get("strike_price", 0)) if data.get("strike_price") else None,
                "expiry_date": datetime.strptime(data.get("expiry_date"), "%Y-%m-%d").date() if data.get("expiry_date") else None,
                "option_type": data.get("option_type")
            })
        
        trade = model(**trade_data)
        db.session.add(trade)
        db.session.commit()
        return jsonify({"message": "Saved successfully", "trade_id": trade.id}), 200
    except Exception as e:
        db.session.rollback()
        app.logger.exception(f"Failed to save {calc_type} trade")
        return jsonify({"error": "Failed to save trade", "details": str(e)}), 500

# Keep original intraday save route for backward compatibility
@app.route("/save_intraday_result", methods=["POST"])
@login_required
def save_intraday_result():
    return save_universal_result('intraday')

def normalize_trade(trade):
    """Normalize trade object to dict with guaranteed keys."""
    # Resolve symbol from multiple possible fields
    symbol = None
    for field in ['symbol', 'ticker', 'stock_name', 'display', 'name']:
        if hasattr(trade, field):
            value = getattr(trade, field)
            if value and str(value).strip():
                symbol = str(value).strip()
                break
    
    # Extract from comment if no symbol found
    if not symbol and hasattr(trade, 'comment') and trade.comment:
        for word in trade.comment.split():
            if word.isupper() and 2 <= len(word) <= 10 and word.isalpha():
                symbol = word
                break
    
    return {
        'id': trade.id,
        'trade_type': trade.trade_type or 'buy',
        'status': getattr(trade, 'status', 'open'),
        'avg_price': float(trade.avg_price) if trade.avg_price is not None else 0.0,
        'quantity': int(trade.quantity) if trade.quantity is not None else 0,
        'expected_return': float(trade.expected_return) if trade.expected_return is not None else 0.0,
        'risk_percent': float(trade.risk_percent) if trade.risk_percent is not None else 0.0,
        'capital_used': float(trade.capital_used) if trade.capital_used is not None else 0.0,
        'target_price': float(trade.target_price) if trade.target_price is not None else 0.0,
        'stop_loss_price': float(trade.stop_loss_price) if trade.stop_loss_price is not None else 0.0,
        'total_reward': float(trade.total_reward) if trade.total_reward is not None else 0.0,
        'total_risk': float(trade.total_risk) if trade.total_risk is not None else 0.0,
        'rr_ratio': trade.rr_ratio if trade.rr_ratio is not None else 0.0,
        'comment': trade.comment,
        'symbol': symbol,
        'lot_size': getattr(trade, 'lot_size', None),
        'leverage': getattr(trade, 'leverage', None),
        'derivative_name': getattr(trade, 'derivative_name', None),
        'timestamp': trade.timestamp
    }

# Universal saved trades route
@app.route("/saved_<calc_type>")
@subscription_required
def show_saved_universal_trades(calc_type):
    if calc_type not in CALCULATOR_CONFIG:
        return redirect(url_for('calculator'))
    
    try:
        config = CALCULATOR_CONFIG[calc_type]
        model = config['model']
        trades = model.query.filter_by(user_id=current_user.id).order_by(model.id.desc()).all()
        normalized_trades = [normalize_trade(trade) for trade in trades]
        
        missing_symbol_count = sum(1 for t in normalized_trades if not t['symbol'])
        app.logger.info(f"Fetched {len(normalized_trades)} {calc_type} trades, {missing_symbol_count} missing symbol")
        
        return render_template(config['saved_template'], trades=normalized_trades, calc_type=calc_type)
    except Exception as e:
        app.logger.error(f"Error fetching {calc_type} trades: {e}")
        return render_template(config['saved_template'], trades=[], calc_type=calc_type)

# Keep original saved route for backward compatibility
@app.route("/saved")
@subscription_required
def show_saved_trades():
    return show_saved_universal_trades('intraday')

# Universal delete route
@app.route("/delete_<calc_type>/<int:trade_id>", methods=["POST"])
@login_required
def delete_universal_trade(calc_type, trade_id):
    if calc_type not in CALCULATOR_CONFIG:
        return jsonify({"error": "Invalid calculator type"}), 400
    
    config = CALCULATOR_CONFIG[calc_type]
    model = config['model']
    trade = model.query.get_or_404(trade_id)
    db.session.delete(trade)
    db.session.commit()
    return redirect(url_for("show_saved_universal_trades", calc_type=calc_type))

# Keep original delete route for backward compatibility
@app.route("/delete/<int:trade_id>", methods=["POST"])
@login_required
def delete_trade(trade_id):
    return delete_universal_trade('intraday', trade_id)

# Universal update route
@app.route("/save_<calc_type>_update", methods=["POST"])
@login_required
def save_universal_position_update(calc_type):
    if calc_type not in CALCULATOR_CONFIG:
        return jsonify({'success': False, 'error': 'Invalid calculator type'}), 400
    
    try:
        data = request.get_json()
        trade_id = data.get('trade_id')
        
        config = CALCULATOR_CONFIG[calc_type]
        model = config['model']
        leverage = config['leverage']
        
        trade = model.query.get_or_404(trade_id)
        
        # Update trade fields
        trade.avg_price = float(data.get('avg_price', trade.avg_price))
        trade.quantity = int(data.get('quantity', trade.quantity))
        trade.stop_loss_price = float(data.get('stop_loss_price', trade.stop_loss_price))
        trade.target_price = float(data.get('target_price', trade.target_price))
        
        # Recalculate derived fields
        capital_used = (trade.avg_price * trade.quantity) / leverage
        
        if trade.trade_type == 'buy':
            reward_per_share = trade.target_price - trade.avg_price
            risk_per_share = trade.avg_price - trade.stop_loss_price
        else:
            reward_per_share = trade.avg_price - trade.target_price
            risk_per_share = trade.stop_loss_price - trade.avg_price
        
        expected_return = (reward_per_share / (trade.avg_price / leverage)) * 100
        risk_percent = (risk_per_share / (trade.avg_price / leverage)) * 100
        
        trade.capital_used = round(capital_used, 2)
        trade.expected_return = round(expected_return, 2)
        trade.risk_percent = round(risk_percent, 2)
        trade.total_reward = round(reward_per_share * trade.quantity, 2)
        trade.total_risk = round(risk_per_share * trade.quantity, 2)
        trade.rr_ratio = round((reward_per_share / risk_per_share) if risk_per_share != 0 else 0.0, 2)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'trade': {
                'id': trade.id,
                'avg_price': trade.avg_price,
                'quantity': trade.quantity,
                'stop_loss_price': trade.stop_loss_price,
                'target_price': trade.target_price,
                'capital_used': trade.capital_used,
                'expected_return': trade.expected_return,
                'risk_percent': trade.risk_percent,
                'total_reward': trade.total_reward,
                'total_risk': trade.total_risk,
                'rr_ratio': trade.rr_ratio
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# Keep original update route for backward compatibility
@app.route("/save_update", methods=["POST"])
@login_required
def save_position_update():
    return save_universal_position_update('intraday')

# Universal close position route
@app.route("/close_<calc_type>_position", methods=["POST"])
@login_required
def close_universal_position(calc_type):
    if calc_type not in CALCULATOR_CONFIG:
        return jsonify({'success': False, 'error': 'Invalid calculator type'}), 400
    
    try:
        data = request.get_json()
        trade_id = data.get('trade_id')
        
        config = CALCULATOR_CONFIG[calc_type]
        model = config['model']
        trade = model.query.get_or_404(trade_id)
        
        # Update trade status to closed
        trade.status = 'closed'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{calc_type.title()} position closed successfully!',
            'trade_id': trade.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# Universal reopen position route
@app.route("/reopen_<calc_type>_position", methods=["POST"])
@login_required
def reopen_universal_position(calc_type):
    if calc_type not in CALCULATOR_CONFIG:
        return jsonify({'success': False, 'error': 'Invalid calculator type'}), 400
    
    try:
        data = request.get_json()
        trade_id = data.get('trade_id')
        
        config = CALCULATOR_CONFIG[calc_type]
        model = config['model']
        trade = model.query.get_or_404(trade_id)
        
        # Update trade status to open
        trade.status = 'open'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{calc_type.title()} position reopened successfully!',
            'trade_id': trade.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# Keep original routes for backward compatibility
@app.route("/close_position", methods=["POST"])
@login_required
def close_position():
    return close_universal_position('intraday')

@app.route("/reopen_position", methods=["POST"])
@login_required
def reopen_position():
    return reopen_universal_position('intraday')

def fibonacci_pivots(H: float, L: float, C: float) -> dict:
    """
    Fibonacci pivot set:
      PP = (H+L+C)/3
      R1 = PP + 0.382*(H-L)
      R2 = PP + 0.618*(H-L)
      R3 = PP + 1.000*(H-L)
      S1 = PP - 0.382*(H-L)
      S2 = PP - 0.618*(H-L)
      S3 = PP - 1.000*(H-L)
    Returned keys mapped to your UI: P,R1,R2,R3,S1,S2,S3
    """
    PP = (H + L + C) / 3.0
    range_ = (H - L)
    return {
        "P":  PP,
        "R1": PP + 0.382 * range_,
        "R2": PP + 0.618 * range_,
        "R3": PP + 1.000 * range_,
        "S1": PP - 0.382 * range_,
        "S2": PP - 0.618 * range_,
        "S3": PP - 1.000 * range_,
    }



def fetch_pivot_data(symbol, avg_price, trade_type):
    """Fetch pivot data for a given symbol and convert to UI percentages"""
    try:
        # First resolve the symbol to get security ID
        resolved = resolve_input(symbol)
        if not resolved:
            return {"error": "Symbol resolution failed."}
            
        if isinstance(resolved, tuple):
            _, _, sec_id = resolved
        elif isinstance(resolved, list) and len(resolved) > 0:
            sec_id = resolved[0]['sec_id']
        else:
            return {"error": "No valid security ID found."}
        
        # Get pivot points
        pivot_response = api_pivots_last_internal(sec_id)
        if not pivot_response or 'error' in pivot_response:
            return {"error": pivot_response.get('error', 'Failed to fetch pivot data')}
        
        # Convert to UI percentages
        pivot_ui = pivots_to_ui_percentages(
            avg_price, 
            trade_type, 
            pivot_response['levels']
        )
        
        return pivot_ui
    except Exception as e:
        print(f"Error in fetch_pivot_data: {e}")
        return {"error": str(e)}
    
def api_pivots_last_internal(sec_id):
    """
    Base day = previous trading day of the last completed trading day.
    Pivots = Fibonacci set.
    """
    base = last_completed_trading_day()
    prev_day = _previous_trading_day(base)
    try:
        data_result = fetch_intraday_ohlc(sec_id, prev_day)
        H = data_result["high"]
        L = data_result["low"]
        C = data_result["close"]
        levels = fibonacci_pivots(H, L, C)
        return {
            "ok": True,
            "date": prev_day.strftime("%Y-%m-%d"),
            "ohlc": {"high": H, "low": L, "close": C},
            "levels": levels,
            "securityId": sec_id
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# Universal detail route
@app.route("/detail_<calc_type>/<int:trade_id>", methods=["GET", "POST"])
@login_required
def detail_universal_trade(calc_type, trade_id):
    if calc_type not in CALCULATOR_CONFIG:
        return redirect(url_for('calculator'))
    
    config = CALCULATOR_CONFIG[calc_type]
    model = config['model']
    trade = model.query.get_or_404(trade_id)

    # --- find symbol ---
    symbol = trade.symbol
    if not symbol and trade.comment:
        for word in trade.comment.split():
            if word.isupper() and 2 <= len(word) <= 10 and word.isalpha():
                symbol = word
                break
    if not symbol:
        symbol = "UNKNOWN"

    # --- pivot data ---
    pivot_ui = {}
    if symbol and symbol != "UNKNOWN":
        try:
            data = fetch_pivot_data(symbol, trade.avg_price, trade.trade_type)
            if data:
                pivot_ui = data
        except Exception as e:
            print(f"Error fetching pivot data: {e}")

    # --- trade dict for template ---
    trade_data = {
        "id": trade.id,
        "avg_price": trade.avg_price,
        "quantity": trade.quantity,
        "expected_return": trade.expected_return,
        "risk_percent": trade.risk_percent,
        "capital_used": trade.capital_used,
        "target_price": trade.target_price,
        "stop_loss_price": trade.stop_loss_price,
        "total_reward": trade.total_reward,
        "total_risk": trade.total_risk,
        "rr_ratio": trade.rr_ratio,
        "comment": trade.comment,
        "trade_type": trade.trade_type,
        "symbol": symbol,
        "status": getattr(trade, 'status', 'open'),
        "calc_type": calc_type,
    }
    
    # Add F&O specific fields if applicable
    if calc_type == 'fo' and hasattr(trade, 'strike_price'):
        trade_data.update({
            "strike_price": trade.strike_price,
            "expiry_date": trade.expiry_date,
            "option_type": trade.option_type
        })

    if request.method == "POST":
        try:
            parts = int(request.form.get("parts", 1))
        except ValueError:
            parts = 1

        sl_parts, total_qty = [], 0
        for i in range(1, parts + 1):
            try:
                qty = int(request.form.get(f"qty_{i}", 0))
                sl = float(request.form.get(f"sl_{i}", 0))
                target = float(request.form.get(f"target_{i}", 0))
            except ValueError:
                qty, sl, target = 0, 0.0, 0.0

            total_qty += qty
            sl_price = trade.avg_price * (1 - sl / 100.0) if qty > 0 else None
            target_price = trade.avg_price * (1 + target / 100.0) if qty > 0 else None

            sl_parts.append({
                "qty": qty,
                "sl_percent": sl,
                "sl_price": round(sl_price, 2) if sl_price is not None else None,
                "target_percent": target,
                "target_price": round(target_price, 2) if target_price is not None else None,
                "part_num": i,
            })

        if total_qty != trade.quantity:
            error = f"Total quantity entered ({total_qty}) does not match trade quantity ({trade.quantity})."
            return render_template(
                config['detail_template'],
                trade=trade_data,
                error=error,
                sl_parts=sl_parts,
                parts=parts,
                symbol=symbol,
                pivot_data=pivot_ui or {},
                calc_type=calc_type,
            )

        return render_template(
            config['detail_template'],
            trade=trade_data,
            sl_parts=sl_parts,
            parts=parts,
            symbol=symbol,
            pivot_data=pivot_ui or {},
            calc_type=calc_type,
        )

    return render_template(
        config['detail_template'],
        trade=trade_data,
        symbol=symbol,
        pivot_data=pivot_ui or {},
        calc_type=calc_type,
    )

# Keep original detail route for backward compatibility
@app.route("/detail/<int:trade_id>", methods=["GET", "POST"])
@login_required
def detail_trade(trade_id):
    return detail_universal_trade('intraday', trade_id)

@app.route("/api/single-day")
def api_single_day():
    symbol = (request.args.get("symbol") or "").strip()
    sec_id = (request.args.get("sec_id") or "").strip()

    if not sec_id:
        if not symbol:
            return jsonify({"ok": False, "error": "Need symbol or sec_id"}), 400
        resolved = resolve_input(symbol)
        if not resolved:
            return jsonify({"ok": False, "error": "Symbol not found"}), 404
        if isinstance(resolved, tuple):
            _, _, sec_id = resolved
        elif isinstance(resolved, list) and len(resolved) > 0:
            sec_id = resolved[0]['sec_id']

    day = last_completed_trading_day()
    try:
        data_result = fetch_intraday_ohlc(sec_id, day)
        data = data_result["data"]
        return jsonify({
            "ok": True,
            "date": day.strftime("%Y-%m-%d"),
            "rows": len(data),
            "data": data,
            "securityId": sec_id
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
@app.route("/api/pivots/fibo")
def api_pivots_fibo():
    symbol = (request.args.get("symbol") or "").strip()
    sec_id = (request.args.get("sec_id") or "").strip()

    if not sec_id:
        if not symbol:
            return jsonify({"ok": False, "error": "Need symbol or sec_id"}), 400
        resolved = resolve_input(symbol)
        if not resolved:
            return jsonify({"ok": False, "error": "Symbol not found"}), 404
        if isinstance(resolved, tuple):
            _, _, sec_id = resolved
        elif isinstance(resolved, list) and len(resolved) > 0:
            sec_id = resolved[0]['sec_id']

    res = api_pivots_last_internal(sec_id)
    if not res.get("ok"):
        return jsonify(res), 500
    return jsonify(res)
@app.route("/api/pivots/last")
def api_pivots_last():
    # keep the same endpoint but forward to fibo logic for backward compatibility
    symbol = (request.args.get("symbol") or "").strip()
    sec_id = (request.args.get("sec_id") or "").strip()

    if not sec_id:
        if not symbol:
            return jsonify({"ok": False, "error": "Need symbol or sec_id"}), 400
        resolved = resolve_input(symbol)
        if not resolved:
            return jsonify({"ok": False, "error": "Symbol not found"}), 404
        if isinstance(resolved, tuple):
            _, _, sec_id = resolved
        elif isinstance(resolved, list) and len(resolved) > 0:
            sec_id = resolved[0]['sec_id']

    res = api_pivots_last_internal(sec_id)
    if not res.get("ok"):
        return jsonify(res), 500
    return jsonify(res)


# ------------------------------------------------------------------------------
# Stock Search and Live Price Routes
# ------------------------------------------------------------------------------
@app.route("/search-stocks", methods=["POST"])
def search_stocks():
    symbol_input = request.form.get("symbol")
    if not symbol_input:
        return jsonify({"error": "Please enter a symbol"})
    
    result = resolve_input(symbol_input)
    
    if isinstance(result, tuple):
        symbol, display, sec_id = result
        return jsonify({
            "exact_match": True,
            "symbol": symbol,
            "display": display,
            "sec_id": sec_id
        })
    
    if isinstance(result, list) and len(result) > 0:
        return jsonify({
            "exact_match": False,
            "matches": [
                {"symbol": m["symbol"], "display": m["display"], "sec_id": m["sec_id"]}
                for m in result
            ]
        })

    
    return jsonify({"error": "Symbol not found"})

@app.route("/get-price/<symbol>")
def get_price(symbol):
    """Get live price for a symbol"""
    if not DHAN_ACCESS_TOKEN:
        return jsonify({"error": "DHAN API not configured"}), 500
        
    price_data = get_live_price(symbol)
    if 'error' in price_data:
        return jsonify({"error": price_data['error']}), 400
    return jsonify(price_data)

@app.route("/get-market-depth/<symbol>")
def get_market_depth_route(symbol):
    # First resolve the symbol to get security ID
    resolved = resolve_input(symbol)
    if not resolved:
        return jsonify({"error": "Symbol not found"})
        
    if isinstance(resolved, tuple):
        _, _, sec_id = resolved
    elif isinstance(resolved, list) and len(resolved) > 0:
        sec_id = resolved[0]['sec_id']
    else:
        return jsonify({"error": "Symbol not found"})
    
    depth_data = get_market_depth(sec_id)
    if depth_data:
        return jsonify(depth_data)
    return jsonify({"error": "Could not fetch market depth"})

# ------------------------------------------------------------------------------
# Stock Analysis Route (from dhan.py)
# ------------------------------------------------------------------------------
@app.route("/stock-analysis")
@login_required
def stock_analysis():
    symbol = request.args.get("symbol")
    if not symbol:
        return render_template("stock_analysis.html", error="Please provide a symbol")
    
    # Resolve the symbol
    resolved = resolve_input(symbol)
    if not resolved:
        return render_template("stock_analysis.html", error="Symbol not found")
    
    if isinstance(resolved, tuple):
        symbol, display, sec_id = resolved
    elif isinstance(resolved, list) and len(resolved) > 0:
        symbol = resolved[0]['symbol']
        display = resolved[0]['display']
        sec_id = resolved[0]['sec_id']
    else:
        return render_template("stock_analysis.html", error="Symbol not found")
    
    # Get market depth
    market_depth = get_market_depth(sec_id) if is_market_open() else None
    
    return render_template("stock_analysis.html",
                           symbol=symbol,
                           display=display,
                           sec_id=sec_id,
                           market_open=is_market_open(),
                           market_depth=market_depth)

# ================== PIVOT POINTS (LAST TRADING DAY, DHAN API) ==================
# import pandas as pd  # Removed for deployment compatibility
from datetime import date as _date, time as _time, datetime as _dt, timedelta as _td

# NSE timings
_NSE_OPEN  = (9, 15)
_NSE_CLOSE = (15, 30)

# 2025 NSE Holidays (expand as needed)
_NSE_HOLIDAYS = {
    "2025-01-26","2025-03-14","2025-03-31","2025-04-14","2025-04-18",
    "2025-05-01","2025-08-15","2025-10-02","2025-10-21","2025-10-31","2025-11-12","2025-12-25",
}

def _is_valid_trading_day(d: _date) -> bool:
    return _is_trading_day(d)

def _previous_trading_day(d: _date) -> _date:
    d = d - _td(days=1)
    while not _is_trading_day(d):
        d -= _td(days=1)
    return d

def _market_closed_for_today(now_ist=None) -> bool:
    now = now_ist or _dt.now(IST)
    ch, cm = _NSE_CLOSE
    close_dt = now.replace(hour=ch, minute=cm, second=0, microsecond=0)
    return now >= close_dt

def last_completed_trading_day(now_ist=None) -> _date:
    """
    अगर आज ट्रेडिंग डे है और market बंद हो चुका है → आज
    वरना → पिछला valid trading day
    """
    now = now_ist or _dt.now(IST)
    today = now.date()
    if _is_trading_day(today) and _market_closed_for_today(now):
        return today
    return _previous_trading_day(today)

def _is_trading_day(d: _date) -> bool:
    if d.weekday() >= 5:  # Sat/Sun
        return False
    return d.strftime("%Y-%m-%d") not in _NSE_HOLIDAYS

def last_trading_day(today_ist=None) -> _date:
    now_ist = today_ist or _dt.now(IST)
    d = now_ist.date() - _td(days=1)
    while not _is_trading_day(d):
        d -= _td(days=1)
    return d

def _day_window_ist(day: _date):
    """Return from/to datetime for given day (in IST)."""
    o_h, o_m = _NSE_OPEN
    c_h, c_m = _NSE_CLOSE
    base = _dt.combine(day, _time.min)
    start = IST.localize(base.replace(hour=o_h, minute=o_m))
    end   = IST.localize(base.replace(hour=c_h, minute=c_m))
    return start, end

def fetch_intraday_ohlc(sec_id: str, day: _date):
    """
    Fetch exactly one day's intraday candles (5m). If empty, fallback to daily OHLC.
    Uses naive 'YYYY-MM-DD HH:MM:SS' timestamps to avoid DH-905 parsing issues.
    """
    # 1) Compute single-day IST window and clamp to market hours
    start_ist, end_ist = _day_window_ist(day)

    # Guard: never request future times
    now_ist = _dt.now(IST)
    if end_ist > now_ist:
        end_ist = now_ist
        # अगर market अभी open है तो भी start 09:15 पर ही रहेगा (single-day)
        if end_ist < start_ist:
            # safety: same minute
            end_ist = start_ist + _td(minutes=1)

    # Format WITHOUT timezone — Dhan parsing is more reliable this way
    from_str = end_str = None
    from_str = start_ist.strftime("%Y-%m-%d %H:%M:%S")
    end_str  = end_ist.strftime("%Y-%m-%d %H:%M:%S")

    url_i = f"{DHAN_BASE_URL}/v2/charts/intraday"
    headers = {"Content-Type": "application/json", "access-token": DHAN_ACCESS_TOKEN}
    if DHAN_CLIENT_ID:
        headers["client-id"] = DHAN_CLIENT_ID

    payload = {
        "securityId": str(sec_id),
        "exchangeSegment": "NSE_EQ",
        "instrument": "EQUITY",
        "interval": "5",
        "oi": False,
        "fromDate": from_str,
        "toDate":   end_str,
    }

    last_err = None
    try:
        r = requests.post(url_i, headers=headers, json=payload, timeout=15)
        if r.status_code != 200:
            # यहाँ error को warning के रूप में रखें ताकि log noisy न हो
            last_err = f"HTTP {r.status_code}: {r.text}"
            app.logger.warning(f"[INTRADAY] Response error: {last_err}")
        else:
            js = r.json()
            data = js.get("data", js)

            if data:
                # Process data without pandas
                processed_data = []
                for row in data:
                    try:
                        # Convert numeric fields
                        for field in ["open", "high", "low", "close"]:
                            if field in row and row[field] is not None:
                                row[field] = float(row[field])
                        
                        # Only include rows with valid OHLC data
                        if all(field in row and row[field] is not None for field in ["open", "high", "low", "close"]):
                            processed_data.append(row)
                    except (ValueError, TypeError):
                        continue

                if processed_data:
                    # Calculate H, L, C without pandas
                    H = max(row["high"] for row in processed_data)
                    L = min(row["low"] for row in processed_data)
                    C = processed_data[-1]["close"]
                    app.logger.debug(f"[INTRADAY] OHLC sec_id={sec_id} date={day}: H={H}, L={L}, C={C}")
                    # Zero-range check (illiquid / holiday glitch)
                    if H == L == C:
                        app.logger.warning(f"[INTRADAY] Zero-range OHLC for sec_id={sec_id} on {day}")
                    # Return data in dict format instead of DataFrame
                    return {"data": processed_data, "high": H, "low": L, "close": C}
            else:
                app.logger.warning(f"[INTRADAY] Empty intraday for sec_id={sec_id} on {day}")
    except Exception as e:
        last_err = str(e)
        app.logger.error(f"[INTRADAY] Exception sec_id={sec_id} on {day}: {last_err}")

    # 2) Fallback to daily 1D bar (same day)
    url_d = f"{DHAN_BASE_URL}/v2/charts/historical"
    try:
        payload_d = {
            "securityId": str(sec_id),
            "exchangeSegment": "NSE_EQ",
            "instrument": "EQUITY",
            "interval": "1D",
            "oi": False,
            "fromDate": day.strftime("%Y-%m-%d"),
            "toDate":   day.strftime("%Y-%m-%d"),
        }
        r = requests.post(url_d, headers=headers, json=payload_d, timeout=15)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
        js = r.json()
        data = js.get("data", js)
        if not data:
            raise RuntimeError("Daily data empty")

        # Process daily data without pandas
        processed_data = []
        for row in data:
            try:
                for field in ["open", "high", "low", "close"]:
                    if field in row and row[field] is not None:
                        row[field] = float(row[field])
                if all(field in row for field in ["open", "high", "low", "close"]):
                    processed_data.append(row)
            except (ValueError, TypeError):
                continue
        
        if not processed_data:
            raise RuntimeError("No valid daily data")
        
        # Calculate OHLC values
        H = max(row["high"] for row in processed_data)
        L = min(row["low"] for row in processed_data)
        C = processed_data[-1]["close"]
        
        app.logger.debug(f"[DAILY] Fallback OHLC sec_id={sec_id} date={day}")
        return {"data": processed_data, "high": H, "low": L, "close": C}
    except Exception as e:
        raise RuntimeError(f"Fetch failed: {last_err or e}")


def classic_pivots(H: float, L: float, C: float):
    """Classic floor pivots (rounded to 2 decimals)."""
    PP = (H + L + C) / 3
    R1 = 2*PP - L
    S1 = 2*PP - H
    R2 = PP + (H - L)
    S2 = PP - (H - L)
    R3 = H + 2*(PP - L)
    S3 = L - 2*(H - PP)
    rnd = lambda x: round(float(x), 2)
    return {"P":rnd(PP),"R1":rnd(R1),"R2":rnd(R2),"R3":rnd(R3),
            "S1":rnd(S1),"S2":rnd(S2),"S3":rnd(S3)}

def pivots_to_ui_percentages(avg_price: float, trade_type: str, levels: dict[str, float]) -> dict:
    """
    Convert absolute pivots to % distances for UI with 5x leverage.
    """
    cap_per_share = avg_price/5 if avg_price else 0
    def pct(level): return round(abs(level-avg_price)/(cap_per_share or 1)*100,2)
    out={}
    labels={"P":"Pivot (P)","R1":"Resistance 1 (R1)","R2":"Resistance 2 (R2)",
            "R3":"Resistance 3 (R3)","S1":"Support 1 (S1)","S2":"Support 2 (S2)",
            "S3":"Support 3 (S3)"}
    for k,v in levels.items():
        out[k]={"slPct":pct(v),"tgtPct":pct(v),"label":labels.get(k,k),"price":round(v,2)}
    return out
# ================== /PIVOT POINTS ==================

# ------------------------------------------------------------------------------
# Preview Template Management
# ------------------------------------------------------------------------------
class PreviewTemplate(db.Model):
    __tablename__ = "preview_templates"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    instrument = db.Column(db.String(50), nullable=False)
    strike = db.Column(db.String(20), nullable=True)
    payload = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

@app.route('/api/templates', methods=['POST'])
@login_required
def save_template():
    """Save split preview template"""
    try:
        data = request.get_json()
        instrument = data.get('instrument')
        strike = data.get('strike')
        payload = data.get('payload')
        
        print(f"[SAVE_TEMPLATE] User: {current_user.id}, Instrument: {instrument}, Strike: {strike}")
        
        if not instrument or not payload:
            print(f"[SAVE_TEMPLATE] Missing data - instrument: {bool(instrument)}, payload: {bool(payload)}")
            return jsonify({'success': False, 'error': 'Missing instrument or payload'}), 400
        
        # Delete existing template for this user/instrument/strike
        deleted_count = PreviewTemplate.query.filter_by(
            user_id=current_user.id,
            instrument=instrument,
            strike=strike
        ).delete()
        print(f"[SAVE_TEMPLATE] Deleted {deleted_count} existing templates")
        
        # Create new template
        template = PreviewTemplate(
            user_id=current_user.id,
            instrument=instrument,
            strike=strike,
            payload=payload
        )
        
        db.session.add(template)
        db.session.commit()
        
        print(f"[SAVE_TEMPLATE] Saved template with ID: {template.id}")
        
        return jsonify({
            'status': 'ok',
            'template_id': template.id,
            'saved_at': template.created_at.isoformat()
        }), 201
    except Exception as e:
        db.session.rollback()
        print(f"[SAVE_TEMPLATE] Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/templates', methods=['GET'])
@login_required
def get_templates():
    """Get templates for instrument/strike"""
    try:
        instrument = request.args.get('instrument')
        strike = request.args.get('strike')
        
        print(f"[GET_TEMPLATES] User: {current_user.id}, Instrument: {instrument}, Strike: {strike}")
        
        if not instrument:
            print(f"[GET_TEMPLATES] No instrument provided, returning empty")
            return jsonify([]), 200
        
        q = PreviewTemplate.query.filter_by(user_id=current_user.id, instrument=instrument)
        if strike:
            q = q.filter_by(strike=strike)
        
        templates = q.order_by(PreviewTemplate.created_at.desc()).all()
        print(f"[GET_TEMPLATES] Found {len(templates)} templates")
        
        result = [
            {
                'id': t.id,
                'payload': t.payload,
                'created_at': t.created_at.isoformat()
            } for t in templates
        ]
        
        return jsonify(result), 200
    except Exception as e:
        print(f"[GET_TEMPLATES] Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/templates/<int:tid>', methods=['DELETE'])
@login_required
def delete_template(tid):
    """Delete a specific template"""
    try:
        template = PreviewTemplate.query.filter_by(id=tid, user_id=current_user.id).first()
        if not template:
            return jsonify({'success': False, 'error': 'Template not found'}), 404
        
        db.session.delete(template)
        db.session.commit()
        
        return jsonify({
            'status': 'deleted',
            'template_id': tid
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# AI Plan Templates
class AIPlanTemplate(db.Model):
    __tablename__ = "ai_plan_templates"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    instrument = db.Column(db.String(50), nullable=False)
    strike = db.Column(db.String(20), nullable=True)
    payload = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

@app.route('/api/ai_plans', methods=['POST'])
@login_required
def save_ai_plan():
    """Save AI plan as template"""
    try:
        data = request.get_json()
        instrument = data.get('instrument')
        strike = data.get('strike')
        payload = data.get('payload')
        
        if not instrument or not payload:
            return jsonify({'success': False, 'error': 'Missing instrument or payload'}), 400
        
        # Delete existing AI plan for this user/instrument/strike
        AIPlanTemplate.query.filter_by(
            user_id=current_user.id,
            instrument=instrument,
            strike=strike
        ).delete()
        
        # Create new AI plan template
        template = AIPlanTemplate(
            user_id=current_user.id,
            instrument=instrument,
            strike=strike,
            payload=payload
        )
        
        db.session.add(template)
        db.session.commit()
        
        return jsonify({
            'status': 'ok',
            'template_id': template.id,
            'saved_at': template.created_at.isoformat()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ai_plans', methods=['GET'])
@login_required
def get_ai_plans():
    """Get AI plans for instrument/strike"""
    try:
        instrument = request.args.get('instrument')
        strike = request.args.get('strike')
        
        if not instrument:
            return jsonify([]), 200
        
        q = AIPlanTemplate.query.filter_by(user_id=current_user.id, instrument=instrument)
        if strike:
            q = q.filter_by(strike=strike)
        
        templates = q.order_by(AIPlanTemplate.created_at.desc()).all()
        
        return jsonify([
            {
                'id': t.id,
                'payload': t.payload,
                'created_at': t.created_at.isoformat()
            } for t in templates
        ]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ------------------------------------------------------------------------------
# Split Management API Routes
# ------------------------------------------------------------------------------
@app.route('/api/trades/<int:trade_id>/splits', methods=['GET'])
@login_required
def get_trade_splits(trade_id):
    """Get all splits for a trade"""
    try:
        splits = TradeSplit.query.filter_by(trade_id=trade_id).all()
        return jsonify({
            'success': True,
            'splits': [{
                'id': split.id,
                'preview': split.preview,
                'qty': split.qty,
                'sl_price': float(split.sl_price),
                'target_price': float(split.target_price),
                'created_at': split.created_at.isoformat()
            } for split in splits]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trades/<int:trade_id>/splits', methods=['POST'])
@login_required
def create_trade_splits(trade_id):
    """Create new splits for a trade"""
    try:
        data = request.get_json()
        splits_data = data.get('splits', [])
        
        # Delete existing splits for this trade
        TradeSplit.query.filter_by(trade_id=trade_id).delete()
        
        # Create new splits
        created_splits = []
        for split_data in splits_data:
            split = TradeSplit(
                trade_id=trade_id,
                preview=split_data['preview'],
                qty=split_data['qty'],
                sl_price=split_data['sl'],
                target_price=split_data['target']
            )
            db.session.add(split)
            created_splits.append(split)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'splits': [{
                'id': split.id,
                'preview': split.preview,
                'qty': split.qty,
                'sl_price': float(split.sl_price),
                'target_price': float(split.target_price)
            } for split in created_splits]
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trades/<int:trade_id>/splits/<int:split_id>', methods=['PATCH'])
@login_required
def update_trade_split(trade_id, split_id):
    """Update a specific split"""
    try:
        split = TradeSplit.query.filter_by(id=split_id, trade_id=trade_id).first()
        if not split:
            return jsonify({'success': False, 'error': 'Split not found'}), 404
        
        data = request.get_json()
        
        if 'sl_price' in data:
            split.sl_price = data['sl_price']
        if 'target_price' in data:
            split.target_price = data['target_price']
        
        split.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'split': {
                'id': split.id,
                'preview': split.preview,
                'qty': split.qty,
                'sl_price': float(split.sl_price),
                'target_price': float(split.target_price)
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ------------------------------------------------------------------------------
# Misc
# ------------------------------------------------------------------------------
# Universal add-to-journal route
@app.route('/add_<calc_type>_to_journal', methods=['POST'])
@login_required
def add_universal_to_journal(calc_type):
    if calc_type not in CALCULATOR_CONFIG:
        return jsonify({'success': False, 'error': 'Invalid calculator type'}), 400
    
    try:
        from journal import Trade
        
        data = request.get_json()
        trade_id = data.get('trade_id')
        
        if not trade_id:
            return jsonify({'success': False, 'error': 'Trade ID is required'}), 400
        
        config = CALCULATOR_CONFIG[calc_type]
        model = config['model']
        trade = model.query.get_or_404(trade_id)
        
        # Calculate PnL for journal (planned trade, so PnL = 0)
        pnl = 0.0
        result = 'planned'
        
        # Create journal Trade entry
        journal_trade = Trade(
            symbol=trade.symbol or 'UNKNOWN',
            entry_price=trade.avg_price,
            exit_price=trade.target_price,
            quantity=trade.quantity,
            date=datetime.now(timezone.utc),
            result=result,
            pnl=pnl,
            notes=f"{calc_type.upper()}: {trade.comment or ''}",
            trade_type='long' if trade.trade_type == 'buy' else 'short',
            risk=trade.total_risk,
            reward=trade.total_reward,
            strategy_id=None
        )
        
        db.session.add(journal_trade)
        db.session.commit()
        
        app.logger.info(f"{calc_type.title()} trade {trade_id} added to journal with ID: {journal_trade.id}")
        
        return jsonify({
            'success': True, 
            'message': f'{calc_type.title()} trade added to journal successfully',
            'journal_trade_id': journal_trade.id
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error adding {calc_type} trade to journal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Add-to-journal routes for new calculators
@app.route('/add_fno_to_journal', methods=['POST'])
@login_required
def add_fno_to_journal():
    try:
        from journal import Trade
        
        data = request.get_json()
        trade_id = data.get('trade_id')
        
        if not trade_id:
            return jsonify({'success': False, 'error': 'Trade ID is required'}), 400
        
        trade = IntradayTrade.query.get_or_404(trade_id)
        
        journal_trade = Trade(
            symbol=trade.symbol or 'UNKNOWN',
            entry_price=trade.avg_price,
            exit_price=trade.target_price,
            quantity=trade.quantity,
            date=datetime.now(timezone.utc),
            result='planned',
            pnl=0.0,
            notes=f"F&O: {trade.comment or ''}",
            trade_type='long' if trade.trade_type == 'buy' else 'short',
            risk=trade.total_risk,
            reward=trade.total_reward,
            strategy_id=None
        )
        
        db.session.add(journal_trade)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'F&O trade added to journal successfully',
            'journal_trade_id': journal_trade.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/add_mtf_to_journal', methods=['POST'])
@login_required
def add_mtf_to_journal():
    try:
        from journal import Trade
        
        data = request.get_json()
        trade_id = data.get('trade_id')
        
        if not trade_id:
            return jsonify({'success': False, 'error': 'Trade ID is required'}), 400
        
        trade = IntradayTrade.query.get_or_404(trade_id)
        
        journal_trade = Trade(
            symbol=trade.symbol or 'UNKNOWN',
            entry_price=trade.avg_price,
            exit_price=trade.target_price,
            quantity=trade.quantity,
            date=datetime.now(timezone.utc),
            result='planned',
            pnl=0.0,
            notes=f"MTF: {trade.comment or ''}",
            trade_type='long' if trade.trade_type == 'buy' else 'short',
            risk=trade.total_risk,
            reward=trade.total_reward,
            strategy_id=None
        )
        
        db.session.add(journal_trade)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'MTF trade added to journal successfully',
            'journal_trade_id': journal_trade.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/add_swing_to_journal', methods=['POST'])
@login_required
def add_swing_to_journal():
    try:
        from journal import Trade
        
        data = request.get_json()
        trade_id = data.get('trade_id')
        
        if not trade_id:
            return jsonify({'success': False, 'error': 'Trade ID is required'}), 400
        
        trade = IntradayTrade.query.get_or_404(trade_id)
        
        journal_trade = Trade(
            symbol=trade.symbol or 'UNKNOWN',
            entry_price=trade.avg_price,
            exit_price=trade.target_price,
            quantity=trade.quantity,
            date=datetime.now(timezone.utc),
            result='planned',
            pnl=0.0,
            notes=f"SWING: {trade.comment or ''}",
            trade_type='long' if trade.trade_type == 'buy' else 'short',
            risk=trade.total_risk,
            reward=trade.total_reward,
            strategy_id=None
        )
        
        db.session.add(journal_trade)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Swing trade added to journal successfully',
            'journal_trade_id': journal_trade.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/add_delivery_to_journal', methods=['POST'])
@login_required
def add_delivery_to_journal():
    try:
        from journal import Trade
        
        data = request.get_json()
        trade_id = data.get('trade_id')
        
        if not trade_id:
            return jsonify({'success': False, 'error': 'Trade ID is required'}), 400
        
        trade = IntradayTrade.query.get_or_404(trade_id)
        
        journal_trade = Trade(
            symbol=trade.symbol or 'UNKNOWN',
            entry_price=trade.avg_price,
            exit_price=trade.target_price,
            quantity=trade.quantity,
            date=datetime.now(timezone.utc),
            result='planned',
            pnl=0.0,
            notes=f"DELIVERY: {trade.comment or ''}",
            trade_type='long' if trade.trade_type == 'buy' else 'short',
            risk=trade.total_risk,
            reward=trade.total_reward,
            strategy_id=None
        )
        
        db.session.add(journal_trade)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Delivery trade added to journal successfully',
            'journal_trade_id': journal_trade.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# Enhanced calculator to journal integration
@app.route('/api/calculator/export_to_journal', methods=['POST'])
@login_required
def export_calculator_to_journal():
    """Export calculator results directly to journal"""
    try:
        from journal import Trade, Strategy
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['symbol', 'avg_price', 'quantity', 'trade_type', 'calculator_type']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        
        # Calculate PnL and result
        entry_price = float(data['avg_price'])
        exit_price = float(data.get('target_price', entry_price))
        quantity = int(data['quantity'])
        trade_type = data['trade_type']
        
        if trade_type == 'long':
            pnl = (exit_price - entry_price) * quantity
        else:
            pnl = (entry_price - exit_price) * quantity
        
        result = 'win' if pnl > 0 else ('loss' if pnl < 0 else 'breakeven')
        
        # Create journal trade
        journal_trade = Trade(
            symbol=data['symbol'].upper(),
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            date=datetime.strptime(data.get('date', datetime.now().strftime('%Y-%m-%d')), '%Y-%m-%d'),
            result=result,
            pnl=pnl,
            notes=f"Imported from {data['calculator_type'].upper()} Calculator\n{data.get('notes', '')}",
            trade_type=trade_type,
            risk=float(data.get('total_risk', 0)),
            reward=float(data.get('total_reward', 0)),
            strategy_id=int(data.get('strategy_id')) if data.get('strategy_id') else None
        )
        
        db.session.add(journal_trade)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Trade exported to journal successfully from {data["calculator_type"]} calculator',
            'journal_trade_id': journal_trade.id,
            'trade': {
                'id': journal_trade.id,
                'symbol': journal_trade.symbol,
                'pnl': journal_trade.pnl,
                'result': journal_trade.result
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# Get strategies for calculator dropdown
@app.route('/api/calculator/strategies', methods=['GET'])
@login_required
def get_calculator_strategies():
    """Get strategies for calculator export dropdown"""
    try:
        from journal import Strategy
        strategies = Strategy.query.filter_by(status='active').all()
        return jsonify({
            'success': True,
            'strategies': [{
                'id': s.id,
                'name': s.name,
                'description': s.description
            } for s in strategies]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Keep original add-to-journal route for backward compatibility
@app.route('/add-to-journal', methods=['POST'])
@login_required
def add_to_journal():
    return add_universal_to_journal('intraday')

# New calculator routes
@app.route('/fo_calculator', methods=['GET', 'POST'])
@subscription_required
def fo_calculator():
    if request.method == 'POST':
        try:
            avg_price = float(request.form['avgPrice'])
            quantity = int(request.form['quantity'])
            expected_return = float(request.form['expectedReturn'])
            risk_percent = float(request.form['riskPercent'])
            comment = request.form.get('comment', '').strip()
            trade_type = request.form.get('trade_type', 'buy').strip().lower()
            lot_size = int(request.form.get('lot_size', 1))
            
            # F&O uses no leverage - capital = avg_price * quantity
            capital_used = avg_price * quantity
            reward_per_share = (expected_return / 100.0) * avg_price
            risk_per_share = (risk_percent / 100.0) * avg_price
            
            if trade_type == 'buy':
                target_price = avg_price + reward_per_share
                stop_loss_price = avg_price - risk_per_share
            else:
                target_price = avg_price - reward_per_share
                stop_loss_price = avg_price + risk_per_share
            
            total_reward = reward_per_share * quantity
            total_risk = risk_per_share * quantity
            rr_ratio = (reward_per_share / risk_per_share) if risk_per_share != 0 else 0.0
            
            result = {
                'trade_type': trade_type,
                'avg_price': avg_price,
                'quantity': quantity,
                'expected_return': expected_return,
                'risk_percent': risk_percent,
                'capital_used': round(capital_used, 2),
                'target_price': round(target_price, 2),
                'stop_loss_price': round(stop_loss_price, 2),
                'total_reward': round(total_reward, 2),
                'total_risk': round(total_risk, 2),
                'rr_ratio': round(rr_ratio, 2),
                'comment': comment,
                'lot_size': lot_size
            }
            return render_template('fo_calculator.html', result=result)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return render_template('fo_calculator.html')

@app.route('/mtf_calculator', methods=['GET', 'POST'])
@subscription_required
def mtf_calculator():
    if request.method == 'POST':
        try:
            avg_price = float(request.form['avgPrice'])
            quantity = int(request.form['quantity'])
            expected_return = float(request.form['expectedReturn'])
            risk_percent = float(request.form['riskPercent'])
            comment = request.form.get('comment', '').strip()
            trade_type = request.form.get('trade_type', 'buy').strip().lower()
            leverage = float(request.form.get('leverage', 1))
            
            if leverage <= 0:
                leverage = 1
            
            capital_used = (avg_price * quantity) / leverage
            reward_per_share = (expected_return / 100.0) * avg_price
            risk_per_share = (risk_percent / 100.0) * avg_price
            
            if trade_type == 'buy':
                target_price = avg_price + reward_per_share
                stop_loss_price = avg_price - risk_per_share
            else:
                target_price = avg_price - reward_per_share
                stop_loss_price = avg_price + risk_per_share
            
            total_reward = reward_per_share * quantity
            total_risk = risk_per_share * quantity
            rr_ratio = (reward_per_share / risk_per_share) if risk_per_share != 0 else 0.0
            
            result = {
                'trade_type': trade_type,
                'avg_price': avg_price,
                'quantity': quantity,
                'expected_return': expected_return,
                'risk_percent': risk_percent,
                'capital_used': round(capital_used, 2),
                'target_price': round(target_price, 2),
                'stop_loss_price': round(stop_loss_price, 2),
                'total_reward': round(total_reward, 2),
                'total_risk': round(total_risk, 2),
                'rr_ratio': round(rr_ratio, 2),
                'comment': comment,
                'leverage': leverage
            }
            return render_template('mtf_calculator.html', result=result)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return render_template('mtf_calculator.html')

@app.route('/swing_calculator', methods=['GET', 'POST'])
@subscription_required
def swing_calculator():
    if request.method == 'POST':
        try:
            avg_price = float(request.form['avgPrice'])
            quantity = int(request.form['quantity'])
            expected_return = float(request.form['expectedReturn'])
            risk_percent = float(request.form['riskPercent'])
            comment = request.form.get('comment', '').strip()
            trade_type = request.form.get('trade_type', 'buy').strip().lower()
            
            # Swing uses no leverage
            capital_used = avg_price * quantity
            reward_per_share = (expected_return / 100.0) * avg_price
            risk_per_share = (risk_percent / 100.0) * avg_price
            
            if trade_type == 'buy':
                target_price = avg_price + reward_per_share
                stop_loss_price = avg_price - risk_per_share
            else:
                target_price = avg_price - reward_per_share
                stop_loss_price = avg_price + risk_per_share
            
            total_reward = reward_per_share * quantity
            total_risk = risk_per_share * quantity
            rr_ratio = (reward_per_share / risk_per_share) if risk_per_share != 0 else 0.0
            
            result = {
                'trade_type': trade_type,
                'avg_price': avg_price,
                'quantity': quantity,
                'expected_return': expected_return,
                'risk_percent': risk_percent,
                'capital_used': round(capital_used, 2),
                'target_price': round(target_price, 2),
                'stop_loss_price': round(stop_loss_price, 2),
                'total_reward': round(total_reward, 2),
                'total_risk': round(total_risk, 2),
                'rr_ratio': round(rr_ratio, 2),
                'comment': comment
            }
            return render_template('swing_calculator.html', result=result)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return render_template('swing_calculator.html')

@app.route('/delivery_calculator', methods=['GET', 'POST'])
@subscription_required
def delivery_calculator():
    if request.method == 'POST':
        try:
            avg_price = float(request.form['avgPrice'])
            quantity = int(request.form['quantity'])
            expected_return = float(request.form['expectedReturn'])
            risk_percent = float(request.form['riskPercent'])
            comment = request.form.get('comment', '').strip()
            trade_type = request.form.get('trade_type', 'buy').strip().lower()
            
            # Delivery uses no leverage
            capital_used = avg_price * quantity
            reward_per_share = (expected_return / 100.0) * avg_price
            risk_per_share = (risk_percent / 100.0) * avg_price
            
            if trade_type == 'buy':
                target_price = avg_price + reward_per_share
                stop_loss_price = avg_price - risk_per_share
            else:
                target_price = avg_price - reward_per_share
                stop_loss_price = avg_price + risk_per_share
            
            total_reward = reward_per_share * quantity
            total_risk = risk_per_share * quantity
            rr_ratio = (reward_per_share / risk_per_share) if risk_per_share != 0 else 0.0
            
            result = {
                'trade_type': trade_type,
                'avg_price': avg_price,
                'quantity': quantity,
                'expected_return': expected_return,
                'risk_percent': risk_percent,
                'capital_used': round(capital_used, 2),
                'target_price': round(target_price, 2),
                'stop_loss_price': round(stop_loss_price, 2),
                'total_reward': round(total_reward, 2),
                'total_risk': round(total_risk, 2),
                'rr_ratio': round(rr_ratio, 2),
                'comment': comment
            }
            return render_template('delivery_calculator.html', result=result)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return render_template('delivery_calculator.html')

# Saved pages routes
@app.route('/saved_fno')
@subscription_required
def saved_fno():
    try:
        # F&O trades are identified by having lot_size field set
        trades = IntradayTrade.query.filter(
            IntradayTrade.lot_size.isnot(None),
            IntradayTrade.leverage.is_(None)  # Exclude MTF trades that might have lot_size
        ).order_by(IntradayTrade.id.desc()).all()
        normalized_trades = [normalize_trade(trade) for trade in trades]
        return render_template('saved_fno.html', trades=normalized_trades)
    except Exception as e:
        app.logger.error(f"Error fetching F&O trades: {e}")
        return render_template('saved_fno.html', trades=[])

@app.route('/saved_mtf')
@subscription_required
def saved_mtf():
    try:
        trades = IntradayTrade.query.filter(IntradayTrade.leverage.isnot(None)).order_by(IntradayTrade.id.desc()).all()
        normalized_trades = [normalize_trade(trade) for trade in trades]
        return render_template('saved_mtf.html', trades=normalized_trades)
    except:
        return render_template('saved_mtf.html', trades=[])

@app.route('/saved_swing')
@subscription_required
def saved_swing():
    try:
        trades = IntradayTrade.query.filter(IntradayTrade.leverage.is_(None), IntradayTrade.lot_size.is_(None)).order_by(IntradayTrade.id.desc()).all()
        normalized_trades = [normalize_trade(trade) for trade in trades]
        return render_template('saved_swing.html', trades=normalized_trades)
    except:
        return render_template('saved_swing.html', trades=[])

@app.route('/saved_delivery')
@subscription_required
def saved_delivery():
    try:
        trades = IntradayTrade.query.filter(IntradayTrade.leverage.is_(None), IntradayTrade.lot_size.is_(None)).order_by(IntradayTrade.id.desc()).all()
        normalized_trades = [normalize_trade(trade) for trade in trades]
        return render_template('saved_delivery.html', trades=normalized_trades)
    except:
        return render_template('saved_delivery.html', trades=[])

# Detail routes
@app.route('/fno/detail/<int:trade_id>', methods=['GET', 'POST'])
@login_required
def fno_detail(trade_id):
    trade = IntradayTrade.query.get_or_404(trade_id)
    
    # Resolve symbol/derivative name
    symbol = getattr(trade, 'derivative_name', None) or trade.symbol or 'UNKNOWN'
    
    trade_data = {
        'id': trade.id,
        'avg_price': trade.avg_price,
        'quantity': trade.quantity,
        'expected_return': trade.expected_return,
        'risk_percent': trade.risk_percent,
        'capital_used': trade.capital_used,
        'target_price': trade.target_price,
        'stop_loss_price': trade.stop_loss_price,
        'total_reward': trade.total_reward,
        'total_risk': trade.total_risk,
        'rr_ratio': trade.rr_ratio,
        'comment': trade.comment,
        'trade_type': trade.trade_type,
        'symbol': symbol,
        'derivative_name': getattr(trade, 'derivative_name', None),
        'lot_size': getattr(trade, 'lot_size', 25),
        'status': getattr(trade, 'status', 'open'),
        'timestamp': trade.timestamp
    }
    
    # Handle position splitting
    if request.method == 'POST':
        try:
            parts = int(request.form.get('parts', 1))
        except ValueError:
            parts = 1

        sl_parts, total_qty = [], 0
        for i in range(1, parts + 1):
            try:
                qty = int(request.form.get(f'qty_{i}', 0))
                sl = float(request.form.get(f'sl_{i}', 0))
                target = float(request.form.get(f'target_{i}', 0))
            except ValueError:
                qty, sl, target = 0, 0.0, 0.0

            total_qty += qty
            sl_price = trade.avg_price * (1 - sl / 100.0) if qty > 0 else None
            target_price = trade.avg_price * (1 + target / 100.0) if qty > 0 else None

            sl_parts.append({
                'qty': qty,
                'sl_percent': sl,
                'sl_price': round(sl_price, 2) if sl_price is not None else None,
                'target_percent': target,
                'target_price': round(target_price, 2) if target_price is not None else None,
                'part_num': i,
            })

        if total_qty != trade.quantity:
            error = f'Total quantity entered ({total_qty}) does not match trade quantity ({trade.quantity}).'
            return render_template('detail_fno.html', trade=trade_data, error=error, sl_parts=sl_parts, parts=parts)

        return render_template('detail_fno.html', trade=trade_data, sl_parts=sl_parts, parts=parts)
    
    return render_template('detail_fno.html', trade=trade_data)

@app.route('/mtf/detail/<int:trade_id>')
@login_required
def mtf_detail(trade_id):
    trade = IntradayTrade.query.get_or_404(trade_id)
    symbol = trade.symbol or 'UNKNOWN'
    trade_data = {
        'id': trade.id,
        'avg_price': trade.avg_price,
        'quantity': trade.quantity,
        'expected_return': trade.expected_return,
        'risk_percent': trade.risk_percent,
        'capital_used': trade.capital_used,
        'target_price': trade.target_price,
        'stop_loss_price': trade.stop_loss_price,
        'total_reward': trade.total_reward,
        'total_risk': trade.total_risk,
        'rr_ratio': trade.rr_ratio,
        'comment': trade.comment,
        'trade_type': trade.trade_type,
        'symbol': symbol,
        'status': getattr(trade, 'status', 'open'),
        'timestamp': trade.timestamp,
        'ltp': trade.avg_price
    }
    return render_template('detail_mtf.html', trade=trade_data, symbol=symbol)

@app.route('/swing/detail/<int:trade_id>')
@login_required
def swing_detail(trade_id):
    trade = IntradayTrade.query.get_or_404(trade_id)
    symbol = trade.symbol or 'UNKNOWN'
    trade_data = {
        'id': trade.id,
        'avg_price': trade.avg_price,
        'quantity': trade.quantity,
        'expected_return': trade.expected_return,
        'risk_percent': trade.risk_percent,
        'capital_used': trade.capital_used,
        'target_price': trade.target_price,
        'stop_loss_price': trade.stop_loss_price,
        'total_reward': trade.total_reward,
        'total_risk': trade.total_risk,
        'rr_ratio': trade.rr_ratio,
        'comment': trade.comment,
        'trade_type': trade.trade_type,
        'symbol': symbol,
        'status': getattr(trade, 'status', 'open'),
        'timestamp': trade.timestamp,
        'ltp': trade.avg_price
    }
    return render_template('detail_swing.html', trade=trade_data, symbol=symbol)

@app.route('/delivery/detail/<int:trade_id>')
@login_required
def delivery_detail(trade_id):
    trade = IntradayTrade.query.get_or_404(trade_id)
    symbol = trade.symbol or 'UNKNOWN'
    trade_data = {
        'id': trade.id,
        'avg_price': trade.avg_price,
        'quantity': trade.quantity,
        'expected_return': trade.expected_return,
        'risk_percent': trade.risk_percent,
        'capital_used': trade.capital_used,
        'target_price': trade.target_price,
        'stop_loss_price': trade.stop_loss_price,
        'total_reward': trade.total_reward,
        'total_risk': trade.total_risk,
        'rr_ratio': trade.rr_ratio,
        'comment': trade.comment,
        'trade_type': trade.trade_type,
        'symbol': symbol,
        'status': getattr(trade, 'status', 'open'),
        'timestamp': trade.timestamp,
        'ltp': trade.avg_price
    }
    return render_template('detail_delivery.html', trade=trade_data, symbol=symbol)

# Save routes for new calculators
@app.route('/save_fno_result', methods=['POST'])
@login_required
def save_fno_result():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data received'}), 400
    
    try:
        trade_data = {
            'user_id': current_user.id,
            'trade_type': data.get('trade_type', 'buy'),
            'avg_price': float(data.get('avg_price')),
            'quantity': int(data.get('quantity')),
            'expected_return': float(data.get('expected_return')),
            'risk_percent': float(data.get('risk_percent')),
            'capital_used': float(data.get('capital_used')),
            'target_price': float(data.get('target_price')),
            'stop_loss_price': float(data.get('stop_loss_price')),
            'total_reward': float(data.get('total_reward')),
            'total_risk': float(data.get('total_risk')),
            'rr_ratio': float(data.get('rr_ratio')),
            'symbol': data.get('symbol'),
            'comment': data.get('comment')
        }
        
        # Only add lot_size if the column exists
        if hasattr(IntradayTrade, 'lot_size'):
            trade_data['lot_size'] = int(data.get('lot_size', 25))
            
        # Add derivative name for F&O trades
        if hasattr(IntradayTrade, 'derivative_name'):
            trade_data['derivative_name'] = data.get('symbol')  # symbol contains derivative name
            
        trade = IntradayTrade(**trade_data)
        db.session.add(trade)
        db.session.commit()
        return jsonify({'message': 'Saved successfully', 'trade_id': trade.id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to save trade', 'details': str(e)}), 500

@app.route('/save_mtf_result', methods=['POST'])
@login_required
def save_mtf_result():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data received'}), 400
    
    try:
        trade_data = {
            'trade_type': data.get('trade_type', 'buy'),
            'avg_price': float(data.get('avg_price')),
            'quantity': int(data.get('quantity')),
            'expected_return': float(data.get('expected_return')),
            'risk_percent': float(data.get('risk_percent')),
            'capital_used': float(data.get('capital_used')),
            'target_price': float(data.get('target_price')),
            'stop_loss_price': float(data.get('stop_loss_price')),
            'total_reward': float(data.get('total_reward')),
            'total_risk': float(data.get('total_risk')),
            'rr_ratio': float(data.get('rr_ratio')),
            'symbol': data.get('symbol'),
            'comment': data.get('comment')
        }
        
        # Add leverage for MTF trades
        trade_data['leverage'] = float(data.get('leverage', 1))
        trade_data['user_id'] = current_user.id
            
        trade = IntradayTrade(**trade_data)
        db.session.add(trade)
        db.session.commit()
        return jsonify({'message': 'Saved successfully', 'trade_id': trade.id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to save trade', 'details': str(e)}), 500

@app.route('/save_swing_result', methods=['POST'])
@login_required
def save_swing_result():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data received'}), 400
    
    try:
        trade = IntradayTrade(
            user_id=current_user.id,
            trade_type=data.get('trade_type', 'buy'),
            avg_price=float(data.get('avg_price')),
            quantity=int(data.get('quantity')),
            expected_return=float(data.get('expected_return')),
            risk_percent=float(data.get('risk_percent')),
            capital_used=float(data.get('capital_used')),
            target_price=float(data.get('target_price')),
            stop_loss_price=float(data.get('stop_loss_price')),
            total_reward=float(data.get('total_reward')),
            total_risk=float(data.get('total_risk')),
            rr_ratio=float(data.get('rr_ratio')),
            symbol=data.get('symbol'),
            comment=data.get('comment')
        )
        db.session.add(trade)
        db.session.commit()
        return jsonify({'message': 'Saved successfully', 'trade_id': trade.id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to save trade', 'details': str(e)}), 500

@app.route('/save_delivery_result', methods=['POST'])
@login_required
def save_delivery_result():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data received'}), 400
    
    try:
        trade = IntradayTrade(
            user_id=current_user.id,
            trade_type=data.get('trade_type', 'buy'),
            avg_price=float(data.get('avg_price')),
            quantity=int(data.get('quantity')),
            expected_return=float(data.get('expected_return')),
            risk_percent=float(data.get('risk_percent')),
            capital_used=float(data.get('capital_used')),
            target_price=float(data.get('target_price')),
            stop_loss_price=float(data.get('stop_loss_price')),
            total_reward=float(data.get('total_reward')),
            total_risk=float(data.get('total_risk')),
            rr_ratio=float(data.get('rr_ratio')),
            symbol=data.get('symbol'),
            comment=data.get('comment')
        )
        db.session.add(trade)
        db.session.commit()
        return jsonify({'message': 'Saved successfully', 'trade_id': trade.id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to save trade', 'details': str(e)}), 500

# Swing-specific routes
@app.route('/delete_swing/<int:trade_id>', methods=['POST'])
@login_required
def delete_swing_trade(trade_id):
    try:
        trade = IntradayTrade.query.get_or_404(trade_id)
        db.session.delete(trade)
        db.session.commit()
        return redirect(url_for('saved_swing'))
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete trade', 'details': str(e)}), 500

@app.route('/save_swing_update', methods=['POST'])
@login_required
def save_swing_position_update():
    try:
        data = request.get_json()
        trade_id = data.get('trade_id')
        
        trade = IntradayTrade.query.get_or_404(trade_id)
        
        trade.avg_price = float(data.get('avg_price', trade.avg_price))
        trade.quantity = int(data.get('quantity', trade.quantity))
        trade.stop_loss_price = float(data.get('stop_loss_price', trade.stop_loss_price))
        trade.target_price = float(data.get('target_price', trade.target_price))
        
        # Swing uses no leverage - capital = avg_price * quantity
        capital_used = trade.avg_price * trade.quantity
        
        if trade.trade_type == 'buy':
            reward_per_share = trade.target_price - trade.avg_price
            risk_per_share = trade.avg_price - trade.stop_loss_price
        else:
            reward_per_share = trade.avg_price - trade.target_price
            risk_per_share = trade.stop_loss_price - trade.avg_price
        
        expected_return = (reward_per_share / trade.avg_price) * 100
        risk_percent = (risk_per_share / trade.avg_price) * 100
        
        trade.capital_used = round(capital_used, 2)
        trade.expected_return = round(expected_return, 2)
        trade.risk_percent = round(risk_percent, 2)
        trade.total_reward = round(reward_per_share * trade.quantity, 2)
        trade.total_risk = round(risk_per_share * trade.quantity, 2)
        trade.rr_ratio = round((reward_per_share / risk_per_share) if risk_per_share != 0 else 0.0, 2)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'trade': {
                'id': trade.id,
                'avg_price': trade.avg_price,
                'quantity': trade.quantity,
                'stop_loss_price': trade.stop_loss_price,
                'target_price': trade.target_price,
                'capital_used': trade.capital_used,
                'expected_return': trade.expected_return,
                'risk_percent': trade.risk_percent,
                'total_reward': trade.total_reward,
                'total_risk': trade.total_risk,
                'rr_ratio': trade.rr_ratio
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/close_swing_position', methods=['POST'])
@login_required
def close_swing_position():
    try:
        data = request.get_json()
        trade_id = data.get('trade_id')
        
        trade = IntradayTrade.query.get_or_404(trade_id)
        trade.status = 'closed'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Swing position closed successfully!',
            'trade_id': trade.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/reopen_swing_position', methods=['POST'])
@login_required
def reopen_swing_position():
    try:
        data = request.get_json()
        trade_id = data.get('trade_id')
        
        trade = IntradayTrade.query.get_or_404(trade_id)
        trade.status = 'open'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Swing position reopened successfully!',
            'trade_id': trade.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# MTF-specific routes
@app.route('/save_mtf_update', methods=['POST'])
@login_required
def save_mtf_position_update():
    try:
        data = request.get_json()
        trade_id = data.get('trade_id')
        
        trade = IntradayTrade.query.get_or_404(trade_id)
        
        trade.avg_price = float(data.get('avg_price', trade.avg_price))
        trade.quantity = int(data.get('quantity', trade.quantity))
        trade.stop_loss_price = float(data.get('stop_loss_price', trade.stop_loss_price))
        trade.target_price = float(data.get('target_price', trade.target_price))
        
        leverage = trade.leverage or 1
        capital_used = (trade.avg_price * trade.quantity) / leverage
        
        if trade.trade_type == 'buy':
            reward_per_share = trade.target_price - trade.avg_price
            risk_per_share = trade.avg_price - trade.stop_loss_price
        else:
            reward_per_share = trade.avg_price - trade.target_price
            risk_per_share = trade.stop_loss_price - trade.avg_price
        
        expected_return = (reward_per_share / (trade.avg_price / leverage)) * 100
        risk_percent = (risk_per_share / (trade.avg_price / leverage)) * 100
        
        trade.capital_used = round(capital_used, 2)
        trade.expected_return = round(expected_return, 2)
        trade.risk_percent = round(risk_percent, 2)
        trade.total_reward = round(reward_per_share * trade.quantity, 2)
        trade.total_risk = round(risk_per_share * trade.quantity, 2)
        trade.rr_ratio = round((reward_per_share / risk_per_share) if risk_per_share != 0 else 0.0, 2)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'trade': {
                'id': trade.id,
                'avg_price': trade.avg_price,
                'quantity': trade.quantity,
                'stop_loss_price': trade.stop_loss_price,
                'target_price': trade.target_price,
                'capital_used': trade.capital_used,
                'expected_return': trade.expected_return,
                'risk_percent': trade.risk_percent,
                'total_reward': trade.total_reward,
                'total_risk': trade.total_risk,
                'rr_ratio': trade.rr_ratio
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/close_mtf_position', methods=['POST'])
@login_required
def close_mtf_position():
    try:
        data = request.get_json()
        trade_id = data.get('trade_id')
        
        trade = IntradayTrade.query.get_or_404(trade_id)
        trade.status = 'closed'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'MTF position closed successfully!',
            'trade_id': trade.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/reopen_mtf_position', methods=['POST'])
@login_required
def reopen_mtf_position():
    try:
        data = request.get_json()
        trade_id = data.get('trade_id')
        
        trade = IntradayTrade.query.get_or_404(trade_id)
        trade.status = 'open'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'MTF position reopened successfully!',
            'trade_id': trade.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# Delivery-specific routes
@app.route('/delete_delivery/<int:trade_id>', methods=['POST'])
@login_required
def delete_delivery_trade(trade_id):
    try:
        trade = IntradayTrade.query.get_or_404(trade_id)
        db.session.delete(trade)
        db.session.commit()
        return redirect(url_for('saved_delivery'))
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete trade', 'details': str(e)}), 500

@app.route('/save_delivery_update', methods=['POST'])
@login_required
def save_delivery_position_update():
    try:
        data = request.get_json()
        trade_id = data.get('trade_id')
        
        trade = IntradayTrade.query.get_or_404(trade_id)
        
        trade.avg_price = float(data.get('avg_price', trade.avg_price))
        trade.quantity = int(data.get('quantity', trade.quantity))
        trade.stop_loss_price = float(data.get('stop_loss_price', trade.stop_loss_price))
        trade.target_price = float(data.get('target_price', trade.target_price))
        
        capital_used = trade.avg_price * trade.quantity
        
        if trade.trade_type == 'buy':
            reward_per_share = trade.target_price - trade.avg_price
            risk_per_share = trade.avg_price - trade.stop_loss_price
        else:
            reward_per_share = trade.avg_price - trade.target_price
            risk_per_share = trade.stop_loss_price - trade.avg_price
        
        expected_return = (reward_per_share / trade.avg_price) * 100
        risk_percent = (risk_per_share / trade.avg_price) * 100
        
        trade.capital_used = round(capital_used, 2)
        trade.expected_return = round(expected_return, 2)
        trade.risk_percent = round(risk_percent, 2)
        trade.total_reward = round(reward_per_share * trade.quantity, 2)
        trade.total_risk = round(risk_per_share * trade.quantity, 2)
        trade.rr_ratio = round((reward_per_share / risk_per_share) if risk_per_share != 0 else 0.0, 2)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'trade': {
                'id': trade.id,
                'avg_price': trade.avg_price,
                'quantity': trade.quantity,
                'stop_loss_price': trade.stop_loss_price,
                'target_price': trade.target_price,
                'capital_used': trade.capital_used,
                'expected_return': trade.expected_return,
                'risk_percent': trade.risk_percent,
                'total_reward': trade.total_reward,
                'total_risk': trade.total_risk,
                'rr_ratio': trade.rr_ratio
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/close_delivery_position', methods=['POST'])
@login_required
def close_delivery_position():
    try:
        data = request.get_json()
        trade_id = data.get('trade_id')
        
        trade = IntradayTrade.query.get_or_404(trade_id)
        trade.status = 'closed'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Delivery position closed successfully!',
            'trade_id': trade.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/reopen_delivery_position', methods=['POST'])
@login_required
def reopen_delivery_position():
    try:
        data = request.get_json()
        trade_id = data.get('trade_id')
        
        trade = IntradayTrade.query.get_or_404(trade_id)
        trade.status = 'open'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Delivery position reopened successfully!',
            'trade_id': trade.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# Debug routes
@app.route('/debug-trades/<calculator>')
@login_required
def debug_trades_calc(calculator):
    try:
        if calculator == 'intraday':
            trades = IntradayTrade.query.order_by(IntradayTrade.id.desc()).all()
        elif calculator == 'fno':
            trades = IntradayTrade.query.filter(IntradayTrade.lot_size.isnot(None)).order_by(IntradayTrade.id.desc()).all()
        elif calculator == 'mtf':
            trades = IntradayTrade.query.filter(IntradayTrade.leverage.isnot(None)).order_by(IntradayTrade.id.desc()).all()
        elif calculator in ['swing', 'delivery']:
            trades = IntradayTrade.query.filter(IntradayTrade.leverage.is_(None), IntradayTrade.lot_size.is_(None)).order_by(IntradayTrade.id.desc()).all()
        else:
            trades = []
        normalized_trades = [normalize_trade(trade) for trade in trades]
        return jsonify(normalized_trades)
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/debug-trades')
@login_required
def debug_trades():
    return debug_trades_calc('intraday')

@app.route('/delete_mtf/<int:trade_id>', methods=['POST'])
@login_required
def delete_mtf_trade(trade_id):
    try:
        trade = IntradayTrade.query.get_or_404(trade_id)
        db.session.delete(trade)
        db.session.commit()
        return redirect(url_for('saved_mtf'))
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete trade', 'details': str(e)}), 500

@app.route('/delete_fno/<int:trade_id>', methods=['POST'])
@login_required
def delete_fno_trade(trade_id):
    try:
        trade = IntradayTrade.query.get_or_404(trade_id)
        db.session.delete(trade)
        db.session.commit()
        return redirect(url_for('saved_fno'))
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete trade', 'details': str(e)}), 500

@app.route('/save_fno_update', methods=['POST'])
@login_required
def save_fno_position_update():
    try:
        data = request.get_json()
        trade_id = data.get('trade_id')
        
        trade = IntradayTrade.query.get_or_404(trade_id)
        
        trade.avg_price = float(data.get('avg_price', trade.avg_price))
        trade.quantity = int(data.get('quantity', trade.quantity))
        trade.stop_loss_price = float(data.get('stop_loss_price', trade.stop_loss_price))
        trade.target_price = float(data.get('target_price', trade.target_price))
        
        # F&O uses no leverage - capital = avg_price * quantity
        capital_used = trade.avg_price * trade.quantity
        
        if trade.trade_type == 'buy':
            reward_per_share = trade.target_price - trade.avg_price
            risk_per_share = trade.avg_price - trade.stop_loss_price
        else:
            reward_per_share = trade.avg_price - trade.target_price
            risk_per_share = trade.stop_loss_price - trade.avg_price
        
        expected_return = (reward_per_share / trade.avg_price) * 100
        risk_percent = (risk_per_share / trade.avg_price) * 100
        
        trade.capital_used = round(capital_used, 2)
        trade.expected_return = round(expected_return, 2)
        trade.risk_percent = round(risk_percent, 2)
        trade.total_reward = round(reward_per_share * trade.quantity, 2)
        trade.total_risk = round(risk_per_share * trade.quantity, 2)
        trade.rr_ratio = round((reward_per_share / risk_per_share) if risk_per_share != 0 else 0.0, 2)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'trade': {
                'id': trade.id,
                'avg_price': trade.avg_price,
                'quantity': trade.quantity,
                'stop_loss_price': trade.stop_loss_price,
                'target_price': trade.target_price,
                'capital_used': trade.capital_used,
                'expected_return': trade.expected_return,
                'risk_percent': trade.risk_percent,
                'total_reward': trade.total_reward,
                'total_risk': trade.total_risk,
                'rr_ratio': trade.rr_ratio
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/close_fno_position', methods=['POST'])
@login_required
def close_fno_position():
    try:
        data = request.get_json()
        trade_id = data.get('trade_id')
        
        trade = IntradayTrade.query.get_or_404(trade_id)
        trade.status = 'closed'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'F&O position closed successfully!',
            'trade_id': trade.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/reopen_fno_position', methods=['POST'])
@login_required
def reopen_fno_position():
    try:
        data = request.get_json()
        trade_id = data.get('trade_id')
        
        trade = IntradayTrade.query.get_or_404(trade_id)
        trade.status = 'open'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'F&O position reopened successfully!',
            'trade_id': trade.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# Favicon routes with cache busting
@app.route("/favicon.ico")
def favicon():
    response = send_from_directory("static/favicons", "favicon.ico", mimetype="image/vnd.microsoft.icon")
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route("/apple-touch-icon.png")
def apple_touch_icon():
    return send_from_directory("static/favicons", "apple-touch-icon.png")

@app.route("/favicon-<int:size>x<int:size2>.png")
def favicon_png(size, size2):
    return send_from_directory("static/favicons", f"favicon-{size}x{size2}.png")

@app.route("/android-chrome-<int:size>x<int:size2>.png")
def android_chrome(size, size2):
    return send_from_directory("static/favicons", f"android-chrome-{size}x{size2}.png")

@app.route("/favicon.svg")
def favicon_svg():
    response = send_from_directory("static/favicons", "favicon.svg", mimetype="image/svg+xml")
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

@app.route("/site.webmanifest")
def site_webmanifest():
    return send_from_directory("static/favicons", "site.webmanifest", mimetype="application/manifest+json")

@app.route("/test-email")
@login_required
def test_email():
    """Test email functionality"""
    try:
        test_email = current_user.email
        send_email(
            to=test_email,
            subject="Test Email from CalculatenTrade",
            html="<p>This is a test email. If you receive this, email configuration is working!</p>"
        )
        return jsonify({"success": True, "message": f"Test email sent to {test_email}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/test-dhan-api")
@login_required
def test_dhan_api():
    """Test DHAN API configuration"""
    if not DHAN_ACCESS_TOKEN:
        return jsonify({"success": False, "error": "DHAN_ACCESS_TOKEN not configured"})
    
    price_data = get_live_price("RELIANCE")
    if 'error' in price_data:
        return jsonify({"success": False, "error": price_data['error']})
    
    return jsonify({"success": True, "message": f"API working! RELIANCE price: {price_data['price']}"})

@app.route("/test-toast")
def test_toast():
    """Test page for toast notifications"""
    return render_template("toast_test.html")

# ------------------------------------------------------------------------------
# Register Blueprints (after all models are defined)
# ------------------------------------------------------------------------------
app.register_blueprint(calculatentrade_bp)
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(employee_dashboard_bp, url_prefix='/employee')
app.register_blueprint(mentor_bp, url_prefix='/mentor')
app.register_blueprint(subscription_admin_bp, url_prefix='/admin/subscription')

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # Initialize database when running directly
    init_app_database()
    
    # Initialize timezone
    try:
        IST = pytz.timezone("Asia/Kolkata")
        print("Timezone initialized successfully")
    except Exception as e:
        print(f"Warning: Timezone initialization failed: {e}")
        IST = pytz.UTC
    
    app.run(host="0.0.0.0", port="5000", debug=True)