import os
import json
import requests
from flask import Flask, request, redirect, session, jsonify, render_template, Blueprint, current_app
from dotenv import load_dotenv
from datetime import datetime
import pyotp
# KiteConnect SDK
from kiteconnect import KiteConnect
# Database imports
from broker_session_model import init_broker_session_model, save_session, get_active_session, cleanup_expired

# DhanHQ SDK (handles both old and new versions)
try:
    from dhanhq import DhanHQ
    def make_dhan_client(client_id: str, access_token: str):
        return DhanHQ(client_id=client_id, access_token=access_token)
except ImportError:
    from dhanhq import dhanhq as _dhan_factory
    def make_dhan_client(client_id: str, access_token: str):
        return _dhan_factory(client_id, access_token)

# Angel One SmartAPI SDK
from SmartApi import SmartConnect

load_dotenv()

# Blueprint for multi-broker routes
multi_broker_bp = Blueprint('multi_broker', __name__, url_prefix='/api/multi_broker')

# Additional blueprint for legacy callback URLs
legacy_broker_bp = Blueprint('legacy_broker', __name__)

BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:5000")

# In-memory stores for app credentials (temporary)
USER_APPS = {
    "kite": {},
    "dhan": {},
    "angel": {}
}

# Database-backed session management
def get_user_session(broker, user_id, user_email=None):
    """Get session from database"""
    try:
        if not user_email:
            user_email = user_id
        session_row = get_active_session(user_email, broker, user_id)
        return json.loads(session_row.session_data) if session_row else None
    except Exception:
        return None

def save_user_session(broker, user_id, session_data, user_email=None, remember=True):
    """Save session to database"""
    try:
        if not user_email:
            user_email = user_id
        save_session(user_email, broker, user_id, session_data, remember)
        return True
    except Exception:
        return False

# Legacy compatibility - populate from database
USER_SESSIONS = {
    "kite": {},
    "dhan": {},
    "angel": {}
}

def sync_sessions_from_db():
    """Sync active sessions from database to memory for compatibility"""
    try:
        from flask import current_app
        db = current_app.extensions['sqlalchemy']
        BrokerSession = init_broker_session_model(db)
        
        active_sessions = BrokerSession.query.filter(BrokerSession.expires_at > datetime.utcnow()).all()
        for session_row in active_sessions:
            try:
                USER_SESSIONS[session_row.broker][session_row.user_id] = json.loads(session_row.session_data)
            except (json.JSONDecodeError, KeyError):
                continue
    except Exception:
        pass

# Add session validation endpoints
@multi_broker_bp.route('/validate_session/<broker>/<user_id>')
def validate_session(broker, user_id):
    """Validate if a session is still active"""
    if broker not in ['kite', 'dhan', 'angel'] or not user_id:
        return jsonify({'error': 'Invalid parameters'}), 400
    
    sess = get_user_session(broker, user_id)
    if sess:
        return jsonify({
            'connected': True,
            'broker': broker,
            'user_id': user_id,
            'session_data': sess
        })
    else:
        return jsonify({
            'connected': False,
            'broker': broker,
            'user_id': user_id
        })

# Add disconnect endpoint
@multi_broker_bp.route('/disconnect/<broker>/<user_id>', methods=['POST', 'GET'])
def disconnect_broker_session(broker, user_id):
    """Disconnect from a broker"""
    try:
        # Remove from database
        from flask import current_app
        db = current_app.extensions['sqlalchemy']
        BrokerSession = init_broker_session_model(db)
        
        session_row = BrokerSession.query.filter_by(broker=broker, user_id=user_id).first()
        if session_row:
            db.session.delete(session_row)
            db.session.commit()
        
        # Remove from memory
        if broker in USER_SESSIONS and user_id in USER_SESSIONS[broker]:
            del USER_SESSIONS[broker][user_id]
        
        if request.method == 'GET':
            return redirect('/saved_sessions')
        return jsonify({"ok": True, "message": f"Disconnected from {broker.upper()}"})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)})

# Saved sessions page
@multi_broker_bp.route('/saved_sessions')
def saved_sessions():
    """Display saved broker sessions"""
    try:
        from flask import current_app
        db = current_app.extensions['sqlalchemy']
        BrokerSession = init_broker_session_model(db)
        
        sessions = BrokerSession.query.all()
        session_data = []
        
        for sess in sessions:
            data = json.loads(sess.session_data)
            session_info = {
                'broker': sess.broker,
                'user_id': sess.user_id,
                'client_code': data.get('client_code', 'N/A'),
                'updated_at': sess.updated_at,
                'expires_at': sess.expires_at,
                'is_active': sess.expires_at > datetime.utcnow()
            }
            session_data.append(session_info)
        
        return render_template('saved_sessions.html', sessions=session_data)
    except Exception as e:
        return f"Error loading sessions: {str(e)}", 500

# Quick login for saved sessions
@multi_broker_bp.route('/<broker>/quick_login')
def quick_login(broker):
    """Quick login using saved credentials"""
    user_id = request.args.get('user_id')
    if not user_id:
        return "User ID required", 400
    
    try:
        sess = get_user_session(broker, user_id)
        if sess and sess.get('saved_credentials'):
            creds = sess['saved_credentials']
            
            # Register credentials first
            USER_APPS[broker][user_id] = {
                "api_key": creds.get('api_key'),
                "api_secret": creds.get('api_secret'),
                "client_id": creds.get('client_id'),
                "access_token": creds.get('access_token'),
                "totp_secret": creds.get('totp_secret'),
                "client_code": creds.get('client_code'),
                "password": creds.get('password')
            }
            
            if broker == 'angel':
                # Auto-generate TOTP and login
                if creds.get('totp_secret'):
                    totp = pyotp.TOTP(creds['totp_secret'].replace(' ', '').upper()).now()
                    
                    smart = SmartConnect(api_key=creds['api_key'])
                    data = smart.generateSession(
                        clientCode=creds['client_code'],
                        password=creds['password'],
                        totp=totp
                    )
                    
                    if not data.get('errorcode'):
                        # Update session with new tokens
                        jwt_token = data['data'].get('jwtToken')
                        sess['access_token'] = jwt_token
                        sess['refresh_token'] = data['data'].get('refreshToken')
                        sess['feed_token'] = data['data'].get('feedToken')
                        
                        save_user_session(broker, user_id, sess, user_id, remember=True)
                        memory_session = sess.copy()
                        memory_session['smart_api'] = smart
                        USER_SESSIONS[broker][user_id] = memory_session
                        
                        return redirect('/saved_sessions')
                    else:
                        return f"Angel login failed: {data.get('message')}", 400
                else:
                    return redirect(f'/api/multi_broker/{broker}/login?user_id={user_id}')
            
            elif broker == 'kite':
                # Redirect to Kite OAuth flow
                return redirect(f'/api/multi_broker/{broker}/login?user_id={user_id}')
            
            elif broker == 'dhan':
                # Direct connection for Dhan
                return redirect(f'/api/multi_broker/{broker}/login?user_id={user_id}')
            
            return f"Quick login not supported for {broker} yet", 400
        else:
            return redirect(f'/api/multi_broker/{broker}/login?user_id={user_id}')
    except Exception as e:
        return f"Quick login failed: {str(e)}", 400

# ===================== KITE HELPERS =====================
def get_kite_for_user(user_id, access_token=None):
    creds = USER_APPS["kite"].get(user_id)
    if not creds:
        raise ValueError("No app credentials for this user")
    kite = KiteConnect(api_key=creds["api_key"])
    if access_token:
        kite.set_access_token(access_token)
    return kite

# ===================== DHAN HELPERS =====================
DHAN_AUTH_BASE = "https://auth.dhan.co"

def _dhan_headers(partner_id, partner_secret):
    return {
        "partner_id": partner_id,
        "partner_secret": partner_secret,
        "Content-Type": "application/json"
    }

def _dhan_generate_consent(partner_id, partner_secret):
    try:
        url = f"{DHAN_AUTH_BASE}/partner/generate-consent"
        r = requests.post(url, headers=_dhan_headers(partner_id, partner_secret), json={}, timeout=30)
        r.raise_for_status()
        data = r.json() if r.headers.get("content-type","").startswith("application/json") else {}
        consent_id = data.get("consentId") or data.get("consent_id")
        if not consent_id:
            raise RuntimeError(f"generate-consent missing consentId: {data}")
        return consent_id
    except requests.RequestException as e:
        raise RuntimeError(f"Dhan API error: {str(e)}")

def _dhan_consume_consent(partner_id, partner_secret, token_id):
    try:
        url = f"{DHAN_AUTH_BASE}/partner/consume-consent"
        r = requests.get(url, headers=_dhan_headers(partner_id, partner_secret), params={"tokenId": token_id}, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Dhan API error: {str(e)}")

def _dhan_client_from_session(user_id):
    sess = get_user_session("dhan", user_id) or USER_SESSIONS["dhan"].get(user_id)
    if not sess:
        return None, jsonify({"ok": False, "message": "Not connected"}), 401
    client_id = sess.get("dhan_client_id") or user_id
    access_token = sess.get("access_token")
    if not access_token:
        return None, jsonify({"ok": False, "message": "Missing Dhan access token"}), 500
    return make_dhan_client(client_id, access_token), None, None

# ===================== ANGEL ONE SESSION MANAGER =====================
def _angel_login_with_totp(user_id: str):
    """Fresh login using saved creds + TOTP secret. Returns SmartConnect + tokens."""
    creds = USER_APPS["angel"].get(user_id) or {}
    api_key = creds.get("api_key")
    client_code = creds.get("client_code")
    password = creds.get("password")
    secret_raw = (creds.get("totp_secret") or "")
    if not all([api_key, client_code, password, secret_raw]):
        raise RuntimeError("Angel creds incomplete (need api_key, client_code, password, totp_secret)")

    secret = secret_raw.replace(" ", "").upper()
    totp = pyotp.TOTP(secret).now()

    smart = SmartConnect(api_key=api_key)
    data = smart.generateSession(clientCode=client_code, password=password, totp=totp)

    if data.get("errorcode"):
        raise RuntimeError(f"Angel login failed: {data.get('message')}")

    # v2 payload layout -> tokens live under data["data"]
    d = data.get("data") or {}
    jwt_token = d.get("jwtToken")
    refresh_token = d.get("refreshToken")
    feed_token = d.get("feedToken")

    if not jwt_token:
        raise RuntimeError("Angel login ok but jwtToken missing")

    # persist to DB (without smart instance)
    session_data = {
        "access_token": jwt_token,
        "refresh_token": refresh_token,
        "feed_token": feed_token,
        "angel_client_id": api_key,
        "client_code": client_code,
    }
    save_user_session("angel", user_id, session_data, user_id, remember=True)

    # keep SmartConnect only in memory
    memory_session = session_data.copy()
    memory_session["smart_api"] = smart
    USER_SESSIONS["angel"][user_id] = memory_session

    return smart, memory_session

def _ensure_angel_smart(user_id: str):
    """Return a live SmartConnect. Re-login if missing/expired."""
    # 1) have in-memory client?
    sess = USER_SESSIONS["angel"].get(user_id)
    if sess and "smart_api" in sess:
        return sess["smart_api"], sess

    # 2) try DB session; if present, prefer FULL relogin (don't trust setAccessToken)
    return _angel_login_with_totp(user_id)

def _handle_angel_call(user_id: str, fn_name: str):
    """
    Call SmartAPI fn with auto-relogin on AG8001.
    fn_name in {"orderBook","position","tradeBook"}
    """
    smart, sess = _ensure_angel_smart(user_id)
    try:
        fn = getattr(smart, fn_name)
        return fn()
    except Exception as e:
        msg = str(e)
        # If token invalid, do a fresh login and retry once
        if "AG8001" in msg or "Invalid Token" in msg:
            smart, sess = _angel_login_with_totp(user_id)
            fn = getattr(smart, fn_name)
            return fn()
        raise

# ===================== REGISTRATION =====================
@multi_broker_bp.route('/register_app/<broker>', methods=["POST"])
def register_app_broker(broker):
    if broker not in USER_APPS:
        return jsonify({"ok": False, "message": "unknown broker"}), 400
    
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"ok": False, "message": "No data provided"}), 400
            
        user_id = data.get("user_id", "").strip()
        if not user_id:
            return jsonify({"ok": False, "message": "user_id required"}), 400

        # Validate required fields per broker
        if broker == 'kite':
            if not data.get("api_key") or not data.get("api_secret"):
                return jsonify({"ok": False, "message": "api_key and api_secret required for Kite"}), 400
        elif broker == 'dhan':
            if not data.get("client_id") or not data.get("access_token"):
                return jsonify({"ok": False, "message": "client_id and access_token required for Dhan"}), 400
        elif broker == 'angel':
            if not data.get("api_key") or not data.get("api_secret"):
                return jsonify({"ok": False, "message": "api_key and api_secret required for Angel"}), 400

        USER_APPS[broker][user_id] = {
            "api_key": data.get("api_key", ""),
            "api_secret": data.get("api_secret", ""),
            "client_id": data.get("client_id", ""),
            "access_token": data.get("access_token", ""),
            "totp_secret": data.get("totp_secret", ""),
            "client_code": data.get("client_code", ""),
            "password": data.get("password", "")
        }
        return jsonify({"ok": True, "message": f"Registered {user_id} for {broker}"}), 200
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500

# Backward-compatible (Kite single route)
@multi_broker_bp.route('/register_app', methods=["POST"])
def register_app_single():
    data = request.get_json(force=True)
    user_id = data.get("user_id", "").strip()
    api_key = data.get("api_key")
    api_secret = data.get("api_secret")
    if not all([user_id, api_key, api_secret]):
        return jsonify({"ok": False, "message": "user_id, api_key, api_secret required"}), 400
    USER_APPS["kite"][user_id] = {"api_key": api_key, "api_secret": api_secret}
    return jsonify({"ok": True, "message": f"Registered {user_id} for kite"}), 200

# ===================== KITE LOGIN FLOW =====================
@multi_broker_bp.route('/kite/login')
def kite_login():
    user_id = request.args.get("user_id", "").strip()
    if not user_id or user_id not in USER_APPS["kite"]:
        return jsonify({"ok": False, "message": "Unknown user_id or app not registered"}), 400
    session["oauth_user_id"] = user_id
    kite = get_kite_for_user(user_id)
    login_url = kite.login_url()
    sep = "&" if "?" in login_url else "?"
    return redirect(f"{login_url}{sep}state={user_id}")

@multi_broker_bp.route('/kite/callback')
def kite_callback():
    request_token = request.args.get("request_token")
    user_id = session.get("oauth_user_id") or request.args.get("state")
    if not request_token or not user_id:
        return "Missing request_token or session/state lost", 400
    creds = USER_APPS["kite"].get(user_id)
    if not creds:
        return f"No stored credentials for user {user_id}", 400
    kite = KiteConnect(api_key=creds["api_key"])
    try:
        data = kite.generate_session(request_token, api_secret=creds["api_secret"])
        session_data = {
            "access_token": data["access_token"],
            "kite_user_id": data.get("user_id")
        }
        save_user_session("kite", user_id, session_data, user_id, remember=True)
        USER_SESSIONS["kite"][user_id] = session_data
        return redirect('/saved_sessions')
    except Exception as e:
        return f"Auth error: {str(e)}", 400



# ===================== DHAN LOGIN FLOW =====================
@multi_broker_bp.route('/dhan/login')
def dhan_login():
    user_id = request.args.get("user_id", "").strip()
    if not user_id:
        return jsonify({"ok": False, "message": "user_id required"}), 400

    creds = USER_APPS["dhan"].get(user_id)
    if not creds:
        return jsonify({"ok": False, "message": "No Dhan registration found for this user"}), 400

    # Direct token mode
    if creds.get("client_id") and creds.get("access_token"):
        session_data = {
            "access_token": creds["access_token"],
            "dhan_client_id": creds["client_id"],
            "mode": "direct"
        }
        save_user_session("dhan", user_id, session_data, user_id, remember=True)
        USER_SESSIONS["dhan"][user_id] = session_data
        return redirect('/saved_sessions')

    # Partner consent mode
    partner_id = creds.get("api_key")
    partner_secret = creds.get("api_secret")
    if partner_id and partner_secret:
        try:
            consent_id = _dhan_generate_consent(partner_id, partner_secret)
        except Exception as e:
            return jsonify({"ok": False, "message": f"generate-consent failed: {e}"}), 400
        session["dhan_user_id"] = user_id
        session["dhan_consent_id"] = consent_id
        consent_url = f"{DHAN_AUTH_BASE}/consent-login?consentId={consent_id}"
        return redirect(consent_url)

    return jsonify({"ok": False, "message": "Provide either client_id+access_token or partner_id+partner_secret"}), 400

@multi_broker_bp.route('/dhan/callback')
def dhan_callback():
    token_id = request.args.get("tokenid") or request.args.get("tokenId")
    user_id = session.get("dhan_user_id")
    consent_id = session.get("dhan_consent_id")
    if not token_id or not user_id:
        return "Missing tokenId or session lost", 400

    creds = USER_APPS["dhan"].get(user_id)
    if not creds:
        return f"No stored Dhan credentials for user {user_id}", 400

    partner_id = creds.get("api_key")
    partner_secret = creds.get("api_secret")
    if not partner_id or not partner_secret:
        return "Partner credentials missing for consent consume", 400

    try:
        consume = _dhan_consume_consent(partner_id, partner_secret, token_id)
        client_id = consume.get("clientId") or consume.get("client_id") or user_id
        access_token = (
            consume.get("accessToken")
            or consume.get("access_token")
            or consume.get("jwt")
            or consume.get("JWT")
        )
        if not access_token:
            return f"Consume consent ok, but token missing. Payload: {json.dumps(consume)}", 400

        session_data = {
            "access_token": access_token,
            "dhan_client_id": client_id,
            "consent_id": consent_id,
            "mode": "partner"
        }
        save_user_session("dhan", user_id, session_data, user_id, remember=True)
        USER_SESSIONS["dhan"][user_id] = session_data
        return redirect('/saved_sessions')
    except Exception as e:
        return f"Dhan consume-consent error: {str(e)}", 400

# ===================== ANGEL ONE LOGIN FLOW =====================
@multi_broker_bp.route('/angel/login')
def angel_login():
    user_id = request.args.get("user_id", "").strip()
    if not user_id:
        return jsonify({"ok": False, "message": "user_id required"}), 400

    creds = USER_APPS["angel"].get(user_id)
    if not creds or not creds.get("api_key") or not creds.get("api_secret"):
        return jsonify({"ok": False, "message": "Register Angel client_id (api_key) and client_secret (api_secret) first"}), 400

    # Generate TOTP only if real secret exists
    totp_value = ""
    client_code = creds.get("client_code", "")
    password = creds.get("password", "")
    totp_secret = creds.get("totp_secret", "")
    
    if totp_secret:
        try:
            clean_secret = totp_secret.replace(" ", "").upper()
            totp = pyotp.TOTP(clean_secret)
            totp_value = totp.now()
        except Exception as e:
            totp_value = "ERROR"

    return render_template("angel_login.html", 
                         user_id=user_id,
                         totp_value=totp_value,
                         client_code=client_code,
                         password=password,
                         totp_secret=totp_secret)

@multi_broker_bp.route('/angel/login/password', methods=["POST"])
def angel_login_password():
    user_id = request.form.get("user_id", "").strip()
    client_code = request.form.get("client_code", "").strip()
    password = request.form.get("password", "").strip()
    totp = request.form.get("totp", "").strip()
    remember_me = request.form.get("remember_me") == "1"
    
    if not all([user_id, client_code, password, totp]):
        return "All fields are required", 400

    creds = USER_APPS["angel"].get(user_id)
    if not creds:
        return f"No Angel credentials found for user {user_id}", 400

    try:
        # Initialize SmartConnect
        smart = SmartConnect(api_key=creds["api_key"])
        
        # Generate session
        data = smart.generateSession(clientCode=client_code, password=password, totp=totp)
        
        print(f"Angel API response: {data}")
        
        # Check for errors in response
        if data.get('errorcode'):
            error_msg = data.get('message', 'Unknown error')
            # Return to login page with error instead of generic error
            return render_template("angel_login.html", 
                                 user_id=user_id,
                                 client_code=client_code,
                                 error=f"Login failed: {error_msg}",
                                 totp_value=""), 400
            
        # Extract tokens from response data
        jwt_token = data['data'].get('jwtToken')
        refresh_token = data['data'].get('refreshToken')
        feed_token = data['data'].get('feedToken')
        
        if not jwt_token:
            return "Angel login ok but JWT token missing", 400

        session_data = {
            "access_token": jwt_token,
            "refresh_token": refresh_token,
            "feed_token": feed_token,
            "angel_client_id": creds["api_key"],
            "client_code": client_code
        }
        
        # Save credentials if remember me is checked
        if remember_me:
            session_data["saved_credentials"] = {
                "client_code": client_code,
                "password": password,
                "api_key": creds["api_key"],
                "totp_secret": creds.get("totp_secret", "")
            }
        
        save_user_session("angel", user_id, session_data, user_id, remember=remember_me)
        # Keep smart_api in memory only (not in database)
        memory_session = session_data.copy()
        memory_session["smart_api"] = smart
        USER_SESSIONS["angel"][user_id] = memory_session
        return redirect('/saved_sessions')
    except Exception as e:
        print(f"Angel login exception: {e}")
        return render_template("angel_login.html", 
                             user_id=user_id,
                             client_code=client_code,
                             error=f"Login failed: {str(e)}",
                             totp_value=""), 400

# ===================== DATA ENDPOINTS =====================

# ----- Kite Connect Endpoints -----
@multi_broker_bp.route('/kite/trades')
def kite_trades():
    user_id = request.args.get("user_id")
    sess = get_user_session("kite", user_id) or USER_SESSIONS["kite"].get(user_id)
    if not sess:
        return jsonify({"ok": False, "data": [], "message": "Kite not connected"})
    try:
        kite = get_kite_for_user(user_id, sess["access_token"])
        return jsonify({"ok": True, "data": kite.trades()})
    except Exception as e:
        return jsonify({"ok": False, "data": [], "message": str(e)})

@multi_broker_bp.route('/kite/orders')
def kite_orders():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "user_id required"}), 400
        
    sess = get_user_session("kite", user_id) or USER_SESSIONS["kite"].get(user_id)
    if not sess:
        return jsonify({
            "ok": False, 
            "data": [],
            "message": "Kite not connected",
            "connect_url": f"/api/multi_broker/kite/login?user_id={user_id}"
        })
    try:
        kite = get_kite_for_user(user_id, sess["access_token"])
        orders = kite.orders()
        return jsonify({"ok": True, "data": orders})
    except Exception as e:
        return jsonify({"ok": False, "data": [], "message": str(e)}), 400

@multi_broker_bp.route('/kite/positions')
def kite_positions():
    user_id = request.args.get("user_id")
    sess = get_user_session("kite", user_id) or USER_SESSIONS["kite"].get(user_id)
    if not sess:
        return jsonify({"ok": False, "data": [], "message": "Kite not connected"})
    try:
        kite = get_kite_for_user(user_id, sess["access_token"])
        return jsonify({"ok": True, "data": kite.positions()})
    except Exception as e:
        return jsonify({"ok": False, "data": [], "message": str(e)})

# ----- DhanHQ Endpoints -----
@multi_broker_bp.route('/dhan/orders')
def dhan_orders():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "user_id required"}), 400
        
    client, resp, code = _dhan_client_from_session(user_id)
    if client is None:
        return jsonify({
            "ok": False, 
            "message": "Dhan not connected",
            "connect_url": f"/api/multi_broker/dhan/login?user_id={user_id}"
        }), 401
    try:
        orders = client.get_order_list()
        return jsonify({"ok": True, "data": orders})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 400

@multi_broker_bp.route('/dhan/positions')
def dhan_positions():
    user_id = request.args.get("user_id")
    client, resp, code = _dhan_client_from_session(user_id)
    if client is None:
        return resp, code
    try:
        positions = client.get_positions()
        return jsonify({"ok": True, "data": positions})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 400

@multi_broker_bp.route('/dhan/trades')
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

# ----- Angel One Endpoints -----
@multi_broker_bp.route('/angel/orders')
def angel_orders():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "message": "user_id required"}), 400
        
    try:
        data = _handle_angel_call(user_id, "orderBook")
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        msg = str(e)
        expired = ("AG8001" in msg) or ("Invalid Token" in msg)
        return jsonify({"ok": False, "data": [], "message": msg, "expired": expired})

@multi_broker_bp.route('/angel/positions')
def angel_positions():
    user_id = request.args.get("user_id")
    try:
        data = _handle_angel_call(user_id, "position")
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        msg = str(e)
        expired = ("AG8001" in msg) or ("Invalid Token" in msg)
        return jsonify({"ok": False, "data": [], "message": msg, "expired": expired})

@multi_broker_bp.route('/angel/trades')
def angel_trades():
    user_id = request.args.get("user_id")
    try:
        data = _handle_angel_call(user_id, "tradeBook")
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        msg = str(e)
        expired = ("AG8001" in msg) or ("Invalid Token" in msg)
        return jsonify({"ok": False, "data": [], "message": msg, "expired": expired})

# ===================== STATUS ENDPOINTS =====================
@multi_broker_bp.route('/kite/status')
def kite_status():
    user_id = request.args.get("user_id")
    return jsonify(USER_SESSIONS["kite"].get(user_id) or {"msg": "no session"})

@multi_broker_bp.route('/dhan/status')
def dhan_status():
    user_id = request.args.get("user_id")
    return jsonify(USER_SESSIONS["dhan"].get(user_id) or {"msg": "no session"})

@multi_broker_bp.route('/angel/status')
def angel_status():
    user_id = request.args.get("user_id")
    sess = USER_SESSIONS["angel"].get(user_id)
    if not sess:
        return jsonify({"msg": "no session"})
    # Don't return the full smart_api object as it's not JSON serializable
    return jsonify({
        "angel_client_id": sess.get("angel_client_id"),
        "client_code": sess.get("client_code"),
        "has_smart_api": "smart_api" in sess
    })

@multi_broker_bp.route('/health')
def health():
    return "ok", 200

# Get all data endpoint (missing from original)
@multi_broker_bp.route('/get-all-data')
def get_all_data():
    """Get all broker data for a user"""
    broker = request.args.get('broker')
    user_id = request.args.get('user_id')
    
    if not broker or not user_id:
        return jsonify({"ok": False, "message": "broker and user_id required"}), 400
    
    try:
        if broker == 'kite':
            sess = get_user_session("kite", user_id) or USER_SESSIONS["kite"].get(user_id)
            if not sess:
                return jsonify({"ok": False, "message": "Kite not connected"}), 401
            
            kite = get_kite_for_user(user_id, sess["access_token"])
            return jsonify({
                "ok": True,
                "orders": kite.orders(),
                "positions": kite.positions(),
                "trades": kite.trades()
            })
            
        elif broker == 'dhan':
            client, resp, code = _dhan_client_from_session(user_id)
            if client is None:
                return jsonify({"ok": False, "message": "Dhan not connected"}), 401
            
            orders = client.get_order_list()
            positions = client.get_positions()
            trades = client.get_trade_book() if hasattr(client, "get_trade_book") else []
            
            return jsonify({
                "ok": True,
                "orders": orders,
                "positions": positions,
                "trades": trades
            })
            
        elif broker == 'angel':
            try:
                orders = _handle_angel_call(user_id, "orderBook")
                positions = _handle_angel_call(user_id, "position")
                trades = _handle_angel_call(user_id, "tradeBook")
                
                return jsonify({
                    "ok": True,
                    "orders": orders,
                    "positions": positions,
                    "trades": trades
                })
            except Exception as e:
                return jsonify({"ok": False, "message": str(e)}), 401
        
        else:
            return jsonify({"ok": False, "message": "Invalid broker"}), 400
            
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500

@multi_broker_bp.route('/refresh_session/<broker>/<user_id>', methods=['POST'])
def refresh_session(broker, user_id):
    """Refresh session expiry to prevent timeout"""
    try:
        from flask import current_app
        db = current_app.extensions['sqlalchemy']
        BrokerSession = init_broker_session_model(db)
        
        db_session = BrokerSession.query.filter_by(broker=broker, user_id=user_id).first()
        if db_session:
            # Extend expiry by 30 days
            from datetime import datetime, timedelta
            db_session.expires_at = datetime.utcnow() + timedelta(days=30)
            db_session.updated_at = datetime.utcnow()
            db.session.commit()
            
            return jsonify({
                "ok": True, 
                "message": "Session refreshed",
                "expires_at": db_session.expires_at.isoformat()
            })
        else:
            return jsonify({"ok": False, "message": "Session not found"}), 404
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500

# ===================== INTEGRATION FUNCTIONS =====================

# Legacy callback routes
@legacy_broker_bp.route('/calculatentrade_journal/real_broker_connect/kite/callback')
def legacy_kite_callback():
    """Legacy callback route for Kite Connect OAuth"""
    request_token = request.args.get("request_token")
    # Try to get user_id from session or use default
    user_id = session.get("oauth_user_id", "default_user")
    
    if not request_token:
        return "Missing request_token", 400
    
    # Check if we have credentials for any user (fallback)
    if not USER_APPS["kite"].get(user_id) and USER_APPS["kite"]:
        user_id = list(USER_APPS["kite"].keys())[0]  # Use first available user
    
    creds = USER_APPS["kite"].get(user_id)
    if not creds:
        return f"No stored credentials for user {user_id}. Please register your Kite app first.", 400
    
    kite = KiteConnect(api_key=creds["api_key"])
    try:
        data = kite.generate_session(request_token, api_secret=creds["api_secret"])
        session_data = {
            "access_token": data["access_token"],
            "kite_user_id": data.get("user_id")
        }
        save_user_session("kite", user_id, session_data, user_id, remember=True)
        USER_SESSIONS["kite"][user_id] = session_data
        return redirect('/saved_sessions')
    except Exception as e:
        return f"Auth error: {str(e)}", 400

def integrate_with_calculatentrade(app):
    """
    Integrate multi-broker system with CalculatenTrade app
    """
    # Register the blueprints
    app.register_blueprint(multi_broker_bp)
    app.register_blueprint(legacy_broker_bp)
    
    # Initialize database sessions on startup
    with app.app_context():
        sync_sessions_from_db()
    
    # Add the missing get-all-data endpoint at app level
    @app.route('/api/broker/get-all-data', methods=['GET'])
    def get_all_broker_data():
        """Get all broker data - app level endpoint"""
        broker = request.args.get('broker')
        user_id = request.args.get('user_id')
        
        if not broker or not user_id:
            return jsonify({"success": False, "message": "broker and user_id required"}), 400
        
        if broker not in ['kite', 'dhan', 'angel']:
            return jsonify({"success": False, "message": "Invalid broker"}), 400
        
        try:
            if broker == 'kite':
                sess = get_user_session("kite", user_id) or USER_SESSIONS["kite"].get(user_id)
                if not sess:
                    return jsonify({"success": False, "message": "Kite not connected"}), 401
                
                return jsonify({
                    "success": True,
                    "data": {
                        "orders": get_kite_for_user(user_id, sess["access_token"]).orders(),
                        "positions": get_kite_for_user(user_id, sess["access_token"]).positions(),
                        "trades": get_kite_for_user(user_id, sess["access_token"]).trades()
                    }
                })
                
            elif broker == 'dhan':
                client, resp, code = _dhan_client_from_session(user_id)
                if client is None:
                    return jsonify({"success": False, "message": "Dhan not connected"}), 401
                
                return jsonify({
                    "success": True,
                    "data": {
                        "orders": client.get_order_list(),
                        "positions": client.get_positions(),
                        "trades": client.get_trade_book() if hasattr(client, "get_trade_book") else []
                    }
                })
                
            elif broker == 'angel':
                return jsonify({
                    "success": True,
                    "data": {
                        "orders": _handle_angel_call(user_id, "orderBook"),
                        "positions": _handle_angel_call(user_id, "position"),
                        "trades": _handle_angel_call(user_id, "tradeBook")
                    }
                })
                
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
    
    # Add saved sessions route at app level too
    @app.route('/saved_sessions')
    def app_saved_sessions():
        """App level saved sessions route"""
        try:
            from flask import current_app
            db = current_app.extensions['sqlalchemy']
            BrokerSession = init_broker_session_model(db)
            
            sessions = BrokerSession.query.all()
            session_data = []
            
            for sess in sessions:
                try:
                    data = json.loads(sess.session_data)
                    session_info = {
                        'broker': sess.broker,
                        'user_id': sess.user_id,
                        'client_code': data.get('client_code', data.get('angel_client_id', 'N/A')),
                        'updated_at': sess.updated_at,
                        'expires_at': sess.expires_at,
                        'is_active': sess.expires_at > datetime.utcnow()
                    }
                    session_data.append(session_info)
                except Exception as e:
                    print(f"Error processing session {sess.id}: {e}")
                    continue
            
            return render_template('saved_sessions.html', sessions=session_data)
        except Exception as e:
            return f"Error loading sessions: {str(e)}", 500
    
    # Add broker connection check routes
    @app.route('/api/broker/check-multi', methods=['GET'])
    def check_multi_broker_connections():
        """Check all broker connections for a user"""
        user_id = request.args.get('user_id', 'default_user')
        brokers = ['kite', 'dhan', 'angel']
        
        connected_brokers = []
        for broker in brokers:
            if USER_SESSIONS[broker].get(user_id):
                connected_brokers.append({
                    'broker': broker,
                    'user_id': user_id,
                    'status': 'connected'
                })
        
        return jsonify({
            'connected_brokers': connected_brokers,
            'total_connected': len(connected_brokers)
        })
    
    @app.route('/api/broker/connect-multi', methods=['POST'])
    def connect_multi_broker():
        """Connect to multiple brokers"""
        data = request.get_json()
        broker = data.get('broker')
        user_id = data.get('user_id', 'default_user')
        
        if broker not in ['kite', 'dhan', 'angel']:
            return jsonify({'ok': False, 'message': 'Invalid broker'}), 400
        
        # Check if already connected
        if USER_SESSIONS[broker].get(user_id):
            return jsonify({
                'ok': True,
                'message': f'Already connected to {broker.upper()}',
                'broker': broker
            })
        
        # Return login URL for the broker
        login_urls = {
            'kite': f'/api/multi_broker/kite/login?user_id={user_id}',
            'dhan': f'/api/multi_broker/dhan/login?user_id={user_id}',
            'angel': f'/api/multi_broker/angel/login?user_id={user_id}'
        }
        
        return jsonify({
            'ok': True,
            'login_url': login_urls[broker],
            'message': f'Redirect to {broker.upper()} login'
        })

def get_broker_session_status(broker: str, user_id: str) -> dict:
    """Get session status for a broker"""
    # Check database first, then memory
    session_obj = get_user_session(broker, user_id) or USER_SESSIONS[broker].get(user_id)
    if session_obj:
        return {
            'connected': True,
            'broker': broker,
            'user_id': user_id,
            'session_data': session_obj
        }
    else:
        return {
            'connected': False,
            'broker': broker,
            'user_id': user_id
        }
