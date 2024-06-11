import json
import pandas as pd

from orm.database import Database
from orm.models import Transaction, TransactionItem, Account, Order, OrderItem, Position
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
         transactions = json.load(f)

      accounts = get_accounts_from_db()
      account_id = accounts.get(transactions[0]['accountId'], None)

      if account_id is None:
         logger.error(f'Account ID {transactions[0]["accountId"]} not found in the database. Skipping')
         continue

      store_transactions(account_id, transactions)

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

   accounts = get_accounts_from_db()
   for account_number in account:
      api.initialize(accountNumber=account_number)

      account_id = accounts.get(int(account_number), None)

      for transaction_type in ('TRADE', 'DIVIDEND_OR_INTEREST'):
         logger.info(f'Getting {transaction_type} transactions for account {account_number}')
         transactions = api.transactions.transactions(start_date, end_date, transaction_type).json()
         if debug:
            print(json.dumps(transactions, indent=2))
         result = store_transactions(account_id, transactions)
         logger.info(f'Loaded {result["new_transactions"]} new transactions, skipped {result["skipped_transactions"]} transactions')
   return

@app.command()
def get_positions(account: Annotated[List[str], Option(..., "--account", help="One or more account numbers")],
                  debug: bool = Option(None, help="print the transaction json")) -> list:

   for account_number in account:
      api.initialize(accountNumber=account_number)
      positions_json = api.accounts.getAccount(fields="positions").json()

      if debug:
         print(json.dumps(positions_json, indent=2))
      
      accounts = get_accounts_from_db()
      account_id = accounts.get(int(positions_json['securitiesAccount']['accountNumber']), None)

      results = store_positions(account_id, positions_json)
      logger.info(f'Updated {results}')
      
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

      result = store_orders(account_id, orders)
      logger.info(f'Loaded {result["new_orders"]} new orders, updated {result["updated_orders"]} orders, skipped {result["skipped_orders"]} orders')

def store_transactions(account_id: int, transactions: list) -> dict:
   """
   Transform and load transactions
   """
   existing_transactions = get_transactions_from_db()

   skipped_transactions = 0
   new_transactions = 0
   for transaction_json in transactions:
      if int(transaction_json['activityId']) in existing_transactions:
         skipped_transactions += 1
         continue

      transaction = Transaction(
         transaction_id = transaction_json['activityId'],
         account_id = account_id,
         date = datetime.strptime(transaction_json['time'], "%Y-%m-%dT%H:%M:%S%z"),
         type = transaction_json['type'],
         status = transaction_json['status'],
         amount = transaction_json['netAmount'],
         order_id = transaction_json.get('orderId'),
         description = transaction_json.get('description'),
         position_id = transaction_json.get('positionId')
      )
      session.add(transaction)
      new_transactions += 1

      for transferItem in transaction_json['transferItems']:
         assetType = transferItem['instrument']['assetType']
         load_dividend_or_interest(transaction, transferItem, assetType)
         load_fee(transaction, transferItem, assetType)
         load_option(transaction, transferItem, assetType)
         load_equity(transaction, transferItem, assetType)
         load_fixed_income(transaction, transferItem, assetType)
   session.commit()
   return {'new_transactions': new_transactions, 'skipped_transactions': skipped_transactions}

def load_dividend_or_interest(transaction: dict, transferItem: dict, assetType: str):

   """
   transform activity of type dividend_or_interest to a transaction item
   """


   if transaction.type != 'DIVIDEND_OR_INTEREST':
      return

   transaction_item = TransactionItem(transaction_id = transaction.transaction_id,
                                       asset_type = assetType,
                                       transaction = 'DIVIDEND',
                                       amount = transferItem['amount'],
                                       extended_amount = transferItem['amount'],
                                       quantity = 0)
                                      
                                    
   # Check to see if description contains the word interest
   if 'interest' in transaction.description.lower():
      transaction_item.transaction = 'INTEREST'
   else:
      transaction_item.transaction = 'DIVIDEND'

   if 'dividend~' in transaction.description.lower():
      transaction_item.symbo = transaction.description.split('~')[1].strip()
   session.add(transaction_item)
   return

def load_fee(transaction: Transaction, transferItem: dict, assetType: str):
   if transaction.type != 'TRADE' or assetType != 'CURRENCY':
      return

   transaction_item = TransactionItem(transaction_id = transaction.transaction_id,
                                       asset_type = assetType,
                                       transaction = 'FEE',
                                       amount = transferItem['amount'],
                                       extended_amount = transferItem['amount'],
                                       quantity = 0)
   if 'feeType' in transferItem:
      transaction_item.description = transferItem['feeType']
   else:
      transaction_item.description = 'Not Specified'
   session.add(transaction_item)
   return

def load_option(transaction: Transaction, transferItem: dict, assetType: str):
   if assetType != 'OPTION':
      return

   transaction_item = TransactionItem(transaction_id = transaction.transaction_id,
                                       asset_type = assetType,
                                       transaction = 'BUY' if transferItem['amount'] > 0 else 'SELL',
                                       amount = transferItem['price'],
                                       extended_amount = transferItem['cost'],
                                       quantity = abs(transferItem['amount']),
                                       symbol = transferItem['instrument']['symbol'],
                                       description = transferItem['instrument']['description'],
                                       strike_price = transferItem['instrument']['strikePrice'],
                                       underlying = transferItem['instrument']['underlyingSymbol'],
                                       position_effect = transferItem.get('positionEffect'))

   if 'expirationDate' in transferItem['instrument']:
      transaction_item.expiration_date = datetime.strptime(transferItem['instrument']['expirationDate'],"%Y-%m-%dT%H:%M:%S%z")

   session.add(transaction_item)
   return

def load_equity(transaction: Transaction, transferItem: dict, assetType: str):
   if assetType != 'EQUITY':
      return

   transaction_item = TransactionItem(transaction_id = transaction.transaction_id,
                                       asset_type = assetType,
                                       transaction = 'BUY' if transferItem['amount'] > 0 else 'SELL',
                                       amount = transferItem['price'],
                                       extended_amount = transferItem['cost'],
                                       quantity = abs(transferItem['amount']),
                                       symbol = transferItem['instrument']['symbol'],
                                       description = transferItem['instrument']['description'])
   session.add(transaction_item)
   return

def load_fixed_income(transaction: Transaction, transferItem: dict, assetType: str):
   if assetType != 'FIXED_INCOME':
      return

   transaction_item = TransactionItem(transaction_id = transaction.transaction_id,
                                       asset_type = assetType,
                                       transaction = 'BUY' if transferItem['amount'] > 0 else 'SELL',
                                       extended_amount = transferItem['cost'],
                                       quantity = abs(transferItem['amount']),
                                       symbol = transferItem['instrument']['symbol'],
                                       description = transferItem['instrument']['description'])

   maturity_date = transferItem['instrument'].get('maturityDate')
   if maturity_date:
      transaction_item.expiration_date = datetime.strptime(maturity_date, "%Y-%m-%dT%H:%M:%S%z")
   multiplier = transferItem['instrument'].get('multiplier', 1)
   transaction_item.multiplier = multiplier
   transaction_item.amount = transferItem['price'] * multiplier
   session.add(transaction_item)
   return

def store_orders(account_id: int, orders: list) -> dict:
   """
   Transform and load orders
   """
   existing_orders = get_orders_from_db()

   skipped_orders = 0
   updated_orders = 0
   new_orders = 0
   for order_json in orders:
      order_id = order_json.get('orderId')
      status = order_json.get('status')

      if order_id in existing_orders and existing_orders[order_id] == status:
         # Order exists in db but has the same status as the one from the API
         # Skip
         skipped_orders += 1
         continue
      elif order_id in existing_orders and existing_orders[order_id] != status:
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
      if 'cancelTime' in order_json:
         order.cancel_time = datetime.strptime(order_json.get('cancelTime'),"%Y-%m-%dT%H:%M:%S%z")

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
   return {'new_orders': new_orders, 'updated_orders': updated_orders, 'skipped_orders': skipped_orders}

def store_positions(account_id, positions_json: str):
   """
   Transform and load positions
   """
   
   date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

   if account_id is None:
      logger.error(f'Account ID {positions_json["securitiesAccount"]["accountNumber"]} not found in the database. Skipping')
      return
   if 'shortQuantity' not in positions_json['securitiesAccount']['positions'][0]:
      logger.error(f'No positions found in the response. Skipping')
      return

   # Reset the latest positions in the database
   reset_latest_positions(account_id)

   for position_json in positions_json['securitiesAccount']['positions']:

      position = Position(
         account_id = account_id,
         date = date,
         short_quantity = position_json['shortQuantity'],
         long_quantity = position_json['longQuantity'],
         average_price = position_json['averagePrice'],
         maintenance_requirement = position_json['maintenanceRequirement'],
         current_day_profit_loss = position_json['currentDayProfitLoss'],
         market_value = position_json['marketValue'],
         current_day_profit_loss_percentage = position_json['currentDayProfitLossPercentage'],
         cusip = position_json['instrument'].get('cusip'),
         asset_type = position_json['instrument'].get('putCall', position_json['instrument'].get('assetType')),
         symbol = position_json['instrument'].get('symbol'),
         underlying_symbol = position_json['instrument'].get('underlyingSymbol', position_json['instrument'].get('symbol')),
         description = position_json['instrument'].get('description'),
         variable_rate = position_json['instrument'].get('variableRate'),
         net_change = position_json['instrument'].get('netChange',0),
         latest = 'Y'
      )
      if 'maturityDate' in position_json['instrument']:
         position.maturity_date = datetime.strptime(position_json['instrument'].get('maturityDate'), "%Y-%m-%dT%H:%M:%S.%f%z")
      if position.asset_type == 'COLLECTIVE_INVESTMENT':
         position.asset_type = 'EQUITY'
      session.add(position)

   session.commit()
   return

def reset_latest_positions(account_id: int ):
   """
   Reset the latest positions in the database using SQLAlchemy ORM
   """
   if account_id is None:
      logger.error(f'Account ID {account_id} not found in the database. Skipping')
      return
   
   session.query(Position).filter(Position.account_id == account_id).update({Position.latest: 'N'})
   session.commit()
   return


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

   app()
   db.close()





