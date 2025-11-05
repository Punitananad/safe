from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime, timezone, timedelta
from journal import db
import json

simple_sub_admin_bp = Blueprint('simple_sub_admin', __name__)

def admin_required(f):
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

@simple_sub_admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Simple subscription dashboard"""
    from sqlalchemy import text
    
    try:
        # Get basic stats using raw SQL
        active_count = db.session.execute(text(
            "SELECT COUNT(*) FROM user_subscriptions WHERE status = 'active'"
        )).scalar() or 0
        
        total_revenue = db.session.execute(text(
            "SELECT SUM(amount_paid) FROM user_subscriptions WHERE status IN ('active', 'expired')"
        )).scalar() or 0
        
        stats = {
            'total_active': active_count,
            'total_revenue': total_revenue,
            'total_expired': 0,
            'expiring_soon': 0,
            'monthly_active': 0,
            'yearly_active': 0
        }
    except Exception as e:
        print(f"Error getting stats: {e}")
        stats = {'total_active': 0, 'total_revenue': 0, 'total_expired': 0, 'expiring_soon': 0, 'monthly_active': 0, 'yearly_active': 0}
    
    return render_template('admin/simple_subscription_dashboard.html', stats=stats)

@simple_sub_admin_bp.route('/users')
@admin_required
def users():
    """Simple user management"""
    from sqlalchemy import text
    
    try:
        result = db.session.execute(text("""
            SELECT u.id, u.email, u.registered_on, u.subscription_active, u.subscription_type, u.subscription_expires
            FROM users u
            ORDER BY u.registered_on DESC
            LIMIT 50
        """))
        
        users_data = []
        for row in result:
            users_data.append({
                'id': row[0],
                'email': row[1],
                'registered_on': row[2],
                'subscription_active': bool(row[3]),
                'subscription_type': row[4],
                'subscription_expires': row[5]
            })
    except Exception as e:
        print(f"Error fetching users: {e}")
        users_data = []
    
    return render_template('admin/simple_manage_users.html', users=users_data)

@simple_sub_admin_bp.route('/user/<int:user_id>/activate', methods=['POST'])
@admin_required
def activate_user_subscription(user_id):
    """Activate subscription for user"""
    try:
        plan_type = request.json.get('plan_type', 'monthly')
        days = 30 if plan_type == 'monthly' else 365
        
        from sqlalchemy import text
        # Update user subscription
        db.session.execute(text("""
            UPDATE users 
            SET subscription_active = 1, 
                subscription_type = :plan_type,
                subscription_expires = :expires
            WHERE id = :user_id
        """), {
            'plan_type': plan_type,
            'expires': datetime.now(timezone.utc) + timedelta(days=days),
            'user_id': user_id
        })
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'{plan_type} subscription activated'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@simple_sub_admin_bp.route('/user/<int:user_id>/deactivate', methods=['POST'])
@admin_required
def deactivate_user_subscription(user_id):
    """Deactivate subscription for user"""
    try:
        from sqlalchemy import text
        db.session.execute(text("""
            UPDATE users 
            SET subscription_active = 0, 
                subscription_type = NULL,
                subscription_expires = NULL
            WHERE id = :user_id
        """), {'user_id': user_id})
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Subscription deactivated'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500