/**
 * Mobile-specific enhancements for trades journal
 * Fixes touch events, prevents double-tap zoom, and improves mobile UX
 */

(function() {
    'use strict';
    
    // Only run on mobile devices
    if (!window.matchMedia || !window.matchMedia('(max-width: 768px)').matches) {
        return;
    }
    
    // Mobile initialization
    function initMobile() {
        preventIOSZoom();
        setupTouchFeedback();
        fixViewportIssues();
        setupMobileEventHandlers();
        createMobileActionBar();
    }
    
    // Prevent iOS zoom on form inputs
    function preventIOSZoom() {
        if (/iPad|iPhone|iPod/.test(navigator.userAgent)) {
            const viewport = document.querySelector('meta[name=viewport]');
            if (viewport) {
                viewport.setAttribute('content', 
                    'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover'
                );
            }
        }
        
        // Set font-size to prevent zoom
        const inputs = document.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            input.style.fontSize = '16px';
            input.style.touchAction = 'manipulation';
        });
    }
    
    // Setup touch feedback for interactive elements
    function setupTouchFeedback() {
        const interactiveElements = document.querySelectorAll('button, .btn, a, .stat-card, .filter-card');
        
        interactiveElements.forEach(element => {
            element.style.webkitTapHighlightColor = 'transparent';
            element.style.touchAction = 'manipulation';
            element.style.userSelect = 'none';
            element.style.webkitUserSelect = 'none';
            
            let touchStarted = false;
            
            element.addEventListener('touchstart', function(e) {
                touchStarted = true;
                this.style.transform = 'scale(0.98)';
                this.style.opacity = '0.9';
            }, { passive: true });
            
            element.addEventListener('touchend', function(e) {
                if (touchStarted) {
                    this.style.transform = 'scale(1)';
                    this.style.opacity = '1';
                    touchStarted = false;
                }
            }, { passive: true });
            
            element.addEventListener('touchcancel', function() {
                this.style.transform = 'scale(1)';
                this.style.opacity = '1';
                touchStarted = false;
            }, { passive: true });
        });
    }
    
    // Fix viewport and scrolling issues
    function fixViewportIssues() {
        // Prevent horizontal scroll
        document.documentElement.style.overflowX = 'hidden';
        document.body.style.overflowX = 'hidden';
        document.body.style.maxWidth = '100vw';
        
        // Fix iOS Safari bottom bar issues
        if (/iPad|iPhone|iPod/.test(navigator.userAgent)) {
            const setVH = () => {
                const vh = window.innerHeight * 0.01;
                document.documentElement.style.setProperty('--vh', `${vh}px`);
            };
            
            setVH();
            window.addEventListener('resize', setVH);
            window.addEventListener('orientationchange', () => {
                setTimeout(setVH, 100);
            });
        }
        
        // Improve scrolling performance
        const scrollableElements = document.querySelectorAll('.overflow-y-auto, .table-container');
        scrollableElements.forEach(element => {
            element.style.webkitOverflowScrolling = 'touch';
        });
    }
    
    // Setup mobile-specific event handlers
    function setupMobileEventHandlers() {
        // Fix button event handlers to work properly on mobile
        const mobileButtons = [
            '#show-advanced-analytics-mobile',
            '#apply-filters-mobile',
            '#reset-filters-mobile',
            '#export-csv-mobile'
        ];
        
        mobileButtons.forEach(selector => {
            const button = document.querySelector(selector);
            if (button) {
                // Remove existing handlers and add mobile-optimized ones
                button.removeEventListener('click', button.clickHandler);
                
                button.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    // Add visual feedback
                    this.style.transform = 'scale(0.95)';
                    setTimeout(() => {
                        this.style.transform = 'scale(1)';
                    }, 150);
                    
                    // Execute the appropriate action
                    switch(selector) {
                        case '#show-advanced-analytics-mobile':
                            if (typeof showAdvancedAnalytics === 'function') {
                                showAdvancedAnalytics();
                            }
                            break;
                        case '#apply-filters-mobile':
                            if (typeof applyFilters === 'function') {
                                applyFilters();
                            }
                            break;
                        case '#reset-filters-mobile':
                            resetFilters();
                            break;
                        case '#export-csv-mobile':
                            if (typeof exportToCSV === 'function') {
                                exportToCSV();
                            }
                            break;
                    }
                }, { passive: false });
            }
        });
        
        // Fix broker button handler
        const brokerButtons = document.querySelectorAll('[data-action="add-trade-via-broker"]');
        brokerButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                const userId = window.CURRENT_USER_ID || 'NES881';
                window.location.href = `/calculatentrade_journal/real_broker_connect?user_id=${userId}`;
            }, { passive: false });
        });
    }
    
    // Create mobile action bar
    function createMobileActionBar() {
        const existingBar = document.querySelector('.mobile-action-bar');
        if (existingBar) {
            return; // Already exists
        }
        
        const bar = document.createElement('div');
        bar.className = 'mobile-action-bar';
        bar.style.cssText = `
            position: fixed;
            left: 0;
            right: 0;
            bottom: 0;
            z-index: 60;
            display: flex;
            gap: 0.3rem;
            padding: 0.5rem 0.75rem;
            background: linear-gradient(90deg, rgba(15,23,42,0.98), rgba(17,24,39,0.98));
            border-top: 1px solid #334155;
            backdrop-filter: blur(10px);
            justify-content: space-around;
            -webkit-tap-highlight-color: transparent;
            touch-action: manipulation;
            safe-area-inset-bottom: env(safe-area-inset-bottom);
            padding-bottom: calc(0.5rem + env(safe-area-inset-bottom));
        `;
        
        bar.innerHTML = `
            <button class="action bg-emerald-600 text-white" id="mobile-add" title="Add Trade">
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 4v16m8-8H4"/>
                </svg>
            </button>
            <button class="action bg-purple-600 text-white" id="mobile-analytics" title="Analytics">
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                </svg>
            </button>
            <button class="action bg-teal-600 text-white" id="mobile-broker" title="Broker">
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M4 7v10c0 2.21 3.58 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.58 4 8 4s8-1.79 8-4M4 7c0-2.21 3.58-4 8-4s8 1.79 8 4"/>
                </svg>
            </button>
            <button class="action bg-slate-700 text-white" id="mobile-more" title="More">
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 6v.01M12 12v.01M12 18v.01"/>
                </svg>
            </button>
        `;
        
        // Style action buttons
        const actions = bar.querySelectorAll('.action');
        actions.forEach(action => {
            action.style.cssText = `
                flex: 1;
                min-height: 44px;
                border-radius: 0.375rem;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                padding: 0.5rem;
                font-size: 0.65rem;
                gap: 0.2rem;
                transition: all 0.2s ease;
                border: none;
                cursor: pointer;
                -webkit-tap-highlight-color: transparent;
                touch-action: manipulation;
                user-select: none;
                -webkit-user-select: none;
            `;
        });
        
        document.body.appendChild(bar);
        document.body.style.paddingBottom = 'calc(60px + env(safe-area-inset-bottom))';
        
        // Setup action handlers
        setupActionBarHandlers(bar);
    }
    
    // Setup action bar event handlers
    function setupActionBarHandlers(bar) {
        const addBtn = bar.querySelector('#mobile-add');
        const analyticsBtn = bar.querySelector('#mobile-analytics');
        const brokerBtn = bar.querySelector('#mobile-broker');
        const moreBtn = bar.querySelector('#mobile-more');
        
        // Add touch feedback
        [addBtn, analyticsBtn, brokerBtn, moreBtn].forEach(btn => {
            if (btn) {
                let touchStarted = false;
                
                btn.addEventListener('touchstart', function(e) {
                    e.preventDefault();
                    touchStarted = true;
                    this.style.transform = 'scale(0.95)';
                    this.style.opacity = '0.8';
                }, { passive: false });
                
                btn.addEventListener('touchend', function(e) {
                    e.preventDefault();
                    if (touchStarted) {
                        this.style.transform = 'scale(1)';
                        this.style.opacity = '1';
                        touchStarted = false;
                        
                        // Trigger click after animation
                        setTimeout(() => {
                            this.click();
                        }, 50);
                    }
                }, { passive: false });
                
                btn.addEventListener('touchcancel', function() {
                    this.style.transform = 'scale(1)';
                    this.style.opacity = '1';
                    touchStarted = false;
                });
            }
        });
        
        // Setup click handlers
        if (addBtn) {
            addBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const tradeFormLink = document.querySelector('a[href*="trade_form"]');
                if (tradeFormLink) {
                    window.location.href = tradeFormLink.href;
                }
            });
        }
        
        if (analyticsBtn) {
            analyticsBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (typeof showAdvancedAnalytics === 'function') {
                    showAdvancedAnalytics();
                }
            });
        }
        
        if (brokerBtn) {
            brokerBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const userId = window.CURRENT_USER_ID || 'NES881';
                window.location.href = `/calculatentrade_journal/real_broker_connect?user_id=${userId}`;
            });
        }
        
        if (moreBtn) {
            moreBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                showMobileMenu();
            });
        }
    }
    
    // Show mobile menu
    function showMobileMenu() {
        const existingMenu = document.querySelector('.mobile-menu');
        if (existingMenu) {
            existingMenu.remove();
        }
        
        const menu = document.createElement('div');
        menu.className = 'mobile-menu';
        menu.style.cssText = `
            position: fixed;
            bottom: calc(68px + env(safe-area-inset-bottom));
            right: 12px;
            background: var(--card);
            border: 1px solid #334155;
            padding: 8px;
            border-radius: 8px;
            z-index: 9999;
            min-width: 140px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            -webkit-tap-highlight-color: transparent;
        `;
        
        menu.innerHTML = `
            <button class="menu-item" data-action="apply">✅ Apply Filters</button>
            <button class="menu-item" data-action="reset">🔄 Reset Filters</button>
            <button class="menu-item" data-action="export">📥 Export CSV</button>
            <button class="menu-item" data-action="refresh">🔄 Refresh</button>
        `;
        
        // Style menu items
        menu.querySelectorAll('.menu-item').forEach(item => {
            item.style.cssText = `
                display: block;
                width: 100%;
                text-align: left;
                padding: 8px 12px;
                background: none;
                border: none;
                color: white;
                font-size: 0.8rem;
                border-radius: 4px;
                margin-bottom: 2px;
                touch-action: manipulation;
                -webkit-tap-highlight-color: transparent;
            `;
            
            // Add touch feedback
            item.addEventListener('touchstart', () => {
                item.style.background = '#334155';
            });
            item.addEventListener('touchend', () => {
                item.style.background = 'none';
            });
        });
        
        document.body.appendChild(menu);
        
        // Close menu on outside click/touch
        const closeMenu = (e) => {
            if (!menu.contains(e.target) && !document.getElementById('mobile-more').contains(e.target)) {
                if (document.body.contains(menu)) {
                    menu.remove();
                }
                document.removeEventListener('click', closeMenu);
                document.removeEventListener('touchstart', closeMenu);
            }
        };
        
        setTimeout(() => {
            document.addEventListener('click', closeMenu);
            document.addEventListener('touchstart', closeMenu);
        }, 100);
        
        // Handle menu actions
        menu.addEventListener('click', (e) => {
            const action = e.target.dataset.action;
            if (action) {
                handleMenuAction(action);
                menu.remove();
            }
        });
    }
    
    // Handle menu actions
    function handleMenuAction(action) {
        switch(action) {
            case 'apply':
                if (typeof applyFilters === 'function') {
                    applyFilters();
                }
                break;
            case 'reset':
                resetFilters();
                break;
            case 'export':
                if (typeof exportToCSV === 'function') {
                    exportToCSV();
                }
                break;
            case 'refresh':
                window.location.reload();
                break;
        }
    }
    
    // Reset filters helper
    function resetFilters() {
        const filterResult = document.getElementById('filter-result');
        const filterStrategy = document.getElementById('filter-strategy');
        const filterDate = document.getElementById('filter-date');
        const searchTrades = document.getElementById('search-trades');
        
        if (filterResult) filterResult.value = 'all';
        if (filterStrategy) filterStrategy.value = 'all';
        if (filterDate) filterDate.value = '';
        if (searchTrades) searchTrades.value = '';
        
        if (typeof applyFilters === 'function') {
            applyFilters();
        }
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initMobile);
    } else {
        initMobile();
    }
    
    // Re-initialize on orientation change
    window.addEventListener('orientationchange', () => {
        setTimeout(initMobile, 100);
    });
    
})();