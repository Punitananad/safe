/**
 * Centralized Toast Service for CalculateNTrade
 * Provides consistent, non-blocking notifications with deduplication
 */
class ToastService {
    constructor() {
        this.container = null;
        this.activeToasts = new Map(); // id -> toast element
        this.recentToasts = new Set(); // for deduplication
        this.init();
    }

    init() {
        this.createContainer();
        this.setupGlobalErrorHandler();
    }

    createContainer() {
        if (this.container) return;
        
        this.container = document.createElement('div');
        this.container.id = 'toast-container';
        this.container.className = 'fixed top-4 right-4 z-[9999] space-y-2 pointer-events-none';
        this.container.style.cssText = `
            position: fixed;
            top: 1rem;
            right: 1rem;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            pointer-events: none;
            max-width: 400px;
        `;
        
        // Mobile responsive positioning
        const mediaQuery = window.matchMedia('(max-width: 640px)');
        const updatePosition = (e) => {
            if (e.matches) {
                this.container.style.cssText = `
                    position: fixed;
                    bottom: 1rem;
                    left: 1rem;
                    right: 1rem;
                    top: auto;
                    z-index: 9999;
                    display: flex;
                    flex-direction: column;
                    gap: 0.5rem;
                    pointer-events: none;
                    max-width: none;
                `;
            } else {
                this.container.style.cssText = `
                    position: fixed;
                    top: 1rem;
                    right: 1rem;
                    z-index: 9999;
                    display: flex;
                    flex-direction: column;
                    gap: 0.5rem;
                    pointer-events: none;
                    max-width: 400px;
                `;
            }
        };
        
        mediaQuery.addListener(updatePosition);
        updatePosition(mediaQuery);
        
        document.body.appendChild(this.container);
    }

    setupGlobalErrorHandler() {
        // Intercept global API errors
        const originalFetch = window.fetch;
        window.fetch = async (...args) => {
            try {
                const response = await originalFetch(...args);
                if (!response.ok && response.status >= 400) {
                    // Only show error toasts for non-auth endpoints to avoid noise
                    const url = args[0];
                    if (typeof url === 'string' && !url.includes('/login') && !url.includes('/register')) {
                        this.show({
                            message: `Request failed: ${response.statusText}`,
                            variant: 'error',
                            id: `fetch-error-${response.status}`,
                            duration: 4000
                        });
                    }
                }
                return response;
            } catch (error) {
                this.show({
                    message: 'Network error occurred',
                    variant: 'error',
                    id: 'network-error',
                    duration: 4000
                });
                throw error;
            }
        };
    }

    /**
     * Show a toast notification
     * @param {Object} options - Toast options
     * @param {string} options.message - Toast message
     * @param {string} options.variant - Toast variant: 'success', 'info', 'warning', 'error'
     * @param {string} [options.id] - Unique ID for deduplication
     * @param {number} [options.duration=3000] - Auto-dismiss duration in ms
     * @param {boolean} [options.dedupe=true] - Enable deduplication
     */
    show({ message, variant = 'info', id, duration = 3000, dedupe = true }) {
        if (!message || typeof message !== 'string') return;

        // Clean message - no raw error objects
        const cleanMessage = this.sanitizeMessage(message);
        
        // Deduplication logic
        if (dedupe && id) {
            if (this.recentToasts.has(id)) return;
            if (this.activeToasts.has(id)) {
                this.dismiss(id);
            }
        }

        const toastId = id || `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        const toast = this.createToastElement(cleanMessage, variant, toastId);
        
        this.activeToasts.set(toastId, toast);
        if (dedupe && id) {
            this.recentToasts.add(id);
            setTimeout(() => this.recentToasts.delete(id), 10000); // Clear from recent after 10s
        }

        this.container.appendChild(toast);
        
        // Trigger entrance animation
        requestAnimationFrame(() => {
            toast.style.transform = 'translateX(0)';
            toast.style.opacity = '1';
        });

        // Auto-dismiss
        if (duration > 0) {
            setTimeout(() => this.dismiss(toastId), duration);
        }

        return toastId;
    }

    createToastElement(message, variant, id) {
        const toast = document.createElement('div');
        toast.id = id;
        toast.className = 'toast-item';
        toast.style.cssText = `
            transform: translateX(100%);
            opacity: 0;
            transition: all 0.3s ease-out;
            pointer-events: auto;
            max-width: 100%;
            word-wrap: break-word;
        `;

        const colors = {
            success: { bg: '#10b981', border: '#059669', icon: '✓' },
            error: { bg: '#ef4444', border: '#dc2626', icon: '✕' },
            warning: { bg: '#f59e0b', border: '#d97706', icon: '⚠' },
            info: { bg: '#3b82f6', border: '#2563eb', icon: 'ℹ' }
        };

        const color = colors[variant] || colors.info;

        toast.innerHTML = `
            <div style="
                background: ${color.bg};
                border: 1px solid ${color.border};
                border-radius: 0.5rem;
                padding: 0.75rem 1rem;
                color: white;
                font-size: 0.875rem;
                line-height: 1.25rem;
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
                display: flex;
                align-items: flex-start;
                gap: 0.5rem;
                min-width: 250px;
                position: relative;
            ">
                <span style="
                    font-weight: bold;
                    font-size: 1rem;
                    flex-shrink: 0;
                    margin-top: 0.125rem;
                ">${color.icon}</span>
                <span style="flex: 1; word-break: break-word;">${this.escapeHtml(message)}</span>
                <button onclick="window.toastService.dismiss('${id}')" style="
                    background: none;
                    border: none;
                    color: rgba(255, 255, 255, 0.8);
                    cursor: pointer;
                    padding: 0;
                    margin: 0;
                    font-size: 1.125rem;
                    line-height: 1;
                    flex-shrink: 0;
                    margin-left: 0.5rem;
                    margin-top: 0.125rem;
                " title="Dismiss">×</button>
            </div>
        `;

        return toast;
    }

    dismiss(id) {
        const toast = this.activeToasts.get(id);
        if (!toast) return;

        toast.style.transform = 'translateX(100%)';
        toast.style.opacity = '0';
        
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
            this.activeToasts.delete(id);
        }, 300);
    }

    dismissAll() {
        for (const id of this.activeToasts.keys()) {
            this.dismiss(id);
        }
    }

    sanitizeMessage(message) {
        if (typeof message === 'object') {
            return 'An error occurred';
        }
        
        // Clean up common error patterns
        let clean = String(message)
            .replace(/^\[.*?\]\s*/, '') // Remove [ERROR] prefixes
            .replace(/Error:\s*/i, '') // Remove "Error:" prefix
            .replace(/Exception:\s*/i, '') // Remove "Exception:" prefix
            .trim();
            
        // Ensure reasonable length
        if (clean.length > 200) {
            clean = clean.substring(0, 197) + '...';
        }
        
        return clean || 'An error occurred';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Convenience methods
    success(message, options = {}) {
        return this.show({ ...options, message, variant: 'success' });
    }

    error(message, options = {}) {
        return this.show({ ...options, message, variant: 'error', duration: 4000 });
    }

    warning(message, options = {}) {
        return this.show({ ...options, message, variant: 'warning' });
    }

    info(message, options = {}) {
        return this.show({ ...options, message, variant: 'info' });
    }
}

// Initialize global toast service
window.toastService = new ToastService();

// Legacy flash message support - convert Flask flash messages to toasts
document.addEventListener('DOMContentLoaded', () => {
    // Convert any existing flash messages to toasts
    const flashMessages = document.querySelectorAll('[data-flash-message]');
    flashMessages.forEach(el => {
        const message = el.textContent.trim();
        const category = el.dataset.flashCategory || 'info';
        const variant = category === 'success' ? 'success' : 
                       category === 'error' ? 'error' : 
                       category === 'warning' ? 'warning' : 'info';
        
        if (message) {
            window.toastService.show({
                message,
                variant,
                id: `flash-${category}-${Date.now()}`,
                duration: variant === 'error' ? 5000 : 3000
            });
        }
        
        // Hide original flash message
        el.style.display = 'none';
    });
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ToastService;
}