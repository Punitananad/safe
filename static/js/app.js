// Modern Trading Journal Frontend
class TradingApp {
    constructor() {
        this.currentPage = 'dashboard';
        this.trades = [];
        this.mistakes = [];
        this.strategies = [];
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadInitialData();
        this.renderCurrentPage();
    }

    setupEventListeners() {
        // Navigation
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-page]')) {
                e.preventDefault();
                this.navigateTo(e.target.dataset.page);
            }
        });

        // Mobile menu toggle
        const mobileMenuBtn = document.getElementById('mobile-menu-btn');
        const mobileMenu = document.getElementById('mobile-menu');
        if (mobileMenuBtn) {
            mobileMenuBtn.addEventListener('click', () => {
                mobileMenu.classList.toggle('hidden');
            });
        }
    }

    async loadInitialData() {
        try {
            const [tradesRes, mistakesRes, strategiesRes] = await Promise.all([
                fetch('/calculatentrade_journal/api/trades'),
                fetch('/calculatentrade_journal/api/mistakes'),
                fetch('/calculatentrade_journal/api/strategies')
            ]);

            this.trades = await tradesRes.json();
            this.mistakes = await mistakesRes.json();
            this.strategies = await strategiesRes.json();
        } catch (error) {
            console.error('Failed to load data:', error);
        }
    }

    navigateTo(page) {
        this.currentPage = page;
        this.updateActiveNav(page);
        this.renderCurrentPage();
        history.pushState({page}, '', `#${page}`);
    }

    updateActiveNav(page) {
        document.querySelectorAll('[data-page]').forEach(link => {
            link.classList.remove('bg-blue-600', 'text-white');
            link.classList.add('text-gray-600', 'hover:text-blue-600');
        });
        
        const activeLink = document.querySelector(`[data-page="${page}"]`);
        if (activeLink) {
            activeLink.classList.add('bg-blue-600', 'text-white');
            activeLink.classList.remove('text-gray-600', 'hover:text-blue-600');
        }
    }

    renderCurrentPage() {
        const content = document.getElementById('main-content');
        
        switch(this.currentPage) {
            case 'dashboard':
                content.innerHTML = this.renderDashboard();
                this.initDashboardCharts();
                break;
            case 'trades':
                content.innerHTML = this.renderTrades();
                break;
            case 'mistakes':
                content.innerHTML = this.renderMistakes();
                break;
            case 'strategies':
                content.innerHTML = this.renderStrategies();
                break;
            case 'calculators':
                content.innerHTML = this.renderCalculators();
                break;
            case 'reports':
                content.innerHTML = this.renderReports();
                this.initReportCharts();
                break;
            default:
                content.innerHTML = this.renderDashboard();
        }
    }

    renderDashboard() {
        const totalPnL = this.trades.trades?.reduce((sum, trade) => sum + trade.pnl, 0) || 0;
        const winRate = this.calculateWinRate();
        const totalTrades = this.trades.trades?.length || 0;

        return `
            <div class="space-y-6">
                <!-- Header -->
                <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                    <div>
                        <h1 class="text-3xl font-bold text-gray-900">Trading Dashboard</h1>
                        <p class="text-gray-600">Welcome back! Here's your trading overview.</p>
                    </div>
                    <button onclick="app.openTradeModal()" class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors">
                        <i class="fas fa-plus mr-2"></i>Add Trade
                    </button>
                </div>

                <!-- KPI Cards -->
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    <div class="bg-gradient-to-r from-blue-500 to-blue-600 text-white p-6 rounded-xl shadow-lg">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-blue-100">Total P&L</p>
                                <p class="text-2xl font-bold">₹${totalPnL.toLocaleString()}</p>
                            </div>
                            <i class="fas fa-chart-line text-3xl text-blue-200"></i>
                        </div>
                    </div>
                    
                    <div class="bg-gradient-to-r from-green-500 to-green-600 text-white p-6 rounded-xl shadow-lg">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-green-100">Win Rate</p>
                                <p class="text-2xl font-bold">${winRate}%</p>
                            </div>
                            <i class="fas fa-target text-3xl text-green-200"></i>
                        </div>
                    </div>
                    
                    <div class="bg-gradient-to-r from-purple-500 to-purple-600 text-white p-6 rounded-xl shadow-lg">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-purple-100">Total Trades</p>
                                <p class="text-2xl font-bold">${totalTrades}</p>
                            </div>
                            <i class="fas fa-exchange-alt text-3xl text-purple-200"></i>
                        </div>
                    </div>
                    
                    <div class="bg-gradient-to-r from-orange-500 to-orange-600 text-white p-6 rounded-xl shadow-lg">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-orange-100">Active Strategies</p>
                                <p class="text-2xl font-bold">${this.strategies.strategies?.length || 0}</p>
                            </div>
                            <i class="fas fa-brain text-3xl text-orange-200"></i>
                        </div>
                    </div>
                </div>

                <!-- Charts Row -->
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div class="bg-white p-6 rounded-xl shadow-lg">
                        <h3 class="text-lg font-semibold mb-4">Equity Curve</h3>
                        <canvas id="equityChart" height="200"></canvas>
                    </div>
                    
                    <div class="bg-white p-6 rounded-xl shadow-lg">
                        <h3 class="text-lg font-semibold mb-4">P&L Distribution</h3>
                        <canvas id="pnlChart" height="200"></canvas>
                    </div>
                </div>

                <!-- Recent Trades -->
                <div class="bg-white rounded-xl shadow-lg p-6">
                    <h3 class="text-lg font-semibold mb-4">Recent Trades</h3>
                    <div class="overflow-x-auto">
                        ${this.renderRecentTradesTable()}
                    </div>
                </div>
            </div>
        `;
    }

    renderTrades() {
        return `
            <div class="space-y-6">
                <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                    <h1 class="text-3xl font-bold text-gray-900">Trades</h1>
                    <div class="flex gap-3">
                        <input type="text" placeholder="Search trades..." class="px-4 py-2 border rounded-lg">
                        <button onclick="app.openTradeModal()" class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700">
                            <i class="fas fa-plus mr-2"></i>Add Trade
                        </button>
                    </div>
                </div>

                <div class="bg-white rounded-xl shadow-lg overflow-hidden">
                    ${this.renderTradesTable()}
                </div>
            </div>
        `;
    }

    renderMistakes() {
        return `
            <div class="space-y-6">
                <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                    <h1 class="text-3xl font-bold text-gray-900">Trading Mistakes</h1>
                    <button onclick="app.openMistakeModal()" class="bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700">
                        <i class="fas fa-plus mr-2"></i>Add Mistake
                    </button>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    ${this.renderMistakeCards()}
                </div>
            </div>
        `;
    }

    renderStrategies() {
        return `
            <div class="space-y-6">
                <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                    <h1 class="text-3xl font-bold text-gray-900">Trading Strategies</h1>
                    <button onclick="app.openStrategyModal()" class="bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700">
                        <i class="fas fa-plus mr-2"></i>Add Strategy
                    </button>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    ${this.renderStrategyCards()}
                </div>
            </div>
        `;
    }

    renderCalculators() {
        return `
            <div class="space-y-6">
                <h1 class="text-3xl font-bold text-gray-900">Trading Calculators</h1>
                
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    <div class="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-shadow cursor-pointer" onclick="window.location.href='/intraday_calculator'">
                        <div class="text-center">
                            <i class="fas fa-chart-line text-4xl text-blue-600 mb-4"></i>
                            <h3 class="text-xl font-semibold mb-2">Intraday Calculator</h3>
                            <p class="text-gray-600">Calculate intraday trading positions and risk</p>
                        </div>
                    </div>
                    
                    <div class="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-shadow cursor-pointer" onclick="window.location.href='/delivery_calculator'">
                        <div class="text-center">
                            <i class="fas fa-truck text-4xl text-green-600 mb-4"></i>
                            <h3 class="text-xl font-semibold mb-2">Delivery Calculator</h3>
                            <p class="text-gray-600">Calculate delivery trading positions</p>
                        </div>
                    </div>
                    
                    <div class="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-shadow cursor-pointer" onclick="window.location.href='/fo_calculator'">
                        <div class="text-center">
                            <i class="fas fa-coins text-4xl text-purple-600 mb-4"></i>
                            <h3 class="text-xl font-semibold mb-2">F&O Calculator</h3>
                            <p class="text-gray-600">Calculate futures and options positions</p>
                        </div>
                    </div>
                    
                    <div class="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-shadow cursor-pointer" onclick="window.location.href='/mtf_calculator'">
                        <div class="text-center">
                            <i class="fas fa-layer-group text-4xl text-orange-600 mb-4"></i>
                            <h3 class="text-xl font-semibold mb-2">MTF Calculator</h3>
                            <p class="text-gray-600">Calculate margin trading positions</p>
                        </div>
                    </div>
                    
                    <div class="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-shadow cursor-pointer" onclick="window.location.href='/swing_calculator'">
                        <div class="text-center">
                            <i class="fas fa-wave-square text-4xl text-teal-600 mb-4"></i>
                            <h3 class="text-xl font-semibold mb-2">Swing Calculator</h3>
                            <p class="text-gray-600">Calculate swing trading positions</p>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    renderReports() {
        return `
            <div class="space-y-6">
                <h1 class="text-3xl font-bold text-gray-900">Trading Reports</h1>
                
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div class="bg-white p-6 rounded-xl shadow-lg">
                        <h3 class="text-lg font-semibold mb-4">Monthly Performance</h3>
                        <canvas id="monthlyChart" height="200"></canvas>
                    </div>
                    
                    <div class="bg-white p-6 rounded-xl shadow-lg">
                        <h3 class="text-lg font-semibold mb-4">Strategy Performance</h3>
                        <canvas id="strategyChart" height="200"></canvas>
                    </div>
                </div>
                
                <div class="bg-white p-6 rounded-xl shadow-lg">
                    <h3 class="text-lg font-semibold mb-4">Detailed Analytics</h3>
                    ${this.renderAnalyticsTable()}
                </div>
            </div>
        `;
    }

    renderRecentTradesTable() {
        const recentTrades = this.trades.trades?.slice(0, 5) || [];
        
        if (recentTrades.length === 0) {
            return '<p class="text-gray-500 text-center py-8">No trades found</p>';
        }

        return `
            <table class="min-w-full">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Symbol</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">P&L</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-200">
                    ${recentTrades.map(trade => `
                        <tr class="hover:bg-gray-50">
                            <td class="px-6 py-4 whitespace-nowrap font-medium">${trade.symbol}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-gray-600">${trade.date}</td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <span class="px-2 py-1 text-xs rounded-full ${trade.trade_type === 'long' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                                    ${trade.trade_type}
                                </span>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap font-medium ${trade.pnl >= 0 ? 'text-green-600' : 'text-red-600'}">
                                ₹${trade.pnl.toLocaleString()}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <span class="px-2 py-1 text-xs rounded-full ${trade.result === 'win' ? 'bg-green-100 text-green-800' : trade.result === 'loss' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-800'}">
                                    ${trade.result}
                                </span>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    calculateWinRate() {
        const trades = this.trades.trades || [];
        if (trades.length === 0) return 0;
        
        const wins = trades.filter(trade => trade.result === 'win').length;
        return Math.round((wins / trades.length) * 100);
    }

    initDashboardCharts() {
        this.initEquityChart();
        this.initPnLChart();
    }

    initEquityChart() {
        const ctx = document.getElementById('equityChart');
        if (!ctx) return;

        const trades = this.trades.trades || [];
        let cumulative = 0;
        const data = trades.map(trade => {
            cumulative += trade.pnl;
            return cumulative;
        });

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: trades.map((_, i) => `Trade ${i + 1}`),
                datasets: [{
                    label: 'Equity Curve',
                    data: data,
                    borderColor: 'rgb(59, 130, 246)',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    tension: 0.1,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false
                    }
                }
            }
        });
    }

    initPnLChart() {
        const ctx = document.getElementById('pnlChart');
        if (!ctx) return;

        const trades = this.trades.trades || [];
        const wins = trades.filter(t => t.result === 'win').length;
        const losses = trades.filter(t => t.result === 'loss').length;
        const breakeven = trades.filter(t => t.result === 'breakeven').length;

        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Wins', 'Losses', 'Breakeven'],
                datasets: [{
                    data: [wins, losses, breakeven],
                    backgroundColor: [
                        'rgb(34, 197, 94)',
                        'rgb(239, 68, 68)',
                        'rgb(156, 163, 175)'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    }

    openTradeModal() {
        // Implementation for trade modal
        console.log('Opening trade modal');
    }

    openMistakeModal() {
        // Implementation for mistake modal
        console.log('Opening mistake modal');
    }

    openStrategyModal() {
        // Implementation for strategy modal
        console.log('Opening strategy modal');
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new TradingApp();
});