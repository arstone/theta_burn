import json
import pandas as pd
from sqlalchemy import create_engine, text
import os
import sys
import logging
import typer
from dotenv import load_dotenv

from modules import api, stream
from datetime import datetime, timedelta


app = typer.Typer()

class credentials:
   db_host = None
   db_user = None
   db_password = None
   db_name = None
   aaron_ira_accountNumber = None
   stacey_ira_accountNumber = None
   family_accountNumber = None



def get_transactions_from_db() -> list:

   """
   Get transactions from the database
   """
   existing_transactions = []

   query = text('SELECT transaction_id FROM transactions')
   for row in db.execute(query):
      existing_transactions.append(row.transaction_id) 
   return existing_transactions

def get_accounts_from_db() -> dict:
      """
      Get accounts from the database
      """
      
      accounts = {}

      query = text('SELECT account_id, account_number FROM accounts')
      for row in db.execute(query):
         accounts[row.account_number] = row.account_id

      return accounts 

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
def get_transactions(account_number: str, 
                     days: int = 7, 
                     start_date: str = None, 
                     end_date: str = None) -> list:

   """
   Get transactions from the API
   """

   if start_date is None:
      start_date = datetime.now() - timedelta(days=days)
   else:
      start_date = datetime.strptime(start_date, '%Y-%m-%d')

   if end_date is None:
      end_date = datetime.now()
   else:
      end_date = datetime.strptime(end_date, '%Y-%m-%d')

   api.initialize(accountNumber=account_number)

   for transaction_type in ('TRADE', 'DIVIDEND_OR_INTEREST'):
      activities = api.transactions.transactions(start_date, end_date, transaction_type).json()
      load_activities(activities)
   return


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
      }

   if 'orderId' in activity:
      transaction['order_id'] = activity['orderId']

   if 'description' in activity:
      transaction['description'] = activity['description']

   if 'positionId' in activity:
      transaction['position_id'] = activity['positionId']

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

   if 'symbol' in transferItem['instrument']:
      item['symbol'] = transferItem['instrument']['symbol']
   item['description'] = transferItem['instrument']['description']
   item['expiration_date'] = transferItem['instrument']['expirationDate']
   item['strike_price'] = transferItem['instrument']['strikePrice']
   item['underlying'] = transferItem['instrument']['underlyingSymbol']
   item['quantity'] = abs(transferItem['amount'])
   item['amount'] = transferItem['price']
   item['extended_amount'] = transferItem['cost']
   if 'positionEffect' in transferItem:
      item['position_effect'] = transferItem['positionEffect']
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
   if transferItem['amount'] > 0:
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
   credentials.aaron_ira_accountNumber = os.getenv('aaron_ira_accountNumber')
   credentials.stacey_ira_accountNumber = os.getenv('stacey_ira_accountNumber')
   credentials.family_accountNumber = os.getenv('family_accountNumber')
   credentials.db_host = os.getenv('db_host')
   credentials.db_user = os.getenv('db_user')
   credentials.db_password = os.getenv('db_password')
   credentials.db_name = os.getenv('db_name')
   
   # connect to mariadb
   engine = create_engine(f'mysql+mysqlconnector://{credentials.db_user}:{credentials.db_password}@{credentials.db_host}/{credentials.db_name}')

   # Create a logger
   logger = logging.getLogger('theta_burn.log')

   # Set the level of this logger. Only messages with level INFO or higher will be processed
   logger.setLevel(logging.INFO)

   db = engine.connect()

   transactions = []
   transaction_items = []
   
   app()
   db.close()





