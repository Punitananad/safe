"""
Toast notification utilities for CalculateNTrade application
Provides centralized toast management with deduplication and session persistence
"""

from flask import session, request
import json
from datetime import datetime
import hashlib

class ToastManager:
    """Centralized toast notification manager"""
    
    @staticmethod
    def _get_toast_key():
        """Get session key for toast storage"""
        return '_toast_notifications'
    
    @staticmethod
    def _generate_toast_id(message, toast_type):
        """Generate unique ID for toast deduplication"""
        content = f"{message}_{toast_type}_{datetime.now().strftime('%Y%m%d%H')}"
        return hashlib.md5(content.encode()).hexdigest()[:8]
    
    @staticmethod
    def add_toast(message, toast_type='info', title=None, duration=5000, persistent=False):
        """Add toast notification to session"""
        if '_toast_notifications' not in session:
            session['_toast_notifications'] = []
        
        toast_id = ToastManager._generate_toast_id(message, toast_type)
        
        # Check for duplicates
        existing_toasts = session['_toast_notifications']
        for toast in existing_toasts:
            if toast.get('id') == toast_id:
                return  # Skip duplicate
        
        toast = {
            'id': toast_id,
            'message': message,
            'type': toast_type,
            'title': title,
            'duration': duration,
            'persistent': persistent,
            'timestamp': datetime.now().isoformat()
        }
        
        session['_toast_notifications'].append(toast)
        session.modified = True
    
    @staticmethod
    def get_toasts():
        """Get and clear toast notifications from session"""
        toasts = session.pop('_toast_notifications', [])
        return toasts
    
    @staticmethod
    def clear_toasts():
        """Clear all toast notifications"""
        session.pop('_toast_notifications', None)

# Convenience functions
def toast_success(message, title="Success", duration=4000):
    """Add success toast notification"""
    ToastManager.add_toast(message, 'success', title, duration)

def toast_error(message, title="Error", duration=6000):
    """Add error toast notification"""
    ToastManager.add_toast(message, 'error', title, duration)

def toast_warning(message, title="Warning", duration=5000):
    """Add warning toast notification"""
    ToastManager.add_toast(message, 'warning', title, duration)

def toast_info(message, title="Info", duration=4000):
    """Add info toast notification"""
    ToastManager.add_toast(message, 'info', title, duration)

def toast_context_processor():
    """Context processor to make toast utilities available in templates"""
    return {
        'get_toast_notifications': ToastManager.get_toasts,
        'toast_success': toast_success,
        'toast_error': toast_error,
        'toast_warning': toast_warning,
        'toast_info': toast_info
    }