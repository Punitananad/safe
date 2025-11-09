# Add this route to your Flask application (journal.py or wherever your routes are)

@calculatentrade.route('/api/update_trade/<int:trade_id>', methods=['POST'])
def update_trade(trade_id):
    try:
        data = request.get_json()
        
        # Find the trade in your database
        trade = Trade.query.get_or_404(trade_id)
        
        # Update trade fields
        trade.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        trade.symbol = data['symbol']
        trade.trade_type = data['trade_type']
        trade.quantity = int(data['quantity'])
        trade.entry_price = float(data['entry_price'])
        trade.exit_price = float(data['exit_price'])
        trade.pnl = float(data['pnl'])
        trade.result = data['result']
        if 'notes' in data:
            trade.notes = data['notes']
        
        # Save to database
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Trade updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500