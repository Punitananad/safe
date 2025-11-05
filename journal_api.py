"""
Enhanced API endpoints for Trading Journal
Supports advanced charts, broker connections, and data import
"""

from flask import Blueprint, request, jsonify, session
from datetime import datetime, timedelta
import json
import random

journal_api = Blueprint('journal_api', __name__, url_prefix='/calculatentrade_journal/api')

# Mock data for demonstration - replace with actual database queries
MOCK_TRADES = [
    {'date': '2024-01-15', 'pnl': 150.50, 'result': 'win'},
    {'date': '2024-01-16', 'pnl': -75.25, 'result': 'loss'},
    {'date': '2024-01-17', 'pnl': 200.00, 'result': 'win'},
    {'date': '2024-01-18', 'pnl': 0.00, 'result': 'breakeven'},
    {'date': '2024-01-19', 'pnl': -120.75, 'result': 'loss'},
]

@journal_api.route('/chart-data/pnl')
def get_pnl_chart_data():
    """Get P&L chart data for specified timeframe"""
    timeframe = request.args.get('timeframe', '30d')
    
    # Generate mock cumulative P&L data
    days = 30 if timeframe == '30d' else 7 if timeframe == '7d' else 90
    
    labels = []
    values = []
    cumulative_pnl = 0
    
    for i in range(days):
        date = datetime.now() - timedelta(days=days-i-1)
        labels.append(date.strftime('%Y-%m-%d'))
        
        # Mock daily P&L
        daily_pnl = random.uniform(-100, 150)
        cumulative_pnl += daily_pnl
        values.append(round(cumulative_pnl, 2))
    
    return jsonify({
        'ok': True,
        'labels': labels,
        'values': values
    })

@journal_api.route('/chart-data/winloss')
def get_winloss_chart_data():
    """Get win/loss distribution data"""
    # Mock data - replace with actual database query
    return jsonify({
        'ok': True,
        'wins': 15,
        'losses': 8,
        'breakeven': 2
    })

@journal_api.route('/broker/status')
def get_broker_status():
    """Check broker connection status"""
    broker = request.args.get('broker')
    
    # Mock connection status - replace with actual broker API calls
    mock_status = {
        'kite': random.choice([True, False]),
        'dhan': random.choice([True, False]),
        'angel': random.choice([True, False])
    }
    
    connected = mock_status.get(broker, False)
    
    return jsonify({
        'ok': True,
        'connected': connected,
        'broker': broker,
        'message': 'Connected successfully' if connected else 'Not connected'
    })

@journal_api.route('/broker/trades')
def get_broker_trades():
    """Fetch trades from broker"""
    broker = request.args.get('broker')
    from_date = request.args.get('from')
    to_date = request.args.get('to')
    symbol = request.args.get('symbol')
    
    # Mock trade data - replace with actual broker API calls
    mock_trades = [
        {
            'tradingsymbol': 'RELIANCE',
            'transaction_type': 'BUY',
            'quantity': 10,
            'average_price': 2450.50,
            'order_timestamp': '2024-01-15T09:30:00',
            'trade_id': 'T001'
        },
        {
            'tradingsymbol': 'TCS',
            'transaction_type': 'SELL',
            'quantity': 5,
            'average_price': 3650.75,
            'order_timestamp': '2024-01-15T14:30:00',
            'trade_id': 'T002'
        }
    ]
    
    # Filter by symbol if provided
    if symbol:
        mock_trades = [t for t in mock_trades if symbol.upper() in t['tradingsymbol']]
    
    return jsonify({
        'ok': True,
        'data': mock_trades,
        'broker': broker,
        'count': len(mock_trades)
    })

@journal_api.route('/broker/orders')
def get_broker_orders():
    """Fetch orders from broker"""
    broker = request.args.get('broker')
    
    # Mock order data
    mock_orders = [
        {
            'order_id': 'O001',
            'tradingsymbol': 'RELIANCE',
            'transaction_type': 'BUY',
            'quantity': 10,
            'price': 2450.00,
            'status': 'COMPLETE',
            'order_timestamp': '2024-01-15T09:30:00'
        }
    ]
    
    return jsonify({
        'ok': True,
        'data': mock_orders,
        'broker': broker
    })

@journal_api.route('/broker/positions')
def get_broker_positions():
    """Fetch current positions from broker"""
    broker = request.args.get('broker')
    
    # Mock position data
    mock_positions = [
        {
            'tradingsymbol': 'RELIANCE',
            'quantity': 10,
            'average_price': 2450.50,
            'last_price': 2475.25,
            'pnl': 247.50,
            'product': 'CNC'
        }
    ]
    
    return jsonify({
        'ok': True,
        'data': mock_positions,
        'broker': broker
    })

@journal_api.route('/trades/import', methods=['POST'])
def import_trade():
    """Import a single trade to the journal"""
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['symbol', 'entry_price', 'quantity', 'trade_type']
    for field in required_fields:
        if field not in data:
            return jsonify({
                'ok': False,
                'error': f'Missing required field: {field}'
            }), 400
    
    # Mock import - replace with actual database insertion
    trade_id = f"T{random.randint(1000, 9999)}"
    
    return jsonify({
        'ok': True,
        'trade_id': trade_id,
        'message': 'Trade imported successfully'
    })

@journal_api.route('/analytics')
def get_analytics():
    """Get advanced analytics data"""
    # Mock analytics - replace with actual calculations
    return jsonify({
        'ok': True,
        'avg_win': 175.50,
        'avg_loss': -95.25,
        'profit_factor': 1.84,
        'max_drawdown': -450.75,
        'sharpe_ratio': 1.23,
        'total_volume': 125000,
        'best_symbol': 'RELIANCE',
        'most_traded': 'TCS'
    })

@journal_api.route('/stats')
def get_stats():
    """Get basic trading statistics"""
    return jsonify({
        'ok': True,
        'total_pnl': 1250.75,
        'total_trades': 25,
        'win_rate': 68.0,
        'winning_trades': 17,
        'losing_trades': 8
    })

@journal_api.route('/trades/<int:trade_id>')
def get_trade_details(trade_id):
    """Get detailed information about a specific trade"""
    # Mock trade details - replace with actual database query
    mock_trade = {
        'id': trade_id,
        'symbol': 'RELIANCE',
        'date': '2024-01-15',
        'trade_type': 'long',
        'entry_price': 2450.50,
        'exit_price': 2475.25,
        'quantity': 10,
        'pnl': 247.50,
        'result': 'win',
        'notes': 'Good breakout trade',
        'strategy': {'name': 'Breakout Strategy'}
    }
    
    return jsonify(mock_trade)

@journal_api.route('/trades/<int:trade_id>', methods=['DELETE'])
def delete_trade(trade_id):
    """Delete a trade from the journal"""
    # Mock deletion - replace with actual database deletion
    return jsonify({
        'success': True,
        'message': 'Trade deleted successfully'
    })

# Error handlers
@journal_api.errorhandler(404)
def not_found(error):
    return jsonify({
        'ok': False,
        'error': 'Endpoint not found'
    }), 404

@journal_api.errorhandler(500)
def internal_error(error):
    return jsonify({
        'ok': False,
        'error': 'Internal server error'
    }), 500