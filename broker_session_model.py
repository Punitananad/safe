from datetime import datetime, timedelta
import json

# Lazy import to avoid circular dependency
def get_db():
    from flask import current_app
    return current_app.extensions['sqlalchemy']

# Model will be created when needed
BrokerSession = None

def init_broker_session_model(db):
    """Initialize the BrokerSession model with the db instance"""
    global BrokerSession
    
    if BrokerSession is not None:
        return BrokerSession
    
    class BrokerSessionModel(db.Model):
        __tablename__ = 'broker_sessions'
        
        id = db.Column(db.Integer, primary_key=True)
        user_email = db.Column(db.String(255), nullable=False)
        broker = db.Column(db.String(50), nullable=False)
        user_id = db.Column(db.String(255), nullable=False)
        session_data = db.Column(db.Text, nullable=False)
        expires_at = db.Column(db.DateTime, nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        
        def __repr__(self):
            return f'<BrokerSession {self.broker}:{self.user_id}>'
        
        def to_dict(self):
            return {
                'id': self.id,
                'user_email': self.user_email,
                'broker': self.broker,
                'user_id': self.user_id,
                'session_data': json.loads(self.session_data),
                'expires_at': self.expires_at.isoformat(),
                'created_at': self.created_at.isoformat()
            }
    
    BrokerSession = BrokerSessionModel
    return BrokerSession

def save_session(user_email, broker, user_id, session_data, remember_session=False):
    """Save broker session to database"""
    from flask import current_app
    db = current_app.extensions['sqlalchemy']
    
    if BrokerSession is None:
        init_broker_session_model(db)
    
    # Remove existing session for this broker/user
    existing = BrokerSession.query.filter_by(
        user_email=user_email, 
        broker=broker, 
        user_id=user_id
    ).first()
    
    if existing:
        db.session.delete(existing)
    
    # Set expiry based on remember_session
    expires_at = datetime.utcnow() + timedelta(days=30 if remember_session else 1)
    
    # Create new session
    session = BrokerSession(
        user_email=user_email,
        broker=broker,
        user_id=user_id,
        session_data=json.dumps(session_data),
        expires_at=expires_at
    )
    
    db.session.add(session)
    db.session.commit()
    return session

def get_active_session(user_email, broker, user_id):
    """Get active broker session from database"""
    from flask import current_app
    db = current_app.extensions['sqlalchemy']
    
    if BrokerSession is None:
        init_broker_session_model(db)
    
    session = BrokerSession.query.filter_by(
        user_email=user_email,
        broker=broker,
        user_id=user_id
    ).filter(BrokerSession.expires_at > datetime.utcnow()).first()
    
    return session

def cleanup_expired():
    """Clean up expired broker sessions"""
    from flask import current_app
    db = current_app.extensions['sqlalchemy']
    
    if BrokerSession is None:
        init_broker_session_model(db)
    
    expired = BrokerSession.query.filter(BrokerSession.expires_at <= datetime.utcnow()).all()
    for session in expired:
        db.session.delete(session)
    db.session.commit()
    return len(expired)
