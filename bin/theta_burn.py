import sys
import os
import traceback

# Add the lib directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lib')))

import json
import requests
import pandas as pd
import re
from sqlalchemy import text, update, select, func

import subprocess
import logging
from typer import Typer, Option
from typing import List, Annotated
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pytz

import schwabdev
import hvac
from orm.database import Database
from orm.models import Transaction, TransactionItem, Account, Order, OrderItem, Position, Security

app = Typer()

# Initialize the Database
db_instance = Database()


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
   for filename in os.listdir(import_dir):

      # Skip files that are not JSON files
      if not filename.endswith('.json'):
         logger.info(f'Skipping file {filename}')
         continue

      with open(os.path.join(import_dir, filename), 'r') as f:
         transactions = json.load(f)

      accounts = get_accounts()
      account_number = transactions[0].get('accountNumber')
      if account_number is None:
         logger.error(f'Account number not found in the transaction file. Skipping')
         continue

      account_id = accounts[int(account_number)].get('account_id', None)
      if account_id is None:
         logger.error(f'Account ID {transactions[0]["accountId"]} not found in the database. Skipping')
         continue

      store_transactions(account_id, transactions)

      # Move the file to the processed directory
      os.rename(os.path.join(import_dir, filename), os.path.join(import_dir, 'processed', filename))
      i = i + 1
   logger.info(f'Processed {i+1} files')

   return

@app.command()
def get_transactions(account: Annotated[List[int], Option(..., "--account", help="One or more account numbers")],
                     days: int = Option(7, help="Number of days back from current date to get transactions for"),
                     start_date: str = Option(None, help="start date of date range to pull transactions for"),
                     end_date: str = Option(None, help="end date of date range to pull transactions for"),
                     debug: bool = Option(None, help="print the transaction json")) -> list:

   """
   Get transactions using the API
   """
   if start_date is None:
      start_date = eastern(datetime.now()) - timedelta(days=days)
   else:
      start_date = eastern(datetime.strptime(start_date, '%Y-%m-%d'))

   if end_date is None:
      end_date = eastern(datetime.now())
   else:
      end_date = eastern(datetime.strptime(end_date, '%Y-%m-%d'))

   accounts = get_accounts()
   for account_number in account:
     
      account_id = accounts[account_number].get('account_id', None)
      account_hash = accounts[account_number].get('account_hash', None)
      if account_id is None:
         logger.error(f'Account ID {account_number} not found in the database. Skipping')
         continue
      if account_hash is None:
         logger.error(f'Account hash for account number {account_number} not found in the database. Skipping')
         continue

      for transaction_type in ('TRADE', 'DIVIDEND_OR_INTEREST'):
         logger.info(f'Getting {transaction_type} transactions for account {account_number}')
         try:
            resp = client.transactions(account_hash, start_date, end_date, transaction_type)
            resp.raise_for_status()  # Raises an HTTPError if the response was an error
            transactions = resp.json()
         except requests.exceptions.HTTPError as e:
            logger.error(f'HTTP error getting transactions: {e}')
            continue
         except ValueError as e:  # In case resp.json() fails to parse JSON
            logger.error(f'Error parsing transactions response as JSON: {e}')
            continue
         if debug:
            print(json.dumps(transactions, indent=2))

         result = store_transactions(account_id, transactions)
         logger.info(f'Loaded {result["new_transactions"]} new transactions, skipped {result["skipped_transactions"]} transactions')
   return

@app.command()
def get_positions(account: Annotated[List[int], Option(..., "--account", help="One or more account numbers")],
                  debug: bool = Option(None, help="print the transaction json")) -> list:

   accounts = get_accounts()

   for account_number in account:
      account_id = accounts[account_number].get('account_id', None)
      account_hash = accounts[account_number].get('account_hash', None)
      if account_id is None:
         logger.error(f'Account ID {account_number} not found in the database. Skipping')
         continue
      if account_hash is None:
         logger.error(f'Account hash for account number {account_number} not found in the database. Skipping')
         continue

      try:
         resp = client.account_details(account_hash, fields="positions")
         resp.raise_for_status()  # Raises an HTTPError if the response was an error
         positions_json = resp.json()
      except requests.exceptions.HTTPError as e:
         logger.error(f'HTTP error getting positions: {e}')
         continue
      except ValueError as e:  # In case resp.json() fails to parse JSON
         logger.error(f'Error parsing positions response as JSON: {e}')
         continue
      if debug:
         print(json.dumps(positions_json, indent=2))
     
      results = store_positions(account_id, positions_json)
      logger.info(f'Updated {results}')
      
   return

@app.command()
def get_orders(account: Annotated[List[int], Option(..., "--account", help="One or more account numbers")],
                     days: int = Option(7, help="Number of days back from current date to get transactions for"),
                     start_date: str = Option(None, help="start date of date range to pull transactions for"),
                     end_date: str = Option(None, help="end date of date range to pull transactions for"),
                     status: str = Option(None, help="status of the order"),
                     debug: bool = Option(None, help="print the transaction json")) -> list:

   """
   Get orders using the API
   """
   if start_date is None:
      start_date = eastern(datetime.now()) - timedelta(days=days)
   else:
      start_date = eastern(datetime.strptime(start_date, '%Y-%m-%d'))

   if end_date is None:
      end_date = eastern(datetime.now())
   else:
      end_date = eastern(datetime.strptime(end_date, '%Y-%m-%d'))

   accounts = get_accounts()
   for account_number in account:
      account_id = accounts[account_number].get('account_id', None)
      account_hash = accounts[account_number].get('account_hash', None)
      if account_id is None:
         logger.error(f'Account ID {account_number} not found in the database. Skipping')
         continue
      if account_hash is None:
         logger.error(f'Account hash for account number {account_number} not found in the database. Skipping')
         continue

      try:
         resp = client.account_orders(account_hash, maxResults=5000, fromEnteredTime=start_date, toEnteredTime=end_date, status=status)
         resp.raise_for_status()  # Raises an HTTPError if the response was an error
         orders = resp.json()
      except requests.exceptions.HTTPError as e:
         logger.error(f'HTTP error getting orders: {e}')
         continue
      except ValueError as e:  # In case resp.json() fails to parse JSON
         logger.error(f'Error parsing orders response as JSON: {e}')
         continue
      if debug:
         print(json.dumps(orders, indent=2))

      result = store_orders(account_id, orders)
      logger.info(f'Loaded {result["new_orders"]} new orders, updated {result["updated_orders"]} orders, skipped {result["skipped_orders"]} orders')

def get_security(symbol: str=None, cuspid: str=None, projection: str="symbol-search", debug: bool=False) -> dict:
   """
   Get security details
   """
   if symbol is not None:
      resp = client.instruments(symbol, projection)
   elif cuspid is not None:
      resp = client.instrument_cusip(cuspid)
   else:
      logger.error(f'Either symbol or cuspid must be provided. [Line {traceback.extract_stack()[-1].lineno}]')
      return None

   if resp.status_code == 404:
      logger.error(f"Resource not found in call to get_security for {'symbol=' + symbol if symbol else 'cuspid=' + cuspid}. Skipping [Line {traceback.extract_stack()[-1].lineno}]")
      return None

   if resp.json() is None or 'instruments' not in resp.json():
      logger.error(f'No instruments found for {symbol or cuspid}. Skipping [Line {traceback.extract_stack()[-1].lineno}]')
      return None
   
   # Store the security
   return store_security(resp.json().get('instruments')[0])


def store_security(instrument: dict) -> dict:
   """
   Transform and load security details
   """
   session = db_instance.get_session()
   symbol = instrument.get('symbol')
   description = instrument.get('description')
   exchange = instrument.get('exchange')
   asset_type = instrument.get('assetType')
   underlying_symbol = instrument.get('underlyingSymbol')

   # Check if the security already exists
   security = session.query(Security).filter_by(description=description).first()

   if security:
      # Return the symbol if the security already exists
      return {'symbol': symbol, 'status': 'exists'}
   else:
      # Create new security
      security = Security(
         symbol=symbol,
         description=description,
         exchange=exchange,
         asset_type=asset_type,
      )
      session.add(security)
      session.commit()
      return {'symbol': symbol, 'status': 'created'}
   
@app.command()
def generate_requirements():
   """
   Generate requirements.txt file
   """
   # Module to exclude
   exclude = ['pywin32']

   # Run pip freeze and decode the output
   pip_freeze_output = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze']).decode()

   # Split the output by lines, filter out the excluded module(s), and join back into a single string
   filtered_requirements = '\n'.join(line for line in pip_freeze_output.splitlines() if not any(excl in line for excl in exclude))

   # Write the filtered requirements to requirements.txt
   with open('requirements.txt', 'w') as f:
      f.write(filtered_requirements)

def store_orders(account_id: int, orders: list) -> dict:
   """
   Transform and load orders.  
   Orders can change status so we need to update db rows if api status != db status
   """
   session = db_instance.get_session()
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
         order.cancel_time = datetime.strptime(order_json['cancelTime'], "%Y-%m-%dT%H:%M:%S%z")

      if 'closeTime' in order_json:
         order.close_time = datetime.strptime(order_json['closeTime'], "%Y-%m-%dT%H:%M:%S%z")

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
            underlying = order_item['instrument'].get('underlyingSymbol'),
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

   session = db_instance.get_session()
   date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

   if account_id is None:
      logger.error(f'Account ID {positions_json["securitiesAccount"]["accountNumber"]} not found in the database. Skipping')
      return
   if 'shortQuantity' not in positions_json['securitiesAccount']['positions'][0]:
      logger.error(f'No positions found in the response. Skipping')
      return

   # Reset the latest positions in the database
   reset_latest_positions(account_id)

   for i, position_json in enumerate(positions_json['securitiesAccount']['positions']):

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
         underlying = position_json['instrument'].get('underlyingSymbol', position_json['instrument'].get('symbol')),
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
      # Get and store the security details in the database
      if position.asset_type == 'EQUITY' or position.asset_type == 'COLLECTIVE_INVESTMENT':
         if position.cusip is not None:
            get_security(cuspid=position.cusip)
         elif position.symbol is not None:
            get_security(symbol=position.symbol)


   session.commit()
   return {'positions': i}

def store_transactions(account_id: int, transactions: list) -> dict:
   """
   Transform and load transactions
   """
   session = db_instance.get_session()
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
         date = datetime.strptime(transaction_json['tradeDate'], "%Y-%m-%dT%H:%M:%S%z"),
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
         load_future(transaction, transferItem, assetType)
         load_equity(transaction, transferItem, assetType)
         load_fixed_income(transaction, transferItem, assetType)
   session.commit()
   return {'new_transactions': new_transactions, 'skipped_transactions': skipped_transactions}

def load_dividend_or_interest(transaction: dict, transferItem: dict, assetType: str):

   """
   transform activity of type dividend_or_interest to a transaction item
   """

   session = db_instance.get_session()
   if transaction.type != 'DIVIDEND_OR_INTEREST':
      return

   transaction_item = TransactionItem(transaction_id = transaction.transaction_id,
                                       asset_type = assetType,
                                       transaction = 'DIVIDEND',
                                       amount = transferItem['amount'],
                                       extended_amount = transferItem['amount'],
                                       quantity = 0)
                                      
   # Schwab lumps interest and dividend transactions together
   # so we need to check the description to see if it is a dividend or interest transaction
   interest_patterns = [
      r'FREE BALANCE INTEREST ADJUSTMENT~NO DESCRIPTION',
      r'OFF-CYCLE INTEREST~MMDA1',
      r'MARGIN INTEREST ADJUSTMENT~NO DESCRIPTION',
      r'INTEREST INCOME - SECURITIES~.*',
      r'Free Balance Interest Adjustment',
      r'Interest Income - Securities',
      r'BANK INT.*',
      r'SCHWAB1 INT.*',
   ]
   if any(re.match(pattern, transaction.description, re.IGNORECASE) for pattern in interest_patterns):
      transaction_item.transaction = 'INTEREST'
   else:
      transaction_item.transaction = 'DIVIDEND'

   # Check to see if description contains the word interest
   if 'interest' in transaction.description.lower() or transaction.description.lower().startswith('bank int'):
      transaction_item.transaction = 'INTEREST'
   else:
         transaction_item.transaction = 'DIVIDEND'

   # Set the symbol and underlying.  
   # It would be nice if Schwab included the symbol in the transaction but they don't for 
   # DIVIDEND_OR_INTEREST transactions

   symbol = lookup_symbol(transaction.description)
   if symbol is not None:
         transaction_item.symbol = symbol
         transaction_item.underlying = symbol
   
   session.add(transaction_item)
   return

def load_fee(transaction: Transaction, transferItem: dict, assetType: str):
   session = db_instance.get_session()
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

def lookup_symbol(description: str) -> str:

   session = db_instance.get_session()
   # Parse symbol and underlying from the description
   for keyword in ('dividend~', 'foreign tax withheld~'):
      if keyword in description.lower():
         parts = description.split('~')
         if len(parts) > 1:
               return parts[1].strip()

   # Lookup the symbol in the securities table
   security = session.query(Security).filter_by(description=description).first()
   if security:
      return security.symbol

   return None

def load_option(transaction: Transaction, transferItem: dict, assetType: str):

   session = db_instance.get_session()
   if assetType != 'OPTION':
      return
  
   transaction_item = TransactionItem(transaction_id = transaction.transaction_id,
                                       asset_type = transferItem['instrument']['putCall'],
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
      if transferItem['instrument'].get('status') == 'DISABLED':
         # parse the expiration date out of the symbol
         # Symbol looks like NFLX_041924P550
         symbol_parts = transferItem['instrument']['symbol'].split('_')
         date_str = symbol_parts[1][:6]  # Get the first 6 characters after the underscore
         transaction_item.expiration_date = datetime.strptime(date_str, "%m%d%y")
      else:
         transaction_item.expiration_date = datetime.strptime(transferItem['instrument']['expirationDate'],"%Y-%m-%dT%H:%M:%S%z")

   session.add(transaction_item)
   return

def load_future(transaction: Transaction, transferItem: dict, assetType: str):

   session = db_instance.get_session()
   if assetType != 'FUTURE':
      return
  
   transaction_item = TransactionItem(transaction_id = transaction.transaction_id,
                                       asset_type = transferItem['instrument']['assetType'],
                                       transaction = 'BUY' if transferItem['amount'] > 0 else 'SELL',
                                       amount = transferItem['price'],
                                       extended_amount = transferItem['cost'],
                                       quantity = abs(transferItem['amount']),
                                       symbol = transferItem['instrument']['symbol'],
                                       description = transferItem['instrument']['description'])

   if 'expirationDate' in transferItem['instrument']:
         transaction_item.expiration_date = datetime.strptime(transferItem['instrument']['expirationDate'],"%Y-%m-%dT%H:%M:%S%z")

   session.add(transaction_item)
   return



def load_equity(transaction: Transaction, transferItem: dict, assetType: str):

   session = db_instance.get_session()
   if assetType not in ('EQUITY', 'COLLECTIVE_INVESTMENT'):
      return

   transaction_item = TransactionItem(transaction_id = transaction.transaction_id,
                                       asset_type = assetType,
                                       transaction = 'BUY' if transferItem['amount'] > 0 else 'SELL',
                                       amount = transferItem['price'],
                                       extended_amount = transferItem['cost'],
                                       quantity = abs(transferItem['amount']),
                                       symbol = transferItem['instrument'].get('symbol'),
                                       underlying = transferItem['instrument'].get('symbol'))
   session.add(transaction_item)


   # Store the security details in the database to provide a way to lookup the security by description
   # This is necessary because dividend transactions do not include the symbol for reasons unbeknownst to me
   security = get_security(transaction_item.symbol, projection='instrument')
   return

def load_fixed_income(transaction: Transaction, transferItem: dict, assetType: str):

   session = db_instance.get_session()
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

def get_transactions_from_db() -> list:
   """
   Get transaction IDs from the database using SQLAlchemy ORM.
   """
   session = db_instance.get_session()
   # Query the database directly using the Account model
   transaction_query = session.query(Transaction.transaction_id).all()

   # Convert the query result to a list
   return [id[0] for id in transaction_query]

def get_accounts() -> dict:
      """
      Get accounts from the database and the API
      """
      session = db_instance.get_session()
      # Query the database directly using the Account model
      accounts_query_result = session.query(Account.account_number, Account.account_id).all()

      # Convert query result to a dictionary for easy lookup
      accounts_query = {account_number: account_id for account_number, account_id in accounts_query_result}

      # Get account hashes from API
      try:
         resp = client.account_linked()
         resp.raise_for_status()  # Raises an HTTPError if the response was an error
         linked_accounts = resp.json()
      except requests.exceptions.HTTPError as e:
         logger.error(f'HTTP error getting linked accounts: {e}')
         sys.exit(1)
      except ValueError as e:  # In case resp.json() fails to parse JSON
         logger.error(f'Error parsing linked accounts response as JSON: {e}')
         sys.exit(1)

         
      # Convert the query result to a dictionary
      accounts = {}
      for linked_account in linked_accounts:
         account_number = int(linked_account['accountNumber'])
         account_hash = linked_account['hashValue']
         account_id = accounts_query.get(account_number, None)
         if account_id is None:
            logger.error(f'Account ID for account number {account_number} not found in the database. Skipping')
            continue
         accounts[account_number] = {'account_id': account_id, 'account_hash': account_hash}
      return accounts

def get_orders_from_db() -> dict:
   """
   Get order IDs and status from the database
   """
   session = db_instance.get_session()
   # Query the database directly using the Account model
   orders_query = session.query(Order.order_id, Order.status).all()

   # Convert the query result to a dictionary
   return  {order_id: status for order_id, status in orders_query}

def reset_latest_positions(account_id: int ):
   """
   Reset the latest positions in the database using SQLAlchemy ORM
   """
   session = db_instance.get_session()
   if account_id is None:
      logger.error(f'Account ID {account_id} not found in the database. Skipping')
      return
   
   session.query(Position).filter(Position.account_id == account_id).update({Position.latest: 'N'})
   session.commit()
   return

def set_log_file(logger: logging.Logger, filename: str):
    # Create a file handler
    handler = logging.FileHandler(filename)

    # Create a formatter and add it to the handler
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(handler)

def eastern(dt: datetime) -> datetime:
   """
   Get the number of hours difference between current timezone and America/New_York
   This is a strange way to adjust the time to Eastern time but it is required because the schwabdev client
   does a flawed conversion of time format that can't handle datetime objects with timezone info.
   """
   
   local_datetime = datetime.now().astimezone()

   # Get the current datetime in 'America/New_York'
   ny_datetime = datetime.now(ZoneInfo('America/New_York'))

   # Calculate the difference in UTC offsets
   offset_difference = local_datetime.utcoffset() - ny_datetime.utcoffset()

   # Convert the difference to hours
   hours_diff = offset_difference.total_seconds() / 3600
   
   return dt - timedelta(hours=hours_diff)

def get_client_and_sync_tokens() -> schwabdev.Client:
    """
    Get the Schwab API client and sync the bearer tokens
    """
    # Check if we are using a hashi vault and sync tokens
    # This allows the theta_burn to run in multiple instances and share the same tokens

    if os.getenv('VAULT_URL') is not None:
        vault_url = os.getenv('VAULT_URL')
        vault_token = os.getenv('VAULT_TOKEN')
        vault_mount = os.getenv('VAULT_MOUNT', 'secret')
        path = 'theta_burn_tokens_json'

        vault_client = hvac.Client(url=vault_url, token=vault_token)
        
        # Check if the secret engine is already enabled
        try:
            vault_client.sys.read_mount_configuration(path='kv')
            logger.info('Secrets engine at path "kv" is already enabled.')
        except hvac.exceptions.InvalidPath:
            # Enable the secrets engine if it's not already enabled
            vault_client.sys.enable_secrets_engine(backend_type='kv', path='kv')
        try:
            secret_metadata = vault_client.secrets.kv.v2.read_secret_metadata(path=path, mount_point=vault_mount)
            kv_token_json = vault_client.secrets.kv.v2.read_secret_version(path=path, mount_point=vault_mount, raise_on_deleted_version=False)
            kv_access_token_issued = kv_token_json['data']['data']['access_token_issued']

            # Convert kv_access_token_issued to a datetime object
            kv_access_token_issued = datetime.fromisoformat(kv_access_token_issued)


            # Construct the absolute path to the tokens.json file
            tokens_file_path = os.path.join(".", 'tokens.json')

            # Check if the tokens.json file exists
            if os.path.exists(tokens_file_path):
                  with open(tokens_file_path, 'r') as f:
                     tokens = json.load(f)
                  file_access_token_issued = tokens['access_token_issued']

                  # Convert file_access_token_issued to a datetime object
                  file_access_token_issued = datetime.fromisoformat(file_access_token_issued)

                  # Ensure both datetime objects are aware
                  if kv_access_token_issued.tzinfo is None:
                     kv_access_token_issued = kv_access_token_issued.replace(tzinfo=pytz.UTC)
                  if file_access_token_issued.tzinfo is None:
                     file_access_token_issued = file_access_token_issued.replace(tzinfo=pytz.UTC)

                  if kv_access_token_issued and file_access_token_issued:
                     # Compare the created time of the tokens.json file and the secret in vault
                     if kv_access_token_issued > file_access_token_issued:
                        # The secret in vault is newer
                        logger.info('The secret in vault is newer than the tokens.json file. Updating the tokens.json file')
                        secret = vault_client.secrets.kv.v2.read_secret_version(path=path, mount_point='kv')
                        # Update the tokens.json file
                        with open(tokens_file_path, 'w') as f:
                              json.dump(secret['data']['data'], f)
        except hvac.exceptions.InvalidPath:
            logger.error(f'Secret metadata for path "{path}" not found in Vault at mount point "{vault_mount}".')
        except Exception as e:
            logger.error(f'An error occurred: {e}')
            logger.error(traceback.format_exc())
    
    # Get the Schwab API client     
    client = schwabdev.Client(os.getenv('appKey'), os.getenv('appSecret'))
    if vault_url is not None and os.path.exists(tokens_file_path):
        # Update the vault with the new token
        with open(tokens_file_path, 'r') as f:
            tokens = json.load(f)
        logger.info('Updating the vault with the new tokens')
        vault_client.secrets.kv.v2.create_or_update_secret(path=path, secret=tokens, mount_point='kv')

    return client


if __name__ == '__main__':
   
   try:
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
      
      # Get the Schwab API client
      client = get_client_and_sync_tokens()

      app()
   except Exception as e:  # Catch all exceptions
      logger.error(f'An error occurred: {e}')
   finally:
      # Close the database connection      
      db_instance.close()