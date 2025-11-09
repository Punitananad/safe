/**
 * Broker Session Manager - Prevents session expiry
 */

class BrokerSessionManager {
    constructor() {
        this.refreshInterval = 30 * 60 * 1000; // 30 minutes
        this.connectedBrokers = [];
        this.userId = null;
        this.intervalId = null;
    }

    init(userId, connectedBrokers = []) {
        this.userId = userId;
        this.connectedBrokers = connectedBrokers;
        this.startAutoRefresh();
        console.log('Broker Session Manager initialized');
    }

    startAutoRefresh() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
        }

        this.intervalId = setInterval(() => {
            this.refreshAllSessions();
        }, this.refreshInterval);

        // Initial refresh after 1 minute
        setTimeout(() => {
            this.refreshAllSessions();
        }, 60000);
    }

    async refreshAllSessions() {
        if (!this.userId || this.connectedBrokers.length === 0) {
            return;
        }

        console.log('Refreshing broker sessions...');
        
        for (const brokerInfo of this.connectedBrokers) {
            try {
                await this.refreshSession(brokerInfo.broker, this.userId);
            } catch (error) {
                console.error(`Failed to refresh ${brokerInfo.broker} session:`, error);
            }
        }
    }

    async refreshSession(broker, userId) {
        const response = await fetch(`/api/multi_broker/refresh_session/${broker}/${userId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        const result = await response.json();
        
        if (result.ok) {
            console.log(`${broker.toUpperCase()} session refreshed until ${result.expires_at}`);
        } else {
            console.warn(`Failed to refresh ${broker} session:`, result.message);
        }

        return result;
    }

    addBroker(broker, userId) {
        if (!this.connectedBrokers.find(b => b.broker === broker)) {
            this.connectedBrokers.push({ broker, user_id: userId });
            console.log(`Added ${broker} to session manager`);
        }
    }

    removeBroker(broker) {
        this.connectedBrokers = this.connectedBrokers.filter(b => b.broker !== broker);
        console.log(`Removed ${broker} from session manager`);
    }

    stop() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
            console.log('Broker Session Manager stopped');
        }
    }
}

// Global instance
window.brokerSessionManager = new BrokerSessionManager();

// Auto-initialize if data is available
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the multi_broker_connect page
    if (window.location.pathname.includes('multi_broker_connect')) {
        // Try to get data from page
        const userIdElement = document.querySelector('[data-user-id]');
        const brokersElement = document.querySelector('[data-connected-brokers]');
        
        if (userIdElement && brokersElement) {
            const userId = userIdElement.dataset.userId;
            const connectedBrokers = JSON.parse(brokersElement.dataset.connectedBrokers || '[]');
            
            if (userId && connectedBrokers.length > 0) {
                window.brokerSessionManager.init(userId, connectedBrokers);
            }
        }
    }
});