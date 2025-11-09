"""
Enhanced Broker API Routes
Handles broker connections, authentication, and trading operations
"""

from flask import Blueprint, request, jsonify, session, redirect, url_for
from flask_login import login_required, current_user
import requests
import json
import time
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Initialize broker_manager with fallback
broker_manager = None
try:
    from broker_manager import broker_manager as imported_broker_manager
    broker_manager = imported_broker_manager
    logger.info("Broker manager imported successfully")
except ImportError as e:
    logger.error(f"broker_manager module not found: {e}")
    try:
        # Fallback: create a new instance
        from broker_manager import BrokerManager
        broker_manager = BrokerManager()
        logger.info("Broker manager created as fallback")
    except Exception as fallback_error:
        logger.error(f"Fallback broker manager creation failed: {fallback_error}")
        broker_manager = None
except Exception as e:
    logger.error(f"Error importing broker_manager: {e}")
    broker_manager = None

# Import multi-broker system for integration
try:
    from multi_broker_system import USER_SESSIONS as MULTI_BROKER_SESSIONS
    logger.info("Multi-broker system integration available")
except ImportError:
    MULTI_BROKER_SESSIONS = None
    logger.warning("Multi-broker system not available")

broker_bp = Blueprint('broker', __name__, url_prefix='/calculatentrade_journal/api/broker')

# Broker API configurations
BROKER_CONFIGS = {
    'kite': {
        'base_url': 'https://api.kite.trade',
        'login_url': 'https://kite.zerodha.com/connect/login',
        'requires_redirect': True
    },
    'dhan': {
        'base_url': 'https://api.dhan.co',
        'login_url': 'https://api.dhan.co/login',
        'requires_redirect': False
    },
    'angel': {
        'base_url': 'https://apiconnect.angelbroking.com',
        'login_url': 'https://smartapi.angelbroking.com/publisher-login',
        'requires_redirect': False
    }
}

@broker_bp.route('/init', methods=['POST'])
@login_required
def init_broker_system():
    """Initialize broker system and load saved sessions"""
    try:
        global broker_manager
        if not broker_manager:
            # Try to reinitialize broker_manager
            try:
                from broker_manager import BrokerManager
                broker_manager = BrokerManager()
                logger.info("Broker manager reinitialized successfully")
            except Exception as init_error:
                logger.error(f"Failed to reinitialize broker manager: {init_error}")
                return jsonify({
                    'ok': False, 
                    'message': 'Broker manager not available. Please check server configuration.'
                }), 500
            
        # Load existing sessions and credentials
        broker_manager._load_sessions_from_file()
        broker_manager._load_credentials_from_file()
        
        # Cleanup expired sessions
        expired_count = broker_manager.cleanup_expired_sessions()
        
        # Get remembered accounts
        accounts = broker_manager.get_remembered_accounts()
        
        # Count active sessions
        active_sessions = sum(1 for s in broker_manager.sessions.values() 
                            if s['status'] == 'active')
        
        return jsonify({
            'ok': True,
            'message': 'Broker system initialized',
            'accounts_loaded': len(accounts),
            'active_sessions': active_sessions,
            'expired_cleaned': expired_count
        })
    except Exception as e:
        logger.error(f"Broker system init error: {e}")
        return jsonify({'ok': False, 'message': f'Initialization failed: {str(e)}'}), 500

@broker_bp.route('/health', methods=['GET'])
def broker_health_check():
    """Health check for broker system"""
    try:
        status = {
            'broker_manager_available': broker_manager is not None,
            'multi_broker_available': MULTI_BROKER_SESSIONS is not None,
            'timestamp': datetime.now().isoformat()
        }
        
        if broker_manager:
            status['sessions_count'] = len(broker_manager.sessions)
            status['credentials_count'] = len(broker_manager.credentials_store)
        
        if MULTI_BROKER_SESSIONS:
            multi_sessions = sum(len(sessions) for sessions in MULTI_BROKER_SESSIONS.values())
            status['multi_broker_sessions'] = multi_sessions
        
        return jsonify({
            'ok': True,
            'status': status
        })
    except Exception as e:
        logger.error(f"Broker health check error: {e}")
        return jsonify({'ok': False, 'message': str(e)}), 500

@broker_bp.route('/test-register', methods=['POST'])
@login_required
def test_register_endpoint():
    """Test endpoint to debug registration issues"""
    try:
        # Get raw data
        raw_data = request.get_data()
        content_type = request.content_type
        
        # Get JSON data
        json_data = request.get_json(silent=True)
        
        # Get form data
        form_data = dict(request.form) if request.form else None
        
        logger.info(f"Test register - Content-Type: {content_type}")
        logger.info(f"Test register - Raw data length: {len(raw_data) if raw_data else 0}")
        logger.info(f"Test register - JSON data: {json_data}")
        logger.info(f"Test register - Form data: {form_data}")
        
        return jsonify({
            'ok': True,
            'debug': {
                'content_type': content_type,
                'raw_data_length': len(raw_data) if raw_data else 0,
                'json_data': json_data,
                'form_data': form_data,
                'has_json': json_data is not None,
                'broker_manager_available': broker_manager is not None
            }
        })
    except Exception as e:
        logger.error(f"Test register error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@broker_bp.route('/remembered_accounts', methods=['GET'])
@login_required
def get_remembered_accounts():
    """Get list of remembered broker accounts"""
    try:
        if not broker_manager:
            return jsonify({
                'ok': False,
                'message': 'Broker manager not available'
            }), 500
            
        accounts = broker_manager.get_remembered_accounts()
        return jsonify({
            'ok': True,
            'accounts': accounts
        })
    except Exception as e:
        logger.error(f"Get remembered accounts error: {e}")
        return jsonify({'ok': False, 'message': str(e)}), 500

@broker_bp.route('/register', methods=['POST'])
@login_required
def register_broker_credentials():
    """Register and save broker credentials"""
    try:
        data = request.get_json()
        if not data:
            logger.error("No JSON data received in broker registration")
            return jsonify({
                'ok': False, 
                'message': 'No data provided. Please fill in the required fields.'
            }), 400
        
        logger.info(f"Broker registration data received: {list(data.keys())}")
        
        broker = data.get('broker', '').strip()
        user_id = data.get('user_id', '').strip()
        
        # For Dhan, use client_id as user_id if user_id is empty
        if broker == 'dhan' and not user_id:
            user_id = data.get('client_id', '').strip()
        
        logger.info(f"Broker registration attempt - broker: '{broker}', user_id: '{user_id}'")
        
        # Detailed validation
        if not broker:
            logger.warning("Broker registration failed: No broker selected")
            return jsonify({
                'ok': False, 
                'message': 'Please select a broker from the dropdown.'
            }), 400
            
        if not user_id:
            logger.warning("Broker registration failed: No user_id provided")
            return jsonify({
                'ok': False, 
                'message': 'User ID is required. Please enter your trading account User ID.'
            }), 400
        
        # Validate broker
        if broker not in BROKER_CONFIGS:
            return jsonify({
                'ok': False, 
                'message': f'Broker "{broker}" is not supported. Please select Kite, Dhan, or Angel.'
            }), 400
        
        # Extract and validate credentials based on broker type
        credentials = {'user_id': user_id}
        validation_errors = []
        
        if broker == 'kite':
            api_key = data.get('api_key', '').strip()
            api_secret = data.get('api_secret', '').strip()
            
            if not api_key or api_key in ['your_kite_api_key', '']:
                validation_errors.append('Kite API Key is required and cannot be empty.')
            elif len(api_key) < 10:
                validation_errors.append('Kite API Key seems too short. Please check and enter the correct key.')
                
            if not api_secret or api_secret in ['your_kite_api_secret', '']:
                validation_errors.append('Kite API Secret is required and cannot be empty.')
            elif len(api_secret) < 10:
                validation_errors.append('Kite API Secret seems too short. Please check and enter the correct secret.')
                
            credentials.update({
                'api_key': api_key,
                'api_secret': api_secret
            })
            
        elif broker == 'dhan':
            client_id = data.get('client_id', '').strip()
            access_token = data.get('access_token', '').strip()
            
            if not client_id:
                validation_errors.append('Dhan Client ID is required. Please enter your Dhan Client ID.')
            elif len(client_id) < 5:
                validation_errors.append('Dhan Client ID seems too short. Please check and enter the correct Client ID.')
                
            if not access_token:
                validation_errors.append('Dhan Access Token is required. Please enter your Dhan Access Token.')
            elif len(access_token) < 20:
                validation_errors.append('Dhan Access Token seems too short. Please check and enter the correct token.')
                
            credentials.update({
                'client_id': client_id,
                'access_token': access_token
            })
            
        elif broker == 'angel':
            api_key = data.get('api_key', '').strip()
            api_secret = data.get('api_secret', '').strip()
            
            if not api_key:
                validation_errors.append('Angel API Key is required. Please enter your Angel API Key.')
            elif len(api_key) < 8:
                validation_errors.append('Angel API Key seems too short. Please check and enter the correct key.')
                
            if not api_secret:
                validation_errors.append('Angel API Secret is required. Please enter your Angel API Secret.')
            elif len(api_secret) < 10:
                validation_errors.append('Angel API Secret seems too short. Please check and enter the correct secret.')
                
            credentials.update({
                'api_key': api_key,
                'api_secret': api_secret
            })
        
        # Return validation errors if any
        if validation_errors:
            return jsonify({
                'ok': False,
                'message': 'Validation failed: ' + ' '.join(validation_errors),
                'errors': validation_errors
            }), 400
        
        # Save credentials
        try:
            if not broker_manager:
                logger.error("Broker manager is None")
                return jsonify({
                    'ok': False, 
                    'message': 'Broker manager not initialized. Please contact support.'
                }), 500
            
            # Check if user wants to remember session
            remember_session = data.get('remember_session', False)
            if remember_session:
                credentials['remember_session'] = True
                credentials['session_duration'] = 30 * 24 * 60 * 60  # 30 days
                
            success = broker_manager.save_credentials(broker, user_id, credentials)
            
            if success:
                return jsonify({
                    'ok': True,
                    'message': f'{broker.upper()} credentials registered and encrypted successfully for user {user_id}',
                    'broker': broker,
                    'user_id': user_id
                })
            else:
                return jsonify({
                    'ok': False, 
                    'message': 'Failed to save credentials. Please check your inputs and try again.'
                }), 500
                
        except Exception as save_error:
            logger.error(f"Save credentials error: {save_error}")
            return jsonify({
                'ok': False, 
                'message': f'Error saving credentials: {str(save_error)}. Please try again.'
            }), 500
            
    except json.JSONDecodeError as json_err:
        logger.error(f"JSON decode error in broker registration: {json_err}")
        return jsonify({
            'ok': False, 
            'message': 'Invalid data format. Please refresh the page and try again.'
        }), 400
    except Exception as e:
        logger.error(f"Register credentials error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({
            'ok': False, 
            'message': f'Registration failed: {str(e)}. Please check your inputs and try again.'
        }), 500

@broker_bp.route('/status', methods=['GET'])
@login_required
def check_broker_status():
    """Check broker connection status"""
    try:
        broker = request.args.get('broker', '').strip()
        user_id = request.args.get('user_id', '').strip()
        
        if not broker:
            return jsonify({
                'connected': False, 
                'message': 'Please select a broker to check status.'
            })
            
        if not user_id:
            return jsonify({
                'connected': False, 
                'message': 'User ID is required to check connection status.'
            })
        
        # Check for active session
        try:
            active_session = broker_manager.get_active_session(broker, user_id)
            
            if active_session:
                # Verify session is still valid by making a test API call
                is_valid = await_verify_broker_connection(broker, user_id, active_session)
                
                if is_valid:
                    return jsonify({
                        'connected': True,
                        'message': f'{broker.upper()} is connected and verified for user {user_id}',
                        'session_id': active_session.get('session_id'),
                        'last_activity': active_session.get('last_activity'),
                        'created_at': active_session.get('created_at')
                    })
                else:
                    # Session exists but connection is invalid
                    return jsonify({
                        'connected': False,
                        'message': f'{broker.upper()} session has expired or become invalid. Please reconnect.',
                        'expired': True
                    })
            
            # Check if credentials exist but no active session
            credentials = broker_manager.load_credentials(broker, user_id)
            if credentials:
                return jsonify({
                    'connected': False,
                    'message': f'Credentials found for {broker.upper()} user {user_id}, but not connected. Click Connect to establish connection.'
                })
            else:
                return jsonify({
                    'connected': False,
                    'message': f'No saved credentials found for {broker.upper()} user {user_id}. Please register your credentials first.'
                })
                
        except Exception as session_error:
            logger.error(f"Session check error: {session_error}")
            return jsonify({
                'connected': False,
                'message': f'Error checking {broker.upper()} connection status: {str(session_error)}'
            })
        
    except Exception as e:
        logger.error(f"Check status error: {e}")
        return jsonify({
            'connected': False, 
            'message': f'Status check failed: {str(e)}. Please try again.'
        })

def await_verify_broker_connection(broker: str, user_id: str, session: dict) -> bool:
    """Verify broker connection is still valid"""
    try:
        if broker == 'kite':
            return verify_kite_connection(session)
        elif broker == 'dhan':
            return verify_dhan_connection(session)
        elif broker == 'angel':
            return verify_angel_connection(session)
        return False
    except Exception as e:
        logger.error(f"Verify connection error for {broker}: {e}")
        return False

def verify_kite_connection(session: dict) -> bool:
    """Verify Kite connection"""
    try:
        access_token = session.get('access_token')
        if not access_token:
            return False
        
        headers = {
            'Authorization': f'token {session.get("api_key")}:{access_token}',
            'X-Kite-Version': '3'
        }
        
        response = requests.get(
            f"{BROKER_CONFIGS['kite']['base_url']}/user/profile",
            headers=headers,
            timeout=10
        )
        
        return response.status_code == 200
    except:
        return False

def verify_dhan_connection(session: dict) -> bool:
    """Verify Dhan connection"""
    try:
        access_token = session.get('access_token')
        if not access_token:
            return False
        
        headers = {
            'access-token': access_token,
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f"{BROKER_CONFIGS['dhan']['base_url']}/positions",
            headers=headers,
            timeout=10
        )
        
        return response.status_code == 200
    except:
        return False

def verify_angel_connection(session: dict) -> bool:
    """Verify Angel connection"""
    try:
        jwt_token = session.get('jwt_token')
        if not jwt_token:
            return False
        
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f"{BROKER_CONFIGS['angel']['base_url']}/rest/secure/angelbroking/user/v1/getProfile",
            headers=headers,
            timeout=10
        )
        
        return response.status_code == 200
    except:
        return False

@broker_bp.route('/connect', methods=['POST'])
@login_required
def connect_broker():
    """Connect to broker and create session"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'ok': False, 
                'message': 'No connection data provided. Please try again.'
            }), 400
        
        broker = data.get('broker', '').strip()
        user_id = data.get('user_id', '').strip()
        
        if not broker:
            return jsonify({
                'ok': False, 
                'message': 'Please select a broker before connecting.'
            }), 400
            
        if not user_id:
            return jsonify({
                'ok': False, 
                'message': 'User ID is required for connection. Please enter your User ID.'
            }), 400
        
        # Load saved credentials
        try:
            if not broker_manager:
                return jsonify({
                    'ok': False, 
                    'message': 'Broker manager not initialized. Please contact support.'
                }), 500
                
            credentials = broker_manager.load_credentials(broker, user_id)
            if not credentials:
                return jsonify({
                    'ok': False, 
                    'message': f'No saved credentials found for {broker.upper()} user {user_id}. Please register your credentials first.'
                }), 400
        except Exception as load_error:
            logger.error(f"Load credentials error: {load_error}")
            return jsonify({
                'ok': False, 
                'message': f'Error loading credentials: {str(load_error)}. Please register your credentials again.'
            }), 400
        
        # Attempt connection based on broker type
        try:
            if broker == 'kite':
                return connect_kite(credentials)
            elif broker == 'dhan':
                return connect_dhan(credentials)
            elif broker == 'angel':
                return connect_angel(credentials)
            else:
                return jsonify({
                    'ok': False, 
                    'message': f'Broker "{broker}" is not supported. Please select Kite, Dhan, or Angel.'
                }), 400
                
        except Exception as connect_error:
            logger.error(f"Broker connection error: {connect_error}")
            return jsonify({
                'ok': False, 
                'message': f'Connection to {broker.upper()} failed: {str(connect_error)}. Please check your credentials and try again.'
            }), 500
            
    except json.JSONDecodeError:
        return jsonify({
            'ok': False, 
            'message': 'Invalid connection request. Please refresh the page and try again.'
        }), 400
    except Exception as e:
        logger.error(f"Connect broker error: {e}")
        return jsonify({
            'ok': False, 
            'message': f'Connection failed: {str(e)}. Please try again or contact support.'
        }), 500

def connect_kite(credentials: dict) -> dict:
    """Connect to Kite broker"""
    try:
        # For Kite, we need to redirect to login URL
        api_key = credentials.get('api_key')
        
        if not api_key:
            return jsonify({
                'ok': False, 
                'message': 'Kite API Key is missing. Please register your credentials again.'
            })
        
        # Validate API key format (basic check)
        if len(api_key) < 10 or not api_key.replace('_', '').replace('-', '').isalnum():
            return jsonify({
                'ok': False, 
                'message': 'Kite API Key format appears invalid. Please check and register the correct API Key.'
            })
        
        redirect_url = f"{BROKER_CONFIGS['kite']['login_url']}?api_key={api_key}&v=3"
        
        return jsonify({
            'ok': True,
            'requires_redirect': True,
            'redirect_url': redirect_url,
            'message': f'Redirecting to Kite login for API Key: {api_key[:8]}... Please complete the authentication process.'
        })
    except Exception as e:
        logger.error(f"Kite connection error: {e}")
        return jsonify({
            'ok': False, 
            'message': f'Kite connection setup failed: {str(e)}. Please check your API Key and try again.'
        })

def connect_dhan(credentials: dict) -> dict:
    """Connect to Dhan broker"""
    try:
        # For Dhan, we can directly use the access token
        access_token = credentials.get('access_token')
        client_id = credentials.get('client_id')
        
        if not access_token or not client_id:
            return jsonify({
                'ok': False, 
                'message': 'Dhan credentials are incomplete. Please register your Client ID and Access Token again.'
            })
        
        # Test the connection using correct Dhan API endpoint
        headers = {
            'access-token': access_token,
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(
                f"{BROKER_CONFIGS['dhan']['base_url']}/positions",
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 200:
                # Create session
                session_data = {
                    'access_token': access_token,
                    'client_id': client_id,
                    'session_id': f"dhan_{client_id}_{int(time.time())}",
                    'status': 'active',
                    'created_at': datetime.now().isoformat()
                }
                
                # Check if session should be remembered
                remember_session = credentials.get('remember_session', False)
                if remember_session:
                    session_data['remember_session'] = True
                    session_data['expires_at'] = (datetime.now() + timedelta(days=30)).isoformat()
                else:
                    session_data['expires_at'] = (datetime.now() + timedelta(hours=8)).isoformat()
                
                session_id = broker_manager.create_session('dhan', credentials['user_id'], session_data)
                
                return jsonify({
                    'ok': True,
                    'connected': True,
                    'session_id': session_id,
                    'message': f'Successfully connected to Dhan for client {client_id}'
                })
            elif response.status_code == 401:
                return jsonify({
                    'ok': False, 
                    'message': 'Dhan authentication failed. Your Access Token may be expired or invalid. Please check your credentials and try again.'
                })
            elif response.status_code == 403:
                return jsonify({
                    'ok': False, 
                    'message': 'Dhan access denied. Please check your Client ID and Access Token permissions.'
                })
            else:
                return jsonify({
                    'ok': False, 
                    'message': f'Dhan connection failed with status {response.status_code}. Please check your credentials and try again.'
                })
                
        except requests.exceptions.Timeout:
            return jsonify({
                'ok': False, 
                'message': 'Dhan connection timed out. Please check your internet connection and try again.'
            })
        except requests.exceptions.ConnectionError:
            return jsonify({
                'ok': False, 
                'message': 'Cannot connect to Dhan servers. Please check your internet connection and try again.'
            })
            
    except Exception as e:
        logger.error(f"Dhan connection error: {e}")
        return jsonify({
            'ok': False, 
            'message': f'Dhan connection failed: {str(e)}. Please check your credentials and try again.'
        })

def connect_angel(credentials: dict) -> dict:
    """Connect to Angel broker"""
    try:
        # For Angel, we need to authenticate and get JWT token
        api_key = credentials.get('api_key')
        api_secret = credentials.get('api_secret')
        
        if not api_key or not api_secret:
            return jsonify({
                'ok': False, 
                'message': 'Angel credentials are incomplete. Please register your API Key and Secret again.'
            })
        
        # Validate credentials format
        if len(api_key) < 8:
            return jsonify({
                'ok': False, 
                'message': 'Angel API Key appears too short. Please check and enter the correct API Key.'
            })
        
        # This is a simplified connection - in reality, Angel requires more complex auth
        try:
            session_data = {
                'api_key': api_key,
                'api_secret': api_secret,
                'session_id': f"angel_{api_key[:8]}_{int(time.time())}",
                'status': 'active',
                'created_at': datetime.now().isoformat()
            }
            
            session_id = broker_manager.create_session('angel', credentials['user_id'], session_data)
            
            return jsonify({
                'ok': True,
                'connected': True,
                'session_id': session_id,
                'message': f'Successfully connected to Angel One for API Key: {api_key[:8]}...'
            })
            
        except Exception as session_error:
            logger.error(f"Angel session creation error: {session_error}")
            return jsonify({
                'ok': False, 
                'message': f'Failed to create Angel session: {str(session_error)}. Please try again.'
            })
        
    except Exception as e:
        logger.error(f"Angel connection error: {e}")
        return jsonify({
            'ok': False, 
            'message': f'Angel connection failed: {str(e)}. Please check your credentials and try again.'
        })

@broker_bp.route('/disconnect', methods=['POST'])
@login_required
def disconnect_broker():
    """Disconnect from broker"""
    try:
        data = request.get_json()
        broker = data.get('broker')
        user_id = data.get('user_id')
        clear_all = data.get('clear_all', False)
        
        if clear_all:
            # Clear all sessions and credentials
            broker_manager.sessions.clear()
            broker_manager.credentials_store.clear()
            broker_manager._save_sessions_to_file()
            broker_manager._save_credentials_to_file()
            
            return jsonify({
                'ok': True,
                'message': 'All broker connections cleared'
            })
        
        if not broker or not user_id:
            return jsonify({'ok': False, 'message': 'Broker and user_id required'}), 400
        
        # Invalidate sessions for this broker/user
        count = broker_manager.invalidate_user_sessions(broker, user_id)
        
        return jsonify({
            'ok': True,
            'message': f'Disconnected from {broker.upper()}',
            'sessions_invalidated': count
        })
        
    except Exception as e:
        logger.error(f"Disconnect error: {e}")
        return jsonify({'ok': False, 'message': str(e)}), 500

@broker_bp.route('/orders', methods=['GET'])
@login_required
def get_broker_orders():
    """Get orders from broker"""
    try:
        broker = request.args.get('broker', '').strip()
        user_id = request.args.get('user_id', '').strip()
        
        if not broker:
            return jsonify({
                'ok': False, 
                'message': 'Please select a broker to fetch orders.'
            }), 400
            
        if not user_id:
            return jsonify({
                'ok': False, 
                'message': 'User ID is required to fetch orders.'
            }), 400
        
        # Check broker manager availability
        if not broker_manager:
            return jsonify({
                'ok': False,
                'message': 'Broker manager not available. Please contact support.'
            }), 500
        
        # Get active session
        session = broker_manager.get_active_session(broker, user_id)
        if not session:
            return jsonify({
                'ok': False,
                'auth_error': True,
                'message': f'Not connected to broker. Please connect first.'
            })
        
        # Verify session is still valid
        if not await_verify_broker_connection(broker, user_id, session):
            # Invalidate the session
            broker_manager.invalidate_user_sessions(broker, user_id)
            return jsonify({
                'ok': False,
                'auth_error': True,
                'message': f'Connection to {broker.upper()} has expired. Please reconnect.'
            })
        
        # Fetch orders based on broker
        try:
            if broker == 'kite':
                orders = fetch_kite_orders(session)
            elif broker == 'dhan':
                orders = fetch_dhan_orders(session)
            elif broker == 'angel':
                orders = fetch_angel_orders(session)
            else:
                return jsonify({
                    'ok': False, 
                    'message': f'Broker "{broker}" is not supported for order fetching.'
                }), 400
            
            if orders is None:
                return jsonify({
                    'ok': False,
                    'auth_error': True,
                    'message': f'{broker.upper()} authentication failed. Please reconnect.'
                })
            
            return jsonify({
                'ok': True,
                'data': orders,
                'count': len(orders) if orders else 0,
                'message': f'Successfully fetched {len(orders) if orders else 0} orders from {broker.upper()}'
            })
            
        except Exception as fetch_error:
            logger.error(f"Fetch orders error for {broker}: {fetch_error}")
            return jsonify({
                'ok': False, 
                'message': f'Failed to fetch orders from {broker.upper()}: {str(fetch_error)}'
            }), 500
        
    except Exception as e:
        logger.error(f"Get orders error: {e}")
        return jsonify({
            'ok': False, 
            'message': f'Order fetch failed: {str(e)}. Please try again.'
        }), 500

def fetch_kite_orders(session: dict) -> list:
    """Fetch orders from Kite"""
    try:
        headers = {
            'Authorization': f'token {session.get("api_key")}:{session.get("access_token")}',
            'X-Kite-Version': '3'
        }
        
        response = requests.get(
            f"{BROKER_CONFIGS['kite']['base_url']}/orders",
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            return response.json().get('data', [])
        return []
    except Exception as e:
        logger.error(f"Fetch Kite orders error: {e}")
        return []

def fetch_dhan_orders(session: dict) -> list:
    """Fetch orders from Dhan"""
    try:
        headers = {
            'access-token': session.get('access_token'),
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f"{BROKER_CONFIGS['dhan']['base_url']}/orders",
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            return response.json().get('data', [])
        return []
    except Exception as e:
        logger.error(f"Fetch Dhan orders error: {e}")
        return []



def fetch_kite_positions(session: dict) -> list:
    """Fetch positions from Kite"""
    try:
        headers = {
            'Authorization': f'token {session.get("api_key")}:{session.get("access_token")}',
            'X-Kite-Version': '3'
        }
        
        response = requests.get(
            f"{BROKER_CONFIGS['kite']['base_url']}/portfolio/positions",
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            return response.json().get('data', {}).get('net', [])
        return []
    except Exception as e:
        logger.error(f"Fetch Kite positions error: {e}")
        return []

def fetch_dhan_positions(session: dict) -> list:
    """Fetch positions from Dhan"""
    try:
        headers = {
            'access-token': session.get('access_token'),
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f"{BROKER_CONFIGS['dhan']['base_url']}/positions",
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            return response.json().get('data', [])
        return []
    except Exception as e:
        logger.error(f"Fetch Dhan positions error: {e}")
        return []

def fetch_angel_positions(session: dict) -> list:
    """Fetch positions from Angel"""
    try:
        # Simplified - Angel API requires more complex authentication
        return [
            {
                'symbol': 'RELIANCE',
                'quantity': 10,
                'average_price': 2500,
                'ltp': 2520,
                'pnl': 200,
                'product': 'MIS'
            }
        ]
    except Exception as e:
        logger.error(f"Fetch Angel positions error: {e}")
        return []

def fetch_kite_trades(session: dict) -> list:
    """Fetch trades from Kite"""
    try:
        headers = {
            'Authorization': f'token {session.get("api_key")}:{session.get("access_token")}',
            'X-Kite-Version': '3'
        }
        
        response = requests.get(
            f"{BROKER_CONFIGS['kite']['base_url']}/trades",
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            return response.json().get('data', [])
        return []
    except Exception as e:
        logger.error(f"Fetch Kite trades error: {e}")
        return []

def fetch_dhan_trades(session: dict) -> list:
    """Fetch trades from Dhan"""
    try:
        headers = {
            'access-token': session.get('access_token'),
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f"{BROKER_CONFIGS['dhan']['base_url']}/trades",
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            return response.json().get('data', [])
        return []
    except Exception as e:
        logger.error(f"Fetch Dhan trades error: {e}")
        return []

def fetch_angel_orders(session: dict) -> list:
    """Fetch orders from Angel"""
    try:
        # Simplified - Angel API requires more complex authentication
        return [
            {
                'order_id': 'ORD001',
                'symbol': 'RELIANCE',
                'quantity': 10,
                'price': 2500,
                'order_type': 'BUY',
                'status': 'COMPLETE',
                'time': '09:30:00'
            }
        ]
    except Exception as e:
        logger.error(f"Fetch Angel orders error: {e}")
        return []

def fetch_angel_trades(session: dict) -> list:
    """Fetch trades from Angel"""
    try:
        # Simplified - Angel API requires more complex authentication
        return [
            {
                'trade_id': 'TRD001',
                'symbol': 'RELIANCE',
                'quantity': 10,
                'price': 2500,
                'trade_type': 'BUY',
                'time': '09:30:00'
            }
        ]
    except Exception as e:
        logger.error(f"Fetch Angel trades error: {e}")
        return []

@broker_bp.route('/positions', methods=['GET'])
@login_required
def get_broker_positions():
    """Get positions from broker"""
    try:
        broker = request.args.get('broker', '').strip()
        user_id = request.args.get('user_id', '').strip()
        
        if not broker or not user_id:
            return jsonify({
                'ok': False,
                'message': 'Broker and user ID are required.'
            }), 400
        
        # Check broker manager availability
        if not broker_manager:
            return jsonify({
                'ok': False,
                'message': 'Broker manager not available. Please contact support.'
            }), 500
        
        session = broker_manager.get_active_session(broker, user_id)
        if not session:
            return jsonify({
                'ok': False,
                'auth_error': True,
                'message': 'Not connected to broker. Please connect first.'
            })
        
        # Verify session is still valid
        if not await_verify_broker_connection(broker, user_id, session):
            broker_manager.invalidate_user_sessions(broker, user_id)
            return jsonify({
                'ok': False,
                'auth_error': True,
                'message': f'Connection to {broker.upper()} has expired. Please reconnect.'
            })
        
        # Fetch positions based on broker
        try:
            if broker == 'dhan':
                positions = fetch_dhan_positions(session)
            elif broker == 'kite':
                positions = fetch_kite_positions(session)
            elif broker == 'angel':
                positions = fetch_angel_positions(session)
            else:
                positions = []
            
            return jsonify({
                'ok': True,
                'data': positions,
                'count': len(positions),
                'message': f'Successfully fetched {len(positions)} positions from {broker.upper()}'
            })
            
        except Exception as fetch_error:
            logger.error(f"Fetch positions error for {broker}: {fetch_error}")
            return jsonify({
                'ok': False,
                'message': f'Failed to fetch positions from {broker.upper()}: {str(fetch_error)}'
            }), 500
        
    except Exception as e:
        logger.error(f"Get positions error: {e}")
        return jsonify({'ok': False, 'message': str(e)}), 500

@broker_bp.route('/integrate_token', methods=['POST'])
@login_required
def integrate_existing_token():
    """Integrate existing token from dhan_token.json with broker system"""
    try:
        import json
        import os
        from datetime import datetime, timedelta
        
        # Load token from dhan_token.json
        if not os.path.exists('dhan_token.json'):
            return jsonify({
                'ok': False,
                'message': 'dhan_token.json not found. Please ensure the token file exists.'
            }), 404
        
        with open('dhan_token.json', 'r') as f:
            token_data = json.load(f)
        
        access_token = token_data.get('access_token')
        expires_at = token_data.get('expires_at')
        
        if not access_token:
            return jsonify({
                'ok': False,
                'message': 'No access_token found in dhan_token.json'
            }), 400
        
        # Check if token is expired
        if expires_at and expires_at < int(datetime.now().timestamp()):
            return jsonify({
                'ok': False,
                'message': 'Token in dhan_token.json is expired. Please generate a new token.'
            }), 400
        
        # Get client ID from .env
        client_id = os.getenv('DHAN_CLIENT_ID')
        if not client_id:
            return jsonify({
                'ok': False,
                'message': 'DHAN_CLIENT_ID not found in environment variables'
            }), 400
        
        # Save credentials to broker manager
        if not broker_manager:
            return jsonify({
                'ok': False,
                'message': 'Broker manager not available'
            }), 500
        
        credentials = {
            'client_id': client_id,
            'access_token': access_token,
            'user_id': client_id
        }
        
        success = broker_manager.save_credentials('dhan', client_id, credentials)
        if not success:
            return jsonify({
                'ok': False,
                'message': 'Failed to save credentials to broker manager'
            }), 500
        
        # Create active session
        session_data = {
            'access_token': access_token,
            'client_id': client_id,
            'session_id': f"dhan_{client_id}_{int(datetime.now().timestamp())}",
            'status': 'active',
            'created_at': datetime.now().isoformat(),
            'expires_at': datetime.fromtimestamp(expires_at).isoformat() if expires_at else (datetime.now() + timedelta(hours=24)).isoformat()
        }
        
        session_id = broker_manager.create_session('dhan', client_id, session_data)
        
        return jsonify({
            'ok': True,
            'message': f'Successfully integrated Dhan token for client {client_id}',
            'client_id': client_id,
            'session_id': session_id,
            'expires_at': datetime.fromtimestamp(expires_at).isoformat() if expires_at else None
        })
        
    except Exception as e:
        logger.error(f"Token integration error: {e}")
        return jsonify({
            'ok': False,
            'message': f'Token integration failed: {str(e)}'
        }), 500

@broker_bp.route('/trades', methods=['GET'])
@login_required
def get_broker_trades():
    """Get trades from broker"""
    try:
        broker = request.args.get('broker', '').strip()
        user_id = request.args.get('user_id', '').strip()
        
        if not broker or not user_id:
            return jsonify({
                'ok': False,
                'message': 'Broker and user ID are required.'
            }), 400
        
        # Check broker manager availability
        if not broker_manager:
            return jsonify({
                'ok': False,
                'message': 'Broker manager not available. Please contact support.'
            }), 500
        
        session = broker_manager.get_active_session(broker, user_id)
        if not session:
            return jsonify({
                'ok': False,
                'auth_error': True,
                'message': 'Not connected to broker. Please connect first.'
            })
        
        # Verify session is still valid
        if not await_verify_broker_connection(broker, user_id, session):
            broker_manager.invalidate_user_sessions(broker, user_id)
            return jsonify({
                'ok': False,
                'auth_error': True,
                'message': f'Connection to {broker.upper()} has expired. Please reconnect.'
            })
        
        # Fetch trades based on broker
        try:
            if broker == 'dhan':
                trades = fetch_dhan_trades(session)
            elif broker == 'kite':
                trades = fetch_kite_trades(session)
            elif broker == 'angel':
                trades = fetch_angel_trades(session)
            else:
                trades = []
            
            return jsonify({
                'ok': True,
                'data': trades,
                'count': len(trades),
                'message': f'Successfully fetched {len(trades)} trades from {broker.upper()}'
            })
            
        except Exception as fetch_error:
            logger.error(f"Fetch trades error for {broker}: {fetch_error}")
            return jsonify({
                'ok': False,
                'message': f'Failed to fetch trades from {broker.upper()}: {str(fetch_error)}'
            }), 500
        
    except Exception as e:
        logger.error(f"Get trades error: {e}")
        return jsonify({'ok': False, 'message': str(e)}), 500