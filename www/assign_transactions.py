import sys
import os
# Add the lib directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lib')))



from flask import Flask, render_template, request, redirect, url_for, jsonify, current_app as app
from orm.models import Trade, TransactionView
from orm.database import Database

# Initialize the Database instance
db_instance = Database()

app = Flask(__name__)
db_instance = Database()


@app.route('/')
def index():
    session = db_instance.get_session()
    trades = session.query(Trade).all()
    return render_template('index.html', trades=trades)

@app.route('/add_trade', methods=['GET', 'POST'])
def add_trade():
    if request.method == 'POST':
        session = db_instance.get_session()
        user_id = request.form['user_id']
        account_id = request.form['account_id']
        open_date = request.form['open_date']
        close_date = request.form['close_date']
        type = request.form['type']
        status = request.form['status']
        amount = request.form['amount']
        profit_target = request.form['profit_target']
        stop_loss_target = request.form['stop_loss_target']
        starting_margin = request.form['starting_margin']
        ending_margin = request.form['ending_margin']
        max_margin = request.form['max_margin']
        adjustments = request.form['adjustments']
        comment = request.form['comment']
        description = request.form['description']

        new_trade = Trade(
            user_id=user_id,
            account_id=account_id,
            open_date=open_date,
            close_date=close_date,
            type=type,
            status=status,
            amount=amount,
            profit_target=profit_target,
            stop_loss_target=stop_loss_target,
            starting_margin=starting_margin,
            ending_margin=ending_margin,
            max_margin=max_margin,
            adjustments=adjustments,
            comment=comment,
            description=description
        )
        session.add(new_trade)
        session.commit()
        return redirect(url_for('index'))
    return render_template('add_trade.html')

@app.route('/api/trades', methods=['GET'])
def api_trades():
    session = db_instance.get_session()
    
    # Get parameters from DataTables request
    draw = request.args.get('draw', type=int)
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    search_value = request.args.get('search[value]', type=str)
    
    # Base query
    query = session.query(Trade)
    
    # Apply search filter
    if search_value:
        query = query.filter(Trade.description.like(f'%{search_value}%'))
    
    # Get total records count
    total_records = query.count()
    
    # Apply pagination
    trades = query.offset(start).limit(length).all()
    
    # Prepare response
    data = [{
        'trade_id': t.trade_id,
        'user_id': t.user_id,
        'account_id': t.account_id,
        'open_date': t.open_date,
        'close_date': t.close_date,
        'type': t.type,
        'status': t.status,
        'amount': t.amount,
        'profit_target': t.profit_target,
        'stop_loss_target': t.stop_loss_target,
        'starting_margin': t.starting_margin,
        'ending_margin': t.ending_margin,
        'max_margin': t.max_margin,
        'adjustments': t.adjustments,
        'comment': t.comment,
        'description': t.description
    } for t in trades]
    
    return jsonify({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })

@app.route('/api/unassigned_transactions', methods=['GET'])
def api_unassigned_transactions():
    session = db_instance.get_session()
    
    # Get parameters from DataTables request
    draw = request.args.get('draw', type=int)
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    search_value = request.args.get('search[value]', type=str)
    
    # Base query
    query = session.query(TransactionView).filter_by(trade_id=None)
    
    # Apply search filter
    if search_value:
        query = query.filter(TransactionView.description.like(f'%{search_value}%'))
    
    # Get total records count
    total_records = query.count()
    
    # Apply pagination
    transactions = query.offset(start).limit(length).all()
    
    # Prepare response
    data = [{
        'select': f'<input type="checkbox" value="{t.transaction_id}">',  # Checkbox HTML
        'transaction_id': t.transaction_id,
        'account_id': t.account_id,
        'date': t.date,
        'month': t.month,
        'year': t.year,
        'position_id': t.position_id,
        'trade_id': t.trade_id,
        'order_id': t.order_id,
        'description': t.description,
        'quantity': t.quantity,
        'symbol': t.symbol,
        'underlying': t.underlying,
        'amount': t.amount,
        'commission': t.commission,
        'fees': t.fees,
        'transaction': t.transaction,
        'asset_type': t.asset_type,
        'expiration_date': t.expiration_date,
        'strike_price': t.strike_price,
        'extended_amount': t.extended_amount,
    } for t in transactions]

    return jsonify({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })

@app.route('/api/assign_transactions/<int:trade_id>', methods=['POST'])
def api_assign_transactions(trade_id):
    session = db_instance.get_session()
    data = request.json
    transaction_ids = data.get('transaction_ids', [])
    for transaction_id in transaction_ids:
        transaction = session.query(TransactionView).get(transaction_id)
        transaction.trade_id = trade_id
    session.commit()
    return '', 204

if __name__ == '__main__':
    try:
        app.run(debug=True)
    finally:
        db_instance.close()