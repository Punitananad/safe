from datetime import datetime, timezone, timedelta
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

# Import the existing db instance and User model
from journal import db
# User model will be imported dynamically to avoid circular imports

class SubscriptionPlan(db.Model):
    """Subscription plans available"""
    __tablename__ = "subscription_plans"
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)  # monthly, yearly
    display_name = db.Column(db.String(100), nullable=False)  # Monthly Plan, Yearly Plan
    price = db.Column(db.Integer, nullable=False)  # Price in paise
    duration_days = db.Column(db.Integer, nullable=False)  # 30, 365
    features = db.Column(db.JSON, nullable=True)  # List of features
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class UserSubscription(db.Model):
    """User subscription records - separate from User model"""
    __tablename__ = "user_subscriptions"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('subscription_plans.id'), nullable=False)
    
    # Subscription status
    status = db.Column(db.String(20), default='active')  # active, expired, cancelled, suspended
    
    # Dates
    start_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    end_date = db.Column(db.DateTime, nullable=False)
    
    # Payment info
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=True)
    amount_paid = db.Column(db.Integer, nullable=False)  # Amount in paise
    
    # Auto-renewal
    auto_renew = db.Column(db.Boolean, default=False)
    
    # Admin notes
    admin_notes = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships - using string references to avoid circular imports
    plan = db.relationship('SubscriptionPlan', backref=db.backref('subscriptions', lazy=True))
    # User relationship will be established dynamically
    # payment relationship will be established when Payment model is available
    
    def is_active(self):
        """Check if subscription is currently active"""
        now = datetime.now(timezone.utc)
        
        # Ensure datetimes are timezone-aware for comparison
        start_date = self.start_date
        end_date = self.end_date
        
        if start_date and start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date and end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
            
        return (self.status == 'active' and 
                start_date <= now <= end_date)
    
    def days_remaining(self):
        """Get days remaining in subscription"""
        if not self.is_active():
            return 0
        now = datetime.now(timezone.utc)
        
        # Ensure end_date is timezone-aware
        end_date = self.end_date
        if end_date and end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
            
        remaining = end_date - now
        return max(0, remaining.days)
    
    def extend_subscription(self, days):
        """Extend subscription by given days"""
        self.end_date = self.end_date + timedelta(days=days)
        self.updated_at = datetime.now(timezone.utc)

class SubscriptionHistory(db.Model):
    """Track all subscription changes"""
    __tablename__ = "subscription_history"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('user_subscriptions.id'), nullable=True)
    
    action = db.Column(db.String(50), nullable=False)  # created, renewed, cancelled, expired, suspended
    old_status = db.Column(db.String(20), nullable=True)
    new_status = db.Column(db.String(20), nullable=True)
    
    # Details
    plan_name = db.Column(db.String(50), nullable=True)
    amount = db.Column(db.Integer, nullable=True)
    days_added = db.Column(db.Integer, nullable=True)
    
    # Admin info
    admin_user_id = db.Column(db.Integer, nullable=True)  # If changed by admin
    notes = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships - using string references to avoid circular imports
    subscription = db.relationship('UserSubscription', backref=db.backref('history', lazy=True))
    # User relationship will be established dynamically

class SubscriptionMetrics(db.Model):
    """Daily subscription metrics for analytics"""
    __tablename__ = "subscription_metrics"
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    
    # Counts
    total_active_subscriptions = db.Column(db.Integer, default=0)
    new_subscriptions = db.Column(db.Integer, default=0)
    cancelled_subscriptions = db.Column(db.Integer, default=0)
    expired_subscriptions = db.Column(db.Integer, default=0)
    
    # Revenue
    daily_revenue = db.Column(db.Integer, default=0)  # In paise
    monthly_revenue = db.Column(db.Integer, default=0)
    yearly_revenue = db.Column(db.Integer, default=0)
    
    # Plan breakdown
    monthly_plan_count = db.Column(db.Integer, default=0)
    yearly_plan_count = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

def establish_user_relationships():
    """Establish User model relationships after all models are loaded"""
    try:
        from flask import current_app
        # Get User model from the registry
        User = current_app.extensions['sqlalchemy'].Model.registry._class_registry.get('User')
        if User:
            # Add relationships to User model if they don't exist
            if not hasattr(User, 'subscriptions'):
                User.subscriptions = db.relationship('UserSubscription', backref='user', lazy=True)
            if not hasattr(User, 'subscription_history'):
                User.subscription_history = db.relationship('SubscriptionHistory', backref='user', lazy=True)
    except Exception as e:
        print(f"Warning: Could not establish User relationships: {e}")

def init_subscription_plans():
    """Initialize default subscription plans"""
    plans = [
        {
            'name': 'monthly',
            'display_name': 'Monthly Plan',
            'price': 2500,  # ₹25 in paise
            'duration_days': 30,
            'features': [
                'All Trading Calculators',
                'Position Management',
                'Trade Journal',
                'Risk Analysis',
                'Real-time Data',
                'Email Support'
            ]
        },
        {
            'name': 'yearly',
            'display_name': 'Yearly Plan',
            'price': 27000,  # ₹270 in paise
            'duration_days': 365,
            'features': [
                'All Trading Calculators',
                'Position Management', 
                'Trade Journal',
                'Risk Analysis',
                'Real-time Data',
                'Priority Support',
                'Advanced Analytics',
                'Custom Strategies'
            ]
        }
    ]
    
    for plan_data in plans:
        existing = SubscriptionPlan.query.filter_by(name=plan_data['name']).first()
        if not existing:
            plan = SubscriptionPlan(**plan_data)
            db.session.add(plan)
    
    db.session.commit()

def create_user_subscription(user_id, plan_name, payment_id=None, amount_paid=None):
    """Create a new subscription for user"""
    plan = SubscriptionPlan.query.filter_by(name=plan_name, is_active=True).first()
    if not plan:
        raise ValueError(f"Plan {plan_name} not found")
    
    # Cancel any existing active subscriptions
    existing = UserSubscription.query.filter_by(
        user_id=user_id, 
        status='active'
    ).first()
    
    if existing:
        existing.status = 'cancelled'
        existing.updated_at = datetime.now(timezone.utc)
        
        # Log history
        history = SubscriptionHistory(
            user_id=user_id,
            subscription_id=existing.id,
            action='cancelled',
            old_status='active',
            new_status='cancelled',
            notes='Cancelled due to new subscription'
        )
        db.session.add(history)
    
    # Create new subscription
    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=plan.duration_days)
    
    subscription = UserSubscription(
        user_id=user_id,
        plan_id=plan.id,
        start_date=start_date,
        end_date=end_date,
        payment_id=payment_id,
        amount_paid=amount_paid or plan.price,
        status='active'
    )
    
    db.session.add(subscription)
    db.session.flush()  # Get the ID
    
    # Log history
    history = SubscriptionHistory(
        user_id=user_id,
        subscription_id=subscription.id,
        action='created',
        new_status='active',
        plan_name=plan.name,
        amount=subscription.amount_paid,
        days_added=plan.duration_days
    )
    db.session.add(history)
    
    db.session.commit()
    return subscription

def get_user_active_subscription(user_id):
    """Get user's current active subscription"""
    return UserSubscription.query.filter_by(
        user_id=user_id,
        status='active'
    ).filter(
        UserSubscription.end_date > datetime.now(timezone.utc)
    ).first()

def check_and_expire_subscriptions():
    """Check and expire subscriptions that have ended"""
    now = datetime.now(timezone.utc)
    
    # Get all active subscriptions
    active_subs = UserSubscription.query.filter(
        UserSubscription.status == 'active'
    ).all()
    
    expired_subs = []
    for sub in active_subs:
        end_date = sub.end_date
        if end_date and end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        if end_date and end_date <= now:
            expired_subs.append(sub)
    
    for sub in expired_subs:
        sub.status = 'expired'
        sub.updated_at = now
        
        # Log history
        history = SubscriptionHistory(
            user_id=sub.user_id,
            subscription_id=sub.id,
            action='expired',
            old_status='active',
            new_status='expired',
            plan_name=sub.plan.name
        )
        db.session.add(history)
    
    db.session.commit()
    return len(expired_subs)

def get_subscription_stats():
    """Get subscription statistics"""
    now = datetime.now(timezone.utc)
    
    # Get counts using raw SQL to avoid timezone issues
    from sqlalchemy import text
    
    try:
        # Count active subscriptions
        active_count = db.session.execute(text(
            "SELECT COUNT(*) FROM user_subscriptions WHERE status = 'active'"
        )).scalar() or 0
        
        expired_count = db.session.execute(text(
            "SELECT COUNT(*) FROM user_subscriptions WHERE status = 'expired'"
        )).scalar() or 0
        
        cancelled_count = db.session.execute(text(
            "SELECT COUNT(*) FROM user_subscriptions WHERE status = 'cancelled'"
        )).scalar() or 0
        
        monthly_count = db.session.execute(text(
            "SELECT COUNT(*) FROM user_subscriptions us JOIN subscription_plans sp ON us.plan_id = sp.id WHERE us.status = 'active' AND sp.name = 'monthly'"
        )).scalar() or 0
        
        yearly_count = db.session.execute(text(
            "SELECT COUNT(*) FROM user_subscriptions us JOIN subscription_plans sp ON us.plan_id = sp.id WHERE us.status = 'active' AND sp.name = 'yearly'"
        )).scalar() or 0
        
        total_revenue = db.session.execute(text(
            "SELECT SUM(amount_paid) FROM user_subscriptions WHERE status IN ('active', 'expired')"
        )).scalar() or 0
        
        stats = {
            'total_active': active_count,
            'total_expired': expired_count,
            'total_cancelled': cancelled_count,
            'monthly_active': monthly_count,
            'yearly_active': yearly_count,
            'expiring_soon': 0,  # Will calculate separately if needed
            'total_revenue': total_revenue
        }
    except Exception as e:
        print(f"Error getting subscription stats: {e}")
        stats = {
            'total_active': 0,
            'total_expired': 0,
            'total_cancelled': 0,
            'monthly_active': 0,
            'yearly_active': 0,
            'expiring_soon': 0,
            'total_revenue': 0
        }
    
    return stats