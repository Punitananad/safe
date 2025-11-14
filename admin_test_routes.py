"""
Simple test routes for admin authentication debugging
Add these routes to app.py for testing
"""

from flask import session, redirect, url_for, jsonify

def add_test_routes(app):
    """Add test routes to the Flask app"""
    
    @app.route('/admin/test-login')
    def test_admin_login():
        """Test route to directly set admin session"""
        session['admin_logged_in'] = True
        session['admin_username'] = 'admin'
        session['admin_role'] = 'owner'
        session['admin_verified'] = True
        return jsonify({
            'success': True,
            'message': 'Admin session set directly',
            'redirect': '/admin/dashboard'
        })
    
    @app.route('/admin/test-session')
    def test_admin_session():
        """Test route to check admin session"""
        return jsonify({
            'admin_logged_in': session.get('admin_logged_in'),
            'admin_username': session.get('admin_username'),
            'admin_role': session.get('admin_role'),
            'admin_verified': session.get('admin_verified'),
            'session_keys': list(session.keys())
        })
    
    @app.route('/admin/test-clear')
    def test_clear_session():
        """Test route to clear admin session"""
        session.clear()
        return jsonify({
            'success': True,
            'message': 'Session cleared'
        })

# Usage: Add this to app.py
# from admin_test_routes import add_test_routes
# add_test_routes(app)