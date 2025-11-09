# Add this to app.py after the existing imports

# Multi-broker system import
from multi_broker_system import multi_broker_bp, integrate_with_calculatentrade, get_broker_session_status

# Add this route after the existing routes in app.py

@app.route('/multi_broker_connect')
@login_required
def multi_broker_connect():
    """Multi-broker connection interface"""
    try:
        # Get user ID for session checking
        user_id = request.args.get('user_id', 'default_user')
        
        # Check for connected brokers
        connected_brokers = []
        brokers = ['kite', 'dhan', 'angel']
        
        for broker in brokers:
            status = get_broker_session_status(broker, user_id)
            if status['connected']:
                connected_brokers.append({
                    'broker': broker,
                    'user_id': user_id,
                    'session_data': status.get('session_data', {})
                })
        
        # Check if we have connected brokers
        has_connected_brokers = len(connected_brokers) > 0
        
        return render_template(
            'multi_broker_connect.html',
            connected_brokers=connected_brokers,
            has_connected_brokers=has_connected_brokers,
            user_id=user_id
        )
        
    except Exception as e:
        print(f"Error in multi_broker_connect route: {e}")
        return render_template(
            'multi_broker_connect.html',
            connected_brokers=[],
            has_connected_brokers=False,
            user_id='default_user',
            error=str(e)
        )

# Additional API route for getting all broker data
@app.route('/api/broker/get-all-data')
@login_required
def get_all_broker_data():
    """Get all trading data from connected brokers"""
    try:
        broker = request.args.get('broker')
        user_id = request.args.get('user_id', 'default_user')
        
        if not broker:
            return jsonify({'success': False, 'error': 'Broker parameter required'}), 400
        
        # This would integrate with the multi_broker_system to fetch data
        # For now, return a placeholder response
        return jsonify({
            'success': True,
            'data': {
                'orders': [],
                'trades': [],
                'positions': []
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Add this after the blueprint registrations in app.py
# Register multi-broker blueprint and integrate
try:
    integrate_with_calculatentrade(app)
    print("Multi-broker system integrated successfully")
except Exception as e:
    print(f"Error integrating multi-broker system: {e}")