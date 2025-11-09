from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session, Blueprint, send_from_directory
from toast_utils import ToastManager, toast_success, toast_error, toast_warning, toast_info
import random
import os
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
import json
import requests
import pyotp
from dotenv import load_dotenv
from flask_session import Session
from flask_login import login_required
from werkzeug.utils import secure_filename

# Safe import of current_app
try:
    from flask import current_app
except ImportError:
    current_app = None

# Safe logging function
def safe_log_error(message):
    """Safely log errors with fallback to print"""
    try:
        if current_app and hasattr(current_app, 'logger'):
            current_app.logger.error(message)
        else:
            print(f"ERROR: {message}")
    except Exception:
        print(f"ERROR: {message}")

def _get_empty_dashboard_data():
    """Return empty dashboard data structure for error cases"""
    return {
        'recent_trades': [],
        'win_rate': 0,
        'highest_pnl': 0,
        'trades_this_month': 0,
        'risk_reward': 0,
        'total_trades': 0,
        'winning_trades': 0,
        'losing_trades': 0,
        'total_pnl': 0,
        'monthly_pnl': 0,
        'equity_curve': [],
        'monthly_heatmap': [],
        'current_streak': 0,
        'longest_win_streak': 0,
        'longest_loss_streak': 0,
        'ai_insights': [],
        'ai_risk_suggestions': [],
        'mistake_alerts': [],
        'rule_compliance': 0,
        'avg_win': 0,
        'avg_loss': 0,
        'profit_factor': 0,
        'max_drawdown': 0,
        'expectancy': 0,
        'sharpe_ratio': 0,
        'risk_of_ruin': 0,
        'avg_holding_time': "0 hours",
        'best_trade_symbol': None,
        'worst_trade_symbol': None,
        'most_profitable_strategy': None,
        'challenge_progress': [],
        'reports_snapshot': {'period': 'No data', 'trades': 0, 'pnl': 0},
        'xp_points': 0,
        'level': 1,
        'badges': [],
        'strategies': [],
        'mistakes': [],
        'now': datetime.now()
    }

# Apply PostgreSQL compatibility fixes early
try:
    import pg_type_fix
except ImportError:
    pass




# KiteConnect SDK
try:
    from kiteconnect import KiteConnect
except ImportError:
    KiteConnect = None

# DhanHQ SDK (handles both old and new versions)
try:
    from dhanhq import DhanHQ
    def make_dhan_client(client_id: str, access_token: str):
        return DhanHQ(client_id=client_id, access_token=access_token)
except ImportError:
    try:
        from dhanhq import dhanhq as _dhan_factory
        def make_dhan_client(client_id: str, access_token: str):
            return _dhan_factory(client_id, access_token)
    except ImportError:
        make_dhan_client = None

# Angel One SmartAPI SDK
try:
    from smartapi_wrapper import SmartConnect
except ImportError:
    SmartConnect = None
except Exception as e:
    print(f"Warning: SmartApi import failed: {e}")
    SmartConnect = None

# Load environment variables
load_dotenv()



# Initialize database
db = SQLAlchemy()

# ----------------- BLUEPRINT ----------------- #
calculatentrade_bp = Blueprint("calculatentrade", __name__, url_prefix="/calculatentrade_journal")

# Initialize Flask app (will be used in main.py or similar)

# Import and register multi-broker blueprint
try:
    from multi_broker_system import multi_broker_bp, integrate_with_calculatentrade
    # The blueprint will be registered in the main app initialization
except ImportError as e:
    safe_log_error(f"Multi-broker system not available: {e}")
    multi_broker_bp = None

# Helper function for subscription checks
def subscription_required_journal(f):
    """Decorator to check subscription for journal routes"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from subscription_models import get_user_active_subscription
        from flask_login import current_user
        from flask import redirect, url_for, session
        from toast_utils import toast_warning
        
        # Check if user is logged in via session
        if "email" not in session:
            toast_warning("Please log in to access Journal features.")
            return redirect(url_for("login"))
        
        # Check if current_user is available and has id attribute
        if not current_user or not hasattr(current_user, 'id') or not current_user.id:
            toast_warning("Please log in to access Journal features.")
            return redirect(url_for("login"))
            
        active_sub = get_user_active_subscription(current_user.id)
        if not active_sub:
            toast_warning("Active subscription required to access Journal features.")
            return redirect(url_for("subscription"))
        
        return f(*args, **kwargs)
    return decorated_function

# Auto-load persisted accounts on module import
def init_broker_accounts():
    """Initialize broker accounts from database on startup"""
    try:
        with current_app.app_context():
            load_persisted_accounts_into_memory()
    except RuntimeError:
        # Not in app context yet, will be called later
        pass


# In-memory stores for broker connections (replace with DB in production)
USER_APPS = {
    "kite": {},
    "dhan": {},
    "angel": {}
}
USER_SESSIONS = {
    "kite": {},
    "dhan": {},
    "angel": {}
}

# DhanHQ constants
DHAN_AUTH_BASE = "https://auth.dhan.co"
ANGEL_API_BASE = "https://apiconnect.angelbroking.in"

# ---------------- MODELS ---------------- #
class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), nullable=False)
    entry_price = db.Column(db.Float, nullable=False)
    exit_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    result = db.Column(db.String(10), nullable=False)  # 'win' or 'loss' or 'breakeven'
    pnl = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text)
    trade_type = db.Column(db.String(10), default='long')  # 'long' or 'short'
    risk = db.Column(db.Float, default=0)
    reward = db.Column(db.Float, default=0)
    strategy_id = db.Column(db.Integer, db.ForeignKey('strategies.id'), nullable=True)

    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_win(self):
        return self.result == 'win'

    @property
    def percentage(self):
        if self.entry_price > 0:
            return ((self.exit_price - self.entry_price) / self.entry_price) * 100
        return 0


    

class Rule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50), default='Risk')  # Risk, Entry, Exit, Psychology, Money Management
    tags = db.Column(db.Text)  # comma-separated tags
    priority = db.Column(db.String(10), default='medium')  # low, medium, high
    active = db.Column(db.Boolean, default=True)
    linked_strategy_id = db.Column(db.Integer, db.ForeignKey('strategies.id'), nullable=True)
    violation_consequence = db.Column(db.String(20), default='log')  # log, warn, notify
    save_template = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    linked_strategy = db.relationship('Strategy', backref='rules')
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'tags': self.tags.split(',') if self.tags else [],
            'priority': self.priority,
            'active': self.active,
            'linked_strategy_id': self.linked_strategy_id,
            'violation_consequence': self.violation_consequence,
            'save_template': self.save_template,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class RuleStats(db.Model):
    __tablename__ = 'rule_stats'
    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey('rule.id'), nullable=False)
    compliance_percentage = db.Column(db.Float, default=0.0)
    violations_count = db.Column(db.Integer, default=0)
    last_violation_date = db.Column(db.DateTime)
    last_violation_example = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    rule = db.relationship('Rule', backref='stats')


# ---- Mistake + supporting models (replace the old simple Mistake class) ----
from sqlalchemy import Index
# Using generic db.JSON for PostgreSQL compatibility

# NOTE: using plain strings for "enums" for PostgreSQL compatibility.
MISTAKE_CATEGORIES = ('execution', 'analysis', 'risk', 'psychology', 'process', 'other')
MISTAKE_SEVERITIES = ('low', 'medium', 'high', 'critical')

class MistakeTag(db.Model):
    __tablename__ = 'mistake_tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Mistake(db.Model):
    __tablename__ = 'mistakes'

    id = db.Column(db.Integer, primary_key=True)
    # Who/What/When fields
    reporter_id = db.Column(db.String(128), nullable=True)   # user who reported / logged it (optional)
    related_trade_id = db.Column(db.Integer, db.ForeignKey('trade.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)

    # Categorization & severity
    category = db.Column(db.String(40), nullable=False, default='other')   # one of MISTAKE_CATEGORIES
    severity = db.Column(db.String(20), nullable=False, default='medium')  # one of MISTAKE_SEVERITIES
    confidence = db.Column(db.Integer, nullable=True)  # 0-100 subjective confidence in the classification

    # Lifecycle / audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by = db.Column(db.String(128), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)  # soft-delete

    # Versioning (latest pointer + relationship to MistakeVersion)
    current_version = db.Column(db.Integer, nullable=True)

    # Attachments & metadata
    # NOTE: attribute renamed to avoid SQLAlchemy reserved attribute 'metadata'
    metadata_json = db.Column('metadata', db.Text, default='{}')
    attachments_count = db.Column(db.Integer, default=0)


    # Tags (many-to-many)
    tags = db.relationship('MistakeTag', secondary='mistake_tag_link', backref='mistakes', lazy='dynamic')

    # KPIs & analytics fields
    pnl_impact = db.Column(db.Float, nullable=True)          # direct pnl impact (positive/negative)
    risk_at_time = db.Column(db.Float, nullable=True)        # amount risked on the linked trade (if available)
    recurrence_count = db.Column(db.Integer, default=0)      # how many times this mistake recurred
    time_to_resolve_seconds = db.Column(db.Integer, nullable=True)  # seconds between created_at and resolved_at (filled on resolve)

    # free-text searchable combined column (optional helper)
    searchable_text = db.Column(db.Text, nullable=True)

    # relationships
    attachments = db.relationship('MistakeAttachment', backref='mistake', cascade='all, delete-orphan', lazy='dynamic')
    versions = db.relationship('MistakeVersion', backref='mistake', cascade='all, delete-orphan', lazy='dynamic')
    related_trade = db.relationship('Trade', backref=db.backref('mistakes', lazy='dynamic'), foreign_keys=[related_trade_id])

    def to_dict(self, include_attachments=False):
        d = {
            'id': self.id,
            'reporter_id': self.reporter_id,
            'related_trade_id': self.related_trade_id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'severity': self.severity,
            'confidence': self.confidence,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolved_by': self.resolved_by,
            'is_deleted': self.is_deleted,
            # expose metadata under the old key name for clients
            'metadata': json.loads(self.metadata_json) if self.metadata_json and self.metadata_json != '{}' else {},
            'attachments_count': self.attachments_count,
            'pnl_impact': self.pnl_impact,
            'risk_at_time': self.risk_at_time,
            'recurrence_count': self.recurrence_count,
            'time_to_resolve_seconds': self.time_to_resolve_seconds,
            'tags': [t.name for t in self.tags],
        }
        if include_attachments:
            d['attachments'] = [a.to_dict() for a in self.attachments.order_by(MistakeAttachment.created_at.desc()).all()]
        return d

# Link table for many-to-many tags
class MistakeTagLink(db.Model):
    __tablename__ = 'mistake_tag_link'
    id = db.Column(db.Integer, primary_key=True)
    mistake_id = db.Column(db.Integer, db.ForeignKey('mistakes.id', ondelete='CASCADE'), nullable=False, index=True)
    tag_id = db.Column(db.Integer, db.ForeignKey('mistake_tags.id', ondelete='CASCADE'), nullable=False, index=True)

# Attachments table
# ---- MistakeAttachment (avoid attribute named `metadata`) ----
class MistakeAttachment(db.Model):
    __tablename__ = 'mistake_attachments'
    id = db.Column(db.Integer, primary_key=True)
    mistake_id = db.Column(db.Integer, db.ForeignKey('mistakes.id', ondelete='CASCADE'), nullable=False, index=True)
    filename = db.Column(db.String(400), nullable=False)
    mime_type = db.Column(db.String(120))
    size = db.Column(db.Integer)
    url = db.Column(db.String(2000))   # path or CDN url
    # python attribute renamed to avoid SQLAlchemy reserved attribute 'metadata'
    attachment_metadata_json = db.Column('metadata', db.Text, default='{}')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'mime_type': self.mime_type,
            'size': self.size,
            'url': self.url,
            # expose as 'metadata' to clients to keep API stable
            'metadata': json.loads(self.attachment_metadata_json) if self.attachment_metadata_json and self.attachment_metadata_json != '{}' else {},
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# Versioning snapshot model
class MistakeVersion(db.Model):
    __tablename__ = 'mistake_versions'
    id = db.Column(db.Integer, primary_key=True)
    mistake_id = db.Column(db.Integer, db.ForeignKey('mistakes.id', ondelete='CASCADE'), nullable=False, index=True)
    version_number = db.Column(db.Integer, nullable=False)
    snapshot = db.Column(db.JSON, nullable=False)  # snapshot of mistake.to_dict()
    created_by = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Link mistakes to multiple trades (optional to keep history)
class MistakeTradeLink(db.Model):
    __tablename__ = 'mistake_trade_link'
    id = db.Column(db.Integer, primary_key=True)
    mistake_id = db.Column(db.Integer, db.ForeignKey('mistakes.id', ondelete='CASCADE'), nullable=False, index=True)
    trade_id = db.Column(db.Integer, db.ForeignKey('trade.id', ondelete='CASCADE'), nullable=False, index=True)
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Indexes for faster search (title + description)

Index('ix_mistakes_searchable_text', Mistake.searchable_text)

# PostgreSQL full-text search can be implemented using tsvector columns if needed


class Challenge(db.Model):
    __tablename__ = 'challenges'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    challenge_type = db.Column(db.String(50), nullable=False, default='profit')  # profit/consistency/risk_control
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    initial_capital = db.Column(db.Float, nullable=False, default=10000.0)
    target_value = db.Column(db.Float, nullable=False)
    target_is_percent = db.Column(db.Boolean, default=False)
    risk_per_trade_pct = db.Column(db.Float, default=2.0)
    max_drawdown_pct = db.Column(db.Float, default=10.0)
    daily_trade_limit = db.Column(db.Integer, default=5)
    milestones = db.Column(db.JSON, default=list)  # [{"value": 5000, "label": "First 5K"}]
    motivation_quote = db.Column(db.Text)
    status = db.Column(db.String(20), default='ongoing')  # ongoing/completed/failed/paused
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    trades = db.relationship('ChallengeTrade', backref='challenge', cascade='all, delete-orphan', lazy='dynamic')
    moods = db.relationship('ChallengeMood', backref='challenge', cascade='all, delete-orphan', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'challenge_type': self.challenge_type,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'initial_capital': self.initial_capital,
            'target_value': self.target_value,
            'target_is_percent': self.target_is_percent,
            'risk_per_trade_pct': self.risk_per_trade_pct,
            'max_drawdown_pct': self.max_drawdown_pct,
            'daily_trade_limit': self.daily_trade_limit,
            'milestones': self.milestones or [],
            'motivation_quote': self.motivation_quote,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class ChallengeTrade(db.Model):
    __tablename__ = 'challenge_trades'
    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id'), nullable=False)
    trade_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    pnl = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'challenge_id': self.challenge_id,
            'trade_date': self.trade_date.isoformat() if self.trade_date else None,
            'pnl': self.pnl,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class ChallengeMood(db.Model):
    __tablename__ = 'challenge_moods'
    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    mood = db.Column(db.String(20), nullable=False)  # happy/neutral/sad/angry/confident
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'challenge_id': self.challenge_id,
            'date': self.date.isoformat() if self.date else None,
            'mood': self.mood,
            'note': self.note,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# ---------------- Models / JSON / Strategy enhancements ----------------
# Replace `from sqlalchemy.dialects.sqlite import JSON` at top with nothing (we use db.JSON).

# Add these model definitions (replace your existing Strategy class with this)
class Strategy(db.Model):
    __tablename__ = 'strategies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)

    # core strategy setup
    timeframe = db.Column(db.String(20), default='1d')         # e.g. 1min, 5min, daily
    market_type = db.Column(db.String(40), nullable=True)      # optional
    status = db.Column(db.String(32), default='active')       # active, archived, draft

    # risk / size / targets
    stop_loss = db.Column(db.Float, nullable=True)
    take_profit = db.Column(db.Float, nullable=True)
    position_size = db.Column(db.Float, default=2.0)
    max_risk_per_trade = db.Column(db.Float, default=1.0)
    risk_score = db.Column(db.Integer, default=5)

    # performance metrics (top-level aggregates)
    sharpe_ratio = db.Column(db.Float, nullable=True)
    max_drawdown = db.Column(db.Float, nullable=True)
    avg_trade_pl = db.Column(db.Float, nullable=True)

    # rule/logic text
    entry_conditions = db.Column(db.Text, nullable=True)
    exit_conditions = db.Column(db.Text, nullable=True)
    primary_indicator = db.Column(db.String(80), nullable=True)
    secondary_indicator = db.Column(db.String(80), nullable=True)

    # flexible JSON fields (use SQLAlchemy's generic JSON for portability)
    parameters = db.Column(db.JSON, default=list)        # list of {name, value}
    tags = db.Column(db.JSON, default=list)              # list of string tags
    backtests = db.Column(db.JSON, default=list)         # list of backtest summaries / results

    # bookkeeping
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relationship to trades
    trades = db.relationship('Trade', backref='strategy', lazy='dynamic')

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "timeframe": self.timeframe,
            "market_type": self.market_type,
            "status": self.status,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "position_size": self.position_size,
            "max_risk_per_trade": self.max_risk_per_trade,
            "risk_score": self.risk_score,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "avg_trade_pl": self.avg_trade_pl,
            "entry_conditions": self.entry_conditions,
            "exit_conditions": self.exit_conditions,
            "primary_indicator": self.primary_indicator,
            "secondary_indicator": self.secondary_indicator,
            "parameters": self.parameters or [],
            "tags": self.tags or [],
            "backtests": self.backtests or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            # computed fields below
            "total_trades": self.total_trades,
            "total_pnl": self.total_pnl,
            "win_rate": self.win_rate
        }

    @property
    def total_trades(self):
        return self.trades.count()

    @property
    def total_pnl(self):
        # sum of trade.pnl for linked trades
        try:
            total = db.session.query(db.func.coalesce(db.func.sum(Trade.pnl), 0.0)).filter(Trade.strategy_id == self.id).scalar()
            return float(total or 0.0)
        except Exception:
            # fallback (less efficient)
            return float(sum([t.pnl for t in self.trades.all()] or [0.0]))

    @property
    def win_rate(self):
        total = self.trades.filter(Trade.result.in_(['win','loss'])).count()
        if total == 0:
            return 0.0
        wins = self.trades.filter_by(result='win').count()
        return round((wins / total) * 100, 2)

# StrategyVersion model to support versioning endpoints used in your blueprint
class StrategyVersion(db.Model):
    __tablename__ = 'strategy_versions'
    id = db.Column(db.Integer, primary_key=True)
    strategy_id = db.Column(db.Integer, db.ForeignKey('strategies.id'), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(150))
    config_data = db.Column(db.Text)   # JSON string of saved config
    created_by = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    strategy = db.relationship('Strategy', backref=db.backref('versions', lazy='dynamic'))

# BacktestSummary as a persistent model (optional but helpful)
class BacktestSummary(db.Model):
    __tablename__ = 'backtest_summaries'
    id = db.Column(db.Integer, primary_key=True)
    strategy_id = db.Column(db.Integer, db.ForeignKey('strategies.id'), nullable=False)
    name = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    summary = db.Column(db.JSON, default={})   # store the summary payload

    strategy = db.relationship('Strategy', backref=db.backref('backtest_models', lazy='dynamic'))



class Watchlist(db.Model):
    __tablename__ = 'watchlists'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, default='My Watchlist')
    symbols = db.Column(db.Text)  # JSON array of symbols
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(50), nullable=False)  # 'create', 'update', 'delete'
    table_name = db.Column(db.String(50), nullable=False)
    record_id = db.Column(db.Integer)
    old_values = db.Column(db.Text)  # JSON string
    new_values = db.Column(db.Text)  # JSON string
    user_id = db.Column(db.String(100))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- add to MODELS area (below Challenge) ---
class BrokerAccount(db.Model):
    """
    Persist broker registration and session tokens per user + broker.
    One row per (broker, user_id).
    """
    id = db.Column(db.Integer, primary_key=True)
    broker = db.Column(db.String(20), nullable=False)    # "kite", "dhan", "angel"
    user_id = db.Column(db.String(128), nullable=False)
    api_key = db.Column(db.String(256))
    api_secret = db.Column(db.String(256))
    client_id = db.Column(db.String(256))   
    access_token = db.Column(db.String(1024))
    totp_secret = db.Column(db.String(512))
    connected = db.Column(db.Boolean, default=False)
    last_connected_at = db.Column(db.DateTime)

    __table_args__ = (db.UniqueConstraint('broker', 'user_id', name='_broker_user_uc'),)

    def to_dict(self):
        return {
            "broker": self.broker,
            "user_id": self.user_id,
            "api_key": self.api_key,
            "api_secret": self.api_secret,
            "client_id": self.client_id,
            "access_token": self.access_token,
            "totp_secret": self.totp_secret,
            "connected": self.connected,
            "last_connected_at": self.last_connected_at.isoformat() if self.last_connected_at else None
        }


# Add these helper functions after the model definitions
from sqlalchemy.exc import IntegrityError

from flask import app
from datetime import datetime

def save_broker_account(broker, user_id, **kwargs):
    """
    Create or update BrokerAccount row.
    If 'access_token' present and truthy, mark account connected and set last_connected_at.
    """
    acc = BrokerAccount.query.filter_by(broker=broker, user_id=user_id).first()
    if not acc:
        acc = BrokerAccount(broker=broker, user_id=user_id)
        db.session.add(acc)

    for k, v in kwargs.items():
        if v is not None and hasattr(acc, k):
            setattr(acc, k, v)

    # If an access token was provided, set connected / timestamp
    if 'access_token' in kwargs and kwargs.get('access_token'):
        acc.connected = True
        acc.last_connected_at = datetime.utcnow()

    db.session.commit()

    # use current_app.logger instead of global app
    try:
        current_app.logger.info("Saved broker account %s/%s (connected=%s)", broker, user_id, acc.connected)
    except RuntimeError:
        # not in an application context (e.g., called during CLI/non-request); fallback to print
        print(f"Saved broker account {broker}/{user_id} (connected={acc.connected})")

    return acc

from flask import current_app

def mark_connected(broker, user_id, connected=True):
    acc = BrokerAccount.query.filter_by(broker=broker, user_id=user_id).first()
    if not acc:
        return None
    acc.connected = bool(connected)
    if connected:
        acc.last_connected_at = datetime.utcnow()
    db.session.commit()
    try:
        current_app.logger.info("Marked connected=%s for %s/%s", connected, broker, user_id)
    except RuntimeError:
        print(f"Marked connected={connected} for {broker}/{user_id}")
    return acc

def load_persisted_accounts_into_memory(app=None):
    """
    Load all persisted BrokerAccount rows into USER_APPS.
    If an account has an access_token, restore USER_SESSIONS for that user so endpoints remain usable.
    """
    if app is None:
        from flask import current_app
        app = current_app
    with app.app_context():
        accounts = BrokerAccount.query.all()
        from flask import current_app
        try:
            current_app.logger.info("Loading %d persisted broker accounts into memory", len(accounts))
        except RuntimeError:
            # not running inside an app context — ignore/log differently
            pass

        for acc in accounts:
            # Always restore credentials to USER_APPS
            USER_APPS.setdefault(acc.broker, {})[acc.user_id] = {
                "api_key": acc.api_key,
                "api_secret": acc.api_secret,
                "client_id": acc.client_id,
                "access_token": acc.access_token,
                "totp_secret": acc.totp_secret
            }
            # restore in-memory session if token exists and not expired
            if acc.access_token and acc.connected:
                # Check if connection is not expired (24 hours)
                if acc.last_connected_at and (datetime.utcnow() - acc.last_connected_at) < timedelta(hours=24):
                    if acc.broker == "kite":
                        USER_SESSIONS.setdefault("kite", {})[acc.user_id] = {"access_token": acc.access_token}
                    elif acc.broker == "dhan":
                        USER_SESSIONS.setdefault("dhan", {})[acc.user_id] = {"access_token": acc.access_token, "dhan_client_id": acc.client_id, "mode": "direct"}
                    elif acc.broker == "angel":
                        # We can't reconstruct SmartConnect object after restart, but store tokens so front-end knows it's connected
                        USER_SESSIONS.setdefault("angel", {})[acc.user_id] = {"jwt_token": acc.access_token, "client_code": acc.client_id}
                    app.logger.info("Restored session for %s/%s", acc.broker, acc.user_id)
                else:
                    # Mark as disconnected if expired
                    acc.connected = False
                    acc.access_token = None
                    db.session.commit()
                    app.logger.info("Expired session for %s/%s", acc.broker, acc.user_id)

# ---------------- BROKER HELPER FUNCTIONS ---------------- #
def get_kite_for_user(user_id, access_token=None):
    creds = USER_APPS["kite"].get(user_id)
    if not creds:
        # Try to load from database
        acc = BrokerAccount.query.filter_by(broker="kite", user_id=user_id).first()
        if acc and acc.api_key:
            creds = {
                "api_key": acc.api_key,
                "api_secret": acc.api_secret,
                "access_token": acc.access_token
            }
            USER_APPS.setdefault("kite", {})[user_id] = creds
        else:
            raise ValueError("No app credentials for this user")
    
    kite = KiteConnect(api_key=creds["api_key"])
    if access_token:
        kite.set_access_token(access_token)
    elif creds.get("access_token"):
        kite.set_access_token(creds["access_token"])
    return kite

def _dhan_headers(partner_id, partner_secret):
    return {
        "partner_id": partner_id,
        "partner_secret": partner_secret,
        "Content-Type": "application/json"
    }

def _dhan_generate_consent(partner_id, partner_secret):
    url = f"{DHAN_AUTH_BASE}/partner/generate-consent"
    r = requests.post(url, headers=_dhan_headers(partner_id, partner_secret), json={})
    r.raise_for_status()
    data = r.json() if r.headers.get("content-type","").startswith("application/json") else {}
    consent_id = data.get("consentId") or data.get("consent_id")
    if not consent_id:
        raise RuntimeError(f"generate-consent missing consentId: {data}")
    return consent_id

def _dhan_consume_consent(partner_id, partner_secret, token_id):
    url = f"{DHAN_AUTH_BASE}/partner/consume-consent"
    r = requests.get(url, headers=_dhan_headers(partner_id, partner_secret), params={"tokenId": token_id})
    r.raise_for_status()
    return r.json()

def _dhan_client_from_session(user_id):
    sess = USER_SESSIONS["dhan"].get(user_id)
    if not sess:
        return None, jsonify({"ok": False, "message": "Not connected"}), 401
    client_id = sess.get("dhan_client_id") or user_id
    access_token = sess.get("access_token")
    if not access_token:
        return None, jsonify({"ok": False, "message": "Missing Dhan access token"}), 500
    return make_dhan_client(client_id, access_token), None, None

def _angel_auth_headers(jwt):
    return {
        "Authorization": f"Bearer {jwt}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-UserType": "USER",
        "X-SourceID": "WEB",
        "X-ClientLocalIP": "CLIENT_LOCAL_IP",
        "X-ClientPublicIP": "CLIENT_PUBLIC_IP",
        "X-MACAddress": "MAC_ADDRESS",
        "X-PrivateKey": os.getenv("ANGEL_API_KEY")
    }

def _angel_sdk_login(api_key: str, client_code: str, password: str, totp: str):
    smart = SmartConnect(api_key=api_key)
    data = smart.generateSession(clientCode=client_code, password=password, totp=totp)
    if data.get('errorcode'):
        raise RuntimeError(f"Angel login failed: {data.get('message')}")
    jwt = data.get("jwtToken")
    if not jwt:
        raise RuntimeError(f"SmartAPI login ok but token missing: {data}")
    return {
        "jwt_token": jwt,
        "refresh_token": data.get("refreshToken"),
        "feed_token": smart.getfeedToken(),
        "smart_api": smart  # Store the SmartConnect instance
    }


# ---------------- FILE SERVING ---------------- #
@calculatentrade_bp.route('/uploads/mistakes/<filename>')
def serve_mistake_attachment(filename):
    upload_folder = os.path.join(os.path.dirname(__file__), 'uploads', 'mistakes')
    # Ensure the upload folder exists
    os.makedirs(upload_folder, exist_ok=True)
    
    file_path = os.path.join(upload_folder, filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found', 'path': file_path}), 404
    
    return send_from_directory(upload_folder, filename)

# Debug route to check attachments
@calculatentrade_bp.route('/debug/attachments/<int:mistake_id>')
def debug_attachments(mistake_id):
    mistake = Mistake.query.get_or_404(mistake_id)
    attachments = mistake.attachments.all()
    
    upload_folder = os.path.join(os.path.dirname(__file__), 'uploads', 'mistakes')
    
    debug_info = {
        'mistake_id': mistake_id,
        'upload_folder': upload_folder,
        'folder_exists': os.path.exists(upload_folder),
        'attachments': []
    }
    
    for att in attachments:
        file_path = os.path.join(upload_folder, f"{mistake_id}_{att.filename}")
        debug_info['attachments'].append({
            'id': att.id,
            'filename': att.filename,
            'url': att.url,
            'file_path': file_path,
            'file_exists': os.path.exists(file_path),
            'mime_type': att.mime_type,
            'size': att.size
        })
    
    if upload_folder and os.path.exists(upload_folder):
        debug_info['files_in_folder'] = os.listdir(upload_folder)
    
    return jsonify(debug_info)

# ---------------- ROUTES ---------------- #
@calculatentrade_bp.route('/')
def index():
    return redirect(url_for('calculatentrade.dashboard'))

# New API endpoints for rules
@calculatentrade_bp.route('/api/rules/validate', methods=['POST'])
def api_validate_rule():
    data = request.json
    title = data.get('title', '').strip()
    rule_id = data.get('rule_id')  # For updates
    
    if not title:
        return jsonify({'valid': False, 'message': 'Title is required'})
    
    query = Rule.query.filter_by(title=title)
    if rule_id:
        query = query.filter(Rule.id != rule_id)
    
    existing = query.first()
    if existing:
        return jsonify({'valid': False, 'message': 'A rule with this title already exists'})
    
    return jsonify({'valid': True})

@calculatentrade_bp.route('/api/rules/templates')
def api_rule_templates():
    templates = [
        {
            'title': 'Always Use Stop Loss',
            'description': 'Never enter a trade without setting a stop loss order',
            'category': 'Risk',
            'priority': 'high',
            'tags': 'stop-loss,risk-management'
        },
        {
            'title': 'Max 3 Trades Per Day',
            'description': 'Limit daily trades to maximum 3 to avoid overtrading',
            'category': 'Psychology',
            'priority': 'medium',
            'tags': 'overtrading,discipline'
        },
        {
            'title': 'Risk Max 2% Per Trade',
            'description': 'Never risk more than 2% of total capital on a single trade',
            'category': 'Money Management',
            'priority': 'high',
            'tags': 'position-sizing,risk'
        },
        {
            'title': 'Wait for Confirmation',
            'description': 'Always wait for price confirmation before entering trades',
            'category': 'Entry',
            'priority': 'medium',
            'tags': 'confirmation,patience'
        },
        {
            'title': 'No Revenge Trading',
            'description': 'Take a break after 2 consecutive losses to avoid emotional trading',
            'category': 'Psychology',
            'priority': 'high',
            'tags': 'emotions,discipline'
        }
    ]
    return jsonify({'templates': templates})

@calculatentrade_bp.route('/api/rules/<int:rule_id>/toggle', methods=['POST'])
def api_toggle_rule(rule_id):
    r = Rule.query.get_or_404(rule_id)
    r.active = not r.active
    r.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True, 'active': r.active})

# New API endpoints for dashboard widgets
@calculatentrade_bp.route('/api/dashboard/equity_curve')
def api_dashboard_equity_curve():
    """Get equity curve data for dashboard chart"""
    days = int(request.args.get('days', 30))
    start_date = datetime.now() - timedelta(days=days)
    trades = Trade.query.filter(Trade.date >= start_date).order_by(Trade.date).all()
    
    equity_data = []
    cumulative_pnl = 0
    for trade in trades:
        cumulative_pnl += trade.pnl
        equity_data.append({
            'date': trade.date.strftime('%Y-%m-%d'),
            'equity': round(cumulative_pnl, 2)
        })
    
    return jsonify({'success': True, 'data': equity_data})

@calculatentrade_bp.route('/api/dashboard/monthly_heatmap')
def api_dashboard_monthly_heatmap():
    """Get monthly P&L heatmap data for dashboard"""
    months = int(request.args.get('months', 12))
    heatmap_data = []
    
    for i in range(months):
        month_start = (datetime.now().replace(day=1) - timedelta(days=30*i)).replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        month_trades = Trade.query.filter(Trade.date >= month_start.date(), Trade.date <= month_end.date()).all()
        month_pnl = sum(t.pnl for t in month_trades)
        
        heatmap_data.append({
            'month': month_start.strftime('%b %Y'),
            'pnl': round(month_pnl, 2),
            'trades': len(month_trades),
            'color': 'green' if month_pnl > 0 else ('red' if month_pnl < 0 else 'gray')
        })
    
    return jsonify({'success': True, 'data': list(reversed(heatmap_data))})



@calculatentrade_bp.route('/api/update_trade/<int:trade_id>', methods=['POST'])
def api_update_trade(trade_id):
    """Update a trade in the database"""
    try:
        data = request.get_json()
        
        # Find the trade
        trade = Trade.query.get_or_404(trade_id)
        
        # Update trade fields
        if 'date' in data:
            trade.date = datetime.strptime(data['date'], '%Y-%m-%d')
        if 'symbol' in data:
            trade.symbol = data['symbol']
        if 'trade_type' in data:
            trade.trade_type = data['trade_type']
        if 'quantity' in data:
            trade.quantity = float(data['quantity'])
        if 'entry_price' in data:
            trade.entry_price = float(data['entry_price'])
        if 'exit_price' in data:
            trade.exit_price = float(data['exit_price'])
        if 'pnl' in data:
            trade.pnl = float(data['pnl'])
        if 'result' in data:
            trade.result = data['result']
        if 'notes' in data:
            trade.notes = data['notes']
        
        # Save to database
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Trade updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@calculatentrade_bp.route('/api/delete_trade/<int:trade_id>', methods=['POST'])
def api_delete_trade(trade_id):
    """Delete a trade from the database"""
    try:
        # Find the trade
        trade = Trade.query.get_or_404(trade_id)
        
        # Delete the trade
        db.session.delete(trade)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Trade deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@calculatentrade_bp.route('/api/dashboard/trade_review', methods=['POST'])
def api_dashboard_trade_review():
    """Mark a trade as reviewed"""
    try:
        data = request.get_json()
        if not data or not data.get('trade_id'):
            return jsonify({'success': False, 'message': 'Trade ID is required'}), 400
            
        trade_id = data.get('trade_id')
        trade = Trade.query.get(trade_id)
        if not trade:
            return jsonify({'success': False, 'message': 'Trade not found'}), 404
            
        # Add reviewed flag to notes
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
        review_note = f'\n[REVIEWED on {current_time}]'
        trade.notes = (trade.notes or '') + review_note
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Trade marked as reviewed'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@calculatentrade_bp.route('/api/dashboard/add_reflection', methods=['POST'])
def api_dashboard_add_reflection():
    """Add reflection to a trade"""
    try:
        data = request.get_json()
        if not data or not data.get('trade_id') or not data.get('reflection'):
            return jsonify({'success': False, 'message': 'Trade ID and reflection are required'}), 400
            
        trade_id = data.get('trade_id')
        reflection = data.get('reflection', '').strip()
        
        trade = Trade.query.get(trade_id)
        if not trade:
            return jsonify({'success': False, 'message': 'Trade not found'}), 404
            
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
        reflection_note = f'\n[REFLECTION {current_time}]: {reflection}'
        trade.notes = (trade.notes or '') + reflection_note
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Reflection added successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@calculatentrade_bp.route('/dashboard')
@subscription_required_journal
def dashboard():
    """Enhanced dashboard with comprehensive error handling"""
    try:
        # Initialize database connection if needed
        if not db or not hasattr(db, 'engine'):
            safe_log_error("Database not properly initialized")
            return render_template(
                'dashboard_new_journal.html',
                error_message="Database connection issue. Please try again.",
                **_get_empty_dashboard_data()
            )
        # Basic metrics with error handling
        try:
            recent_trades = Trade.query.order_by(Trade.date.desc()).limit(10).all()
        except Exception as e:
            safe_log_error(f"Error fetching recent trades: {e}")
            recent_trades = []
        
        try:
            # ✅ FIX: Ensure all counts are integers for safe comparison
            total_trades = Trade.query.count() or 0
            winning_trades = Trade.query.filter_by(result='win').count() or 0
            losing_trades = Trade.query.filter_by(result='loss').count() or 0
            
            # Ensure they are integers
            total_trades = int(total_trades)
            winning_trades = int(winning_trades)
            losing_trades = int(losing_trades)
        except Exception as e:
            safe_log_error(f"Error fetching trade counts: {e}")
            total_trades = 0
            winning_trades = 0
            losing_trades = 0
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
        # PnL calculations with error handling
        try:
            all_trades = Trade.query.all()
            total_pnl = sum(float(t.pnl or 0) for t in all_trades)
            highest_pnl_trade = Trade.query.filter_by(result='win').order_by(Trade.pnl.desc()).first()
            highest_pnl = float(highest_pnl_trade.pnl) if highest_pnl_trade and highest_pnl_trade.pnl else 0
        except Exception as e:
            safe_log_error(f"Error calculating PnL: {e}")
            total_pnl = 0
            highest_pnl = 0
    
        # Monthly stats with error handling
        try:
            start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # ✅ FIX: Ensure count is integer for safe comparison
            trades_this_month = Trade.query.filter(Trade.date >= start_of_month.date()).count() or 0
            trades_this_month = int(trades_this_month)
            monthly_trades = Trade.query.filter(Trade.date >= start_of_month.date()).all()
            monthly_pnl = sum(float(t.pnl or 0) for t in monthly_trades)
        except Exception as e:
            safe_log_error(f"Error calculating monthly stats: {e}")
            trades_this_month = 0
            monthly_pnl = 0
    
        # Risk/Reward calculations
        try:
            trades_with_risk = Trade.query.filter(
                Trade.risk.isnot(None), 
                Trade.reward.isnot(None),
                Trade.risk > 0, 
                Trade.reward > 0
            ).all()
        except Exception as e:
            safe_log_error(f"Error fetching trades with risk: {e}")
            trades_with_risk = []
        
        risk_reward = 0
        if trades_with_risk:
            # ✅ FIX: Ensure proper float conversion and safe comparison
            valid_trades = []
            for trade in trades_with_risk:
                try:
                    risk_val = float(trade.risk) if trade.risk is not None else 0.0
                    reward_val = float(trade.reward) if trade.reward is not None else 0.0
                    if risk_val > 0:
                        valid_trades.append(reward_val / risk_val)
                except (ValueError, TypeError, ZeroDivisionError):
                    continue
            if valid_trades:
                risk_reward = round(sum(valid_trades) / len(valid_trades), 2)
        
        # Equity curve data (last 30 days)
        try:
            last_30_days = datetime.now() - timedelta(days=30)
            trades_30_days = Trade.query.filter(Trade.date >= last_30_days.date()).order_by(Trade.date).all()
            equity_curve = []
            cumulative_pnl = 0
            for trade in trades_30_days:
                try:
                    cumulative_pnl += float(trade.pnl or 0)
                    equity_curve.append({
                        'date': trade.date.strftime('%Y-%m-%d'), 
                        'pnl': round(cumulative_pnl, 2)
                    })
                except (ValueError, TypeError, AttributeError):
                    continue
        except Exception as e:
            safe_log_error(f"Error calculating equity curve: {e}")
            equity_curve = []
        
        # Monthly heatmap data (last 12 months)
        try:
            monthly_heatmap = []
            for i in range(12):
                try:
                    month_start = (datetime.now().replace(day=1) - timedelta(days=30*i)).replace(day=1)
                    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                    month_trades = Trade.query.filter(
                        Trade.date >= month_start.date(), 
                        Trade.date <= month_end.date()
                    ).all()
                    month_pnl = sum(float(t.pnl or 0) for t in month_trades)
                    monthly_heatmap.append({
                        'month': month_start.strftime('%b %Y'),
                        'pnl': round(month_pnl, 2),
                        'trades': len(month_trades)
                    })
                except Exception:
                    continue
        except Exception as e:
            safe_log_error(f"Error calculating monthly heatmap: {e}")
            monthly_heatmap = []
        
        # Win/Loss streaks
        try:
            current_streak = 0
            longest_win_streak = 0
            longest_loss_streak = 0
            temp_win_streak = 0
            temp_loss_streak = 0
            
            for trade in reversed(recent_trades):
                try:
                    if trade.result == 'win':
                        temp_win_streak += 1
                        temp_loss_streak = 0
                        longest_win_streak = max(longest_win_streak, temp_win_streak)
                    elif trade.result == 'loss':
                        temp_loss_streak += 1
                        temp_win_streak = 0
                        longest_loss_streak = max(longest_loss_streak, temp_loss_streak)
                except AttributeError:
                    continue
            
            current_streak = temp_win_streak if temp_win_streak > 0 else -temp_loss_streak
        except Exception as e:
            safe_log_error(f"Error calculating streaks: {e}")
            current_streak = 0
            longest_win_streak = 0
            longest_loss_streak = 0
        
        # AI insights (mock data for now)
        try:
            ai_insights = []
            for t in recent_trades[:5]:
                try:
                    ai_insights.append({
                        "trade_id": t.id, 
                        "reason": "Good entry timing", 
                        "mistake": "Exit too early", 
                        "improvement": "Hold for target"
                    })
                except AttributeError:
                    continue
            
            ai_risk_suggestions = [
                "Consider reducing position size by 10% based on recent volatility",
                "Your win rate is strong - maintain current strategy",
                "Review stop-loss levels - recent trades show 15% average loss"
            ]
        except Exception as e:
            safe_log_error(f"Error generating AI insights: {e}")
            ai_insights = []
            ai_risk_suggestions = []
        
        # Mistake analysis
        try:
            mistake_alerts = []
            mistakes = Mistake.query.all()
            for mistake in mistakes:
                try:
                    # ✅ FIX: Ensure proper integer casting for count comparison
                    count = int(mistake.recurrence_count or 1)
                    if count >= 3:  # Safe: int >= int
                        # ✅ FIX: Ensure pnl_impact is properly cast to float
                        impact = abs(float(mistake.pnl_impact)) if mistake.pnl_impact is not None else 0.0
                        mistake_alerts.append({
                            'title': mistake.title,
                            'count': count,
                            'severity': mistake.severity,
                            'impact': impact
                        })
                except (ValueError, TypeError, AttributeError):
                    continue
        except Exception as e:
            safe_log_error(f"Error analyzing mistakes: {e}")
            mistake_alerts = []
        
        # Rule compliance (mock calculation)
        try:
            total_rules = Rule.query.count() or 0
            total_rules = int(total_rules)  # ✅ FIX: Ensure count is integer
            rule_compliance = 85 if total_rules > 0 else 0  # Safe: int > int
        except Exception as e:
            safe_log_error(f"Error calculating rule compliance: {e}")
            total_rules = 0
            rule_compliance = 0
        
        # Advanced metrics
        try:
            # ✅ FIX: winning_trades and losing_trades are already cast to int above, so comparisons are safe
            win_trades = Trade.query.filter_by(result='win').all()
            loss_trades = Trade.query.filter_by(result='loss').all()
            
            avg_win = sum(float(t.pnl or 0) for t in win_trades) / winning_trades if winning_trades > 0 else 0
            avg_loss = abs(sum(float(t.pnl or 0) for t in loss_trades) / losing_trades) if losing_trades > 0 else 0
        except Exception as e:
            safe_log_error(f"Error calculating advanced metrics: {e}")
            avg_win = 0
            avg_loss = 0
        
        # Profit Factor = Gross Profit ÷ Gross Loss
        try:
            win_trades = Trade.query.filter_by(result='win').all()
            loss_trades = Trade.query.filter_by(result='loss').all()
            
            gross_profit = sum(float(t.pnl or 0) for t in win_trades)
            gross_loss = abs(sum(float(t.pnl or 0) for t in loss_trades))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        except Exception as e:
            safe_log_error(f"Error calculating profit factor: {e}")
            profit_factor = 0
        
        # Max Drawdown calculation
        try:
            all_trades = Trade.query.order_by(Trade.date).all()
            cumulative_pnl = 0
            peak = 0
            max_drawdown = 0
            for trade in all_trades:
                try:
                    cumulative_pnl += float(trade.pnl or 0)
                    if cumulative_pnl > peak:
                        peak = cumulative_pnl
                    drawdown = peak - cumulative_pnl
                    if drawdown > max_drawdown:
                        max_drawdown = drawdown
                except (ValueError, TypeError):
                    continue
        except Exception as e:
            safe_log_error(f"Error calculating max drawdown: {e}")
            max_drawdown = 0
        
        # Expectancy = (Win% × AvgWin) - (Loss% × AvgLoss)
        try:
            # ✅ FIX: total_trades is already cast to int above, so comparison is safe
            expectancy = (win_rate/100 * avg_win) - ((100-win_rate)/100 * avg_loss) if total_trades > 0 else 0
        except Exception as e:
            safe_log_error(f"Error calculating expectancy: {e}")
            expectancy = 0
        
        # Sharpe ratio (simplified)
        try:
            # ✅ FIX: total_trades is already cast to int, comparisons are safe
            if total_trades > 0 and total_pnl != 0:
                avg_return = total_pnl / total_trades
                # Simple volatility estimate
                volatility = abs(total_pnl * 0.1) if total_pnl != 0 else 1
                sharpe_ratio = avg_return / volatility
            else:
                sharpe_ratio = 0
        except Exception as e:
            safe_log_error(f"Error calculating Sharpe ratio: {e}")
            sharpe_ratio = 0
        
        # Risk of ruin (simplified calculation)
        try:
            risk_of_ruin = max(0, min(100, (100 - win_rate) * 2)) if win_rate < 60 else 5
        except Exception as e:
            safe_log_error(f"Error calculating risk of ruin: {e}")
            risk_of_ruin = 0
        
        # Average holding time (mock)
        avg_holding_time = "2.5 hours"  # Would need entry/exit timestamps
        
        # Best and worst trade symbols
        try:
            best_trade = Trade.query.filter_by(result='win').order_by(Trade.pnl.desc()).first()
            worst_trade = Trade.query.filter_by(result='loss').order_by(Trade.pnl.asc()).first()
            best_trade_symbol = best_trade.symbol if best_trade else None
            worst_trade_symbol = worst_trade.symbol if worst_trade else None
        except Exception as e:
            safe_log_error(f"Error finding best/worst trades: {e}")
            best_trade_symbol = None
            worst_trade_symbol = None
        
        # Most profitable strategy
        try:
            most_profitable_strategy = None
            best_pnl = float('-inf')
            strategies = Strategy.query.all()
            for strategy in strategies:
                try:
                    strategy_trades = Trade.query.filter_by(strategy_id=strategy.id).all()
                    strategy_pnl = sum(float(t.pnl or 0) for t in strategy_trades)
                    if strategy_pnl > best_pnl:
                        best_pnl = strategy_pnl
                        most_profitable_strategy = {'name': strategy.name, 'pnl': strategy_pnl}
                except Exception:
                    continue
        except Exception as e:
            safe_log_error(f"Error finding most profitable strategy: {e}")
            most_profitable_strategy = None
        
        # Challenge progress
        try:
            active_challenges = Challenge.query.filter_by(status='ongoing').all()
            challenge_progress = []
            for challenge in active_challenges[:3]:  # Top 3
                try:
                    trades = challenge.trades.all()
                    current_pnl = sum(float(t.pnl or 0) for t in trades)
                    # ✅ FIX: Cast target_value to float to ensure numeric comparison
                    target_value = float(challenge.target_value) if challenge.target_value else 0
                    progress = (current_pnl / target_value * 100) if target_value > 0 else 0
                    challenge_progress.append({
                        'title': challenge.title,
                        'progress': min(progress, 100),
                        'current': current_pnl,
                        'target': target_value
                    })
                except Exception:
                    continue
        except Exception as e:
            safe_log_error(f"Error calculating challenge progress: {e}")
            challenge_progress = []
        
        # Reports snapshot
        try:
            last_7_days = datetime.now() - timedelta(days=7)
            week_trades = Trade.query.filter(Trade.date >= last_7_days.date()).all()
            week_pnl = sum(float(t.pnl or 0) for t in week_trades)
            
            reports_snapshot = {
                'period': 'Last 7 days',
                'trades': len(week_trades),
                'pnl': week_pnl
            }
        except Exception as e:
            safe_log_error(f"Error calculating reports snapshot: {e}")
            reports_snapshot = {'period': 'No data', 'trades': 0, 'pnl': 0}
        
        # Gamification (mock data)
        try:
            # ✅ FIX: Ensure xp_points calculation uses integers
            xp_points = int(total_trades * 10 + winning_trades * 5)
            level = min(10, xp_points // 100 + 1)
            
            badges = []
            # ✅ FIX: winning_trades is already int, comparison is safe
            if winning_trades >= 5:
                badges.append({'name': '5 Wins', 'icon': 'trophy', 'color': 'gold'})
            # ✅ FIX: win_rate is float, comparison is safe
            if win_rate >= 60:
                badges.append({'name': 'High Win Rate', 'icon': 'target', 'color': 'green'})
            # ✅ FIX: monthly_pnl is float, comparison is safe
            if monthly_pnl > 0:
                badges.append({'name': 'Profitable Month', 'icon': 'chart-line', 'color': 'blue'})
        except Exception as e:
            safe_log_error(f"Error calculating gamification data: {e}")
            xp_points = 0
            level = 1
            badges = []
    
        return render_template(
            'dashboard_new_journal.html',
            # Basic metrics
            recent_trades=recent_trades,
            win_rate=round(win_rate, 2),
            highest_pnl=highest_pnl,
            trades_this_month=trades_this_month,
            risk_reward=risk_reward,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            total_pnl=total_pnl,
            monthly_pnl=monthly_pnl,
            
            # Charts data
            equity_curve=equity_curve,
            monthly_heatmap=monthly_heatmap,
            
            # Streaks
            current_streak=current_streak,
            longest_win_streak=longest_win_streak,
            longest_loss_streak=longest_loss_streak,
            
            # AI insights
            ai_insights=ai_insights,
            ai_risk_suggestions=ai_risk_suggestions,
            
            # Mistakes & Rules
            mistake_alerts=mistake_alerts,
            rule_compliance=rule_compliance,
            
            # Advanced metrics
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            expectancy=round(expectancy, 2),
            sharpe_ratio=round(sharpe_ratio, 2),
            risk_of_ruin=round(risk_of_ruin, 1),
            avg_holding_time=avg_holding_time,
            best_trade_symbol=best_trade_symbol,
            worst_trade_symbol=worst_trade_symbol,
            most_profitable_strategy=most_profitable_strategy,
            
            # Reports & Challenges
            challenge_progress=challenge_progress,
            reports_snapshot=reports_snapshot,
            
            # Gamification
            xp_points=xp_points,
            level=level,
            badges=badges,
            
            # Other data
            strategies=Strategy.query.all() if db else [],
            mistakes=Mistake.query.all() if db else [],
            now=datetime.now()
        )
    except Exception as e:
        safe_log_error(f"Critical error in journal dashboard: {e}")
        import traceback
        safe_log_error(f"Dashboard error traceback: {traceback.format_exc()}")
        # Return minimal dashboard with empty data
        return render_template(
            'dashboard_new_journal.html',
            error_message="Dashboard temporarily unavailable. Please try again.",
            **_get_empty_dashboard_data()
        )


@calculatentrade_bp.route('/trades')
@subscription_required_journal
def get_trades():
    trades = Trade.query.order_by(Trade.date.desc()).all()
    strategies = Strategy.query.all()
    
    # Calculate stats for the template
    total_trades = len(trades)
    total_pnl = sum(t.pnl for t in trades) if trades else 0
    winning_trades = len([t for t in trades if t.pnl > 0])
    losing_trades = len([t for t in trades if t.pnl < 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    return render_template('trades_journal.html', 
                         trades=trades, 
                         strategies=strategies,
                         total_trades=total_trades,
                         total_pnl=total_pnl,
                         winning_trades=winning_trades,
                         losing_trades=losing_trades,
                         win_rate=win_rate,
                         now=datetime.now())


# ---------------- API ROUTES ---------------- #
@calculatentrade_bp.route('/api/trades', methods=['GET'])
def api_get_trades():
    filter_type = request.args.get('filter', 'all')
    sort = request.args.get('sort', 'date-desc')
    query = Trade.query

    # Filter
    if filter_type in ['win', 'loss']:
        query = query.filter_by(result=filter_type)

    # Sorting
    if sort == 'date-asc':
        query = query.order_by(Trade.date.asc())
    elif sort == 'pnl-desc':
        query = query.order_by(Trade.pnl.desc())
    elif sort == 'pnl-asc':
        query = query.order_by(Trade.pnl.asc())
    else:  # default newest first
        query = query.order_by(Trade.date.desc())

    trades = [{
        'id': t.id,
        'symbol': t.symbol,
        'entry_price': t.entry_price,
        'exit_price': t.exit_price,
        'quantity': t.quantity,
        'date': t.date.strftime('%Y-%m-%d'),
        'result': t.result,
        'pnl': t.pnl,
        'notes': t.notes,
        'trade_type': t.trade_type,
        'strategy': {'id': t.strategy.id, 'name': t.strategy.name} if t.strategy else None
    } for t in query.all()]

    return jsonify({'trades': trades})


@calculatentrade_bp.route('/api/trades/<int:trade_id>', methods=['GET'])
def api_get_trade(trade_id):
    t = Trade.query.get_or_404(trade_id)
    trade = {
        'id': t.id,
        'symbol': t.symbol,
        'entry_price': t.entry_price,
        'exit_price': t.exit_price,
        'quantity': t.quantity,
        'date': t.date.strftime('%Y-%m-%d'),
        'result': t.result,
        'pnl': t.pnl,
        'notes': t.notes,
        'trade_type': t.trade_type,
        'strategy': {'id': t.strategy.id, 'name': t.strategy.name} if t.strategy else None
    }
    return jsonify(trade)


@calculatentrade_bp.route('/real_broker_connect')
@subscription_required_journal
def real_broker_connect():
    """Route to access multi-broker connect functionality"""
    try:
        # Import multi-broker functions
        from multi_broker_system import get_broker_session_status, USER_SESSIONS
        
        user_id = request.args.get('user_id', 'default_user')
        connected_brokers = []
        
        # Check all brokers for existing connections
        for broker in ['kite', 'dhan', 'angel']:
            try:
                status = get_broker_session_status(broker, user_id)
                if status['connected']:
                    connected_brokers.append({
                        'broker': broker,
                        'user_id': user_id,
                        'session_data': status.get('session_data', {})
                    })
            except Exception as e:
                safe_log_error(f"Error checking {broker} status: {e}")
                continue
        
        return render_template('multi_broker_connect.html',
                             connected_brokers=connected_brokers,
                             has_connected_brokers=len(connected_brokers) > 0,
                             user_id=user_id)
    except Exception as e:
        safe_log_error(f"Error in real_broker_connect: {e}")
        return render_template('multi_broker_connect.html',
                             connected_brokers=[],
                             has_connected_brokers=False,
                             user_id='default_user')

@calculatentrade_bp.route('/api/trades', methods=['POST'])
def api_add_trade():
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
            
        # Validate required fields
        required_fields = ['symbol', 'entry_price', 'exit_price', 'quantity', 'date']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        entry = float(data.get('entry_price', 0))
        exit_ = float(data.get('exit_price', 0))
        qty = float(data.get('quantity', 0))
        trade_type = data.get('trade_type', 'long')

        # Calculate PnL based on trade type
        pnl = (exit_ - entry) * qty if trade_type == 'long' else (entry - exit_) * qty
        
        # Auto-determine result if not provided
        result = data.get('result')
        if not result:
            result = 'win' if pnl > 0 else ('loss' if pnl < 0 else 'breakeven')

        trade = Trade(
            symbol=data.get('symbol').upper(),
            entry_price=entry,
            exit_price=exit_,
            quantity=qty,
            date=datetime.strptime(data.get('date'), '%Y-%m-%d'),
            result=result,
            pnl=pnl,
            notes=data.get('notes', ''),
            trade_type=trade_type,
            risk=float(data.get('risk', 0)),
            reward=float(data.get('reward', 0)),
            strategy_id=int(data.get('strategy_id')) if data.get('strategy_id') else None
        )
        db.session.add(trade)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'id': trade.id,
            'message': 'Trade added successfully',
            'trade': {
                'id': trade.id,
                'symbol': trade.symbol,
                'pnl': trade.pnl,
                'result': trade.result
            }
        })
    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Invalid data format: {str(e)}'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@calculatentrade_bp.route('/api/trades/<int:trade_id>', methods=['PUT'])
def api_update_trade_put(trade_id):
    try:
        trade = Trade.query.get_or_404(trade_id)
        data = request.json

        def safe_float(val, default):
            try:
                return float(val)
            except (TypeError, ValueError):
                return default

        trade.symbol = data.get('symbol', trade.symbol)
        trade.entry_price = safe_float(data.get('entry_price'), trade.entry_price)
        trade.exit_price = safe_float(data.get('exit_price'), trade.exit_price)
        trade.quantity = safe_float(data.get('quantity'), trade.quantity)
        trade.date = datetime.strptime(data.get('date', trade.date.strftime('%Y-%m-%d')), '%Y-%m-%d')
        trade.result = data.get('result', trade.result)
        trade.notes = data.get('notes', trade.notes)
        trade.trade_type = data.get('trade_type', trade.trade_type)
        trade.risk = safe_float(data.get('risk'), trade.risk)
        trade.reward = safe_float(data.get('reward'), trade.reward)

        # strategy_id
        if 'strategy_id' in data:
            strategy_id = data.get('strategy_id')
            trade.strategy_id = int(strategy_id) if strategy_id else None

        # recalc PnL
        if trade.trade_type == 'long':
            trade.pnl = (trade.exit_price - trade.entry_price) * trade.quantity
        else:
            trade.pnl = (trade.entry_price - trade.exit_price) * trade.quantity

        db.session.commit()
        return jsonify({'success': True, 'id': trade.id, 'pnl': trade.pnl})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@calculatentrade_bp.route('/api/trades/<int:trade_id>', methods=['DELETE'])
def api_delete_trade_delete(trade_id):
    trade = Trade.query.get_or_404(trade_id)
    db.session.delete(trade)
    db.session.commit()
    return jsonify({'success': True})



@calculatentrade_bp.route('/api/strategies/<int:strategy_id>', methods=['GET'])
def api_get_strategy(strategy_id):
    s = Strategy.query.get_or_404(strategy_id)
    return jsonify({
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "timeframe": s.timeframe,
        "market_type": s.market_type,
        "status": s.status,
        "stop_loss": s.stop_loss,
        "take_profit": s.take_profit,
        "position_size": s.position_size,
        "max_risk_per_trade": s.max_risk_per_trade,
        "risk_score": s.risk_score,
        "sharpe_ratio": s.sharpe_ratio,
        "max_drawdown": s.max_drawdown,
        "avg_trade_pl": s.avg_trade_pl,
        "entry_conditions": s.entry_conditions,
        "exit_conditions": s.exit_conditions,
        "primary_indicator": s.primary_indicator,
        "secondary_indicator": s.secondary_indicator,
        "parameters": s.parameters or [],
        "tags": s.tags or [],
        "backtests": s.backtests or [],
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None
    })


@calculatentrade_bp.route('/strategies')
@subscription_required_journal
def get_strategies():
    strategies = Strategy.query.all()
    enriched_strategies = []
    for s in strategies:
        enriched_strategies.append({
            'id': s.id,
            'name': s.name,
            'description': s.description,
            'win_rate': round(s.win_rate, 2),
            'total_trades': s.total_trades,
            'total_pnl': round(s.total_pnl, 2),
            'sharpe_ratio': s.sharpe_ratio,
            'max_drawdown': s.max_drawdown,
            'avg_trade_pl': s.avg_trade_pl,
            'status': s.status,
            'market_type': s.market_type,
            'timeframe': s.timeframe,
            'stop_loss': s.stop_loss,
            'take_profit': s.take_profit,
            'position_size': s.position_size,
            'max_risk_per_trade': s.max_risk_per_trade,
            'risk_score': s.risk_score,
            'tags': s.tags,
            'entry_conditions': s.entry_conditions,
            'exit_conditions': s.exit_conditions,
            'primary_indicator': s.primary_indicator,
            'secondary_indicator': s.secondary_indicator,
            'parameters': s.parameters,
            'backtests': s.backtests,
            'created_at': s.created_at.isoformat() if s.created_at else None,
            'updated_at': s.updated_at.isoformat() if s.updated_at else None
        })
    
    total_profit = sum(s['total_pnl'] for s in enriched_strategies)
    active_strategies = len([s for s in enriched_strategies if s['status'] == 'active'])
    avg_win_rate = sum(s['win_rate'] for s in enriched_strategies) / len(enriched_strategies) if enriched_strategies else 0
    avg_risk_score = sum(s['risk_score'] or 5 for s in enriched_strategies) / len(enriched_strategies) if enriched_strategies else 5
    
    return render_template('strategies_journal.html',
                           strategies=enriched_strategies,
                           total_profit=total_profit,
                           active_strategies=active_strategies,
                           avg_win_rate=round(avg_win_rate, 1),
                           avg_risk_score=round(avg_risk_score, 1),
                           now=datetime.now())


@calculatentrade_bp.route('/api/strategies/<int:strategy_id>', methods=['PUT'])
def api_update_strategy(strategy_id):
    try:
        data = request.get_json(force=True) or {}
        s = Strategy.query.get_or_404(strategy_id)

        old_values = {
            'name': s.name,
            'description': s.description,
            'timeframe': s.timeframe,
        }

        allowed_fields = [
            'name', 'description', 'timeframe', 'market_type', 'status',
            'stop_loss', 'take_profit', 'position_size', 'max_risk_per_trade',
            'risk_score', 'sharpe_ratio', 'max_drawdown', 'avg_trade_pl',
            'entry_conditions', 'exit_conditions',
            'primary_indicator', 'secondary_indicator'
        ]

        for field in allowed_fields:
            if field in data:
                setattr(s, field, data[field])

        if 'parameters' in data:
            params = data.get('parameters') or []
            if not isinstance(params, list):
                return jsonify({'success': False, 'message': 'parameters must be a list'}), 400

            clean_params = []
            for p in params:
                if not isinstance(p, dict):
                    continue
                pname = (p.get('name') or '').strip()
                pval = p.get('value') if 'value' in p else ''
                if pname:
                    clean_params.append({'name': pname, 'value': pval})
            s.parameters = clean_params

        db.session.commit()

        try:
            log_audit('update', 'strategy', strategy_id, old_values, data)
        except Exception:
            current_app.logger.debug("Audit logging failed for strategy %s", strategy_id)

        resp = {
            'success': True,
            'id': s.id,
            'strategy': {
                'id': s.id,
                'name': s.name,
                'description': s.description,
                'timeframe': s.timeframe,
                'stop_loss': s.stop_loss,
                'take_profit': s.take_profit,
                'position_size': s.position_size,
                'max_risk_per_trade': s.max_risk_per_trade,
                'risk_score': s.risk_score,
                'entry_conditions': s.entry_conditions,
                'exit_conditions': s.exit_conditions,
                'primary_indicator': s.primary_indicator,
                'secondary_indicator': s.secondary_indicator,
                'parameters': s.parameters or []
            }
        }
        return jsonify(resp), 200

    except Exception as e:
        try:
            current_app.logger.exception("Failed to update strategy %s: %s", strategy_id, e)
        except Exception:
            print(f"Failed to update strategy {strategy_id}: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@calculatentrade_bp.route('/strategies/<int:strategy_id>/edit', methods=['GET', 'POST'])
def edit_strategy(strategy_id):
    """Edit strategy form and handler"""
    strategy = Strategy.query.get_or_404(strategy_id)
    
    if request.method == 'POST':
        try:
            # Handle form submission
            strategy.name = request.form.get('name', strategy.name)
            strategy.description = request.form.get('description', strategy.description)
            strategy.timeframe = request.form.get('timeframe', strategy.timeframe)
            strategy.market_type = request.form.get('market_type', strategy.market_type)
            strategy.status = request.form.get('status', strategy.status)
            
            # Handle numeric fields safely
            def safe_float(val, default=None):
                if val is None or val == '':
                    return default
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return default

            def safe_int(val, default=None):
                if val is None or val == '':
                    return default
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return default
            
            strategy.stop_loss = safe_float(request.form.get('stop_loss_pct'))
            strategy.take_profit = safe_float(request.form.get('take_profit_pct'))
            strategy.position_size = safe_float(request.form.get('position_size'), 2.0)
            strategy.max_risk_per_trade = safe_float(request.form.get('max_risk_per_trade'), 1.0)
            strategy.risk_score = safe_int(request.form.get('risk_score'), 5)
            strategy.entry_conditions = request.form.get('entry_rules')
            strategy.exit_conditions = request.form.get('exit_rules')
            strategy.primary_indicator = request.form.get('primary_indicator')
            strategy.secondary_indicator = request.form.get('secondary_indicator')
            
            # Parse tags if provided as comma-separated string
            tags = request.form.get('tags', [])
            if isinstance(tags, str):
                tags = [tag.strip() for tag in tags.split(',') if tag.strip()]
            strategy.tags = tags
            
            strategy.updated_at = datetime.utcnow()
            db.session.commit()
            
            flash('Strategy updated successfully!', 'success')
            return redirect(url_for('calculatentrade.get_strategies'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating strategy: {str(e)}', 'error')
    
    # GET request - show edit form
    return render_template('strategy_edit_form.html', strategy=strategy)

@calculatentrade_bp.route('/api/strategies/<int:strategy_id>', methods=['DELETE'])
def api_delete_strategy(strategy_id):
    s = Strategy.query.get_or_404(strategy_id)
    db.session.delete(s)
    db.session.commit()
    return jsonify({'success': True})


@calculatentrade_bp.route('/rules')
@subscription_required_journal
def get_rules():
    try:
        # Get filter parameters
        category_filter = request.args.get('category')
        priority_filter = request.args.get('priority')
        active_filter = request.args.get('active')
        tag_filter = request.args.get('tag')
        
        # Build query with fallback for missing columns
        query = Rule.query
        try:
            if category_filter:
                query = query.filter(Rule.category == category_filter)
            if priority_filter:
                query = query.filter(Rule.priority == priority_filter)
            if active_filter is not None:
                query = query.filter(Rule.active == (active_filter.lower() == 'true'))
            if tag_filter:
                query = query.filter(Rule.tags.contains(tag_filter))
        except Exception:
            # Columns don't exist yet, use basic query
            query = Rule.query
        
        rules = query.order_by(Rule.created_at.desc()).all()
        
        # Enrich with stats (mock data for now)
        enriched_rules = []
        for r in rules:
            try:
                stats = RuleStats.query.filter_by(rule_id=r.id).first()
            except Exception:
                stats = None
                
            if not stats:
                # Create mock stats
                compliance = random.uniform(70, 95)
                violations = random.randint(0, 5)
            else:
                compliance = stats.compliance_percentage
                violations = stats.violations_count
            
            # Safe attribute access with fallbacks
            enriched_rules.append({
                'id': r.id,
                'title': r.title,
                'description': r.description,
                'category': getattr(r, 'category', 'Risk'),
                'tags': getattr(r, 'tags', '').split(',') if getattr(r, 'tags', '') else [],
                'priority': getattr(r, 'priority', 'medium'),
                'active': getattr(r, 'active', True),
                'linked_strategy': getattr(r, 'linked_strategy', None),
                'violation_consequence': getattr(r, 'violation_consequence', 'log'),
                'compliance_percentage': round(compliance, 1),
                'violations_count': violations,
                'created_at': r.created_at.strftime('%Y-%m-%d %H:%M')
            })
        
        strategies = Strategy.query.all()
        categories = ['Risk', 'Entry', 'Exit', 'Psychology', 'Money Management']
        priorities = ['low', 'medium', 'high']
        
        return render_template('rules_journal.html', 
                             rules=enriched_rules, 
                             strategies=strategies,
                             categories=categories,
                             priorities=priorities,
                             now=datetime.now())
                             
    except Exception as e:
        # Fallback to basic rules display
        rules = Rule.query.order_by(Rule.created_at.desc()).all()
        basic_rules = []
        for r in rules:
            basic_rules.append({
                'id': r.id,
                'title': r.title,
                'description': r.description,
                'category': 'Risk',
                'tags': [],
                'priority': 'medium',
                'active': True,
                'linked_strategy': None,
                'violation_consequence': 'log',
                'compliance_percentage': 85.0,
                'violations_count': 0,
                'created_at': r.created_at.strftime('%Y-%m-%d %H:%M')
            })
        
        return render_template('rules_journal.html', 
                             rules=basic_rules, 
                             strategies=Strategy.query.all(),
                             categories=['Risk', 'Entry', 'Exit', 'Psychology', 'Money Management'],
                             priorities=['low', 'medium', 'high'],
                             migration_needed=True,
                             now=datetime.now())


# ---------------- API ROUTES FOR RULES ---------------- #
@calculatentrade_bp.route('/api/rules', methods=['GET'])
def api_get_rules():
    rules = Rule.query.all()
    return jsonify([{
        'id': r.id,
        'title': r.title,
        'description': r.description
    } for r in rules])


@calculatentrade_bp.route('/api/rules/<int:rule_id>', methods=['GET'])
def api_get_rule(rule_id):
    r = Rule.query.get_or_404(rule_id)
    return jsonify({
        'id': r.id,
        'title': r.title,
        'description': r.description,
        'category': getattr(r, 'category', 'Entry'),
        'tags': getattr(r, 'tags', ''),
        'priority': getattr(r, 'priority', 'medium'),
        'active': getattr(r, 'active', True),
        'linked_strategy_id': getattr(r, 'linked_strategy_id', None),
        'violation_consequence': getattr(r, 'violation_consequence', 'log'),
        'save_template': getattr(r, 'save_template', False)
    })


@calculatentrade_bp.route('/api/rules', methods=['POST'])
def api_add_rule():
    data = request.json
    
    # Validation
    title = data.get('title', '').strip()
    if not title or len(title) > 100:
        return jsonify({'success': False, 'message': 'Title is required and must be under 100 characters'}), 400
    
    # Check for duplicate title
    existing = Rule.query.filter_by(title=title).first()
    if existing:
        return jsonify({'success': False, 'message': 'A rule with this title already exists'}), 400
    
    r = Rule(
        title=title,
        description=data.get('description', ''),
        category=data.get('category', 'Risk'),
        tags=data.get('tags', ''),
        priority=data.get('priority', 'medium'),
        active=data.get('active', True),
        linked_strategy_id=int(data.get('linked_strategy_id')) if data.get('linked_strategy_id') else None,
        violation_consequence=data.get('violation_consequence', 'log'),
        save_template=data.get('save_template', False)
    )
    db.session.add(r)
    db.session.commit()
    
    # Create initial stats
    stats = RuleStats(rule_id=r.id, compliance_percentage=100.0, violations_count=0)
    db.session.add(stats)
    db.session.commit()
    
    return jsonify({'success': True, 'id': r.id})


@calculatentrade_bp.route('/api/rules/<int:rule_id>', methods=['PUT'])
def api_update_rule(rule_id):
    try:
        data = request.json
        r = Rule.query.get_or_404(rule_id)
        
        # Validation
        title = data.get('title', r.title).strip()
        if not title or len(title) > 100:
            return jsonify({'success': False, 'message': 'Title is required and must be under 100 characters'}), 400
        
        # Check for duplicate title (excluding current rule)
        existing = Rule.query.filter(Rule.title == title, Rule.id != rule_id).first()
        if existing:
            return jsonify({'success': False, 'message': 'A rule with this title already exists'}), 400
        
        r.title = title
        r.description = data.get('description', r.description)
        r.category = data.get('category', r.category)
        r.tags = data.get('tags', r.tags)
        r.priority = data.get('priority', r.priority)
        r.active = data.get('active', r.active)
        r.linked_strategy_id = int(data.get('linked_strategy_id')) if data.get('linked_strategy_id') else None
        r.violation_consequence = data.get('violation_consequence', r.violation_consequence)
        r.save_template = data.get('save_template', r.save_template)
        r.updated_at = datetime.utcnow()
        
        db.session.commit()
        return jsonify({'success': True, 'id': r.id, 'message': 'Rule updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@calculatentrade_bp.route('/api/rules/<int:rule_id>', methods=['DELETE'])
def api_delete_rule(rule_id):
    try:
        r = Rule.query.get(rule_id)
        if not r:
            return jsonify({'success': False, 'message': 'Rule not found'}), 404
        
        # Delete associated rule stats first to avoid foreign key constraint issues
        try:
            stats = RuleStats.query.filter_by(rule_id=rule_id).all()
            for stat in stats:
                db.session.delete(stat)
        except Exception:
            pass  # Stats might not exist
            
        db.session.delete(r)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Rule deleted successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting rule {rule_id}: {str(e)}')
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500

# Add missing rule compliance tracking endpoint
@calculatentrade_bp.route('/api/rules/<int:rule_id>/violation', methods=['POST'])
def api_log_rule_violation(rule_id):
    try:
        data = request.get_json()
        r = Rule.query.get(rule_id)
        if not r:
            return jsonify({'success': False, 'message': 'Rule not found'}), 404
            
        # Get or create rule stats
        stats = RuleStats.query.filter_by(rule_id=rule_id).first()
        if not stats:
            stats = RuleStats(rule_id=rule_id)
            db.session.add(stats)
            
        # Update violation count
        stats.violations_count = (stats.violations_count or 0) + 1
        stats.last_violation_date = datetime.utcnow()
        stats.last_violation_example = data.get('example', '')
        
        # Recalculate compliance percentage (simple example)
        total_trades = Trade.query.count()
        if total_trades > 0:
            stats.compliance_percentage = max(0, 100 - (stats.violations_count / total_trades * 100))
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Rule violation logged'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@calculatentrade_bp.route('/mistakes')
@subscription_required_journal
def get_mistakes():
    mistakes = Mistake.query.order_by(Mistake.created_at.desc()).all()
    enriched_mistakes = []

    for m in mistakes:
        # Get related trade info if exists
        related_trade_info = None
        if m.related_trade_id:
            trade = Trade.query.get(m.related_trade_id)
            if trade:
                related_trade_info = {
                    "id": trade.id,
                    "symbol": trade.symbol,
                    "date": trade.date.strftime('%Y-%m-%d'),
                    "trade_type": trade.trade_type,
                    "pnl": trade.pnl
                }
        
        enriched_mistakes.append({
            "id": m.id,
            "title": m.title,
            "description": m.description,
            "category": m.category or 'other',
            "severity": m.severity or 'medium',
            "pnl_impact": m.pnl_impact,
            "risk_at_time": m.risk_at_time,
            "recurrence_count": m.recurrence_count or 0,
            "attachments_count": m.attachments_count or 0,
            "resolved_at": m.resolved_at.isoformat() if m.resolved_at else None,
            "tags": [t.name for t in m.tags] if hasattr(m, 'tags') else [],
            "confidence": m.confidence,
            "related_trade": related_trade_info,
            # For now, static values until you link mistakes with trades
            "count": m.recurrence_count or 1,
            "impact": abs(m.pnl_impact) if m.pnl_impact else 10,
            "created_at": m.created_at.strftime("%Y-%m-%d %H:%M") if m.created_at else ""
        })

    return render_template(
        "mistakes_journal.html",
        mistakes=enriched_mistakes,
        now=datetime.now()
    )


@calculatentrade_bp.route('/api/mistakes', methods=['GET'])
def api_get_mistakes():
    q = (request.args.get('q') or '').strip()
    category = request.args.get('category')
    severity = request.args.get('severity')
    include_deleted = request.args.get('include_deleted') == '1'

    qry = Mistake.query
    if not include_deleted:
        qry = qry.filter_by(is_deleted=False)
    if category:
        qry = qry.filter_by(category=category)
    if severity:
        qry = qry.filter_by(severity=severity)
    if q:
        # simple search - for production replace with FTS
        like = f"%{q}%"
        qry = qry.filter(db.or_(Mistake.title.ilike(like), Mistake.description.ilike(like), Mistake.searchable_text.ilike(like)))

    mistakes = [m.to_dict() for m in qry.order_by(Mistake.created_at.desc()).limit(200).all()]
    return jsonify({'ok': True, 'mistakes': mistakes})

@calculatentrade_bp.route('/api/mistakes/<int:mistake_id>', methods=['GET'])
def api_get_mistake(mistake_id):
    m = Mistake.query.get_or_404(mistake_id)
    return jsonify(m.to_dict(include_attachments=True))


@calculatentrade_bp.route('/api/mistakes', methods=['POST'])
def api_add_mistake():
    data = request.get_json(silent=True)
    is_json = data is not None
    if not is_json:
        # fallback to form data (FormData)
        data = request.form.to_dict(flat=True)

    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'success': False, 'message': 'title required'}), 400

    # related_trade_id may be '' or None or a string number
    rel = data.get('related_trade_id') or None
    if rel in ('', 'null'):
        rel = None

    # convert to int or None
    related_trade_id = None
    if rel is not None:
        try:
            related_trade_id = int(rel)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'related_trade_id must be a number'}), 400

        # validation: ensure trade exists
        if not Trade.query.get(related_trade_id):
            return jsonify({'success': False, 'message': f'Trade {related_trade_id} does not exist'}), 400

    # Handle numeric field conversions
    def safe_float(val):
        if not val or str(val).strip() == '':
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
    
    pnl_impact = safe_float(data.get('pnl_impact'))
    risk_at_time = safe_float(data.get('risk_at_time'))
    confidence = None
    if data.get('confidence'):
        try:
            confidence = int(data.get('confidence'))
        except (ValueError, TypeError):
            pass

    # Handle metadata
    metadata = data.get('metadata', {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except:
            metadata = {}
    
    # Serialize metadata to JSON string
    metadata_json = json.dumps(metadata) if metadata else '{}'

    # Create Mistake with all available fields
    reporter_id = data.get('reporter_id')
    if reporter_id == '':
        reporter_id = None
        
    m = Mistake(
        reporter_id=reporter_id,
        related_trade_id=related_trade_id,
        title=title,
        description=data.get('description'),
        category=data.get('category', 'other'),
        severity=data.get('severity', 'medium'),
        confidence=confidence,
        pnl_impact=pnl_impact,
        risk_at_time=risk_at_time,
        metadata_json=metadata_json,
        searchable_text=f"{title} {data.get('description', '')}".strip()
    )
    db.session.add(m)
    db.session.commit()
    
    # Handle tags if provided
    tags_data = data.get('tags')
    if tags_data:
        if isinstance(tags_data, str):
            try:
                tags_list = json.loads(tags_data)
            except:
                tags_list = [tags_data]
        else:
            tags_list = tags_data if isinstance(tags_data, list) else []
        
        for tag_name in tags_list:
            if tag_name.strip():
                tag = MistakeTag.query.filter_by(name=tag_name.strip()).first()
                if not tag:
                    tag = MistakeTag(name=tag_name.strip())
                    db.session.add(tag)
                    db.session.flush()
                m.tags.append(tag)
    
    # Handle file attachments
    if 'attachments' in request.files:
        files = request.files.getlist('attachments')
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                # Simple file storage (in production, use cloud storage)
                upload_folder = os.path.join(os.path.dirname(__file__), 'uploads', 'mistakes')
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, f"{m.id}_{filename}")
                file.save(file_path)
                
                # Log file save for debugging
                print(f"Saved file: {file_path}, exists: {os.path.exists(file_path)}")
                
                # Create attachment record
                attachment = MistakeAttachment(
                    mistake_id=m.id,
                    filename=filename,
                    mime_type=file.content_type,
                    size=os.path.getsize(file_path),
                    url=url_for('calculatentrade.serve_mistake_attachment', filename=f"{m.id}_{filename}", _external=True),
                    attachment_metadata_json='{}'
                )
                db.session.add(attachment)
                m.attachments_count = (m.attachments_count or 0) + 1
    
    db.session.commit()
    return jsonify({'success': True, 'id': m.id}), 201

@calculatentrade_bp.route('/api/mistakes/<int:mistake_id>', methods=['PUT'])
def api_update_mistake(mistake_id):
    data = request.get_json(silent=True)
    is_json = data is not None
    if not is_json:
        data = request.form.to_dict(flat=True)
    
    m = Mistake.query.get_or_404(mistake_id)
    
    # Update all available fields
    m.title = data.get('title', m.title)
    m.description = data.get('description', m.description)
    m.category = data.get('category', m.category)
    m.severity = data.get('severity', m.severity)
    
    # Handle numeric fields with conversion
    def safe_float(val):
        if not val or str(val).strip() == '':
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
    
    def safe_int(val):
        if not val or str(val).strip() == '':
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None
    
    if 'confidence' in data:
        m.confidence = safe_int(data.get('confidence'))
    
    if 'pnl_impact' in data:
        m.pnl_impact = safe_float(data.get('pnl_impact'))
    
    if 'risk_at_time' in data:
        m.risk_at_time = safe_float(data.get('risk_at_time'))
    
    # Handle related_trade_id
    if 'related_trade_id' in data:
        rel = data.get('related_trade_id')
        if rel in ('', 'null', None):
            m.related_trade_id = None
        else:
            try:
                trade_id = int(rel)
                if Trade.query.get(trade_id):
                    m.related_trade_id = trade_id
                else:
                    return jsonify({'success': False, 'message': f'Trade {trade_id} does not exist'}), 400
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'related_trade_id must be a number'}), 400
    
    # Update metadata if provided
    if 'metadata' in data:
        metadata = data.get('metadata', {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}
        m.metadata_json = json.dumps(metadata) if metadata else '{}'
    
    # Handle tags update
    if 'tags' in data:
        # Remove existing tag associations
        db.session.execute(
            db.delete(MistakeTagLink).where(MistakeTagLink.mistake_id == m.id)
        )
        
        tags_data = data.get('tags')
        if tags_data:
            if isinstance(tags_data, str):
                try:
                    tags_list = json.loads(tags_data)
                except:
                    tags_list = [tags_data]
            else:
                tags_list = tags_data if isinstance(tags_data, list) else []
            
            for tag_name in tags_list:
                if tag_name.strip():
                    tag = MistakeTag.query.filter_by(name=tag_name.strip()).first()
                    if not tag:
                        tag = MistakeTag(name=tag_name.strip())
                        db.session.add(tag)
                        db.session.flush()
                    
                    # Create new tag link
                    tag_link = MistakeTagLink(mistake_id=m.id, tag_id=tag.id)
                    db.session.add(tag_link)
    
    # Handle new file attachments
    if 'attachments' in request.files:
        files = request.files.getlist('attachments')
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(os.path.dirname(__file__), 'uploads', 'mistakes')
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, f"{m.id}_{filename}")
                file.save(file_path)
                
                # Log file save for debugging
                print(f"Updated file: {file_path}, exists: {os.path.exists(file_path)}")
                
                attachment = MistakeAttachment(
                    mistake_id=m.id,
                    filename=filename,
                    mime_type=file.content_type,
                    size=os.path.getsize(file_path),
                    url=url_for('calculatentrade.serve_mistake_attachment', filename=f"{m.id}_{filename}", _external=True),
                    attachment_metadata_json='{}'
                )
                db.session.add(attachment)
                m.attachments_count = m.attachments.count()
    
    # Update searchable text
    m.searchable_text = f"{m.title} {m.description or ''}".strip()
    m.updated_at = datetime.utcnow()
    
    db.session.commit()
    return jsonify({'success': True, 'id': m.id})


@calculatentrade_bp.route('/api/mistakes/<int:mistake_id>', methods=['DELETE'])
def api_delete_mistake(mistake_id):
    try:
        m = Mistake.query.get(mistake_id)
        if not m:
            return jsonify({'success': False, 'message': 'Mistake not found'}), 404
            
        db.session.delete(m)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Mistake deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# Add missing mistake resolution endpoint
@calculatentrade_bp.route('/api/mistakes/<int:mistake_id>/resolve', methods=['POST'])
def api_resolve_mistake(mistake_id):
    try:
        m = Mistake.query.get(mistake_id)
        if not m:
            return jsonify({'success': False, 'message': 'Mistake not found'}), 404
            
        m.resolved_at = datetime.utcnow()
        m.resolved_by = 'user'  # In a real app, get from session
        
        # Calculate time to resolve if not already set
        if m.created_at and not m.time_to_resolve_seconds:
            time_diff = m.resolved_at - m.created_at
            m.time_to_resolve_seconds = int(time_diff.total_seconds())
            
        db.session.commit()
        return jsonify({'success': True, 'message': 'Mistake marked as resolved'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@calculatentrade_bp.route('/api/trades/for_mistakes', methods=['GET'])
def api_get_trades_for_mistakes():
    """Get trades for mistake dropdown - returns unique trades with identifying info"""
    try:
        trades = Trade.query.order_by(Trade.date.desc()).limit(100).all()
        trade_options = []
        
        for trade in trades:
            # Create a unique identifier string
            identifier = f"{trade.symbol} - {trade.date.strftime('%Y-%m-%d')} - {'Long' if trade.trade_type == 'long' else 'Short'} - ₹{trade.pnl:.2f}"
            
            trade_options.append({
                'id': trade.id,
                'identifier': identifier,
                'symbol': trade.symbol,
                'date': trade.date.strftime('%Y-%m-%d'),
                'trade_type': trade.trade_type,
                'pnl': trade.pnl,
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'quantity': trade.quantity
            })
        
        return jsonify({'success': True, 'trades': trade_options})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------- CHALLENGES ---------------- #
@calculatentrade_bp.route("/challenges")
@subscription_required_journal
def get_challenges():
    challenges = Challenge.query.order_by(Challenge.created_at.desc()).all()
    return render_template("challenges_journal.html", challenges=challenges, now=datetime.now())


# --- Enhanced Challenge API Routes ---
@calculatentrade_bp.route("/api/challenges", methods=["GET"])
def api_get_challenges():
    challenges = Challenge.query.order_by(Challenge.created_at.desc()).all()
    return jsonify({"success": True, "challenges": [c.to_dict() for c in challenges]})

@calculatentrade_bp.route("/api/challenges/<int:challenge_id>", methods=["GET"])
def api_get_challenge(challenge_id):
    c = Challenge.query.get_or_404(challenge_id)
    return jsonify({"success": True, "challenge": c.to_dict()})


@calculatentrade_bp.route("/api/challenges", methods=["POST"])
def api_add_challenge():
    data = request.json
    c = Challenge(
        title=data.get("title"),
        description=data.get("description"),
        challenge_type=data.get("challenge_type", "profit"),
        start_date=datetime.strptime(data["start_date"], "%Y-%m-%d").date(),
        end_date=datetime.strptime(data["end_date"], "%Y-%m-%d").date(),
        initial_capital=float(data.get("initial_capital", 10000)),
        target_value=float(data.get("target_value", 0)),
        target_is_percent=bool(data.get("target_is_percent", False)),
        risk_per_trade_pct=float(data.get("risk_per_trade_pct", 2.0)),
        max_drawdown_pct=float(data.get("max_drawdown_pct", 10.0)),
        daily_trade_limit=int(data.get("daily_trade_limit", 5)),
        milestones=data.get("milestones", []),
        motivation_quote=data.get("motivation_quote", ""),
        status="ongoing"
    )
    db.session.add(c)
    db.session.commit()
    return jsonify({"success": True, "id": c.id})


@calculatentrade_bp.route("/api/challenges/<int:challenge_id>", methods=["PUT"])
def api_update_challenge(challenge_id):
    c = Challenge.query.get_or_404(challenge_id)
    data = request.json
    c.title = data.get("title", c.title)
    c.description = data.get("description", c.description)
    c.challenge_type = data.get("challenge_type", c.challenge_type)
    if "start_date" in data:
        c.start_date = datetime.strptime(data["start_date"], "%Y-%m-%d").date()
    if "end_date" in data:
        c.end_date = datetime.strptime(data["end_date"], "%Y-%m-%d").date()
    if "initial_capital" in data:
        c.initial_capital = float(data["initial_capital"])
    if "target_value" in data:
        c.target_value = float(data["target_value"])
    if "target_is_percent" in data:
        c.target_is_percent = bool(data["target_is_percent"])
    if "milestones" in data:
        c.milestones = data["milestones"]
    if "motivation_quote" in data:
        c.motivation_quote = data["motivation_quote"]
    if "status" in data:
        c.status = data["status"]
    c.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"success": True, "id": c.id})


@calculatentrade_bp.route("/api/challenges/<int:challenge_id>", methods=["DELETE"])
def api_delete_challenge(challenge_id):
    c = Challenge.query.get_or_404(challenge_id)
    db.session.delete(c)
    db.session.commit()
    return jsonify({"success": True})

@calculatentrade_bp.route("/api/challenges/<int:challenge_id>/trade", methods=["POST"])
def api_add_challenge_trade(challenge_id):
    c = Challenge.query.get_or_404(challenge_id)
    data = request.json
    trade = ChallengeTrade(
        challenge_id=challenge_id,
        trade_date=datetime.strptime(data.get("trade_date", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d").date(),
        pnl=float(data.get("pnl", 0)),
        notes=data.get("notes", "")
    )
    db.session.add(trade)
    db.session.commit()
    return jsonify({"success": True, "id": trade.id})

@calculatentrade_bp.route("/api/challenges/<int:challenge_id>/mood", methods=["POST"])
def api_add_challenge_mood(challenge_id):
    c = Challenge.query.get_or_404(challenge_id)
    data = request.json
    mood = ChallengeMood(
        challenge_id=challenge_id,
        date=datetime.strptime(data.get("date", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d").date(),
        mood=data.get("mood", "neutral"),
        note=data.get("note", "")
    )
    db.session.add(mood)
    db.session.commit()
    return jsonify({"success": True, "id": mood.id})

@calculatentrade_bp.route("/api/challenges/<int:challenge_id>/progress", methods=["GET"])
def api_get_challenge_progress(challenge_id):
    c = Challenge.query.get_or_404(challenge_id)
    trades = c.trades.all()
    
    total_pnl = sum(t.pnl for t in trades)
    current_value = c.initial_capital + total_pnl
    
    if c.target_is_percent:
        percent_to_target = (total_pnl / (c.initial_capital * c.target_value / 100)) * 100 if c.target_value else 0
    else:
        percent_to_target = (current_value / c.target_value) * 100 if c.target_value else 0
    
    winning_streak = 0
    current_streak = 0
    for trade in sorted(trades, key=lambda x: x.trade_date, reverse=True):
        if trade.pnl > 0:
            current_streak += 1
            winning_streak = max(winning_streak, current_streak)
        else:
            current_streak = 0
    
    achieved_milestones = []
    for milestone in (c.milestones or []):
        if isinstance(milestone, dict) and "value" in milestone:
            if current_value >= milestone["value"]:
                achieved_milestones.append(milestone)
    
    days_left = (c.end_date - datetime.now().date()).days if c.end_date else 0
    
    return jsonify({
        "success": True,
        "current_pnl": total_pnl,
        "current_value": current_value,
        "percent_to_target": min(percent_to_target, 100),
        "winning_streak": winning_streak,
        "achieved_milestones": achieved_milestones,
        "days_left": max(days_left, 0)
    })

@calculatentrade_bp.route("/api/challenges/<int:challenge_id>/calendar", methods=["GET"])
def api_get_challenge_calendar(challenge_id):
    c = Challenge.query.get_or_404(challenge_id)
    trades = {t.trade_date.isoformat(): t.pnl for t in c.trades.all()}
    moods = {m.date.isoformat(): m.mood for m in c.moods.all()}
    
    calendar_data = []
    current_date = c.start_date
    while current_date <= min(c.end_date, datetime.now().date()):
        date_str = current_date.isoformat()
        calendar_data.append({
            "date": date_str,
            "pnl": trades.get(date_str, 0),
            "mood": moods.get(date_str, None),
            "has_trade": date_str in trades
        })
        current_date += timedelta(days=1)
    
    return jsonify({"success": True, "calendar": calendar_data})


@calculatentrade_bp.route('/reports')
@subscription_required_journal
def get_reports():
    """
    Render enhanced reports page with performance analytics.
    """
    strategies = Strategy.query.all()
    return render_template("reports_journal.html", strategies=strategies, now=datetime.now())


# Enhanced Reports API
@calculatentrade_bp.route('/api/reports/summary')
def api_reports_summary():
    start_date_str = request.args.get("start", (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
    end_date_str = request.args.get("end", datetime.now().strftime("%Y-%m-%d"))
    strategy_id = request.args.get("strategy_id")
    symbol = request.args.get("symbol")
    trade_type = request.args.get("trade_type")

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    query = Trade.query.filter(Trade.date >= start_date, Trade.date <= end_date)
    if strategy_id:
        query = query.filter(Trade.strategy_id == strategy_id)
    if symbol:
        query = query.filter(Trade.symbol.ilike(f"%{symbol}%"))
    if trade_type:
        query = query.filter(Trade.trade_type == trade_type)
    
    trades = query.order_by(Trade.date).all()
    
    if not trades:
        return jsonify({
            "total_pnl": 0, "win_rate": 0, "total_trades": 0, "avg_rr": 0,
            "expectancy": 0, "profit_factor": 0, "max_drawdown": 0, "avg_hold_time": 0
        })

    total_trades = len(trades)
    total_pnl = sum(t.pnl for t in trades)
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl < 0]
    
    win_rate = (len(wins) / total_trades) * 100 if total_trades else 0
    avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 0
    avg_loss = abs(sum(t.pnl for t in losses) / len(losses)) if losses else 0
    
    # Expectancy = (Win% × AvgWin) – (Loss% × AvgLoss)
    expectancy = (win_rate/100 * avg_win) - ((100-win_rate)/100 * avg_loss)
    
    # Profit Factor = Gross Profit ÷ Gross Loss
    gross_profit = sum(t.pnl for t in wins)
    gross_loss = abs(sum(t.pnl for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    
    # Max Drawdown calculation
    cumulative_pnl = 0
    peak = 0
    max_drawdown = 0
    for trade in trades:
        cumulative_pnl += trade.pnl
        if cumulative_pnl > peak:
            peak = cumulative_pnl
        drawdown = peak - cumulative_pnl
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    # R-Multiple calculation
    rr_trades = [t for t in trades if t.risk and t.reward and t.risk > 0]
    avg_rr = sum(t.reward / t.risk for t in rr_trades) / len(rr_trades) if rr_trades else 0
    
    return jsonify({
        "total_pnl": round(total_pnl, 2),
        "win_rate": round(win_rate, 2),
        "total_trades": total_trades,
        "avg_rr": round(avg_rr, 2),
        "expectancy": round(expectancy, 2),
        "profit_factor": round(profit_factor, 2),
        "max_drawdown": round(max_drawdown, 2),
        "avg_hold_time": 0  # Placeholder - would need entry/exit timestamps
    })

@calculatentrade_bp.route('/api/reports/equity_curve')
def api_reports_equity_curve():
    start_date_str = request.args.get("start", (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
    end_date_str = request.args.get("end", datetime.now().strftime("%Y-%m-%d"))
    
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    
    trades = Trade.query.filter(Trade.date >= start_date, Trade.date <= end_date).order_by(Trade.date).all()
    
    equity_data = []
    cumulative_pnl = 0
    peak = 0
    
    for trade in trades:
        cumulative_pnl += trade.pnl
        if cumulative_pnl > peak:
            peak = cumulative_pnl
        drawdown = peak - cumulative_pnl
        
        equity_data.append({
            "date": trade.date.strftime("%Y-%m-%d"),
            "equity": round(cumulative_pnl, 2),
            "drawdown": round(drawdown, 2)
        })
    
    return jsonify({"equity_curve": equity_data})

@calculatentrade_bp.route('/api/reports/r_multiples_hist')
def api_reports_r_multiples():
    start_date_str = request.args.get("start", (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
    end_date_str = request.args.get("end", datetime.now().strftime("%Y-%m-%d"))
    
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    
    trades = Trade.query.filter(Trade.date >= start_date, Trade.date <= end_date).all()
    
    # Calculate R-multiples (using PnL as proxy if risk/reward not available)
    r_multiples = []
    for trade in trades:
        if trade.risk and trade.risk > 0:
            r_multiple = trade.pnl / trade.risk
        else:
            # Fallback: normalize PnL to approximate R-multiple
            r_multiple = trade.pnl / 100 if trade.pnl else 0
        r_multiples.append(r_multiple)
    
    # Create histogram bins
    bins = [-3, -2, -1, 0, 1, 2, 3, 4, 5]
    histogram = [0] * (len(bins) - 1)
    
    for r in r_multiples:
        for i in range(len(bins) - 1):
            if bins[i] <= r < bins[i + 1]:
                histogram[i] += 1
                break
        else:
            if r >= bins[-1]:
                histogram[-1] += 1
    
    return jsonify({
        "bins": [f"{bins[i]:.1f} to {bins[i+1]:.1f}" for i in range(len(bins)-1)],
        "counts": histogram
    })

@calculatentrade_bp.route('/api/reports/trades')
def api_reports_trades():
    start_date_str = request.args.get("start", (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
    end_date_str = request.args.get("end", datetime.now().strftime("%Y-%m-%d"))
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))
    
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    
    query = Trade.query.filter(Trade.date >= start_date, Trade.date <= end_date)
    total = query.count()
    trades = query.order_by(Trade.date.desc()).offset((page-1)*per_page).limit(per_page).all()
    
    trade_data = []
    for t in trades:
        r_multiple = (t.pnl / t.risk) if t.risk and t.risk > 0 else 0
        trade_data.append({
            "id": t.id,
            "date": t.date.strftime("%Y-%m-%d"),
            "symbol": t.symbol,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "quantity": t.quantity,
            "pnl": t.pnl,
            "r_multiple": round(r_multiple, 2),
            "trade_type": t.trade_type,
            "notes": t.notes or "",
            "strategy": t.strategy.name if t.strategy else ""
        })
    
    return jsonify({
        "trades": trade_data,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    })

@calculatentrade_bp.route('/api/reports/by_strategy')
def api_reports_by_strategy():
    start_date_str = request.args.get("start", (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
    end_date_str = request.args.get("end", datetime.now().strftime("%Y-%m-%d"))
    
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    
    trades = Trade.query.filter(Trade.date >= start_date, Trade.date <= end_date).all()
    
    strategy_stats = {}
    for trade in trades:
        strategy_name = trade.strategy.name if trade.strategy else "No Strategy"
        if strategy_name not in strategy_stats:
            strategy_stats[strategy_name] = {"pnl": 0, "trades": 0, "wins": 0}
        
        strategy_stats[strategy_name]["pnl"] += trade.pnl
        strategy_stats[strategy_name]["trades"] += 1
        if trade.pnl > 0:
            strategy_stats[strategy_name]["wins"] += 1
    
    result = []
    for strategy, stats in strategy_stats.items():
        win_rate = (stats["wins"] / stats["trades"]) * 100 if stats["trades"] else 0
        result.append({
            "strategy": strategy,
            "pnl": round(stats["pnl"], 2),
            "trades": stats["trades"],
            "win_rate": round(win_rate, 2)
        })
    
    return jsonify({"strategies": sorted(result, key=lambda x: x["pnl"], reverse=True)})

@calculatentrade_bp.route('/api/reports/by_symbol')
def api_reports_by_symbol():
    start_date_str = request.args.get("start", (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
    end_date_str = request.args.get("end", datetime.now().strftime("%Y-%m-%d"))
    
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    
    trades = Trade.query.filter(Trade.date >= start_date, Trade.date <= end_date).all()
    
    symbol_stats = {}
    for trade in trades:
        symbol = trade.symbol
        if symbol not in symbol_stats:
            symbol_stats[symbol] = {"pnl": 0, "trades": 0, "wins": 0}
        
        symbol_stats[symbol]["pnl"] += trade.pnl
        symbol_stats[symbol]["trades"] += 1
        if trade.pnl > 0:
            symbol_stats[symbol]["wins"] += 1
    
    result = []
    for symbol, stats in symbol_stats.items():
        win_rate = (stats["wins"] / stats["trades"]) * 100 if stats["trades"] else 0
        result.append({
            "symbol": symbol,
            "pnl": round(stats["pnl"], 2),
            "trades": stats["trades"],
            "win_rate": round(win_rate, 2)
        })
    
    return jsonify({"symbols": sorted(result, key=lambda x: x["pnl"], reverse=True)[:20]})

@calculatentrade_bp.route('/api/reports/calendar')
def api_reports_calendar():
    start_date_str = request.args.get("start", (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
    end_date_str = request.args.get("end", datetime.now().strftime("%Y-%m-%d"))
    
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    
    trades = Trade.query.filter(Trade.date >= start_date, Trade.date <= end_date).all()
    
    # Group trades by date
    daily_pnl = {}
    for trade in trades:
        date_str = trade.date.strftime("%Y-%m-%d")
        if date_str not in daily_pnl:
            daily_pnl[date_str] = {"pnl": 0, "trades": 0, "notes": []}
        daily_pnl[date_str]["pnl"] += trade.pnl
        daily_pnl[date_str]["trades"] += 1
        if trade.notes:
            daily_pnl[date_str]["notes"].append(trade.notes)
    
    calendar_data = []
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        day_data = daily_pnl.get(date_str, {"pnl": 0, "trades": 0, "notes": []})
        
        calendar_data.append({
            "date": date_str,
            "pnl": round(day_data["pnl"], 2),
            "trades": day_data["trades"],
            "notes": "; ".join(day_data["notes"][:3])  # Limit to 3 notes
        })
        current_date += timedelta(days=1)
    
    return jsonify({"calendar": calendar_data})


# ---------------- MISSING API ENDPOINTS ---------------- #

@calculatentrade_bp.route('/api/stats', methods=['GET'])
def api_get_stats():
    """Get trading statistics for dashboard updates"""
    try:
        trades = Trade.query.all()
        total_trades = len(trades)
        total_pnl = sum(t.pnl for t in trades) if trades else 0
        winning_trades = len([t for t in trades if t.pnl > 0])
        losing_trades = len([t for t in trades if t.pnl < 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        return jsonify({
            'total_trades': total_trades,
            'total_pnl': total_pnl,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@calculatentrade_bp.route('/api/analytics', methods=['GET'])
def api_get_analytics():
    """Get advanced analytics data"""
    try:
        trades = Trade.query.all()
        if not trades:
            return jsonify({
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0,
                'total_volume': 0,
                'best_symbol': None,
                'most_traded': None
            })
        
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl < 0]
        
        avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.pnl for t in losses) / len(losses) if losses else 0
        
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Calculate max drawdown
        cumulative_pnl = 0
        peak = 0
        max_drawdown = 0
        for trade in sorted(trades, key=lambda x: x.date):
            cumulative_pnl += trade.pnl
            if cumulative_pnl > peak:
                peak = cumulative_pnl
            drawdown = peak - cumulative_pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # Simple Sharpe ratio calculation
        pnl_values = [t.pnl for t in trades]
        avg_return = sum(pnl_values) / len(pnl_values)
        std_dev = (sum((x - avg_return) ** 2 for x in pnl_values) / len(pnl_values)) ** 0.5
        sharpe_ratio = avg_return / std_dev if std_dev > 0 else 0
        
        # Symbol analysis
        symbol_stats = {}
        for trade in trades:
            if trade.symbol not in symbol_stats:
                symbol_stats[trade.symbol] = {'pnl': 0, 'count': 0}
            symbol_stats[trade.symbol]['pnl'] += trade.pnl
            symbol_stats[trade.symbol]['count'] += 1
        
        best_symbol = max(symbol_stats.items(), key=lambda x: x[1]['pnl'])[0] if symbol_stats else None
        most_traded = max(symbol_stats.items(), key=lambda x: x[1]['count'])[0] if symbol_stats else None
        
        total_volume = sum(t.quantity for t in trades)
        
        return jsonify({
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'total_volume': total_volume,
            'best_symbol': best_symbol,
            'most_traded': most_traded
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------------- API OTHER MODELS ---------------- #


import math

# helper: safe serializer for a Strategy instance
def _serialize_strategy(s):
    try:
        params = s.parameters or []
        # if stored as string, try to load; otherwise assume list/dict
        if isinstance(params, str):
            import json
            try:
                params = json.loads(params)
            except Exception:
                params = []
    except Exception:
        params = []

    return {
        'id': s.id,
        'name': s.name,
        'description': s.description,
        'timeframe': s.timeframe,
        'market_type': s.market_type,
        'status': s.status,
        'stop_loss': s.stop_loss,
        'take_profit': s.take_profit,
        'position_size': s.position_size,
        'max_risk_per_trade': s.max_risk_per_trade,
        'risk_score': s.risk_score,
        'sharpe_ratio': s.sharpe_ratio,
        'max_drawdown': s.max_drawdown,
        'avg_trade_pl': s.avg_trade_pl,
        'entry_conditions': s.entry_conditions,
        'exit_conditions': s.exit_conditions,
        'primary_indicator': s.primary_indicator,
        'secondary_indicator': s.secondary_indicator,
        'parameters': params
    }

# Combined endpoint: GET (list) and POST (create)
@calculatentrade_bp.route('/strategies/create', methods=['POST'])
def create_strategy():
    """Create a new strategy from form data"""
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
            
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'success': False, 'message': 'Strategy name is required'}), 400

        # Check for duplicate name
        existing = Strategy.query.filter_by(name=name).first()
        if existing:
            return jsonify({'success': False, 'message': 'Strategy name already exists'}), 400

        # Handle numeric fields safely
        def safe_float(val, default=None):
            if val is None or val == '':
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        def safe_int(val, default=None):
            if val is None or val == '':
                return default
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        # Parse tags if provided as comma-separated string
        tags = data.get('tags', [])
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(',') if tag.strip()]

        strategy = Strategy(
            name=name,
            description=data.get('description', ''),
            timeframe=data.get('timeframe', '1d'),
            market_type=data.get('market_type'),
            status=data.get('status', 'active'),
            stop_loss=safe_float(data.get('stop_loss_pct')),
            take_profit=safe_float(data.get('take_profit_pct')),
            position_size=safe_float(data.get('position_size'), 2.0),
            max_risk_per_trade=safe_float(data.get('max_risk_per_trade'), 1.0),
            risk_score=safe_int(data.get('risk_score'), 5),
            entry_conditions=data.get('entry_rules'),
            exit_conditions=data.get('exit_rules'),
            primary_indicator=data.get('primary_indicator'),
            secondary_indicator=data.get('secondary_indicator'),
            tags=tags
        )

        db.session.add(strategy)
        db.session.commit()

        return jsonify({
            'success': True, 
            'id': strategy.id,
            'message': 'Strategy created successfully',
            'strategy': {
                'id': strategy.id,
                'name': strategy.name,
                'description': strategy.description
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@calculatentrade_bp.route('/api/strategies', methods=['GET', 'POST'])
def api_strategies():
    if request.method == 'GET':
        try:
            strategies = Strategy.query.order_by(Strategy.created_at.desc()).all()
            return jsonify({
                'success': True,
                'strategies': [{
                    'id': s.id,
                    'name': s.name,
                    'description': s.description,
                    'win_rate': s.win_rate,
                    'total_trades': s.total_trades,
                    'total_pnl': s.total_pnl,
                    'status': s.status,
                    'created_at': s.created_at.isoformat() if s.created_at else None
                } for s in strategies]
            })
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

    # POST - Create new strategy (alternative endpoint)
    return create_strategy()



@calculatentrade_bp.route('/trade_form', methods=['GET'])
@subscription_required_journal
def trade_form():
    """Empty form for adding a new trade"""
    strategies = Strategy.query.all()
    mistakes = Mistake.query.all()
    return render_template('trade_form_journal.html', trade=None, strategies=strategies, mistakes=mistakes)

@calculatentrade_bp.route('/trade_form', methods=['POST'])
def trade_form_post():
    """Handle trade form submission"""
    try:
        # Get form data
        symbol = request.form.get('symbol', '').strip().upper()
        entry_price = float(request.form.get('entry_price', 0))
        exit_price = float(request.form.get('exit_price', 0))
        quantity = int(request.form.get('quantity', 0))
        trade_type = request.form.get('trade_type', 'long')
        date_str = request.form.get('date')
        strategy_id = request.form.get('strategy_id')
        notes = request.form.get('notes', '')
        
        # Validate required fields
        if not symbol or not entry_price or not exit_price or not quantity:
            toast_error('Please fill in all required fields')
            return redirect(url_for('calculatentrade.trade_form'))
        
        # Parse date
        if date_str:
            trade_date = datetime.strptime(date_str, '%Y-%m-%d')
        else:
            trade_date = datetime.now()
        
        # Calculate PnL
        if trade_type == 'long':
            pnl = (exit_price - entry_price) * quantity
        else:
            pnl = (entry_price - exit_price) * quantity
        
        # Determine result
        if pnl > 0:
            result = 'win'
        elif pnl < 0:
            result = 'loss'
        else:
            result = 'breakeven'
        
        # Create trade
        trade = Trade(
            symbol=symbol,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            date=trade_date,
            result=result,
            pnl=pnl,
            notes=notes,
            trade_type=trade_type,
            strategy_id=int(strategy_id) if strategy_id else None
        )
        
        db.session.add(trade)
        db.session.commit()
        
        toast_success("Trade saved successfully!")
        return redirect(url_for('calculatentrade.get_trades'))
        
    except Exception as e:
        db.session.rollback()
        toast_error(f'Error adding trade: {str(e)}')
        return redirect(url_for('calculatentrade.trade_form'))


@calculatentrade_bp.route('/trade_form/<int:trade_id>', methods=['GET', 'POST'])
def edit_trade_form(trade_id):
    """Pre-filled form for editing an existing trade"""
    trade = Trade.query.get_or_404(trade_id)
    
    if request.method == 'POST':
        try:
            trade.symbol = request.form.get('symbol', '').strip().upper()
            trade.entry_price = float(request.form.get('entry_price', 0))
            trade.exit_price = float(request.form.get('exit_price', 0))
            trade.quantity = float(request.form.get('quantity', 0))
            trade.trade_type = request.form.get('trade_type', 'long')
            trade.strategy_id = int(request.form.get('strategy_id')) if request.form.get('strategy_id') else None
            trade.notes = request.form.get('notes', '')
            
            if request.form.get('date'):
                trade.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
            
            if trade.trade_type == 'long':
                trade.pnl = (trade.exit_price - trade.entry_price) * trade.quantity
            else:
                trade.pnl = (trade.entry_price - trade.exit_price) * trade.quantity
            
            trade.result = 'win' if trade.pnl > 0 else ('loss' if trade.pnl < 0 else 'breakeven')
            
            db.session.commit()
            toast_success("Trade updated successfully!")
            return redirect(url_for('calculatentrade.get_trades'))
            
        except Exception as e:
            db.session.rollback()
            toast_error(f'Error updating trade: {str(e)}')
    
    strategies = Strategy.query.all()
    mistakes = Mistake.query.all()
    return render_template('trade_form_journal.html', trade=trade, strategies=strategies, mistakes=mistakes)


@calculatentrade_bp.route("/trades/save", methods=["POST"])
def save_trade():
    trade_id = request.form.get("id")
    symbol = request.form["symbol"]
    date = datetime.strptime(request.form["date"], "%Y-%m-%d")   # ✅ convert to datetime
    entry_price = float(request.form["entry_price"])
    exit_price = float(request.form["exit_price"])
    quantity = float(request.form["quantity"])
    trade_type = request.form["trade_type"]
    strategy_id = int(request.form["strategy_id"]) if request.form.get("strategy_id") else None
    result = request.form["result"]
    notes = request.form.get("notes", "")

    # Calculate PnL
    pnl = (exit_price - entry_price) * quantity if trade_type == "long" else (entry_price - exit_price) * quantity

    if trade_id:  # update existing
        trade = Trade.query.get(trade_id)
        trade.symbol = symbol
        trade.date = date
        trade.entry_price = entry_price
        trade.exit_price = exit_price
        trade.quantity = quantity
        trade.trade_type = trade_type
        trade.strategy_id = strategy_id
        trade.result = result
        trade.notes = notes
        trade.pnl = pnl
    else:  # new trade
        trade = Trade(
            symbol=symbol,
            date=date,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            trade_type=trade_type,
            strategy_id=strategy_id,
            result=result,
            notes=notes,
            pnl=pnl
        )
        db.session.add(trade)

    db.session.commit()
    toast_success("Trade saved successfully!")
    return redirect(url_for(".get_trades"))   # ✅ go back to /trades


@calculatentrade_bp.route("/ai_summaries")
def ai_summaries():
    return render_template("ai_summaries.html", now=datetime.now())

@calculatentrade_bp.route("/api/ai_chat", methods=["POST"])
def api_ai_chat():
    data = request.get_json()
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({'error': 'Message is required'}), 400
    
    try:
        # Fetch trading context
        context = fetch_trading_context()
        
        # Generate AI response based on user query
        bot_response = generate_ai_response(user_message, context)
        
        return jsonify(bot_response)
    
    except Exception as e:
        return jsonify({
            'reply': 'Sorry, I encountered an error processing your request. Please try again.',
            'error': str(e)
        }), 500

def fetch_trading_context():
    """Fetch current trading data for AI context"""
    from datetime import datetime, timedelta
    
    # Last 30 days data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # Get trades
    trades = Trade.query.filter(
        Trade.date >= start_date.date(),
        Trade.date <= end_date.date()
    ).order_by(Trade.date.desc()).all()
    
    # Calculate summary metrics
    total_trades = len(trades)
    total_pnl = sum(t.pnl for t in trades)
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl < 0]
    
    win_rate = (len(wins) / total_trades * 100) if total_trades else 0
    avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 0
    avg_loss = abs(sum(t.pnl for t in losses) / len(losses)) if losses else 0
    
    # Symbol performance
    symbol_stats = {}
    for trade in trades:
        if trade.symbol not in symbol_stats:
            symbol_stats[trade.symbol] = {'pnl': 0, 'trades': 0}
        symbol_stats[trade.symbol]['pnl'] += trade.pnl
        symbol_stats[trade.symbol]['trades'] += 1
    
    # Strategy performance
    strategy_stats = {}
    for trade in trades:
        strategy_name = trade.strategy.name if trade.strategy else 'No Strategy'
        if strategy_name not in strategy_stats:
            strategy_stats[strategy_name] = {'pnl': 0, 'trades': 0}
        strategy_stats[strategy_name]['pnl'] += trade.pnl
        strategy_stats[strategy_name]['trades'] += 1
    
    # Active challenges
    active_challenges = Challenge.query.filter_by(status='ongoing').all()
    
    return {
        'period': '30 days',
        'total_trades': total_trades,
        'total_pnl': total_pnl,
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'best_symbol': max(symbol_stats.items(), key=lambda x: x[1]['pnl']) if symbol_stats else None,
        'worst_symbol': min(symbol_stats.items(), key=lambda x: x[1]['pnl']) if symbol_stats else None,
        'best_strategy': max(strategy_stats.items(), key=lambda x: x[1]['pnl']) if strategy_stats else None,
        'active_challenges': len(active_challenges),
        'recent_trades': trades[:5]
    }

def generate_ai_response(user_message, context):
    """Generate AI response based on user query and trading context"""
    message_lower = user_message.lower()
    
    # Quick responses for common queries
    if 'summarize' in message_lower or 'summary' in message_lower:
        return generate_summary_response(context)
    
    elif 'best' in message_lower and ('symbol' in message_lower or 'stock' in message_lower):
        return generate_best_symbol_response(context)
    
    elif 'equity curve' in message_lower or 'performance' in message_lower:
        return generate_equity_curve_response(context)
    
    elif 'risk' in message_lower and 'reward' in message_lower:
        return generate_risk_reward_response(context)
    
    elif 'advice' in message_lower or 'improve' in message_lower:
        return generate_advice_response(context)
    
    elif 'challenge' in message_lower:
        return generate_challenge_response(context)
    
    else:
        return generate_general_response(user_message, context)

def generate_summary_response(context):
    """Generate trading summary response"""
    pnl_status = "profitable" if context['total_pnl'] > 0 else "losing"
    pnl_color = "success" if context['total_pnl'] > 0 else "danger"
    
    reply = f"""📊 **Trading Summary (Last {context['period']})**

• **Total P&L**: ₹{context['total_pnl']:,.2f} ({pnl_status})
• **Total Trades**: {context['total_trades']}
• **Win Rate**: {context['win_rate']:.1f}%
• **Average Win**: ₹{context['avg_win']:,.2f}
• **Average Loss**: ₹{context['avg_loss']:,.2f}

{get_performance_insight(context)}"""
    
    return {
        'reply': reply,
        'chart_type': 'summary',
        'data': {
            'pnl': context['total_pnl'],
            'trades': context['total_trades'],
            'win_rate': context['win_rate'],
            'color': pnl_color
        }
    }

def generate_best_symbol_response(context):
    """Generate best performing symbol response"""
    if not context['best_symbol']:
        return {'reply': 'No trading data available for symbol analysis.'}
    
    symbol, stats = context['best_symbol']
    worst_symbol, worst_stats = context['worst_symbol'] if context['worst_symbol'] else (None, None)
    
    reply = f"""🏆 **Symbol Performance Analysis**

**Best Performer**: {symbol}
• P&L: ₹{stats['pnl']:,.2f}
• Trades: {stats['trades']}
"""
    
    if worst_symbol:
        reply += f"""\n**Worst Performer**: {worst_symbol}
• P&L: ₹{worst_stats['pnl']:,.2f}
• Trades: {worst_stats['trades']}

💡 Consider focusing more on {symbol} and reviewing your {worst_symbol} strategy."""
    
    return {
        'reply': reply,
        'chart_type': 'symbols',
        'data': {
            'best': {'symbol': symbol, 'pnl': stats['pnl']},
            'worst': {'symbol': worst_symbol, 'pnl': worst_stats['pnl']} if worst_symbol else None
        }
    }

def generate_equity_curve_response(context):
    """Generate equity curve insight response"""
    trend = "upward" if context['total_pnl'] > 0 else "downward"
    trend_emoji = "📈" if context['total_pnl'] > 0 else "📉"
    
    reply = f"""{trend_emoji} **Equity Curve Analysis**

Your equity curve shows a {trend} trend over the last {context['period']}.

• **Net P&L**: ₹{context['total_pnl']:,.2f}
• **Win Rate**: {context['win_rate']:.1f}%
• **Trade Frequency**: {context['total_trades']} trades

{get_equity_insight(context)}"""
    
    return {
        'reply': reply,
        'chart_type': 'equity_curve',
        'data': {
            'pnl': context['total_pnl'],
            'trend': trend,
            'win_rate': context['win_rate']
        }
    }

def generate_risk_reward_response(context):
    """Generate risk-reward analysis response"""
    if context['avg_loss'] == 0:
        rr_ratio = "N/A"
        rr_analysis = "No losing trades to calculate risk-reward ratio."
    else:
        rr_ratio = context['avg_win'] / context['avg_loss']
        rr_analysis = f"Your average risk-reward ratio is 1:{rr_ratio:.2f}."
        
        if rr_ratio >= 2:
            rr_analysis += " Excellent! You're capturing good rewards relative to risk."
        elif rr_ratio >= 1.5:
            rr_analysis += " Good ratio, but there's room for improvement."
        else:
            rr_analysis += " Consider improving your reward-to-risk ratio."
    
    reply = f"""⚖️ **Risk-Reward Analysis**

• **Average Win**: ₹{context['avg_win']:,.2f}
• **Average Loss**: ₹{context['avg_loss']:,.2f}
• **R:R Ratio**: {rr_ratio if isinstance(rr_ratio, str) else f'1:{rr_ratio:.2f}'}

{rr_analysis}

💡 **Tip**: Aim for a minimum 1:2 risk-reward ratio for sustainable profitability."""
    
    return {
        'reply': reply,
        'chart_type': 'risk_reward',
        'data': {
            'avg_win': context['avg_win'],
            'avg_loss': context['avg_loss'],
            'ratio': rr_ratio if isinstance(rr_ratio, str) else rr_ratio
        }
    }

def generate_advice_response(context):
    """Generate trading advice response"""
    advice = []
    
    if context['win_rate'] < 50:
        advice.append("🎯 Focus on improving your trade selection - win rate below 50%")
    
    if context['avg_loss'] > context['avg_win']:
        advice.append("✂️ Consider tighter stop losses - average loss exceeds average win")
    
    if context['total_trades'] < 10:
        advice.append("📊 Increase trade frequency for better statistical significance")
    
    if not advice:
        advice.append("👍 Your trading metrics look good! Keep following your strategy")
    
    reply = f"""🤖 **AI Trading Advice**

Based on your last {context['period']} performance:

"""
    
    for i, tip in enumerate(advice, 1):
        reply += f"{i}. {tip}\n"
    
    reply += "\n💡 Remember: Consistency and discipline are key to long-term success!"
    
    return {'reply': reply}

def generate_challenge_response(context):
    """Generate challenge-related response"""
    if context['active_challenges'] == 0:
        reply = "🎯 You don't have any active challenges. Consider creating one to stay motivated and track specific goals!"
    else:
        reply = f"🏆 You have {context['active_challenges']} active challenge(s). Keep pushing towards your goals!"
    
    return {'reply': reply}

def generate_general_response(user_message, context):
    """Generate general response for unrecognized queries"""
    reply = f"""🤖 I'm your trading assistant! I can help you with:

• 📊 Trading summaries and performance analysis
• 🏆 Best/worst performing symbols and strategies  
• 📈 Equity curve insights
• ⚖️ Risk-reward analysis
• 💡 Trading advice and improvements
• 🎯 Challenge progress updates

Try asking: "Summarize my last 30 days" or "What's my best performing symbol?"""
    
    return {'reply': reply}

def get_performance_insight(context):
    """Get performance insight based on metrics"""
    if context['total_pnl'] > 0 and context['win_rate'] > 60:
        return "🎉 Excellent performance! You're profitable with a strong win rate."
    elif context['total_pnl'] > 0:
        return "✅ You're profitable! Focus on improving consistency."
    elif context['win_rate'] > 50:
        return "📈 Good win rate, but work on maximizing winners and minimizing losers."
    else:
        return "⚠️ Consider reviewing your strategy - both profitability and win rate need improvement."

def get_equity_insight(context):
    """Get equity curve insight"""
    if context['total_pnl'] > 0:
        return "💪 Keep following your current approach - it's working!"
    else:
        return "🔄 Consider adjusting your strategy or risk management approach."


from flask import request, session, jsonify
# optional: if you use flask-login
try:
    from flask_login import current_user
except Exception:
    current_user = None


# Audit logging helper
def log_audit(action, table_name, record_id=None, old_values=None, new_values=None):
    """Log audit trail for CRUD operations"""
    try:
        audit = AuditLog(
            action=action,
            table_name=table_name,
            record_id=record_id,
            old_values=json.dumps(old_values) if old_values else None,
            new_values=json.dumps(new_values) if new_values else None,
            user_id=getattr(current_user, 'id', None) if current_user else None,
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get('User-Agent') if request else None
        )
        db.session.add(audit)
        db.session.commit()
    except Exception as e:
        print(f"Audit logging failed: {e}")








@calculatentrade_bp.route('/settings')
@login_required
def settings():
    return render_template('settings_journal.html', now=datetime.now())


@calculatentrade_bp.route('/tutorials')
@subscription_required_journal
def tutorials():
    tutorials_list = [
        {
            'title': 'Trading Journal Overview',
            'description': 'Learn how to effectively use your trading journal to track and improve your performance.',
            'embed_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ'
        },
        {
            'title': 'Risk Management Basics',
            'description': 'Essential risk management principles every trader should know to protect their capital.',
            'embed_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ'
        },
        {
            'title': 'How to Analyze Reports',
            'description': 'Step-by-step guide to analyzing your trading reports and identifying areas for improvement.',
            'embed_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ'
        },
        {
            'title': 'Setting Up Trading Strategies',
            'description': 'Create and manage your trading strategies with proper parameters and backtesting.',
            'embed_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ'
        },
        {
            'title': 'Mistake Tracking & Learning',
            'description': 'How to effectively track your trading mistakes and turn them into learning opportunities.',
            'embed_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ'
        },
        {
            'title': 'Challenge Creation Guide',
            'description': 'Set up trading challenges to stay motivated and achieve your trading goals.',
            'embed_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ'
        }
    ]
    return render_template('tutorials_journal.html', tutorials=tutorials_list, now=datetime.now())


# ---------------- MULTI-BROKER API ENDPOINTS ---------------- #

# Add the missing API endpoints that are returning 404
@calculatentrade_bp.route('/api/multi_broker/register_app/<broker>', methods=['POST'])
def api_register_app_broker(broker):
    """Register broker app credentials"""
    try:
        from multi_broker_system import USER_APPS, save_broker_account
        
        if broker not in ['kite', 'dhan', 'angel']:
            return jsonify({"ok": False, "message": "unknown broker"}), 400
            
        data = request.get_json(force=True)
        user_id = data.get("user_id", "").strip()
        api_key = data.get("api_key")
        api_secret = data.get("api_secret")
        client_id = data.get("client_id")
        access_token = data.get("access_token")
        totp_secret = data.get("totp_secret")
        client_code = data.get("client_code")
        password = data.get("password")

        if not user_id:
            return jsonify({"ok": False, "message": "user_id required"}), 400

        # Save to in-memory store
        USER_APPS.setdefault(broker, {})[user_id] = {
            "api_key": api_key,
            "api_secret": api_secret,
            "client_id": client_id,
            "access_token": access_token,
            "totp_secret": totp_secret,
            "client_code": client_code,
            "password": password
        }
        
        # Save to database if function is available
        try:
            save_broker_account(broker, user_id,
                              api_key=api_key,
                              api_secret=api_secret,
                              client_id=client_id,
                              access_token=access_token,
                              totp_secret=totp_secret)
        except Exception as e:
            safe_log_error(f"Failed to save broker account: {e}")
        
        return jsonify({"ok": True, "message": f"Registered {user_id} for {broker}"}), 200
        
    except Exception as e:
        safe_log_error(f"Error registering {broker} app: {e}")
        return jsonify({"ok": False, "message": str(e)}), 500

@calculatentrade_bp.route('/api/multi_broker/validate_session/<broker>/<user_id>')
def api_validate_session(broker, user_id):
    """Validate if a session is still active"""
    try:
        from multi_broker_system import get_broker_session_status
        
        status = get_broker_session_status(broker, user_id)
        if status['connected']:
            return jsonify({
                'connected': True,
                'broker': broker,
                'user_id': user_id,
                'session_data': status.get('session_data', {})
            })
        else:
            return jsonify({
                'connected': False,
                'broker': broker,
                'user_id': user_id
            })
    except Exception as e:
        safe_log_error(f"Error validating session for {broker}/{user_id}: {e}")
        return jsonify({
            'connected': False,
            'broker': broker,
            'user_id': user_id,
            'error': str(e)
        })

# ---------------- MULTI-BROKER INTEGRATION ---------------- #
@calculatentrade_bp.route('/multi_broker_connect')
def multi_broker_connect():
    """Multi-broker connection page"""
    try:
        # Check for existing broker connections
        from multi_broker_system import get_broker_session_status, USER_SESSIONS
        
        user_id = request.args.get('user_id', 'default_user')
        connected_brokers = []
        
        # Check all brokers for existing connections
        for broker in ['kite', 'dhan', 'angel']:
            try:
                status = get_broker_session_status(broker, user_id)
                if status['connected']:
                    connected_brokers.append({
                        'broker': broker,
                        'user_id': user_id,
                        'session_data': status.get('session_data', {})
                    })
            except Exception as e:
                safe_log_error(f"Error checking {broker} status: {e}")
                continue
        
        return render_template('multi_broker_connect.html',
                             connected_brokers=connected_brokers,
                             has_connected_brokers=len(connected_brokers) > 0,
                             user_id=user_id)
    except Exception as e:
        safe_log_error(f"Error in multi_broker_connect: {e}")
        return render_template('multi_broker_connect.html',
                             connected_brokers=[],
                             has_connected_brokers=False,
                             user_id='default_user')


# ---------------- BROKER CONNECTION ROUTES ---------------- #


# ---------- Helper for TOTP secret normalization ----------
def _normalize_base32_secret(s: str):
    """
    Normalize a user-supplied TOTP secret into valid Base32.
    Accepts:
      - raw Base32 strings with/without spaces/lowercase
      - otpauth:// URIs (extracts ?secret=)
    Returns cleaned/padded Base32 string, or None if empty/invalid.
    """
    if not s:
        return None
    s = s.strip()

    # If user pasted otpauth:// URI, extract secret= param
    if s.lower().startswith("otpauth://"):
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(s)
            qs = parse_qs(parsed.query)
            secrs = qs.get("secret") or qs.get("SECRET")
            if secrs:
                s = secrs[0].strip()
        except Exception:
            pass

    # Remove whitespace, make uppercase
    s = "".join(s.split()).upper()

    # Remove non-base32 chars
    import re
    s = re.sub(r'[^A-Z2-7]', '', s)

    # Pad to multiple of 8 chars
    if s:
        rem = len(s) % 8
        if rem != 0:
            s = s + ("=" * (8 - rem))
    return s or None


# ---------- Register broker app credentials ----------
@calculatentrade_bp.route("/register_app/<broker>", methods=["POST"])
def register_app_broker(broker):
    if broker not in ["kite", "dhan", "angel"]:
        return jsonify({"ok": False, "message": "unknown broker"}), 400

    data = request.get_json(force=True)
    user_id = data.get("user_id", "").strip()
    api_key = data.get("api_key")
    api_secret = data.get("api_secret")
    client_id = data.get("client_id")
    access_token = data.get("access_token")
    raw_totp_secret = data.get("totp_secret")

    # ✅ normalize TOTP before saving
    totp_secret = _normalize_base32_secret(raw_totp_secret)

    if not user_id:
        return jsonify({"ok": False, "message": "user_id required"}), 400

    # validations
    if broker in ["kite", "angel"]:
        if not api_key or not api_secret:
            return jsonify({"ok": False, "message": "api_key and api_secret required"}), 400

    if broker == "dhan":
        if not ((api_key and api_secret) or (client_id and access_token)):
            return jsonify({"ok": False, "message": "Provide either (client_id+access_token) OR (partner_id+partner_secret)"}), 400

    # Save in DB
    try:
        acc = save_broker_account(broker, user_id,
                                  api_key=api_key,
                                  api_secret=api_secret,
                                  client_id=client_id,
                                  access_token=access_token,
                                  totp_secret=totp_secret)
    except IntegrityError:
        db.session.rollback()
        return jsonify({"ok": False, "message": "DB error saving registration"}), 500

    # Update in-memory helper - ensure USER_APPS is initialized
    USER_APPS.setdefault(broker, {})[user_id] = {
        "api_key": api_key, "api_secret": api_secret,
        "client_id": client_id, "access_token": access_token,
        "totp_secret": totp_secret
    }

    current_app.logger.info(f"Successfully registered {broker} credentials for user {user_id}")
    return jsonify({"ok": True, "message": f"Registered {user_id} for {broker}"}), 200


# ---------- Angel Login ----------
@calculatentrade_bp.route("/angel/login")
def angel_login():
    user_id = request.args.get("user_id", "").strip()
    if not user_id:
        return jsonify({"ok": False, "message": "user_id required"}), 400

    creds = USER_APPS["angel"].get(user_id)
    if not creds or not creds.get("api_key") or not creds.get("api_secret"):
        return jsonify({"ok": False, "message": "Register Angel api_key (client_id) and api_secret (client_secret) first"}), 400

    # ✅ Generate TOTP if secret is available
    totp_value = ""
    if creds.get("totp_secret"):
        try:
            secret = _normalize_base32_secret(creds["totp_secret"])
            if secret:
                totp = pyotp.TOTP(secret)
                totp_value = totp.now()
        except Exception as e:
            app.logger.exception("TOTP generation failed for %s: %s", user_id, e)

    return render_template(
        "connect_broker_journal.html",   # keep UI consistent
        now=datetime.now(),
        broker_status={"ok": False, "broker": "angel", "user_id": user_id},
        totp_value=totp_value,
        totp_message=("Auto-generated TOTP" if totp_value else "Enter TOTP manually")
    )


# ---------- Angel Login with Password + TOTP ----------
@calculatentrade_bp.route("/angel/login/password", methods=["POST"])
def angel_login_password():
    user_id = request.form.get("user_id", "").strip()
    client_code = request.form.get("client_code", "").strip()
    password = request.form.get("password", "").strip()
    totp = request.form.get("totp", "").strip()

    if not all([user_id, client_code, password, totp]):
        return render_template(
            "connect_broker_journal.html",
            now=datetime.now(),
            broker_status={"ok": False, "broker": "angel", "message": "All fields required for Angel login"}
        )

    creds = USER_APPS["angel"].get(user_id)
    if not creds:
        return render_template(
            "connect_broker_journal.html",
            now=datetime.now(),
            broker_status={"ok": False, "broker": "angel", "message": f"No Angel credentials found for user {user_id}"}
        )

    # Try SDK login
    try:
        smart = SmartConnect(api_key=creds["api_key"])
        data = smart.generateSession(clientCode=client_code, password=password, totp=totp)

        if isinstance(data, dict) and data.get("errorcode"):
            return render_template(
                "connect_broker_journal.html",
                now=datetime.now(),
                broker_status={"ok": False, "broker": "angel", "message": f"Angel login failed: {data.get('message', data)}"}
            )

        payload = data.get("data") if isinstance(data.get("data"), dict) else data
        jwt_token = payload.get("jwtToken") or payload.get("jwt_token")

        if not jwt_token:
            return render_template(
                "connect_broker_journal.html",
                now=datetime.now(),
                broker_status={"ok": False, "broker": "angel", "message": "Angel login succeeded but JWT missing"}
            )

        # Save session in memory
        USER_SESSIONS.setdefault("angel", {})[user_id] = {
            "jwt_token": jwt_token,
            "refresh_token": payload.get("refreshToken"),
            "feed_token": payload.get("feedToken"),
            "client_code": client_code,
            "smart_api": smart
        }

        # Persist to DB (✅ also normalize TOTP secret again before saving)
        save_broker_account(
            "angel",
            user_id,
            api_key=creds.get("api_key"),
            api_secret=creds.get("api_secret"),
            client_id=client_code,
            access_token=jwt_token,
            totp_secret=_normalize_base32_secret(creds.get("totp_secret"))
        )
        mark_connected("angel", user_id, True)

        # Keep in-memory consistent
        USER_APPS.setdefault("angel", {})[user_id] = {
            "api_key": creds.get("api_key"),
            "api_secret": creds.get("api_secret"),
            "client_id": client_code,
            "access_token": jwt_token,
            "totp_secret": _normalize_base32_secret(creds.get("totp_secret"))
        }

        session["angel_user_id"] = user_id

        return render_template(
            "connect_broker_journal.html",
            now=datetime.now(),
            broker_status={"ok": True, "broker": "angel", "user_id": user_id, "message": "Angel connected successfully"}
        )

    except Exception as e:
        app.logger.exception("Angel login failed for %s: %s", user_id, e)
        return render_template(
            "connect_broker_journal.html",
            now=datetime.now(),
            broker_status={"ok": False, "broker": "angel", "message": f"Angel login failed: {str(e)}"}
        )


@calculatentrade_bp.route("/connect/<broker>", methods=["POST"])
def connect_broker_legacy(broker):
    if broker not in USER_APPS:
        return jsonify({"ok": False, "message": "unknown broker"}), 400
    
    data = request.get_json(force=True)
    user_id = data.get("user_id", "").strip()
    
    if not user_id:
        return jsonify({"ok": False, "message": "user_id required"}), 400
    
    creds = USER_APPS[broker].get(user_id)
    if not creds:
        return jsonify({"ok": False, "message": "no app registered for this user"}), 400
    
    try:
        if broker == "kite":
            return _connect_kite(user_id, creds)
        elif broker == "dhan":
            return _connect_dhan(user_id, creds)
        elif broker == "angel":
            return _connect_angel(user_id, creds, data)
        else:
            return jsonify({"ok": False, "message": "unsupported broker"}), 400
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500


def _connect_kite(user_id, creds):
    """Connect to Kite Connect"""
    if not KiteConnect:
        return jsonify({"ok": False, "message": "KiteConnect SDK not installed"}), 500
    
    kite = KiteConnect(api_key=creds["api_key"])
    login_url = kite.login_url()
    
    # Store temporary state for verification
    session['kite_user_id'] = user_id
    session['kite_api_key'] = creds["api_key"]
    
    return jsonify({
        "ok": True, 
        "login_url": login_url,
        "message": "Redirect to Kite login"
    })


def _connect_dhan(user_id, creds):
    """Connect to DhanHQ"""
    if not make_dhan_client:
        return jsonify({"ok": False, "message": "DhanHQ SDK not installed"}), 500

    # ✅ Direct Token Mode
   # ✅ Direct Token Mode
    if creds.get("client_id") and creds.get("access_token"):
        USER_SESSIONS["dhan"][user_id] = {
            "access_token": creds["access_token"],
            "dhan_client_id": creds["client_id"],
            "mode": "direct"
        }
        save_broker_account("dhan", user_id,
                            client_id=creds.get("client_id"),
                            access_token=creds.get("access_token"))
        mark_connected("dhan", user_id, True)

        return render_template(
            "connect_broker_journal.html",
            now=datetime.now(),
            broker_status={"ok": True, "broker": "dhan", "user_id": user_id, "message": "Dhan connected successfully"}
        )

    # ✅ Partner Consent Mode
    try:
        consent_id = _dhan_generate_consent(creds["api_key"], creds["api_secret"])
        login_url = (
            f"{DHAN_AUTH_BASE}/oauth/authorize"
            f"?response_type=code"
            f"&client_id={creds['api_key']}"
            f"&redirect_uri={url_for('.dhan_auth_callback', _external=True)}"
            f"&consent_id={consent_id}"
        )
        session["dhan_user_id"] = user_id
        session["dhan_partner_id"] = creds["api_key"]
        session["dhan_partner_secret"] = creds["api_secret"]
        session["dhan_consent_id"] = consent_id
        return jsonify({"ok": True, "login_url": login_url, "message": "Redirect to Dhan login"})
    except Exception as e:
        return jsonify({"ok": False, "message": f"Dhan connection failed: {str(e)}"}), 500


def _connect_angel(user_id, creds, data):
    """Connect to Angel One"""
    if not SmartConnect:
        return jsonify({"ok": False, "message": "Angel One SDK not installed"}), 500
    
    try:
        client_code = data.get("client_code", "").strip()
        password = data.get("password", "").strip()
        totp = data.get("totp", "").strip()
        
        if not client_code or not password or not totp:
            return jsonify({"ok": False, "message": "client_code, password, and totp required"}), 400
        
        # Login using Angel One SDK
        result = _angel_sdk_login(creds["api_key"], client_code, password, totp)
        
        # Store session
        USER_SESSIONS["angel"][user_id] = {
            "jwt_token": result["jwt_token"],
            "refresh_token": result["refresh_token"],
            "feed_token": result["feed_token"],
            "smart_api": result["smart_api"]
        }
        
        return jsonify({
            "ok": True,
            "message": "Angel One connected successfully",
            "user_id": user_id
        })
    except Exception as e:
        return jsonify({"ok": False, "message": f"Angel connection failed: {str(e)}"}), 500


# --------- KITE ---------
@calculatentrade_bp.route("/kite/login")
def kite_login():
    user_id = request.args.get("user_id", "").strip()
    if not user_id:
        return jsonify({"ok": False, "message": "user_id required"}), 400
    
    # Check if user has existing credentials in DB
    if user_id not in USER_APPS.get("kite", {}):
        # Try to load from database
        acc = BrokerAccount.query.filter_by(broker="kite", user_id=user_id).first()
        if acc and acc.api_key and acc.api_secret:
            USER_APPS.setdefault("kite", {})[user_id] = {
                "api_key": acc.api_key,
                "api_secret": acc.api_secret,
                "access_token": acc.access_token,
                "client_id": acc.client_id,
                "totp_secret": acc.totp_secret
            }
        else:
            return jsonify({"ok": False, "message": "No Kite credentials found. Please register API key and secret first."}), 400
    
    session["kite_user_id"] = user_id
    creds = USER_APPS["kite"][user_id]
    kite = KiteConnect(api_key=creds["api_key"])
    login_url = kite.login_url()
    sep = "&" if "?" in login_url else "?"
    return redirect(f"{login_url}{sep}state={user_id}")



@calculatentrade_bp.route("/dhan/login")
def dhan_login():
    user_id = str(request.args.get("user_id", "")).strip()
    if not user_id:
        return jsonify({"ok": False, "message": "user_id required"}), 400

    # If missing in-memory, try to reload persisted accounts (helps after restarts)
    if user_id not in USER_APPS.get("dhan", {}):
        try:
            load_persisted_accounts_into_memory()
        except Exception:
            app.logger.exception("Failed to resync accounts while handling dhan/login")

    creds = USER_APPS["dhan"].get(user_id)
    if not creds:
        return render_template(
            "connect_broker_journal.html",
            now=datetime.now(),
            broker_status={"ok": False, "broker": "dhan", "message": f"No Dhan registration found for user {user_id}"}
        ), 400

    try:
        # ✅ Direct Token Mode (client_id + access_token provided)
        if creds.get("client_id") and creds.get("access_token"):
            USER_SESSIONS.setdefault("dhan", {})[user_id] = {
                "access_token": creds["access_token"],
                "dhan_client_id": creds["client_id"],
                "mode": "direct"
            }
            # persist to DB and mark connected
            save_broker_account("dhan", user_id,
                                client_id=creds.get("client_id"),
                                access_token=creds.get("access_token"))
            mark_connected("dhan", user_id, True)

            # Render the same connect_broker page with success status (consistent UX)
            return render_template(
                "connect_broker_journal.html",
                now=datetime.now(),
                broker_status={"ok": True, "broker": "dhan", "user_id": user_id, "message": "Dhan connected successfully (direct token mode)"}
            )

        # ✅ Partner Consent Mode (partner_id + partner_secret)
        partner_id = creds.get("api_key")
        partner_secret = creds.get("api_secret")
        if partner_id and partner_secret:
            consent_id = _dhan_generate_consent(partner_id, partner_secret)
            session["dhan_user_id"] = user_id
            session["dhan_partner_id"] = partner_id
            session["dhan_partner_secret"] = partner_secret
            session["dhan_consent_id"] = consent_id

            # Build consent/login URL using safe url_for for callback
            redirect_uri = url_for(".dhan_auth_callback", _external=True)
            consent_url = f"{DHAN_AUTH_BASE}/oauth/authorize?response_type=code&client_id={partner_id}&redirect_uri={redirect_uri}&consent_id={consent_id}"
            return redirect(consent_url)

        # If neither mode is available, tell the user what to provide
        return render_template(
            "connect_broker_journal.html",
            now=datetime.now(),
            broker_status={"ok": False, "broker": "dhan", "message": "Provide either (client_id+access_token) OR (partner_id+partner_secret)"}
        ), 400

    except Exception as e:
        app.logger.exception("Dhan login failed for user %s: %s", user_id, e)
        return render_template(
            "connect_broker_journal.html",
            now=datetime.now(),
            broker_status={"ok": False, "broker": "dhan", "message": f"Dhan login failed: {str(e)}"}
        ), 500


@calculatentrade_bp.route("/auth/kite/callback")
def kite_auth_callback():
    try:
        request_token = request.args.get("request_token")
        user_id = request.args.get("state") or session.get("kite_user_id")
        if not request_token or not user_id:
            return render_template("connect_broker_journal.html", now=datetime.now(),
                                   broker_status={"ok": False, "broker": "kite", "message": "Missing request_token or user_id"})

        creds = USER_APPS["kite"].get(user_id)
        if not creds:
            return render_template("connect_broker_journal.html", now=datetime.now(),
                                   broker_status={"ok": False, "broker": "kite", "message": "No app credentials registered for this user"})

        kite = KiteConnect(api_key=creds["api_key"])
        data = kite.generate_session(request_token, api_secret=creds["api_secret"])

        access_token = data.get("access_token")
        if not access_token:
            return render_template("connect_broker_journal.html", now=datetime.now(),
                                   broker_status={"ok": False, "broker": "kite", "message": f"Kite session response missing access_token: {data}"})

        # persist in memory + DB with ALL credentials
        USER_SESSIONS["kite"][user_id] = {"access_token": access_token, "kite": kite}
        save_broker_account("kite", user_id, 
                           api_key=creds["api_key"], 
                           api_secret=creds["api_secret"],
                           access_token=access_token)
        mark_connected("kite", user_id, True)

        # Render same page and show success (front-end will auto-load positions/orders/trades)
        return render_template("connect_broker_journal.html", now=datetime.now(),
                               broker_status={"ok": True, "broker": "kite", "user_id": user_id, "message": "Kite connected successfully"})
    except Exception as e:
        return render_template("connect_broker_journal.html", now=datetime.now(),
                               broker_status={"ok": False, "broker": "kite", "message": f"Kite auth failed: {str(e)}"})
    
# ---------------- Dhan & Angel callback + account management routes ----------------

@calculatentrade_bp.route("/auth/dhan/callback")
def dhan_auth_callback():
    token_id = request.args.get("tokenId") or request.args.get("token") or request.args.get("code")
    user_id = session.get("dhan_user_id")
    partner_id = session.get("dhan_partner_id")
    partner_secret = session.get("dhan_partner_secret")

    if not token_id or not user_id:
        return render_template("connect_broker_journal.html", now=datetime.now(),
                               broker_status={"ok": False, "broker": "dhan", "message": "Missing token or session"})

    try:
        resp = _dhan_consume_consent(partner_id, partner_secret, token_id)
        access_token = resp.get("access_token") or resp.get("accessToken") or resp.get("token")
        client_id = resp.get("clientId") or resp.get("client_id") or partner_id

        if not access_token:
            return render_template("connect_broker_journal.html", now=datetime.now(),
                                   broker_status={"ok": False, "broker": "dhan", "message": f"No token in resp: {resp}"})

        USER_SESSIONS["dhan"][user_id] = {"access_token": access_token, "dhan_client_id": client_id, "mode": "partner"}
        save_broker_account("dhan", user_id, client_id=client_id, access_token=access_token)
        mark_connected("dhan", user_id, True)

        return render_template("connect_broker_journal.html", now=datetime.now(),
                               broker_status={"ok": True, "broker": "dhan", "user_id": user_id, "message": "Dhan connected"})
    except Exception as e:
        return render_template("connect_broker_journal.html", now=datetime.now(),
                               broker_status={"ok": False, "broker": "dhan", "message": f"Callback failed: {str(e)}"})

@calculatentrade_bp.route("/auth/angel/callback")
def angel_auth_callback():
    jwt = request.args.get("jwt") or request.args.get("token")
    client_code = request.args.get("client_code") or request.args.get("client")
    user_id = request.args.get("user_id") or session.get("angel_user_id")   # ✅ FIXED

    if not jwt or not user_id:
        return render_template("connect_broker_journal.html", now=datetime.now(),
                               broker_status={"ok": False, "broker": "angel", "message": "Missing jwt or user_id"})

    USER_SESSIONS["angel"][user_id] = {"jwt_token": jwt, "client_code": client_code}
    save_broker_account("angel", user_id, client_id=client_code, access_token=jwt)
    mark_connected("angel", user_id, True)

    return render_template("connect_broker_journal.html", now=datetime.now(),
                           broker_status={"ok": True, "broker": "angel", "user_id": user_id, "message": "Angel connected"})

# ---------------- Account management REST endpoints ----------------

@calculatentrade_bp.route("/api/accounts", methods=["GET"])
def api_list_accounts():
    """Return list of saved broker accounts (for debugging/admin)."""
    accounts = BrokerAccount.query.order_by(BrokerAccount.broker, BrokerAccount.user_id).all()
    return jsonify([a.to_dict() for a in accounts])
@calculatentrade_bp.route("/api/angel/totp")
def api_angel_totp():
    user_id = request.args.get("user_id", "").strip()
    if not user_id:
        return jsonify({"ok": False, "message": "user_id required"}), 400

    creds = USER_APPS.get("angel", {}).get(user_id)
    if not creds:
        # also try DB lookup as fallback
        acc = BrokerAccount.query.filter_by(broker="angel", user_id=user_id).first()
        if acc and acc.totp_secret:
            raw_secret = acc.totp_secret
        else:
            return jsonify({"ok": False, "message": "No credentials found for user or totp not saved"}), 404
    else:
        raw_secret = creds.get("totp_secret") or creds.get("totp") or creds.get("secret")

    secret = _normalize_base32_secret(raw_secret)
    if not secret:
        return jsonify({"ok": False, "message": "TOTP secret not available or invalid"}), 404

    try:
        t = pyotp.TOTP(secret)
        totp_value = t.now()
        period = getattr(t, 'interval', 30)  # pyotp default 30
        # compute seconds remaining until next code change
        import time
        elapsed = int(time.time()) % period
        remaining = period - elapsed
        return jsonify({"ok": True, "totp": totp_value, "period": period, "remaining": remaining})
    except Exception as e:
        app.logger.exception("TOTP generation failed for %s: %s", user_id, e)
        return jsonify({"ok": False, "message": "TOTP generation failed"}), 500

@calculatentrade_bp.route("/api/accounts/<broker>/<user_id>", methods=["GET"])
def api_get_account(broker, user_id):
    a = BrokerAccount.query.filter_by(broker=broker, user_id=user_id).first()
    if not a:
        return jsonify({"ok": False, "message": "Not found"}), 404
    return jsonify({"ok": True, "account": a.to_dict()})


@calculatentrade_bp.route("/api/accounts/<broker>/<user_id>", methods=["PUT"])
def api_update_account(broker, user_id):
    """Update stored credentials: api_key, api_secret, client_id, totp_secret, access_token."""
    payload = request.get_json(force=True) or {}
    a = BrokerAccount.query.filter_by(broker=broker, user_id=user_id).first()
    if not a:
        return jsonify({"ok": False, "message": "Not found"}), 404

    allowed = ["api_key", "api_secret", "client_id", "access_token", "totp_secret", "connected"]
    changed = False
    for k in allowed:
        if k in payload:
            setattr(a, k, payload[k])
            changed = True
    if changed:
        a.updated_at = datetime.utcnow()
        db.session.commit()

    # keep in-memory maps in sync
    USER_APPS.setdefault(broker, {})[user_id] = {
        "api_key": a.api_key, "api_secret": a.api_secret,
        "client_id": a.client_id, "access_token": a.access_token, "totp_secret": a.totp_secret
    }
    if a.access_token:
        USER_SESSIONS.setdefault(broker, {})[user_id] = {"access_token": a.access_token}
    return jsonify({"ok": True, "account": a.to_dict()})


@calculatentrade_bp.route("/api/accounts/<broker>/<user_id>", methods=["DELETE"])
def api_delete_account(broker, user_id):
    """Delete a stored registration and its session from DB and in-memory maps."""
    a = BrokerAccount.query.filter_by(broker=broker, user_id=user_id).first()
    if not a:
        return jsonify({"ok": False, "message": "Not found"}), 404

    db.session.delete(a)
    db.session.commit()

    USER_APPS.get(broker, {}).pop(user_id, None)
    USER_SESSIONS.get(broker, {}).pop(user_id, None)
    return jsonify({"ok": True, "message": f"Deleted {broker}/{user_id}"})


# ---------------- Utility: force-resync in-memory maps from DB (for manual call) ----------------
@calculatentrade_bp.route("/admin/resync_accounts", methods=["POST"])
def admin_resync_accounts():
    """Force reload persisted accounts into memory (useful after manual DB edits)."""
    load_persisted_accounts_into_memory()
    return jsonify({"ok": True, "message": "Resynced in-memory maps from DB"})

@calculatentrade_bp.route("/api/broker/init", methods=["POST"])
def init_broker_system():
    """Initialize broker system - load accounts and check connections"""
    try:
        load_persisted_accounts_into_memory()
        
        # Count loaded accounts
        total_accounts = sum(len(users) for users in USER_APPS.values())
        active_sessions = sum(len(sessions) for sessions in USER_SESSIONS.values())
        
        return jsonify({
            "ok": True, 
            "message": "Broker system initialized",
            "accounts_loaded": total_accounts,
            "active_sessions": active_sessions
        })
    except Exception as e:
        current_app.logger.error(f"Failed to initialize broker system: {e}")
        return jsonify({"ok": False, "message": str(e)}), 500



@calculatentrade_bp.route("/api/broker/status")
def broker_status():
    """Check broker connection status with session validation"""
    user_id = request.args.get("user_id", "NES881").strip()
    broker = request.args.get("broker", "").strip()
    
    if not broker:
        return jsonify({"connected": False, "message": "Broker parameter required"})
    
    if broker not in ["kite", "dhan", "angel"]:
        return jsonify({"connected": False, "message": "Unsupported broker"})
    
    # Load persisted accounts first
    try:
        load_persisted_accounts_into_memory()
    except Exception as e:
        current_app.logger.error(f"Failed to load accounts: {e}")
    
    # Check in-memory session first
    if broker in USER_SESSIONS and user_id in USER_SESSIONS[broker]:
        session_data = USER_SESSIONS[broker][user_id]
        if session_data.get("access_token"):
            return jsonify({
                "connected": True,
                "user_id": user_id,
                "broker": broker,
                "message": "Connected (active session)"
            })
    
    # Check database as fallback
    try:
        account = BrokerAccount.query.filter_by(broker=broker, user_id=user_id).first()
        if account and account.connected and account.access_token:
            # Check if connection is still valid (24 hours)
            if account.last_connected_at and (datetime.utcnow() - account.last_connected_at) < timedelta(hours=24):
                # Restore in-memory session
                if broker == "kite":
                    USER_SESSIONS.setdefault("kite", {})[user_id] = {"access_token": account.access_token}
                elif broker == "dhan":
                    USER_SESSIONS.setdefault("dhan", {})[user_id] = {"access_token": account.access_token, "dhan_client_id": account.client_id, "mode": "direct"}
                elif broker == "angel":
                    USER_SESSIONS.setdefault("angel", {})[user_id] = {"jwt_token": account.access_token, "client_code": account.client_id}
                
                return jsonify({
                    "connected": True,
                    "user_id": user_id,
                    "broker": broker,
                    "message": "Connected (restored from DB)",
                    "last_connected": account.last_connected_at.isoformat()
                })
            else:
                # Connection expired - clean up
                account.connected = False
                account.access_token = None
                db.session.commit()
                return jsonify({
                    "connected": False,
                    "user_id": user_id,
                    "broker": broker,
                    "message": "Connection expired",
                    "expired": True
                })
    except Exception as e:
        current_app.logger.error(f"Error checking broker status: {e}")
    
    return jsonify({
        "connected": False,
        "user_id": user_id,
        "broker": broker,
        "message": "Not connected"
    })


# Multi-Broker Connect API Endpoints
# Production note: Replace with encrypted DB storage and proper secret management

@calculatentrade_bp.route('/api/broker/get-all-data')
def api_get_all_broker_data():
    """Get all trading data from connected broker (orders, trades, positions)"""
    try:
        from multi_broker_system import USER_SESSIONS, get_kite_for_user, _dhan_client_from_session, _handle_angel_call
        
        broker = request.args.get('broker')
        user_id = request.args.get('user_id', 'NES881')
        
        if not broker or broker not in ['kite', 'dhan', 'angel']:
            return jsonify({'success': False, 'message': 'Invalid broker'})
        
        all_data = {}
        
        if broker == 'kite':
            sess = USER_SESSIONS["kite"].get(user_id)
            if sess:
                kite = get_kite_for_user(user_id, sess["access_token"])
                all_data['orders'] = kite.orders()
                all_data['trades'] = kite.trades()
                all_data['positions'] = kite.positions()
        
        elif broker == 'dhan':
            client, _, _ = _dhan_client_from_session(user_id)
            if client:
                all_data['orders'] = client.get_order_list()
                all_data['positions'] = client.get_positions()
                if hasattr(client, "get_trade_book"):
                    all_data['trades'] = client.get_trade_book()
                else:
                    all_data['trades'] = []
        
        elif broker == 'angel':
            all_data['orders'] = _handle_angel_call(user_id, "orderBook")
            all_data['trades'] = _handle_angel_call(user_id, "tradeBook")
            all_data['positions'] = _handle_angel_call(user_id, "position")
        
        return jsonify({'success': True, 'data': all_data})
        
    except Exception as e:
        current_app.logger.error(f"Error fetching all broker data: {e}")
        return jsonify({'success': False, 'message': str(e)})



@calculatentrade_bp.route('/api/broker/multi-status')
def api_multi_broker_status():
    """Get status of all brokers using multi-broker system"""
    try:
        from multi_broker_system import get_broker_session_status
        
        user_id = request.args.get('user_id', 'NES881')
        brokers = ['kite', 'dhan', 'angel']
        
        broker_status = {}
        for broker in brokers:
            try:
                status = get_broker_session_status(broker, user_id)
                broker_status[broker] = {
                    'connected': status['connected'],
                    'user_id': user_id,
                    'has_session_data': bool(status.get('session_data'))
                }
            except Exception as e:
                broker_status[broker] = {
                    'connected': False,
                    'user_id': user_id,
                    'error': str(e)
                }
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'brokers': broker_status
        })
        
    except ImportError:
        return jsonify({
            'success': False,
            'message': 'Multi-broker system not available'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })


@calculatentrade_bp.route("/api/broker/status")
def broker_status_api():
    """Check broker connection status (alternative endpoint)"""
    user_id = request.args.get("user_id", "NES881").strip()
    broker = request.args.get("broker", "").strip()
    
    if not broker or broker not in ["kite", "dhan", "angel"]:
        return jsonify({"connected": False, "user_id": user_id, "broker": broker})
    
    # Load accounts first
    try:
        load_persisted_accounts_into_memory()
    except Exception as e:
        current_app.logger.error(f"Failed to load accounts: {e}")
    
    # Check in-memory session first
    if broker in USER_SESSIONS and user_id in USER_SESSIONS[broker]:
        session_data = USER_SESSIONS[broker][user_id]
        if session_data.get("access_token") or session_data.get("jwt_token"):
            return jsonify({
                "connected": True, 
                "user_id": user_id, 
                "broker": broker,
                "message": "Active session found"
            })
    
    # Check persistent storage (fallback)
    try:
        account = BrokerAccount.query.filter_by(broker=broker, user_id=user_id).first()
        if account and account.connected and account.access_token:
            # Check if not expired (24 hours)
            if account.last_connected_at and (datetime.utcnow() - account.last_connected_at) < timedelta(hours=24):
                # Restore in-memory session
                if broker == "kite":
                    USER_SESSIONS.setdefault("kite", {})[user_id] = {"access_token": account.access_token}
                elif broker == "dhan":
                    USER_SESSIONS.setdefault("dhan", {})[user_id] = {"access_token": account.access_token, "dhan_client_id": account.client_id, "mode": "direct"}
                elif broker == "angel":
                    USER_SESSIONS.setdefault("angel", {})[user_id] = {"jwt_token": account.access_token, "client_code": account.client_id}
                
                return jsonify({
                    "connected": True, 
                    "user_id": user_id, 
                    "broker": broker,
                    "message": "Restored from database"
                })
            else:
                # Expired - clean up
                account.connected = False
                account.access_token = None
                db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Status check error: {e}")
    
    return jsonify({"connected": False, "user_id": user_id, "broker": broker, "message": "Not connected"})

@calculatentrade_bp.route("/api/broker/remembered_accounts")
def broker_remembered_accounts():
    """Get list of saved accounts"""
    try:
        # Load accounts first
        load_persisted_accounts_into_memory()
        
        accounts = BrokerAccount.query.filter(BrokerAccount.api_key.isnot(None)).all()
        account_list = []
        for acc in accounts:
            # Include accounts that have credentials, regardless of connection status
            account_list.append({
                "broker": acc.broker,
                "user_id": acc.user_id,
                "connected": acc.connected,
                "has_credentials": bool(acc.api_key and acc.api_secret),
                "connected_at": acc.last_connected_at.isoformat() if acc.last_connected_at else None
            })
        
        return jsonify({"ok": True, "accounts": account_list})
    except Exception as e:
        current_app.logger.error(f"Remembered accounts error: {e}")
        return jsonify({"ok": False, "accounts": []})

@calculatentrade_bp.route("/api/broker/disconnect", methods=["POST"])
def broker_disconnect_api():
    """Disconnect broker"""
    try:
        data = request.get_json(force=True)
        user_id = data.get("user_id", "NES881").strip()
        broker = data.get("broker", "").strip()
        
        if not broker or broker not in ["kite", "dhan", "angel"]:
            return jsonify({"ok": False, "message": "Invalid broker"})
        
        # Clear persistent storage
        account = BrokerAccount.query.filter_by(broker=broker, user_id=user_id).first()
        if account:
            account.connected = False
            # Keep access_token for potential reconnection
            db.session.commit()
        
        # Clear in-memory sessions
        if broker in USER_SESSIONS and user_id in USER_SESSIONS[broker]:
            del USER_SESSIONS[broker][user_id]
        
        current_app.logger.info(f"Broker {broker} disconnected for user {user_id}")
        return jsonify({"ok": True})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Disconnect error: {e}")
        return jsonify({"ok": False, "message": str(e)})

@calculatentrade_bp.route("/api/broker/disconnect_legacy", methods=["POST"])
def disconnect_broker():
    data = request.get_json(force=True)
    user_id = data.get("user_id", "NES881").strip()
    broker = data.get("broker", "").strip()

    if not broker or broker not in ["kite", "dhan", "angel"]:
        return jsonify({"ok": False, "message": "Invalid parameters"})

    try:
        # Mark DB account as disconnected
        acc = BrokerAccount.query.filter_by(broker=broker, user_id=user_id).first()
        if acc:
            acc.connected = False
            # Keep access_token for potential reconnection
            db.session.commit()
        
        # Remove from in-memory sessions
        if user_id in USER_SESSIONS.get(broker, {}):
            del USER_SESSIONS[broker][user_id]
        
        return jsonify({"ok": True, "message": f"Disconnected from {broker}"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "message": str(e)})

@calculatentrade_bp.route("/_debug/accounts")
def debug_accounts():
    return jsonify([a.to_dict() for a in BrokerAccount.query.all()])

@calculatentrade_bp.route("/api/portfolio")
def get_portfolio():
    """Get portfolio data from connected broker"""
    user_id = request.args.get("user_id", "NES881").strip()
    broker = request.args.get("broker", "").strip()
    
    if not broker:
        return jsonify({"ok": False, "message": "broker parameter required"}), 400
    
    # Ensure accounts are loaded
    try:
        load_persisted_accounts_into_memory()
    except Exception as e:
        current_app.logger.error(f"Failed to load accounts: {e}")
    
    try:
        # Try to fetch real data from broker API
        if broker == "kite":
            sess = USER_SESSIONS.get("kite", {}).get(user_id)
            if sess and sess.get("access_token"):
                try:
                    kite = get_kite_for_user(user_id, sess["access_token"])
                    holdings = kite.holdings()
                    positions = kite.positions()
                    portfolio = {
                        "holdings": holdings,
                        "positions": positions,
                        "broker": broker
                    }
                    return jsonify({"ok": True, "data": portfolio})
                except Exception as e:
                    current_app.logger.error(f"Kite portfolio API error: {e}")
                    # Check if it's an authentication error
                    if "api_key" in str(e).lower() or "access_token" in str(e).lower():
                        # Clear invalid session
                        USER_SESSIONS.get("kite", {}).pop(user_id, None)
                        acc = BrokerAccount.query.filter_by(broker="kite", user_id=user_id).first()
                        if acc:
                            acc.connected = False
                            acc.access_token = None
                            db.session.commit()
                        return jsonify({"ok": False, "message": "Authentication failed. Please reconnect to Kite.", "auth_error": True, "data": {}})
                    return jsonify({"ok": False, "message": f"Kite API Error: {str(e)}", "data": {}})
        
        elif broker == "dhan":
            client, resp, code = _dhan_client_from_session(user_id)
            if client:
                try:
                    holdings = client.get_holdings()
                    positions = client.get_positions()
                    portfolio = {
                        "holdings": holdings,
                        "positions": positions,
                        "broker": broker
                    }
                    return jsonify({"ok": True, "data": portfolio})
                except Exception as e:
                    current_app.logger.error(f"Dhan portfolio API error: {e}")
                    return jsonify({"ok": False, "message": f"Dhan API Error: {str(e)}", "data": {}})
        
        elif broker == "angel":
            sess = USER_SESSIONS.get("angel", {}).get(user_id)
            if sess and sess.get("smart_api"):
                try:
                    holdings = sess["smart_api"].holding()
                    positions = sess["smart_api"].position()
                    portfolio = {
                        "holdings": holdings,
                        "positions": positions,
                        "broker": broker
                    }
                    return jsonify({"ok": True, "data": portfolio})
                except Exception as e:
                    current_app.logger.error(f"Angel portfolio API error: {e}")
                    return jsonify({"ok": False, "message": f"Angel API Error: {str(e)}", "data": {}})
        
        return jsonify({"ok": False, "message": "Broker not connected or no active session. Please connect first.", "data": {}})
        
    except Exception as e:
        current_app.logger.exception("get_portfolio error for %s/%s: %s", broker, user_id, e)
        return jsonify({"ok": False, "message": "System error occurred", "data": {}})


def _get_kite_portfolio(user_id):
    sess = USER_SESSIONS["kite"].get(user_id)
    if not sess:
        return jsonify({"error": "Not connected to Kite"}), 401
    kite = get_kite_for_user(user_id, sess["access_token"])
    return jsonify({
        "holdings": kite.holdings(),
        "positions": kite.positions(),
        "broker": "kite"
    })


def _get_dhan_portfolio(user_id):
    client, resp, code = _dhan_client_from_session(user_id)
    if client is None:
        return resp, code
    return jsonify({
        "holdings": client.get_holdings(),
        "positions": client.get_positions(),
        "broker": "dhan"
    })


def _get_angel_portfolio(user_id):
    sess = USER_SESSIONS["angel"].get(user_id)
    if not sess:
        return jsonify({"error": "Not connected to Angel"}), 401
    smart_api = sess["smart_api"]
    return jsonify({
        "portfolio": smart_api.holding(),
        "positions": smart_api.position(),
        "orders": smart_api.orderBook(),
        "broker": "angel"
    })

# ---------------- Generic /api/broker/* endpoints (add to your app) ----------------

@calculatentrade_bp.route("/api/broker/positions")
def api_broker_positions():
    """Generic positions endpoint used by the frontend: /api/broker/positions?broker=kite&user_id=..."""
    user_id = request.args.get("user_id", "NES881").strip()
    broker = request.args.get("broker", "").strip()
    if not broker:
        return jsonify({"ok": False, "message": "broker parameter required"}), 400

    # Ensure accounts are loaded
    try:
        load_persisted_accounts_into_memory()
    except Exception as e:
        current_app.logger.error(f"Failed to load accounts: {e}")

    try:
        # Try to fetch real data from broker API
        if broker == "kite":
            sess = USER_SESSIONS.get("kite", {}).get(user_id)
            if sess and sess.get("access_token"):
                try:
                    kite = get_kite_for_user(user_id, sess["access_token"])
                    positions = kite.positions()
                    return jsonify({"ok": True, "data": positions})
                except Exception as e:
                    current_app.logger.error(f"Kite positions API error: {e}")
                    # Check if it's an authentication error
                    if "api_key" in str(e).lower() or "access_token" in str(e).lower():
                        # Clear invalid session
                        USER_SESSIONS.get("kite", {}).pop(user_id, None)
                        acc = BrokerAccount.query.filter_by(broker="kite", user_id=user_id).first()
                        if acc:
                            acc.connected = False
                            acc.access_token = None
                            db.session.commit()
                        return jsonify({"ok": False, "message": "Authentication failed. Please reconnect to Kite.", "auth_error": True, "data": []})
                    return jsonify({"ok": False, "message": f"Kite API Error: {str(e)}", "data": []})
        
        elif broker == "dhan":
            client, resp, code = _dhan_client_from_session(user_id)
            if client:
                try:
                    positions = client.get_positions()
                    return jsonify({"ok": True, "data": positions})
                except Exception as e:
                    current_app.logger.error(f"Dhan positions API error: {e}")
                    return jsonify({"ok": False, "message": f"Dhan API Error: {str(e)}", "data": []})
        
        elif broker == "angel":
            sess = USER_SESSIONS.get("angel", {}).get(user_id)
            if sess and sess.get("smart_api"):
                try:
                    positions = sess["smart_api"].position()
                    return jsonify({"ok": True, "data": positions})
                except Exception as e:
                    current_app.logger.error(f"Angel positions API error: {e}")
                    return jsonify({"ok": False, "message": f"Angel API Error: {str(e)}", "data": []})
        
        return jsonify({"ok": False, "message": "Broker not connected or no active session. Please connect first.", "data": []})
        
    except Exception as e:
        current_app.logger.exception("api_broker_positions error for %s/%s: %s", broker, user_id, e)
        return jsonify({"ok": False, "message": "System error occurred", "data": []})


@calculatentrade_bp.route("/api/broker/orders")
def api_broker_orders():
    user_id = request.args.get("user_id", "NES881").strip()
    broker = request.args.get("broker", "").strip()
    
    if not broker:
        return jsonify({"ok": False, "message": "broker parameter required"}), 400

    # Ensure accounts are loaded
    try:
        load_persisted_accounts_into_memory()
    except Exception as e:
        current_app.logger.error(f"Failed to load accounts: {e}")

    try:
        # Try to fetch real data from broker API
        if broker == "kite":
            sess = USER_SESSIONS.get("kite", {}).get(user_id)
            if sess and sess.get("access_token"):
                try:
                    kite = get_kite_for_user(user_id, sess["access_token"])
                    orders = kite.orders()
                    return jsonify({"ok": True, "data": orders})
                except Exception as e:
                    current_app.logger.error(f"Kite orders API error: {e}")
                    # Check if it's an authentication error
                    if "api_key" in str(e).lower() or "access_token" in str(e).lower():
                        # Clear invalid session
                        USER_SESSIONS.get("kite", {}).pop(user_id, None)
                        acc = BrokerAccount.query.filter_by(broker="kite", user_id=user_id).first()
                        if acc:
                            acc.connected = False
                            acc.access_token = None
                            db.session.commit()
                        return jsonify({"ok": False, "message": "Authentication failed. Please reconnect to Kite.", "auth_error": True, "data": []})
                    return jsonify({"ok": False, "message": f"Kite API Error: {str(e)}", "data": []})
        
        elif broker == "dhan":
            client, resp, code = _dhan_client_from_session(user_id)
            if client:
                try:
                    orders = client.get_order_list()
                    return jsonify({"ok": True, "data": orders})
                except Exception as e:
                    current_app.logger.error(f"Dhan orders API error: {e}")
                    return jsonify({"ok": False, "message": f"Dhan API Error: {str(e)}", "data": []})
        
        elif broker == "angel":
            sess = USER_SESSIONS.get("angel", {}).get(user_id)
            if sess and sess.get("smart_api"):
                try:
                    orders = sess["smart_api"].orderBook()
                    return jsonify({"ok": True, "data": orders})
                except Exception as e:
                    current_app.logger.error(f"Angel orders API error: {e}")
                    return jsonify({"ok": False, "message": f"Angel API Error: {str(e)}", "data": []})
        
        return jsonify({"ok": False, "message": "Broker not connected or no active session. Please connect first.", "data": []})
        
    except Exception as e:
        current_app.logger.exception("api_broker_orders error for %s/%s: %s", broker, user_id, e)
        return jsonify({"ok": False, "message": "System error occurred", "data": []})

@calculatentrade_bp.route("/api/broker/debug")
def api_broker_debug():
    user_id = request.args.get("user_id", "default").strip()
    broker = request.args.get("broker", "").strip()
    
    debug_info = {
        "user_id": user_id,
        "broker": broker,
        "flask_session": {},
        "db_account": None,
        "memory_session": None,
        "connection_status": "unknown"
    }
    
    try:
        # Check Flask session
        session_key = f'broker_{broker}_{user_id}'
        session_data = session.get(session_key)
        debug_info['flask_session'] = session_data or {}
        
        # Check database
        account = BrokerAccount.query.filter_by(broker=broker, user_id=user_id).first()
        if account:
            debug_info['db_account'] = {
                "connected": account.connected,
                "has_token": bool(account.access_token),
                "last_connected": account.last_connected_at.isoformat() if account.last_connected_at else None
            }
        
        # Check in-memory sessions
        in_memory_session = USER_SESSIONS.get(broker, {}).get(user_id)
        debug_info['memory_session'] = bool(in_memory_session)
        
        # Determine connection status
        if session_data and session_data.get('connected'):
            debug_info['connection_status'] = "flask_session_active"
        elif account and account.connected and account.access_token:
            debug_info['connection_status'] = "db_connected"
        elif in_memory_session:
            debug_info['connection_status'] = "memory_session_active"
        else:
            debug_info['connection_status'] = "not_connected"
        
        return jsonify({"ok": True, "debug": debug_info})
        
    except Exception as e:
        debug_info['error'] = str(e)
        return jsonify({"ok": False, "debug": debug_info})


@calculatentrade_bp.route("/api/broker/trades")
def api_broker_trades():
    user_id = request.args.get("user_id", "NES881").strip()
    broker = request.args.get("broker", "").strip()
    if not broker:
        return jsonify({"ok": False, "message": "broker parameter required"}), 400

    # Ensure accounts are loaded
    try:
        load_persisted_accounts_into_memory()
    except Exception as e:
        current_app.logger.error(f"Failed to load accounts: {e}")

    try:
        # Try to fetch real data from broker API
        if broker == "kite":
            sess = USER_SESSIONS.get("kite", {}).get(user_id)
            if sess and sess.get("access_token"):
                try:
                    kite = get_kite_for_user(user_id, sess["access_token"])
                    trades = kite.trades()
                    return jsonify({"ok": True, "data": trades})
                except Exception as e:
                    current_app.logger.error(f"Kite trades API error: {e}")
                    # Check if it's an authentication error
                    if "api_key" in str(e).lower() or "access_token" in str(e).lower():
                        # Clear invalid session
                        USER_SESSIONS.get("kite", {}).pop(user_id, None)
                        acc = BrokerAccount.query.filter_by(broker="kite", user_id=user_id).first()
                        if acc:
                            acc.connected = False
                            acc.access_token = None
                            db.session.commit()
                        return jsonify({"ok": False, "message": "Authentication failed. Please reconnect to Kite.", "auth_error": True, "data": []})
                    return jsonify({"ok": False, "message": f"Kite API Error: {str(e)}", "data": []})
        
        elif broker == "dhan":
            client, resp, code = _dhan_client_from_session(user_id)
            if client:
                try:
                    trades = client.get_trade_book()
                    return jsonify({"ok": True, "data": trades})
                except Exception as e:
                    current_app.logger.error(f"Dhan trades API error: {e}")
                    return jsonify({"ok": False, "message": f"Dhan API Error: {str(e)}", "data": []})
        
        elif broker == "angel":
            sess = USER_SESSIONS.get("angel", {}).get(user_id)
            if sess and sess.get("smart_api"):
                try:
                    trades = sess["smart_api"].tradeBook()
                    return jsonify({"ok": True, "data": trades})
                except Exception as e:
                    current_app.logger.error(f"Angel trades API error: {e}")
                    return jsonify({"ok": False, "message": f"Angel API Error: {str(e)}", "data": []})
        
        return jsonify({"ok": False, "message": "Broker not connected or no active session. Please connect first.", "data": []})
        
    except Exception as e:
        current_app.logger.exception("api_broker_trades error for %s/%s: %s", broker, user_id, e)
        return jsonify({"ok": False, "message": "System error occurred", "data": []})

@calculatentrade_bp.route("/kite/positions")
def kite_positions():
    user_id = request.args.get("user_id", "NES881")
    
    # Ensure accounts are loaded
    try:
        load_persisted_accounts_into_memory()
    except Exception as e:
        current_app.logger.error(f"Failed to load accounts: {e}")
    
    sess = USER_SESSIONS.get("kite", {}).get(user_id)
    if not sess:
        return jsonify({"ok": False, "message": "Not connected"}), 401
    kite = get_kite_for_user(user_id, sess["access_token"])
    try:
        return jsonify({"ok": True, "data": kite.positions()})
    except Exception as e:
        # Clear invalid session on auth error
        if "api_key" in str(e).lower() or "access_token" in str(e).lower():
            USER_SESSIONS.get("kite", {}).pop(user_id, None)
            acc = BrokerAccount.query.filter_by(broker="kite", user_id=user_id).first()
            if acc:
                acc.connected = False
                acc.access_token = None
                db.session.commit()
        return jsonify({"ok": False, "message": str(e)}), 400


@calculatentrade_bp.route("/kite/orders")
def kite_orders():
    user_id = request.args.get("user_id", "NES881")
    
    # Ensure accounts are loaded
    try:
        load_persisted_accounts_into_memory()
    except Exception as e:
        current_app.logger.error(f"Failed to load accounts: {e}")
    
    sess = USER_SESSIONS.get("kite", {}).get(user_id)
    if not sess:
        return jsonify({"ok": False, "message": "Not connected"}), 401
    kite = get_kite_for_user(user_id, sess["access_token"])
    try:
        return jsonify({"ok": True, "data": kite.orders()})
    except Exception as e:
        # Clear invalid session on auth error
        if "api_key" in str(e).lower() or "access_token" in str(e).lower():
            USER_SESSIONS.get("kite", {}).pop(user_id, None)
            acc = BrokerAccount.query.filter_by(broker="kite", user_id=user_id).first()
            if acc:
                acc.connected = False
                acc.access_token = None
                db.session.commit()
        return jsonify({"ok": False, "message": str(e)}), 400


@calculatentrade_bp.route("/kite/trades")
def kite_trades():
    user_id = request.args.get("user_id", "NES881")
    
    # Ensure accounts are loaded
    try:
        load_persisted_accounts_into_memory()
    except Exception as e:
        current_app.logger.error(f"Failed to load accounts: {e}")
    
    sess = USER_SESSIONS.get("kite", {}).get(user_id)
    if not sess:
        return jsonify({"ok": False, "message": "Not connected"}), 401
    kite = get_kite_for_user(user_id, sess["access_token"])
    try:
        return jsonify({"ok": True, "data": kite.trades()})
    except Exception as e:
        # Clear invalid session on auth error
        if "api_key" in str(e).lower() or "access_token" in str(e).lower():
            USER_SESSIONS.get("kite", {}).pop(user_id, None)
            acc = BrokerAccount.query.filter_by(broker="kite", user_id=user_id).first()
            if acc:
                acc.connected = False
                acc.access_token = None
                db.session.commit()
        return jsonify({"ok": False, "message": str(e)}), 400

@calculatentrade_bp.route("/dhan/positions")
def dhan_positions():
    user_id = request.args.get("user_id")
    client, resp, code = _dhan_client_from_session(user_id)
    if client is None:
        return resp, code
    try:
        return jsonify({"ok": True, "data": client.get_positions()})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 400


@calculatentrade_bp.route("/dhan/orders")
def dhan_orders():
    user_id = request.args.get("user_id")
    client, resp, code = _dhan_client_from_session(user_id)
    if client is None:
        return resp, code
    try:
        return jsonify({"ok": True, "data": client.get_order_list()})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 400


@calculatentrade_bp.route("/dhan/trades")
def dhan_trades():
    user_id = request.args.get("user_id")
    client, resp, code = _dhan_client_from_session(user_id)
    if client is None:
        return resp, code
    try:
        if hasattr(client, "get_trade_book"):
            trades = client.get_trade_book()
        elif hasattr(client, "get_trade_history"):
            trades = client.get_trade_history(from_date=None, to_date=None, page_number=0)
        else:
            trades = []
        return jsonify({"ok": True, "data": trades})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 400

@calculatentrade_bp.route("/angel/positions")
def angel_positions():
    user_id = request.args.get("user_id")
    sess = USER_SESSIONS["angel"].get(user_id)
    if not sess:
        return jsonify({"ok": False, "message": "Not connected"}), 401
    try:
        return jsonify({"ok": True, "data": sess["smart_api"].position()})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 400


@calculatentrade_bp.route("/angel/orders")
def angel_orders():
    user_id = request.args.get("user_id")
    sess = USER_SESSIONS["angel"].get(user_id)
    if not sess:
        return jsonify({"ok": False, "message": "Not connected"}), 401
    try:
        return jsonify({"ok": True, "data": sess["smart_api"].orderBook()})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 400


@calculatentrade_bp.route("/angel/trades")
def angel_trades():
    user_id = request.args.get("user_id")
    sess = USER_SESSIONS["angel"].get(user_id)
    if not sess:
        return jsonify({"ok": False, "message": "Not connected"}), 401
    try:
        return jsonify({"ok": True, "data": sess["smart_api"].tradeBook()})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 400
    
@calculatentrade_bp.route('/api/trades/from_broker', methods=['POST'])
def api_add_trade_from_broker():
    """
    Accepts either:
      - JSON with 'legs': [leg1, leg2] where each leg is a broker row (dict)
      - or JSON with merged trade fields (symbol, date, entry_price, exit_price, quantity, trade_type, strategy_id)
    Attempts to create a single Trade row or update an existing open placeholder for that symbol+qty.
    """
    data = request.get_json(force=True) or {}
    try:
        # If legs present -> merge them
        legs = data.get('legs')
        if legs and isinstance(legs, list) and len(legs) >= 2:
            # simple merging: choose earliest leg as open, later as close
            def _leg_time(leg):
                for k in ('timestamp','time','trade_date','tradeTime','created_at','date'):
                    if k in leg and leg[k]:
                        try:
                            t = leg[k]
                            if isinstance(t, (int,float)):
                                return float(t)
                            return float(datetime.fromisoformat(str(t)).timestamp())
                        except Exception:
                            pass
                return 0
            legs_sorted = sorted(legs, key=_leg_time)
            open_leg = legs_sorted[0]
            close_leg = legs_sorted[1]
            # helper to find numeric fields
            def n(val):
                try:
                    return float(str(val).replace(',',''))
                except Exception:
                    return 0.0
            # heuristics: symbol, qty, price fields
            symbol = open_leg.get('tradingsymbol') or open_leg.get('symbol') or open_leg.get('instrument') or data.get('symbol')
            qty = abs(n(open_leg.get('quantity') or open_leg.get('qty') or open_leg.get('netQuantity') or data.get('quantity', 0)))
            entry_price = n(open_leg.get('average_price') or open_leg.get('avg_price') or open_leg.get('price') or open_leg.get('entry_price') or open_leg.get('open_price') or 0)
            exit_price = n(close_leg.get('close_price') or close_leg.get('price') or close_leg.get('exit_price') or close_leg.get('last_price') or 0)
            trade_type = 'short' if (str(open_leg.get('side','')).lower().startswith('s') or str(open_leg.get('transaction_type','')).lower().startswith('s') or str(open_leg.get('type','')).lower().startswith('sell')) else 'long'
            # compute pnl consistent with model
            pnl = (exit_price - entry_price) * qty if trade_type == 'long' else (entry_price - exit_price) * qty
            result = 'win' if pnl > 0 else ('loss' if pnl < 0 else 'breakeven')
            # allow provided strategy_id override
            strategy_id = int(data.get('strategy_id')) if data.get('strategy_id') else None
            # attempt to find an open placeholder trade: (simple heuristic)
            trade = None
            if symbol:
                # look for a trade with same symbol and zero exit_price or pnl == 0 (placeholder)
                tmatch = Trade.query.filter(Trade.symbol == symbol).filter((Trade.exit_price == 0) | (Trade.pnl == 0)).first()
                if tmatch:
                    trade = tmatch
            if trade:
                trade.exit_price = exit_price
                trade.quantity = qty
                trade.trade_type = trade_type
                trade.result = result
                trade.pnl = pnl
                trade.notes = (trade.notes or '') + '\nMerged from broker legs'
                if strategy_id:
                    trade.strategy_id = strategy_id
                db.session.commit()
                return jsonify({'success': True, 'id': trade.id, 'updated': True})
            else:
                new_trade = Trade(
                    symbol=symbol or data.get('symbol'),
                    entry_price=entry_price,
                    exit_price=exit_price,
                    quantity=qty,
                    date=datetime.utcnow() if not data.get('date') else datetime.fromisoformat(data.get('date')),
                    result=result,
                    pnl=pnl,
                    notes='Imported from broker legs: ' + json.dumps({'open': open_leg, 'close': close_leg}),
                    trade_type=trade_type,
                    strategy_id=strategy_id
                )
                db.session.add(new_trade)
                db.session.commit()
                return jsonify({'success': True, 'id': new_trade.id, 'created': True})

        # fallback: direct merged fields provided
        symbol = data.get('symbol')
        if symbol and 'entry_price' in data and 'exit_price' in data:
            entry_price = float(data.get('entry_price') or 0)
            exit_price = float(data.get('exit_price') or 0)
            qty = float(data.get('quantity') or 0)
            trade_type = data.get('trade_type') or ('short' if entry_price > exit_price else 'long')
            pnl = (exit_price - entry_price) * qty if trade_type == 'long' else (entry_price - exit_price) * qty
            result = 'win' if pnl > 0 else ('loss' if pnl < 0 else 'breakeven')
            strategy_id = int(data.get('strategy_id')) if data.get('strategy_id') else None
            new_trade = Trade(
                symbol=symbol,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=qty,
                date=datetime.utcnow() if not data.get('date') else datetime.fromisoformat(data.get('date')),
                result=result,
                pnl=pnl,
                notes='Imported from broker (merged payload). ' + str(data.get('notes') or ''),
                trade_type=trade_type,
                strategy_id=strategy_id
            )
            db.session.add(new_trade)
            db.session.commit()
            return jsonify({'success': True, 'id': new_trade.id})
        return jsonify({'ok': False, 'message': 'Unrecognized payload'}), 400
    except Exception as e:
        app.logger.exception('Failed /api/trades/from_broker: %s', e)
        return jsonify({'ok': False, 'message': str(e)}), 500


# ---------------- NEW ENHANCED API ENDPOINTS ---------------- #

# Templates API


# Strategy versions API
@calculatentrade_bp.route('/api/strategies/<int:strategy_id>/versions', methods=['GET'])
def api_get_strategy_versions(strategy_id):
    versions = StrategyVersion.query.filter_by(strategy_id=strategy_id).order_by(StrategyVersion.version_number.desc()).all()
    return jsonify({
        'ok': True,
        'data': [{
            'id': v.id,
            'version_number': v.version_number,
            'name': v.name,
            'description': v.description,
            'created_at': v.created_at.isoformat(),
            'created_by': v.created_by
        } for v in versions]
    })

@calculatentrade_bp.route('/api/strategies/<int:strategy_id>/revert/<int:version_id>', methods=['POST'])
def api_revert_strategy(strategy_id, version_id):
    version = StrategyVersion.query.get_or_404(version_id)
    strategy = Strategy.query.get_or_404(strategy_id)
    
    if version.strategy_id != strategy_id:
        return jsonify({'ok': False, 'error': 'Version does not belong to strategy'}), 400
    
    # Restore strategy from version config
    config = json.loads(version.config_data)
    for field, value in config.items():
        if hasattr(strategy, field):
            setattr(strategy, field, value)
    
    db.session.commit()
    log_audit('revert', 'strategy', strategy_id, None, {'reverted_to_version': version_id})
    return jsonify({'ok': True, 'data': {'message': f'Reverted to version {version.version_number}'}})

# backtestss API
@calculatentrade_bp.route('/api/strategies/<int:strategy_id>/backtest', methods=['POST'])
def api_run_backtest(strategy_id):
    data = request.json or {}
    strategy = Strategy.query.get_or_404(strategy_id)

    # simple mock backtest (replace with real backtesting logic)
    import random
    total_return = random.uniform(-20, 50)
    sharpe_ratio = random.uniform(0.5, 2.5)
    max_drawdown = random.uniform(5, 25)
    win_rate = random.uniform(40, 70)
    total_trades = random.randint(50, 200)
    winning_trades = int(total_trades * win_rate / 100)

    # create equity curve
    start_date = datetime.strptime(data.get('start_date', datetime.now().strftime('%Y-%m-%d')), '%Y-%m-%d').date()
    initial_capital = float(data.get('initial_capital', 10000))
    equity_curve = []
    equity = initial_capital
    for i in range(30):
        equity *= (1 + random.uniform(-0.05, 0.08))
        equity_curve.append({'date': (start_date + timedelta(days=i*7)).isoformat(), 'equity': round(equity, 2)})

    summary = {
        "id": int(datetime.utcnow().timestamp()),            # small unique id
        "name": data.get('name', f'{strategy.name} backtest'),
        "start_date": data.get('start_date'),
        "end_date": data.get('end_date'),
        "initial_capital": initial_capital,
        "commission_per_trade": data.get('commission_per_trade', 1.0),
        "total_return": total_return,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": total_trades - winning_trades,
        "equity_curve": equity_curve,
        "created_at": datetime.utcnow().isoformat(),
        "status": "completed"
    }
        # append to strategy.backtests JSON column
    curr = strategy.backtests or []
    curr.append(summary)
    strategy.backtests = curr

    # store as model record too
    bt = BacktestSummary(strategy_id=strategy.id, name=summary.get('name'), summary=summary)
    db.session.add(bt)

    # update top-level metrics on strategy
    strategy.sharpe_ratio = sharpe_ratio
    strategy.max_drawdown = max_drawdown

    db.session.commit()

    log_audit('create', 'strategy_backtest', strategy_id, None, summary)

    return jsonify({'ok': True, 'data': summary})


@calculatentrade_bp.route('/api/strategies/<int:strategy_id>/details', methods=['GET'])
def api_get_strategy_details(strategy_id):
    strategy = Strategy.query.get_or_404(strategy_id)

    # latest backtest stored in BacktestSummary model if exists
    latest = BacktestSummary.query.filter_by(strategy_id=strategy_id).order_by(BacktestSummary.created_at.desc()).first()
    latest_backtest_payload = None
    if latest:
        latest_backtest_payload = latest.summary

    params = strategy.parameters if isinstance(strategy.parameters, list) else []

    return jsonify({
        'ok': True,
        'data': {
            'id': strategy.id,
            'name': strategy.name,
            'description': strategy.description,
            'win_rate': round(strategy.win_rate or 0, 2),
            'total_pnl': float(strategy.total_pnl or 0),
            'sharpe_ratio': strategy.sharpe_ratio,
            'max_drawdown': strategy.max_drawdown,
            'stop_loss': strategy.stop_loss,
            'take_profit': strategy.take_profit,
            'position_size': strategy.position_size,
            'risk_score': strategy.risk_score,
            'entry_conditions': strategy.entry_conditions,
            'exit_conditions': strategy.exit_conditions,
            'parameters': params or [],
            'latest_backtest': latest_backtest_payload
        }
    })


# Watchlist API
@calculatentrade_bp.route('/api/watchlist', methods=['GET'])
def api_get_watchlist():
    watchlist = Watchlist.query.first()
    if not watchlist:
        watchlist = Watchlist(name='Default Watchlist', symbols=json.dumps(['AAPL', 'MSFT', 'GOOGL']))
        db.session.add(watchlist)
        db.session.commit()
    
    symbols = json.loads(watchlist.symbols) if watchlist.symbols else []
    return jsonify({
        'ok': True,
        'data': {
            'id': watchlist.id,
            'name': watchlist.name,
            'symbols': symbols
        }
    })

@calculatentrade_bp.route('/api/watchlist', methods=['PUT'])
def api_update_watchlist():
    data = request.json
    watchlist = Watchlist.query.first()
    if not watchlist:
        watchlist = Watchlist()
        db.session.add(watchlist)
    
    watchlist.name = data.get('name', watchlist.name)
    watchlist.symbols = json.dumps(data.get('symbols', []))
    watchlist.updated_at = datetime.utcnow()
    db.session.commit()
    log_audit('update', 'watchlists', watchlist.id, None, data)
    return jsonify({'ok': True, 'data': {'id': watchlist.id}})

# ---------------- DIRECT /strategies ROUTES (without blueprint prefix) ---------------- #
@calculatentrade_bp.route('/strategies')
def strategies_redirect():
    """Redirect /strategies to blueprint route"""
    return redirect(url_for('calculatentrade.get_strategies'))


@calculatentrade_bp.route('/strategies', methods=['POST'])
def strategies_post_redirect():
    """Redirect POST /strategies to blueprint route"""
    return redirect(url_for('calculatentrade.api_add_strategy'), code=307)


@calculatentrade_bp.route('/strategies/<int:strategy_id>')
def strategy_detail_redirect(strategy_id):
    """Redirect /strategies/<id> to blueprint route"""
    return redirect(url_for('calculatentrade.api_get_strategy', strategy_id=strategy_id))


@calculatentrade_bp.route('/strategies/<int:strategy_id>', methods=['PUT'])
def strategy_put_redirect(strategy_id):
    """Redirect PUT /strategies/<id> to blueprint route"""
    return redirect(url_for('calculatentrade.api_update_strategy', strategy_id=strategy_id), code=307)


@calculatentrade_bp.route('/strategies/<int:strategy_id>', methods=['DELETE'])
def strategy_delete_redirect(strategy_id):
    """Redirect DELETE /strategies/<id> to blueprint route"""
    return redirect(url_for('calculatentrade.api_delete_strategy', strategy_id=strategy_id), code=307)


# ---------------- HEALTH CHECK ---------------- #
@calculatentrade_bp.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': 'connected' if db.engine else 'disconnected'
    })


# ---------------- INITIALIZATION ---------------- #
def init_db(app=None):
    """Initialize database with sample data"""
    if app is None:
        from flask import current_app
        app = current_app
    with app.app_context():
        # Run migration for Rule table
        migrate_rules_table()
        db.create_all()

def migrate_rules_table():
    """Add new columns to existing Rule table if they don't exist"""
    try:
        # Check if new columns exist by trying to query them
        db.session.execute("SELECT category FROM rule LIMIT 1")
        print("Rule table already migrated")
        return
    except Exception:
        # Columns don't exist, add them
        migration_sql = [
            "ALTER TABLE rule ADD COLUMN category VARCHAR(50) DEFAULT 'Risk'",
            "ALTER TABLE rule ADD COLUMN tags TEXT",
            "ALTER TABLE rule ADD COLUMN priority VARCHAR(10) DEFAULT 'medium'", 
            "ALTER TABLE rule ADD COLUMN active BOOLEAN DEFAULT true",
            "ALTER TABLE rule ADD COLUMN linked_strategy_id INTEGER",
            "ALTER TABLE rule ADD COLUMN violation_consequence VARCHAR(20) DEFAULT 'log'",
            "ALTER TABLE rule ADD COLUMN save_template BOOLEAN DEFAULT false",
            "ALTER TABLE rule ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        ]
        
        for sql in migration_sql:
            try:
                db.session.execute(sql)
                print(f"Added column: {sql.split('ADD COLUMN')[1].split()[0]}")
            except Exception as e:
                print(f"Column might already exist: {e}")
        
        db.session.commit()
        print("Rule table migration completed")
        
        # Update existing rules with default values
        existing_rules = Rule.query.all()
        for rule in existing_rules:
            try:
                if not rule.category:
                    rule.category = 'Risk'
                if not rule.priority:
                    rule.priority = 'medium'
                if rule.active is None:
                    rule.active = True
                if not rule.violation_consequence:
                    rule.violation_consequence = 'log'
                if rule.save_template is None:
                    rule.save_template = False
            except Exception:
                pass  # Skip if columns don't exist yet
        
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        
        # Create sample strategies if none exist
        if Strategy.query.count() == 0:
            strategies = [
                Strategy(name="Breakout Trading", description="Trading breakouts from consolidation"),
                Strategy(name="Pullback Trading", description="Trading pullbacks in trends"),
                Strategy(name="Range Trading", description="Trading range-bound markets"),
                Strategy(name="News Trading", description="Trading based on news events")
            ]
            db.session.bulk_save_objects(strategies)
            try:
                # app.session_interface is an instance of SqlAlchemySessionInterface
                # which has a .db attribute pointing to the SQLAlchemy instance
                try:
                    if hasattr(current_app, "session_interface") and getattr(current_app.session_interface, "db", None):
                        current_app.session_interface.db.create_all()
                except RuntimeError:
                    # no current_app context; skip
                    pass

                    app.logger.info("Created session table via app.session_interface.db.create_all()")
                else:
                    app.logger.info("No session_interface.db found; session table not created here.")
            except Exception as e:
                app.logger.error("Failed to create session table: %s", e)
            
        # Create sample rules if none exist
        if Rule.query.count() == 0:
            rules = [
                Rule(title="Risk Management", description="Never risk more than 2% of capital on a single trade"),
                Rule(title="Stop Loss", description="Always set a stop loss before entering a trade"),
                Rule(title="Profit Taking", description="Take profits at predetermined levels"),
                Rule(title="Emotional Control", description="Don't let emotions dictate trading decisions")
            ]
            db.session.bulk_save_objects(rules)
        
        # Create sample mistakes if none exist
        if Mistake.query.count() == 0:
            mistakes = [
                Mistake(
                    title="Revenge Trading", 
                    description="Trying to recover losses immediately. Take a break after a loss.",
                    category="psychology",
                    severity="high",
                    pnl_impact=-500.0,
                    searchable_text="Revenge Trading Trying to recover losses immediately. Take a break after a loss."
                ),
                Mistake(
                    title="Overtrading", 
                    description="Taking too many trades. Focus on quality over quantity.",
                    category="process",
                    severity="medium",
                    pnl_impact=-200.0,
                    searchable_text="Overtrading Taking too many trades. Focus on quality over quantity."
                ),
                Mistake(
                    title="Ignoring Stop Loss", 
                    description="Not setting or moving stop loss. Always respect your stop loss.",
                    category="risk",
                    severity="critical",
                    pnl_impact=-1000.0,
                    searchable_text="Ignoring Stop Loss Not setting or moving stop loss. Always respect your stop loss."
                )
            ]
            db.session.bulk_save_objects(mistakes)
        
        db.session.commit()

        # Load persisted broker accounts into in-memory store (so endpoints work immediately)
        load_persisted_accounts_into_memory(app)

# ---------------- MAIN ---------------- #
        return jsonify({"ok": True, "message": f"Disconnected {broker} for user {user_id}"})
        
    except Exception as e:
        current_app.logger.error(f"Disconnect error: {e}")
        return jsonify({"ok": False, "message": str(e)})


# Initialize broker accounts on module load
try:
    init_broker_accounts()
except Exception as e:
    print(f"Warning: Could not initialize broker accounts: {e}")


# Export the blueprint
__all__ = ['calculatentrade_bp']