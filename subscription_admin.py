from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime, timezone, timedelta
from subscription_models import (
    SubscriptionPlan, UserSubscription, SubscriptionHistory, SubscriptionMetrics,
    create_user_subscription, get_user_active_subscription, 
    check_and_expire_subscriptions, get_subscription_stats
)
from journal import db
import json

subscription_admin_bp = Blueprint('subscription_admin', __name__)

# Admin decorator (you can modify this based on your admin system)
def admin_required(f):
    def subscription_admin_decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        # Add your admin check logic here
        # For now, assuming admin check is done elsewhere
        return f(*args, **kwargs)
    subscription_admin_decorated_function.__name__ = f.__name__
    return subscription_admin_decorated_function

@subscription_admin_bp.route('/dashboard')
@admin_required
def admin_dashboard():
    """Subscription admin dashboard"""
    stats = get_subscription_stats()
    
    # Get recent subscriptions using raw SQL
    from sqlalchemy import text
    try:
        recent_result = db.session.execute(text("""
            SELECT us.id, us.status, us.start_date, us.end_date, us.amount_paid,
                   u.email, sp.display_name, us.user_id
            FROM user_subscriptions us
            JOIN users u ON us.user_id = u.id
            JOIN subscription_plans sp ON us.plan_id = sp.id
            ORDER BY us.created_at DESC
            LIMIT 10
        """))
        
        recent_subs = []
        for row in recent_result:
            # Create simple objects for template
            class SimpleSub:
                def __init__(self, row):
                    self.id = row[0]
                    self.status = row[1]
                    # Ensure dates are datetime objects or None
                    self.start_date = row[2] if row[2] and hasattr(row[2], 'strftime') else None
                    self.end_date = row[3] if row[3] and hasattr(row[3], 'strftime') else None
                    self.amount_paid = row[4]
                    self.user_id = row[7]
                    
                    # Create nested objects
                    class SimpleUser:
                        def __init__(self, email):
                            self.email = email
                    class SimplePlan:
                        def __init__(self, display_name):
                            self.display_name = display_name
                    
                    self.user = SimpleUser(row[5])
                    self.plan = SimplePlan(row[6])
            
            recent_subs.append(SimpleSub(row))
    except Exception as e:
        print(f"Error fetching recent subscriptions: {e}")
        recent_subs = []
    
    # For now, set expiring_subs to empty to avoid errors
    expiring_subs = []
    
    return render_template('admin/subscription_dashboard.html', 
                         stats=stats, 
                         recent_subs=recent_subs,
                         expiring_subs=expiring_subs)

@subscription_admin_bp.route('/users')
@admin_required
def manage_users():
    """Manage user subscriptions"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    
    # Import User model dynamically to avoid circular imports
    from flask import current_app
    User = current_app.extensions['sqlalchemy'].Model.registry._class_registry.get('User')
    if not User:
        # Fallback: use raw SQL query
        from sqlalchemy import text
        if search:
            search_filter = f"WHERE email LIKE '%{search}%'"
        else:
            search_filter = ""
        
        result = db.session.execute(text(f"""
            SELECT u.id, u.email, u.registered_on, u.verified,
                   us.status, us.start_date, us.end_date, sp.display_name
            FROM users u
            LEFT JOIN user_subscriptions us ON u.id = us.user_id AND us.status = 'active'
            LEFT JOIN subscription_plans sp ON us.plan_id = sp.id
            {search_filter}
            ORDER BY u.registered_on DESC
            LIMIT 20 OFFSET {(page-1)*20}
        """))
        
        users_data = []
        for row in result:
            users_data.append({
                'id': row[0],
                'email': row[1], 
                'registered_on': row[2],
                'verified': row[3],
                'subscription_status': row[4],
                'subscription_start': row[5],
                'subscription_end': row[6],
                'plan_name': row[7]
            })
        
        # Create a mock pagination object
        class MockPagination:
            def __init__(self, items):
                self.items = items
                self.pages = 1
                self.page = page
                self.has_prev = False
                self.has_next = False
                self.prev_num = None
                self.next_num = None
            def iter_pages(self):
                return [1]
        
        users = MockPagination(users_data)
        user_subs = {}
        
        return render_template('admin/manage_users.html', 
                             users=users, 
                             user_subs=user_subs,
                             search=search,
                             status=status)
    
    query = db.session.query(User).outerjoin(UserSubscription).outerjoin(SubscriptionPlan)
    
    if search:
        query = query.filter(User.email.contains(search))
    
    if status:
        if status == 'active':
            now = datetime.now(timezone.utc)
            query = query.filter(
                UserSubscription.status == 'active',
                UserSubscription.end_date > now
            )
        elif status == 'expired':
            query = query.filter(UserSubscription.status == 'expired')
        elif status == 'no_subscription':
            query = query.filter(UserSubscription.id.is_(None))
    
    users = query.paginate(page=page, per_page=20, error_out=False)
    
    # Get subscription info for each user
    user_subs = {}
    for user in users.items:
        active_sub = get_user_active_subscription(user.id)
        user_subs[user.id] = active_sub
    
    return render_template('admin/manage_users.html', 
                         users=users, 
                         user_subs=user_subs,
                         search=search,
                         status=status)

@subscription_admin_bp.route('/user/<int:user_id>')
@admin_required
def user_detail(user_id):
    """User subscription details"""
    # Use raw SQL to get user data
    from sqlalchemy import text
    user_result = db.session.execute(text(
        "SELECT id, email, registered_on, verified, name, google_id FROM users WHERE id = :user_id"
    ), {'user_id': user_id}).fetchone()
    
    if not user_result:
        from flask import abort
        abort(404)
    
    # Create a simple user object
    class SimpleUser:
        def __init__(self, row):
            self.id = row[0]
            self.email = row[1]
            # Ensure registered_on is datetime object or None
            self.registered_on = row[2] if row[2] and hasattr(row[2], 'strftime') else None
            self.verified = row[3]
            self.name = row[4]
            self.google_id = row[5]
    
    user = SimpleUser(user_result)
    
    # Get all subscriptions for this user
    subscriptions = UserSubscription.query.filter_by(user_id=user_id).join(
        SubscriptionPlan
    ).order_by(UserSubscription.created_at.desc()).all()
    
    # Get subscription history
    history = SubscriptionHistory.query.filter_by(user_id=user_id).order_by(
        SubscriptionHistory.created_at.desc()
    ).all()
    
    # Get active subscription
    active_sub = get_user_active_subscription(user_id)
    
    return render_template('admin/user_subscription_detail.html',
                         user=user,
                         subscriptions=subscriptions,
                         history=history,
                         active_sub=active_sub)

@subscription_admin_bp.route('/user/<int:user_id>/create_subscription', methods=['POST'])
@admin_required
def create_subscription_for_user(user_id):
    """Create subscription for user (admin action)"""
    try:
        data = request.get_json()
        plan_name = data.get('plan_name')
        days = data.get('days')  # Custom days override
        notes = data.get('notes', '')
        
        if not plan_name:
            return jsonify({'success': False, 'error': 'Plan name required'}), 400
        
        plan = SubscriptionPlan.query.filter_by(name=plan_name).first()
        if not plan:
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
        
        # Create subscription
        subscription = create_user_subscription(
            user_id=user_id,
            plan_name=plan_name,
            amount_paid=0  # Admin created, no payment
        )
        
        # Override duration if specified
        if days:
            subscription.end_date = subscription.start_date + timedelta(days=int(days))
            subscription.admin_notes = f"Custom duration: {days} days. {notes}"
        else:
            subscription.admin_notes = notes
        
        # Log admin action
        history = SubscriptionHistory(
            user_id=user_id,
            subscription_id=subscription.id,
            action='admin_created',
            new_status='active',
            plan_name=plan.name,
            admin_user_id=current_user.id,
            notes=f"Created by admin. {notes}"
        )
        db.session.add(history)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Subscription created successfully',
            'subscription_id': subscription.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@subscription_admin_bp.route('/user/<int:user_id>/extend_subscription', methods=['POST'])
@admin_required
def extend_user_subscription(user_id):
    """Extend user subscription"""
    try:
        data = request.get_json()
        days = int(data.get('days', 0))
        notes = data.get('notes', '')
        
        if days <= 0:
            return jsonify({'success': False, 'error': 'Days must be positive'}), 400
        
        active_sub = get_user_active_subscription(user_id)
        if not active_sub:
            return jsonify({'success': False, 'error': 'No active subscription found'}), 404
        
        # Extend subscription
        old_end_date = active_sub.end_date
        active_sub.extend_subscription(days)
        active_sub.admin_notes = f"{active_sub.admin_notes or ''}\nExtended by {days} days. {notes}".strip()
        
        # Log admin action
        history = SubscriptionHistory(
            user_id=user_id,
            subscription_id=active_sub.id,
            action='admin_extended',
            old_status='active',
            new_status='active',
            days_added=days,
            admin_user_id=current_user.id,
            notes=f"Extended by {days} days. {notes}"
        )
        db.session.add(history)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Subscription extended by {days} days',
            'new_end_date': active_sub.end_date.isoformat()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@subscription_admin_bp.route('/user/<int:user_id>/cancel_subscription', methods=['POST'])
@admin_required
def cancel_user_subscription(user_id):
    """Cancel user subscription"""
    try:
        data = request.get_json()
        notes = data.get('notes', '')
        
        active_sub = get_user_active_subscription(user_id)
        if not active_sub:
            return jsonify({'success': False, 'error': 'No active subscription found'}), 404
        
        # Cancel subscription
        active_sub.status = 'cancelled'
        active_sub.updated_at = datetime.now(timezone.utc)
        active_sub.admin_notes = f"{active_sub.admin_notes or ''}\nCancelled by admin. {notes}".strip()
        
        # Log admin action
        history = SubscriptionHistory(
            user_id=user_id,
            subscription_id=active_sub.id,
            action='admin_cancelled',
            old_status='active',
            new_status='cancelled',
            admin_user_id=current_user.id,
            notes=f"Cancelled by admin. {notes}"
        )
        db.session.add(history)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Subscription cancelled successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@subscription_admin_bp.route('/plans')
@admin_required
def manage_plans():
    """Manage subscription plans"""
    try:
        from sqlalchemy import text
        result = db.session.execute(text("""
            SELECT id, name, display_name, price, duration_days, features, is_active, created_at
            FROM subscription_plans
            ORDER BY created_at DESC
        """))
        
        plans = []
        for row in result:
            class SimplePlan:
                def __init__(self, row):
                    self.id = row[0]
                    self.name = row[1]
                    self.display_name = row[2]
                    self.price = row[3]
                    self.duration_days = row[4]
                    self.features = json.loads(row[5]) if row[5] else []
                    self.is_active = bool(row[6])
                    # Ensure created_at is datetime object or None
                    self.created_at = row[7] if row[7] and hasattr(row[7], 'strftime') else None
                
                def to_dict(self):
                    return {
                        'id': self.id,
                        'name': self.name,
                        'display_name': self.display_name,
                        'price': self.price,
                        'duration_days': self.duration_days,
                        'features': self.features,
                        'is_active': self.is_active
                    }
            
            plan_obj = SimplePlan(row)
            plans.append(plan_obj)
    except Exception as e:
        print(f"Error fetching plans: {e}")
        plans = []
    
    return render_template('admin/manage_plans.html', plans=plans)

@subscription_admin_bp.route('/plans/create', methods=['POST'])
@admin_required
def create_plan():
    """Create new subscription plan"""
    try:
        data = request.get_json()
        
        plan = SubscriptionPlan(
            name=data['name'],
            display_name=data['display_name'],
            price=int(data['price']),
            duration_days=int(data['duration_days']),
            features=data.get('features', []),
            is_active=data.get('is_active', True)
        )
        
        db.session.add(plan)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Plan created successfully',
            'plan_id': plan.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@subscription_admin_bp.route('/plans/<int:plan_id>/update', methods=['POST'])
@admin_required
def update_plan(plan_id):
    """Update subscription plan"""
    try:
        plan = SubscriptionPlan.query.get_or_404(plan_id)
        data = request.get_json()
        
        plan.display_name = data.get('display_name', plan.display_name)
        plan.price = int(data.get('price', plan.price))
        plan.duration_days = int(data.get('duration_days', plan.duration_days))
        plan.features = data.get('features', plan.features)
        plan.is_active = data.get('is_active', plan.is_active)
        plan.updated_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Plan updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@subscription_admin_bp.route('/analytics')
@admin_required
def analytics():
    """Subscription analytics"""
    stats = get_subscription_stats()
    
    # For now, use empty data to avoid SQL complexity
    monthly_revenue = []
    plan_distribution = [('Monthly Plan', stats.get('monthly_active', 0)), ('Yearly Plan', stats.get('yearly_active', 0))]
    
    return render_template('admin/subscription_analytics.html',
                         stats=stats,
                         monthly_revenue=monthly_revenue,
                         plan_distribution=plan_distribution)

@subscription_admin_bp.route('/api/expire_check')
@admin_required
def expire_check():
    """Check and expire subscriptions"""
    try:
        expired_count = check_and_expire_subscriptions()
        return jsonify({
            'success': True,
            'expired_count': expired_count,
            'message': f'Checked subscriptions, {expired_count} expired'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@subscription_admin_bp.route('/api/stats')
@admin_required
def api_stats():
    """Get subscription stats API"""
    try:
        stats = get_subscription_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@subscription_admin_bp.route('/export/users')
@admin_required
def export_users():
    """Export user subscription data"""
    try:
        users_data = db.session.query(
            User.id,
            User.email,
            User.registered_on,
            UserSubscription.status,
            UserSubscription.start_date,
            UserSubscription.end_date,
            SubscriptionPlan.display_name,
            UserSubscription.amount_paid
        ).outerjoin(UserSubscription).outerjoin(SubscriptionPlan).all()
        
        # Convert to list of dicts for JSON export
        export_data = []
        for row in users_data:
            export_data.append({
                'user_id': row[0],
                'email': row[1],
                'registered_on': row[2].isoformat() if row[2] else None,
                'subscription_status': row[3],
                'subscription_start': row[4].isoformat() if row[4] else None,
                'subscription_end': row[5].isoformat() if row[5] else None,
                'plan_name': row[6],
                'amount_paid': row[7] / 100 if row[7] else 0  # Convert paise to rupees
            })
        
        return jsonify({
            'success': True,
            'data': export_data,
            'count': len(export_data)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500