import json
import pandas as pd

from orm.database import Database
from orm.models import Transaction, Account, Order, OrderItem, Position
from sqlalchemy import text, update, select, func

import os
import sys
import logging
from typer import Typer, Option
from typing import List, Annotated
from dotenv import load_dotenv

from broker.schwab import api, stream
from datetime import datetime, timedelta


app = Typer()

def get_transactions_from_db() -> list:
   """
   Get transaction IDs from the database using SQLAlchemy ORM.
   """

   # Query the database directly using the Account model
   transaction_query = session.query(Transaction.transaction_id).all()

   # Convert the query result to a list
   return [id[0] for id in transaction_query]

def get_accounts_from_db() -> dict:
   """
   Get accounts from the database
   """
      
   # Query the database directly using the Account model
   accounts_query = session.query(Account.account_number, Account.account_id).all()

   # Convert the query result to a dictionary
   return  {account_number: account_id for account_number, account_id in accounts_query}

def get_orders_from_db() -> dict:
   """
   Get order IDs and status from the database
   """
      
   # Query the database directly using the Account model
   orders_query = session.query(Order.order_id, Order.status).all()

   # Convert the query result to a dictionary
   return  {order_id: status for order_id, status in orders_query}



def set_log_file(logger: logging.Logger, filename: str):
    # Create a file handler
    handler = logging.FileHandler(filename)

    # Create a formatter and add it to the handler
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(handler)

@app.command()
def process_transaction_files( import_dir: str = './data/import',
                        log_dir: str = '.',
                        log_file: str = 'import_transactions.log'):
   """
   Import transactions from a directory
   """
   if log_dir != '.':
       set_log_file(logger, os.path.join(log_dir, log_file))

   logger.info(f'Importing transactions from {import_dir}')

   i = 0
   for i, filename in enumerate(os.listdir(import_dir)):

      # Skip files that are not JSON files
      if not filename.endswith('.json'):
         logger.info(f'Skipping file {filename}')
         continue

      with open(os.path.join(import_dir, filename), 'r') as f:
         activities = json.load(f)
      load_activities(activities)

      # Move the file to the processed directory
      os.rename(os.path.join(import_dir, filename), os.path.join(import_dir, 'processed', filename))
   logger.info(f'Processed {i+1} files')

   return

@app.command()
def get_transactions(account: Annotated[List[str], Option(..., "--account", help="One or more account numbers")],
                     days: int = Option(7, help="Number of days back from current date to get transactions for"),
                     start_date: str = Option(None, help="start date of date range to pull transactions for"),
                     end_date: str = Option(None, help="end date of date range to pull transactions for"),
                     debug: bool = Option(None, help="print the transaction json")) -> list:

   """
   Get transactions using the API
   """
   if start_date is None:
      start_date = datetime.now() - timedelta(days=days)
   else:
      start_date = datetime.strptime(start_date, '%Y-%m-%d')

   if end_date is None:
      end_date = datetime.now()
   else:
      end_date = datetime.strptime(end_date, '%Y-%m-%d')

   for account_number in account:
      api.initialize(accountNumber=account_number)

      for transaction_type in ('TRADE', 'DIVIDEND_OR_INTEREST'):
         activities = api.transactions.transactions(start_date, end_date, transaction_type).json()
         if debug:
            print(json.dumps(activities, indent=2))
         load_activities(activities)
   return

@app.command()
def get_positions(account: Annotated[List[str], Option(..., "--account", help="One or more account numbers")],
                  debug: bool = Option(None, help="print the transaction json")) -> list:

   for account_number in account:
      api.initialize(accountNumber=account_number)
      positions = api.accounts.getAccount(fields="positions").json()

      if debug:
         print(json.dumps(positions, indent=2))
      
      load_positions(positions)
   return


def load_positions(positions_json: str):
   """
   Transform and load positions
   """
   account_id = None
   positions = []

   accounts = get_accounts_from_db()
   account_id = accounts.get(int(positions_json['securitiesAccount']['accountNumber']), None)
   
   date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')


   for j in positions_json['securitiesAccount']['positions']:

      position = {
         'account_id': account_id,
         'date': date,
         'short_quantity': j['shortQuantity'],
         'long_quantity': j['longQuantity'],
         'average_price': j['averagePrice'],
         'maintenance_requirement': j['maintenanceRequirement'],
         'current_day_profit_loss': j['currentDayProfitLoss'],
         'market_value': j['marketValue'],
         'current_day_profit_loss_percentage': j['currentDayProfitLossPercentage'],
         'cusip': j['instrument'].get('cusip'),
         'asset_type': j['instrument'].get('putCall', j['instrument'].get('assetType')),
         'symbol': j['instrument'].get('symbol'),
         'underlying_symbol': j['instrument'].get('underlyingSymbol', j['instrument'].get('symbol')),            
         'description': j['instrument'].get('description'),
         'maturity_date': j['instrument'].get('maturityDate'),
         'variable_rate': j['instrument'].get('variableRate'),
         'net_change': j['instrument'].get('netChange',0),
      }
      if position['asset_type'] == 'COLLECTIVE_INVESTMENT': 
         position['asset_type'] = 'EQUITY'
      
      positions.append(position)
   
   store_positions(positions)
   reset_latest_positions()
   return

def store_positions(positions: list):
   """
   Store positions in the database
   """
   if len(positions) == 0:
      logger.info('No positions to store in the database. Exiting.')
      return

   positions_df = pd.DataFrame(positions)
   positions_df['date'] = pd.to_datetime(positions_df['date'])
   positions_df['maturity_date'] = pd.to_datetime(positions_df['maturity_date'])

   positions_df.to_sql('positions', engine, if_exists='append', index=False)

   reset_latest_positions()

   return

def reset_latest_positions():
    """
    Reset the latest positions in the database using SQLAlchemy ORM
    """
    # First, reset all 'latest' flags to 'N'
    session.query(Position).update({"latest": "N"}, synchronize_session=False)

    # Then, identify the most recent position for each account and set 'latest' to 'Y'
    subq = session.query(
        Position.account_id,
        func.max(Position.date).label('max_date')
    ).group_by(Position.account_id).subquery('max_dates')

    # Correlated update statement
    update_stmt = update(Position).\
        values(latest="Y").\
        where(Position.date == subq.c.max_date).\
        where(Position.account_id == subq.c.account_id)
    session.execute(update_stmt)

    session.commit()
    return

@app.command()
def get_orders(account: Annotated[List[str], Option(..., "--account", help="One or more account numbers")],
                     days: int = Option(7, help="Number of days back from current date to get transactions for"),
                     start_date: str = Option(None, help="start date of date range to pull transactions for"),
                     end_date: str = Option(None, help="end date of date range to pull transactions for"),
                     status: str = Option(None, help="status of the order"),
                     debug: bool = Option(None, help="print the transaction json")) -> list:

   """
   Get orders using the API
   """
   if start_date is None:
      start_date = datetime.now() - timedelta(days=days)
   else:
      start_date = datetime.strptime(start_date, '%Y-%m-%d')

   if end_date is None:
      end_date = datetime.now()
   else:
      end_date = datetime.strptime(end_date, '%Y-%m-%d')


   for account_number in account:
      api.initialize(accountNumber=account_number)

      accounts = get_accounts_from_db()
      account_id = accounts.get(int(account_number), None)

      orders = api.orders.getOrders(maxResults=5000, fromEnteredTime=start_date, toEnteredTime=end_date, status=status).json()
      if debug:
         print(json.dumps(orders, indent=2))

      existing_orders = get_orders_from_db()

      skipped_orders = 0
      updated_orders = 0
      new_orders = 0

      for order_json in orders:
         order_id = order_json.get('orderId')
         status = order_json.get('status')

         if existing_orders.get(order_id) is not None and existing_orders.get(order_id) == status:
            # Order exists in db but has the same status than the one from the API
            # Skip
            skipped_orders += 1
            continue
         elif existing_orders.get(order_id) is not None and existing_orders.get(order_id) != status:
            # Order exists in the db and status has changed
            # Delete the order from the db and insert the the updated one from the API
            # Rows in order_items table will be deleted by the cascade delete
            session.query(Order).filter(Order.order_id == order_id).delete()
            session.commit()
            updated_orders += 1
         else:
            # Order does not exist in the db
            new_orders += 1

         order = Order(
               account_id = account_id,
               entered_time = datetime.strptime(order_json.get('enteredTime'),"%Y-%m-%dT%H:%M:%S%z"),
               order_id = order_json.get('orderId'),
               order_type = order_json.get('orderType'),
               cancel_time = datetime.strptime(order_json.get('cancelTime'),"%Y-%m-%dT%H:%M:%S%z"),
               quantity = order_json.get('quantity'),
               filled_quantity = order_json.get('filledQuantity'),
               remaining_quantity = order_json.get('remainingQuantity'),
               requested_destination = order_json.get('requestedDestination'),
               order_strategy_type = order_json.get('orderStrategyType'),
               status = order_json.get('status'),
               price = order_json.get('price'),
               order_duration = order_json.get('orderDuration'),
               order_class = order_json.get('orderClass')
               )
         session.add(order)
         session.commit()

         for order_item in order_json['orderLegCollection']:
            strike_price = None
            multiplier = 1
            if order_item.get('orderLegType') == 'OPTION':
               strike_price = order_item['instrument'].get('symbol')[-8:-2]
               strike_price = int(strike_price) / 10  # Convert to a decimal number
            if 'instrument' in order_item and 'optionDeliverables' in order_item['instrument']:
               multiplier = order_item['instrument']['optionDeliverables'][0]['deliverableUnits']
            else:
               multiplier = 1

            order_item = OrderItem(
               account_id = account_id,
               order_id = order_id,
               order_leg_type = order_item.get('orderLegType'),
               instruction = order_item.get('instruction'),
               quantity = order_item.get('quantity'),
               asset_type = order_item['instrument'].get('assetType'),
               symbol = order_item['instrument'].get('symbol'),
               description = order_item['instrument'].get('description'),
               cusip = order_item['instrument'].get('cusip'),
               put_call = order_item['instrument'].get('putCall'),
               underlying_symbol = order_item['instrument'].get('underlyingSymbol'),
               maturity_date = order_item['instrument'].get('maturityDate'),
               strike_price = strike_price,
               multiplier = multiplier,
               order_item_id = order_item.get('legId')
            )
            session.add(order_item)
            session.commit()
      logger.info(f'Orders: {new_orders} new orders, {updated_orders} updated orders, {skipped_orders} skipped orders')


def load_activities(activities: list):
   """
   Load activities into the database
   """
   account_id = None

   # Get the existing transactions and accounts from the database
   existing_transactions = get_transactions_from_db()
   accounts = get_accounts_from_db()

   i = 0
   for i, activity in enumerate(activities):

      account_id = accounts.get(int(activity['accountNumber']), None)
      if account_id is None:
         logger.error(f'Account ID {activity["accountNumber"]} not found in the database. Skipping')
         continue
      if int(activity['activityId']) in existing_transactions:
         logger.error(f'Transaction: {activity["activityId"]} alraday exists in the database. Skipping')
         continue
      transaction = load_transaction(activity, account_id)

      for transferItem in activity['transferItems']:
         assetType = transferItem['instrument']['assetType']
         load_dividend_or_interest(transaction, activity, transferItem, assetType)
         load_fee(transaction, activity, transferItem, assetType)
         load_option(transaction, activity, transferItem, assetType)
         load_equity(transaction, activity, transferItem, assetType)
      
   transaction_count = store_transactions(transactions, transaction_items)
   logger.info(f'{transaction_count} transactions loaded to the db')
   transactions.clear()
   transaction_items.clear()

   logger.info(f'Processed {i+1} transactions')

   return

def load_transaction(activity: dict, account_id: int):
   """
   Transform and load activity into a transaction
   """
   transaction = {
         'transaction_id': activity['activityId'],
         'date': activity['time'],
         'account_id': account_id,
         'type': activity['type'],
         'status': activity['status'],
         'amount': activity['netAmount'],
         'order_id': activity.get('orderId'),
         'description': activity.get('description'),
         'position_id': activity.get('positionId')
   }
   transactions.append(transaction)
   return transaction

def load_dividend_or_interest(transaction: dict, activity: dict, transferItem: dict, assetType: str):

   """
   transform activity of type dividend_or_interest to a transaction item
   """
   item = {}

   if transaction['type'] != 'DIVIDEND_OR_INTEREST':
      return

   item['transaction_id'] = activity['activityId']
   item['asset_type'] = assetType

   # Check to see if description contains the word interest
   if 'interest' in transaction['description'].lower():
      item['transaction'] = 'INTEREST'
   else:
      item['transaction'] = 'DIVIDEND'

   if 'dividend~' in transaction['description'].lower():
      item['symbol'] = transaction['description'].split('~')[1].strip()
   item['amount'] = transferItem['amount']
   item['extended_amount'] = transferItem['amount']
   item['quantity'] = 0

   transaction_items.append(item)

   return

def load_fee(transaction: dict, activity: dict,transferItem: dict, assetType: str):
   if transaction['type'] != 'TRADE' or assetType != 'CURRENCY':
      return

   item = {} 
   item['transaction_id'] = activity['activityId']
   item['asset_type'] = assetType

   item['amount'] = transferItem['cost']
   item['extended_amount'] = transferItem['cost']
   item['quantity'] = 0
   item['transaction'] = 'FEE'
   if 'feeType' in transferItem:
      item['description'] = transferItem['feeType']
   else:
      item['description'] = 'Not Specified'

   transaction_items.append(item)
   return

def load_option(transaction: dict, activity: dict, transferItem: dict, assetType: str):
   if assetType != 'OPTION':
      return

   item = {}

   item['transaction_id'] = activity['activityId']
   item['asset_type'] = transferItem['instrument']['putCall']
   item['symbol'] = transferItem['instrument'].get('symbol')  
   item['description'] = transferItem['instrument']['description']
   item['expiration_date'] = transferItem['instrument']['expirationDate']
   item['strike_price'] = transferItem['instrument']['strikePrice']
   item['underlying'] = transferItem['instrument']['underlyingSymbol']
   item['quantity'] = abs(transferItem['amount'])
   item['amount'] = transferItem['price']
   item['extended_amount'] = transferItem['cost']
   item['position_effect'] = transferItem.get('positionEffect')
   if transferItem['amount'] < 0:
      item['transaction'] = 'SELL'
   else:
      item['transaction'] = 'BUY'

   transaction_items.append(item)
   return

def load_equity(transaction: dict, activity: dict, transferItem: dict, assetType: str):
   if assetType != 'EQUITY':
      return

   item = {}

   item['transaction_id'] = activity['activityId']
   item['asset_type'] = assetType

   item['symbol'] = transferItem['instrument']['symbol']
   item['quantity'] = abs(transferItem['amount'])
   item['amount'] = transferItem['price']
   item['extended_amount'] = transferItem['cost']
   if transferItem['cost'] > 0:
      item['transaction'] = 'SELL'
   else:
      item['transaction'] = 'BUY'

   transaction_items.append(item)

   return

def load_fixed_income(transaction: dict, activity: dict, transferItem: dict, assetType: str):
   if assetType != 'FIXED_INCOME':
      return

   item = {}

   item['transaction_id'] = activity['activityId']
   item['asset_type'] = assetType

   item['symbol'] = transferItem['instrument']['symbol']
   item['quantity'] = abs(transferItem['amount'])

   multiplier = 1
   if 'multiplier' in transferItem['instrument']:
      multiplier = transferItem['instrument']['multiplier']

   item['amount'] = transferItem['price'] * multiplier
   item['extended_amount'] = transferItem['cost']
   item['expiration_date'] = transferItem['instrument']['maturityDate']
   if transferItem['amount'] > 0:
      item['transaction'] = 'BUY'
   else:
      item['transaction'] = 'SELL'

   transaction_items.append(item)

   return

def store_transactions(transactions: list, transaction_items: list) -> int:
   """
   Store transactions and transaction_items in the database
   """

   if len(transactions) == 0:
      logger.info('No transactions to store in the database. Exiting.')
      return 0
   
   # Create a DataFrame from the orders list
   transactions_df = pd.DataFrame(transactions)
   transactions_df['date'] = pd.to_datetime(transactions_df['date'])
 
   transaction_items_df = pd.DataFrame(transaction_items)

   # Check to see if expiration_date is a column in the DataFrame
   if 'expiration_date' in transaction_items_df.columns:
      transaction_items_df['expiration_date'] = pd.to_datetime(transaction_items_df['expiration_date'])

   # Write the DataFrame to the database
   transactions_df.to_sql('transactions', engine, if_exists='append', index=False)
   transaction_items_df.to_sql('transaction_items', engine, if_exists='append', index=False)
  
   return len(transactions)

if __name__ == '__main__':
   
   load_dotenv()
   db_host = os.getenv('db_host')
   db_user = os.getenv('db_user')
   db_password = os.getenv('db_password')
   db_name = os.getenv('db_name')
   
   # connect to the database
   db = Database(db_name, db_user, db_password, db_host)
   engine = db.engine
   session = db.Session

   # Create a logger
   logger = logging.getLogger()
   logger.setLevel(logging.INFO)

   # Create a console handler and set level to info
   handler = logging.StreamHandler(sys.stdout)
   handler.setLevel(logging.INFO)

   # Create a formatter
   formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

   # Add formatter to handler
   handler.setFormatter(formatter)

   # Add handler to logger
   logger.addHandler(handler)
   
   transactions = []
   transaction_items = []
   orders = []
   order_items = []
   
   app()
   db.close()





