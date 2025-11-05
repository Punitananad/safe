"""
Toast notification utilities for CalculateNTrade
Provides standardized flash message handling with deduplication
"""

from flask import flash, session
import time
from typing import Optional, Dict, Any
import hashlib

class ToastManager:
    """Centralized toast message management"""
    
    # Standard message templates to avoid duplication
    MESSAGES = {
        'login_success': 'Welcome back! You have successfully logged in.',
        'login_failed': 'Invalid credentials. Please check your email and password.',
        'logout_success': 'You have been logged out successfully.',
        'register_success': 'Account created successfully! You can now log in.',
        'register_failed': 'Registration failed. Please try again.',
        'email_exists': 'An account with this email already exists.',
        'verification_sent': 'Verification code sent to your email.',
        'verification_failed': 'Verification failed. Please try again.',
        'password_reset_sent': 'If that email exists, a reset code has been sent.',
        'password_reset_success': 'Password reset successful. Please log in.',
        'settings_updated': 'Settings updated successfully.',
        'trade_saved': 'Trade saved successfully.',
        'trade_updated': 'Trade updated successfully.',
        'trade_deleted': 'Trade deleted successfully.',
        'strategy_saved': 'Strategy saved successfully.',
        'strategy_updated': 'Strategy updated successfully.',
        'strategy_deleted': 'Strategy deleted successfully.',
        'mistake_saved': 'Mistake logged successfully.',
        'mistake_updated': 'Mistake updated successfully.',
        'mistake_deleted': 'Mistake deleted successfully.',
        'subscription_required': 'This feature requires an active subscription.',
        'subscription_success': 'Subscription activated successfully!',
        'payment_success': 'Payment processed successfully.',
        'payment_failed': 'Payment failed. Please try again.',
        'access_denied': 'Access denied. Insufficient permissions.',
        'session_expired': 'Your session has expired. Please log in again.',
        'network_error': 'Network error. Please check your connection.',
        'server_error': 'Server error. Please try again later.',
        'validation_error': 'Please check your input and try again.',
        'file_upload_success': 'File uploaded successfully.',
        'file_upload_failed': 'File upload failed. Please try again.',
        'data_export_success': 'Data exported successfully.',
        'data_import_success': 'Data imported successfully.',
        'broker_connected': 'Broker account connected successfully.',
        'broker_disconnected': 'Broker account disconnected.',
        'broker_connection_failed': 'Failed to connect to broker. Please check your credentials.'
    }
    
    @staticmethod
    def _get_message_id(message: str, category: str = 'info') -> str:
        """Generate unique ID for message deduplication"""
        content = f"{category}:{message}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    @staticmethod
    def _should_dedupe(message_id: str, dedupe_window: int = 10) -> bool:
        """Check if message should be deduplicated"""
        if 'toast_recent' not in session:
            session['toast_recent'] = {}
        
        recent = session['toast_recent']
        current_time = time.time()
        
        # Clean old entries
        session['toast_recent'] = {
            k: v for k, v in recent.items() 
            if current_time - v < dedupe_window
        }
        
        if message_id in session['toast_recent']:
            return True
        
        session['toast_recent'][message_id] = current_time
        return False
    
    @classmethod
    def show(cls, message: str, category: str = 'info', 
             template_key: Optional[str] = None, dedupe: bool = True) -> None:
        """
        Show a toast notification
        
        Args:
            message: Message text or template key
            category: Message category ('success', 'error', 'warning', 'info')
            template_key: Use predefined message template
            dedupe: Enable deduplication
        """
        # Use template if provided
        if template_key and template_key in cls.MESSAGES:
            message = cls.MESSAGES[template_key]
        
        # Clean and validate message
        if not message or not isinstance(message, str):
            return
        
        message = message.strip()
        if not message:
            return
        
        # Deduplication
        if dedupe:
            message_id = cls._get_message_id(message, category)
            if cls._should_dedupe(message_id):
                return
        
        # Ensure category is valid
        valid_categories = {'success', 'error', 'warning', 'info'}
        if category not in valid_categories:
            category = 'info'
        
        flash(message, category)
    
    @classmethod
    def success(cls, message: str = None, template_key: str = None, dedupe: bool = True) -> None:
        """Show success toast"""
        cls.show(message or '', 'success', template_key, dedupe)
    
    @classmethod
    def error(cls, message: str = None, template_key: str = None, dedupe: bool = True) -> None:
        """Show error toast"""
        cls.show(message or '', 'error', template_key, dedupe)
    
    @classmethod
    def warning(cls, message: str = None, template_key: str = None, dedupe: bool = True) -> None:
        """Show warning toast"""
        cls.show(message or '', 'warning', template_key, dedupe)
    
    @classmethod
    def info(cls, message: str = None, template_key: str = None, dedupe: bool = True) -> None:
        """Show info toast"""
        cls.show(message or '', 'info', template_key, dedupe)

# Convenience functions for backward compatibility
def toast_success(message: str = None, template_key: str = None, dedupe: bool = True) -> None:
    """Show success toast"""
    ToastManager.success(message, template_key, dedupe)

def toast_error(message: str = None, template_key: str = None, dedupe: bool = True) -> None:
    """Show error toast"""
    ToastManager.error(message, template_key, dedupe)

def toast_warning(message: str = None, template_key: str = None, dedupe: bool = True) -> None:
    """Show warning toast"""
    ToastManager.warning(message, template_key, dedupe)

def toast_info(message: str = None, template_key: str = None, dedupe: bool = True) -> None:
    """Show info toast"""
    ToastManager.info(message, template_key, dedupe)

# Context processor for templates
def toast_context_processor() -> Dict[str, Any]:
    """Add toast utilities to template context"""
    return {
        'toast_success': toast_success,
        'toast_error': toast_error,
        'toast_warning': toast_warning,
        'toast_info': toast_info,
    }