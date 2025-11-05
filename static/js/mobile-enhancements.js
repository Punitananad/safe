// Mobile Enhancement Script for Trading Calculator
document.addEventListener('DOMContentLoaded', function() {
    
    // Mobile menu enhancements
    function initMobileMenu() {
        const menuToggle = document.getElementById('menu_toggle');
        const leftCol = document.querySelector('.left_col');
        
        if (menuToggle && leftCol) {
            // Create overlay for mobile
            const overlay = document.createElement('div');
            overlay.className = 'mobile-overlay';
            overlay.style.cssText = `
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.5);
                z-index: 9998;
            `;
            document.body.appendChild(overlay);
            
            // Toggle function
            function toggleMobileMenu() {
                if (window.innerWidth <= 991) {
                    leftCol.classList.toggle('mobile-active');
                    overlay.style.display = leftCol.classList.contains('mobile-active') ? 'block' : 'none';
                }
            }
            
            menuToggle.addEventListener('click', toggleMobileMenu);
            overlay.addEventListener('click', toggleMobileMenu);
            
            // Close on window resize
            window.addEventListener('resize', function() {
                if (window.innerWidth > 991) {
                    leftCol.classList.remove('mobile-active');
                    overlay.style.display = 'none';
                }
            });
        }
    }
    
    // Touch enhancements for calculator cards
    function initTouchEnhancements() {
        const calculatorCards = document.querySelectorAll('.tile-stats');
        
        calculatorCards.forEach(card => {
            // Touch feedback
            card.addEventListener('touchstart', function(e) {
                this.style.transform = 'scale(0.98)';
                this.style.transition = 'transform 0.1s ease';
            });
            
            card.addEventListener('touchend', function(e) {
                this.style.transform = 'scale(1)';
                setTimeout(() => {
                    this.style.transition = 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
                }, 100);
            });
            
            // Prevent double-tap zoom on calculator cards
            let lastTouchEnd = 0;
            card.addEventListener('touchend', function(e) {
                const now = (new Date()).getTime();
                if (now - lastTouchEnd <= 300) {
                    e.preventDefault();
                }
                lastTouchEnd = now;
            }, false);
        });
    }
    
    // Smooth scroll enhancements
    function initSmoothScroll() {
        // Add smooth scrolling to all anchor links
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });
    }
    
    // Performance optimizations
    function initPerformanceOptimizations() {
        // Lazy load images
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        if (img.dataset.src) {
                            img.src = img.dataset.src;
                            img.removeAttribute('data-src');
                            imageObserver.unobserve(img);
                        }
                    }
                });
            });
            
            document.querySelectorAll('img[data-src]').forEach(img => {
                imageObserver.observe(img);
            });
        }
        
        // Preload critical calculator pages
        const criticalPages = [
            '/intraday_calculator',
            '/fo_calculator',
            '/mtf_calculator'
        ];
        
        criticalPages.forEach(url => {
            const link = document.createElement('link');
            link.rel = 'prefetch';
            link.href = url;
            document.head.appendChild(link);
        });
    }
    
    // Initialize all enhancements
    initMobileMenu();
    initTouchEnhancements();
    initSmoothScroll();
    initPerformanceOptimizations();
    
    // Add mobile-specific CSS classes
    if (window.innerWidth <= 768) {
        document.body.classList.add('mobile-device');
    }
    
    // Update on orientation change
    window.addEventListener('orientationchange', function() {
        setTimeout(() => {
            if (window.innerWidth <= 768) {
                document.body.classList.add('mobile-device');
            } else {
                document.body.classList.remove('mobile-device');
            }
        }, 100);
    });
});

// Add mobile-specific styles
const mobileStyles = `
    .mobile-device .tile-stats {
        margin-bottom: 20px;
    }
    
    .mobile-device .calculator-grid {
        gap: 15px;
    }
    
    .mobile-device .x_content {
        padding: 15px;
    }
    
    .left_col.mobile-active {
        transform: translateX(230px) !important;
    }
    
    @media (max-width: 991px) {
        .left_col {
            transform: translateX(-230px);
            transition: transform 0.3s ease;
        }
    }
`;

// Inject mobile styles
const styleSheet = document.createElement('style');
styleSheet.textContent = mobileStyles;
document.head.appendChild(styleSheet);