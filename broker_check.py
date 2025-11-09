"""
Broker connection status checker
"""

from broker_manager import broker_manager
from flask import jsonify

def check_broker_connection(broker: str, user_id: str) -> dict:
    """Check if broker is connected and return status"""
    try:
        # Get active session
        session = broker_manager.get_active_session(broker, user_id)
        
        if session:
            return {
                'connected': True,
                'broker': broker,
                'user_id': user_id,
                'session_id': session.get('session_id'),
                'message': f'{broker.upper()} is connected'
            }
        else:
            return {
                'connected': False,
                'broker': broker,
                'user_id': user_id,
                'message': f'{broker.upper()} is not connected',
                'connect_url': f'/multi_broker_connect?broker={broker}&user_id={user_id}'
            }
    except Exception as e:
        return {
            'connected': False,
            'broker': broker,
            'user_id': user_id,
            'error': str(e),
            'connect_url': f'/multi_broker_connect?broker={broker}&user_id={user_id}'
        }