# Add this at the end of app.py after all models are defined

# ------------------------------------------------------------------------------
# Register Blueprints (after all models are defined)
# ------------------------------------------------------------------------------
from broker_routes import broker_bp
from broker_check import check_broker_connection

# Register broker blueprint
app.register_blueprint(broker_bp)

# Register other blueprints
app.register_blueprint(calculatentrade_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(employee_dashboard_bp)
app.register_blueprint(mentor_bp)
app.register_blueprint(subscription_admin_bp)

# Multi-broker connection check route
@app.route('/api/broker/check-all', methods=['GET'])
@login_required
def api_check_all_brokers():
    user_id = request.args.get('user_id', current_user.email)
    brokers = ['kite', 'dhan', 'angel']
    
    connected_brokers = []
    for broker in brokers:
        status = check_broker_connection(broker, user_id)
        if status['connected']:
            connected_brokers.append(status)
    
    return jsonify({
        'ok': True,
        'connected_brokers': connected_brokers,
        'total_connected': len(connected_brokers)
    })

if __name__ == "__main__":
    # Initialize database tables
    with app.app_context():
        try:
            db.create_all()
            print("Database tables created successfully")
        except Exception as e:
            print(f"Database initialization error: {e}")
    
    app.run(debug=True, host="0.0.0.0", port=5000)