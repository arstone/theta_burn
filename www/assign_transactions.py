import sys
import os
# Add the lib directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lib')))


from sqlalchemy import asc, desc, or_, func
from flask import Flask, render_template, request, redirect, url_for, jsonify, current_app as app
from orm.models import Trade, TransactionView, Account, Position
from orm.database import Database

app = Flask(__name__)

db_instance = Database()


@app.route('/')
def index():
    session = db_instance.get_session(singleton=False)
    trades = session.query(Trade).all()
    return render_template('index.html', trades=trades)


@app.route('/api/add_trade', methods=['POST'])
def api_add_trade():
    session = db_instance.get_session(singleton=False)
    data = request.form.to_dict()
    trade = Trade(
        user_id=data['user_id'],
        account_id=data['account_id'],
        open_date=data['open_date'],
        close_date=data['close_date'],
        description=data['description'],
        type=data['type'],
        status=data['status'],
        amount=data['amount'],
        profit_target=data['profit_target'],
        stop_loss_target=data['stop_loss_target'],
        starting_margin=data['starting_margin'],
        ending_margin=data['ending_margin'],
        max_margin=data['max_margin'],
        adjustments=data.get('adjustments'),
        comment=data.get('comment')
    )
    session.add(trade)
    session.commit()
    return jsonify({'success': True})

@app.route('/api/trades', methods=['GET'])
def api_trades():
    session = db_instance.get_session(singleton=False)
    
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

@app.route('/api/transaction_columns', methods=['GET'])
def api_transaction_columns():
    columns = [
        {"data": "select", "orderable": False, "className": "select-checkbox"}
    ]
    for column in TransactionView.__table__.columns:
        columns.append({"data": column.name})
    return jsonify(columns)

@app.route('/api/unassigned_transactions', methods=['GET'])
def api_unassigned_transactions():
    session = db_instance.get_session(singleton=False)
    
    # Get parameters from DataTables request
    draw = request.args.get('draw', type=int)
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    search_value = request.args.get('search[value]', type=str)
    order_column = request.args.get('order[0][column]', type=int)
    order_dir = request.args.get('order[0][dir]', type=str)
    
    # Base query
    query = session.query(TransactionView).filter_by(trade_id=None)
    
    # Apply search filter
    if search_value:
        search_filter = or_(
            TransactionView.description.like(f'%{search_value}%'),
            TransactionView.symbol.like(f'%{search_value}%'),
            TransactionView.underlying.like(f'%{search_value}%'),
            TransactionView.transaction_id.like(f'%{search_value}%'),
            TransactionView.trade_id.like(f'%{search_value}%'),
            TransactionView.order_id.like(f'%{search_value}%')
        )
        query = query.filter(search_filter)    

    # Apply sorting
    if order_column is not None and order_dir is not None:
        column_name = request.args.get(f'columns[{order_column}][data]')
        if column_name != 'select':  # Skip the 'select' column
            column_attr = getattr(TransactionView, column_name)
            if order_dir == 'asc':
                query = query.order_by(asc(column_attr))
            else:
                query = query.order_by(desc(column_attr))
    
    # Get total records count
    total_records = query.count()
    
    # Apply pagination
    transactions = query.offset(start).limit(length).all()
    
    # Prepare response
    data = [t.to_dict() for t in transactions]
    for item in data:
        item['select'] = f'<input type="checkbox" value="{item["transaction_id"]}">'  # Add checkbox HTML
    
    # Calculate total extended amount
    total_extended_amount = query.with_entities(func.sum(TransactionView.extended_amount)).scalar() or 0
    
    return jsonify({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data,
        'totalExtendedAmount': total_extended_amount})

@app.route('/api/assign_transactions/<int:trade_id>', methods=['POST'])
def api_assign_transactions(trade_id):
    session = db_instance.get_session(singleton=False)
    data = request.json
    transaction_ids = data.get('transaction_ids', [])
    for transaction_id in transaction_ids:
        transaction = session.query(TransactionView).get(transaction_id)
        transaction.trade_id = trade_id
    session.commit()
    return '', 204

@app.route('/api/accounts', methods=['GET'])
def api_accounts():
    session = db_instance.get_session(singleton=False)
    accounts = session.query(Account).all()
    data = [{'account_id': account.account_id, 'name': account.name} for account in accounts]
    return jsonify(data)


@app.route('/api/positions', methods=['GET'])
def api_positions():
    # Get parameters from DataTables request
    draw = request.args.get('draw', type=int)
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    search_value = request.args.get('search[value]', type=str)
    order_column = request.args.get('order[0][column]', type=int)
    order_dir = request.args.get('order[0][dir]', type=str)

    session = db_instance.get_session(singleton=False)
    query = session.query(Position).filter_by(latest='Y')
    total_records = query.count()

    # Apply pagination
    positions = query.offset(start).limit(length).all()
    data = [p.to_dict() for p in positions]

    return jsonify({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })

@app.route('/api/position_columns', methods=['GET'])
def api_position_columns():
    columns = []
    for column in Position.__table__.columns:
        columns.append({"data": column.name})
    return jsonify(columns)

if __name__ == '__main__':
    try:
        app.run(debug=True)
    finally:
        db_instance.close()
