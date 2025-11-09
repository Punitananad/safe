/**
 * Session Manager - Handles persistent user sessions
 * Automatically extends sessions and manages user authentication state
 */

class SessionManager {
    constructor() {
        this.checkInterval = 15 * 60 * 1000; // Check every 15 minutes
        this.extendInterval = 24 * 60 * 60 * 1000; // Extend every 24 hours
        this.lastExtension = localStorage.getItem('lastSessionExtension');
        this.init();
    }

    init() {
        // Start periodic session checks
        this.startSessionMonitoring();
        
        // Extend session on user activity
        this.bindActivityListeners();
        
        // Check session status on page load
        this.checkSessionStatus();
    }

    startSessionMonitoring() {
        // Check session status periodically
        setInterval(() => {
            this.checkSessionStatus();
        }, this.checkInterval);

        // Auto-extend session if needed
        setInterval(() => {
            this.autoExtendSession();
        }, this.extendInterval);
    }

    bindActivityListeners() {
        // Extend session on user activity
        const activities = ['click', 'keypress', 'scroll', 'mousemove'];
        let lastActivity = Date.now();

        activities.forEach(activity => {
            document.addEventListener(activity, () => {
                const now = Date.now();
                // Only extend if last activity was more than 1 hour ago
                if (now - lastActivity > 60 * 60 * 1000) {
                    this.extendSessionOnActivity();
                    lastActivity = now;
                }
            }, { passive: true });
        });
    }

    async checkSessionStatus() {
        try {
            const response = await fetch('/api/session/status');
            const data = await response.json();
            
            if (data.authenticated) {
                console.log('Session active:', data);
                this.updateSessionInfo(data);
            } else {
                console.log('No active session');
                this.handleSessionExpired();
            }
        } catch (error) {
            console.error('Error checking session status:', error);
        }
    }

    async extendSession() {
        try {
            const response = await fetch('/api/session/extend', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
            });
            
            const data = await response.json();
            
            if (data.success) {
                console.log('Session extended successfully');
                localStorage.setItem('lastSessionExtension', Date.now().toString());
                return true;
            } else {
                console.error('Failed to extend session:', data.error);
                return false;
            }
        } catch (error) {
            console.error('Error extending session:', error);
            return false;
        }
    }

    async extendSessionOnActivity() {
        // Only extend if user is authenticated
        const status = await this.checkSessionStatus();
        if (status) {
            await this.extendSession();
        }
    }

    async autoExtendSession() {
        const now = Date.now();
        const lastExtension = parseInt(this.lastExtension || '0');
        
        // Auto-extend if last extension was more than 24 hours ago
        if (now - lastExtension > this.extendInterval) {
            console.log('Auto-extending session...');
            await this.extendSession();
        }
    }

    updateSessionInfo(sessionData) {
        // Update UI elements with session info if needed
        const sessionInfo = document.getElementById('session-info');
        if (sessionInfo) {
            sessionInfo.innerHTML = `
                <small class="text-muted">
                    Session active until: ${this.formatExpiryDate(sessionData.login_time)}
                </small>
            `;
        }
    }

    handleSessionExpired() {
        // Clear any stored session data
        localStorage.removeItem('lastSessionExtension');
        
        // Show session expired message if user is on a protected page
        if (window.location.pathname !== '/login' && 
            window.location.pathname !== '/register' && 
            window.location.pathname !== '/') {
            
            // Show a non-intrusive notification
            this.showSessionExpiredNotification();
        }
    }

    showSessionExpiredNotification() {
        // Create a subtle notification
        const notification = document.createElement('div');
        notification.className = 'alert alert-warning alert-dismissible fade show position-fixed';
        notification.style.cssText = `
            top: 20px;
            right: 20px;
            z-index: 9999;
            max-width: 300px;
        `;
        notification.innerHTML = `
            <small>
                <i class="fas fa-clock"></i>
                Your session will expire soon. 
                <a href="#" onclick="sessionManager.extendSession(); this.parentElement.parentElement.remove();">
                    Extend session
                </a>
            </small>
            <button type="button" class="btn-close btn-close-sm" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 10 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 10000);
    }

    formatExpiryDate(loginTime) {
        if (!loginTime) return 'Unknown';
        
        const login = new Date(loginTime);
        const expiry = new Date(login.getTime() + (30 * 24 * 60 * 60 * 1000)); // 30 days
        
        return expiry.toLocaleDateString() + ' ' + expiry.toLocaleTimeString();
    }

    // Manual session extension (can be called from UI)
    async manualExtendSession() {
        const success = await this.extendSession();
        if (success) {
            // Show success message
            const toast = document.createElement('div');
            toast.className = 'toast align-items-center text-white bg-success border-0 position-fixed';
            toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999;';
            toast.innerHTML = `
                <div class="d-flex">
                    <div class="toast-body">
                        Session extended for 30 more days!
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            `;
            
            document.body.appendChild(toast);
            const bsToast = new bootstrap.Toast(toast);
            bsToast.show();
            
            // Remove after showing
            toast.addEventListener('hidden.bs.toast', () => {
                toast.remove();
            });
        }
    }

    // Get session info for debugging
    async getSessionInfo() {
        try {
            const response = await fetch('/api/session/status');
            return await response.json();
        } catch (error) {
            console.error('Error getting session info:', error);
            return null;
        }
    }
}

// Initialize session manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.sessionManager = new SessionManager();
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SessionManager;
}