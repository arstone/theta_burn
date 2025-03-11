from sqlalchemy import create_engine, Column, Integer, String, DECIMAL, Date, DateTime, ForeignKey
from sqlalchemy import Boolean, Text, CHAR, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

# Create a base class
Base = declarative_base()

class BaseModel(Base):
    __abstract__ = True  # This ensures that SQLAlchemy does not create a table for this class

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class Broker(BaseModel):
    __tablename__ = 'brokers'
    broker_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)

class User(BaseModel):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    password_hash = Column(CHAR(128))
    phone = Column(String(255), nullable=False)
    address = Column(String(255), nullable=False)
    city = Column(String(255), nullable=False)
    state = Column(String(255), nullable=False)
    zip = Column(String(255), nullable=False)
    country = Column(String(255), nullable=False)

class Account(BaseModel):
    __tablename__ = 'accounts'
    account_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    account_number = Column(BigInteger)
    broker_id = Column(Integer, ForeignKey('brokers.broker_id'), nullable=False)
    name = Column(String(255), nullable=False)
    type = Column(String(255), nullable=False)
    balance = Column(DECIMAL(10,2), nullable=False)
    user = relationship("User")
    broker = relationship("Broker")

class AccountBalance(BaseModel):
    __tablename__ = 'account_balances'
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('accounts.account_id'), nullable=False)
    balance = Column(DECIMAL(15, 2))
    date = Column(Date)
    account = relationship("Account", backref="account_balances")

class Strategy(BaseModel):
    __tablename__ = 'strategies'
    strategy_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(String(255), nullable=False)
    author = Column(String(255), nullable=False)
    link = Column(String(255), nullable=True)
    user = relationship("User")

class Trade(BaseModel):
    __tablename__ = 'trades'
    trade_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_trade_id = Column(Integer, nullable=False, default=0)
    strategy_id = Column(Integer, ForeignKey('strategies.strategy_id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    account_id = Column(Integer, ForeignKey('accounts.account_id'), nullable=False)
    open_date = Column(Date, nullable=False)
    close_date = Column(Date, nullable=False)
    type = Column(String(255), nullable=False)
    status = Column(String(255), nullable=False)
    order_id = Column(BigInteger)
    position_id = Column(BigInteger)
    amount = Column(DECIMAL(10,2), nullable=False)
    profit_target = Column(DECIMAL(10,2), nullable=False)
    stop_loss_target = Column(DECIMAL(10,2), nullable=False)
    starting_margin = Column(DECIMAL(10,2), nullable=False)
    ending_margin = Column(DECIMAL(10,2), nullable=False)
    max_margin = Column(DECIMAL(10,2), nullable=False)
    adjustments = Column(Integer, default=0)
    comment = Column(String(1024))
    description = Column(String(255), nullable=False)
    strategy = relationship("Strategy")
    user = relationship("User")
    account = relationship("Account")

class Transaction(BaseModel):
    __tablename__ = 'transactions'
    transaction_id = Column(BigInteger, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.account_id'), nullable=False, primary_key=True)
    date = Column(Date, nullable=False)
    type = Column(String(255), nullable=False)
    status = Column(String(255), nullable=False)
    trade_id = Column(BigInteger)
    order_id = Column(BigInteger)
    position_id = Column(BigInteger)
    amount = Column(DECIMAL(10,2), nullable=False)
    description = Column(String(255))
    account = relationship("Account")

class TransactionItem(BaseModel):
    __tablename__ = 'transaction_items'
    item_id = Column(BigInteger, primary_key=True, autoincrement=True)
    transaction_id = Column(BigInteger, ForeignKey('transactions.transaction_id'))
    asset_type = Column(String(255), nullable=False)
    transaction = Column(String(255))
    amount = Column(DECIMAL(10,2))
    quantity = Column(DECIMAL(10,2))
    symbol = Column(String(255))
    description = Column(String(255))
    strike_price = Column(DECIMAL(10,2))
    expiration_date = Column(Date)
    underlying = Column(String(255))
    extended_amount = Column(DECIMAL(10,2))
    position_effect = Column(String(255))
    transaction_rel = relationship("Transaction")

class Quote(BaseModel):
    __tablename__ = 'quotes'
    quote_id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(255), nullable=False)
    date = Column(Date, nullable=False)
    bid = Column(DECIMAL(10,2), nullable=False)
    ask = Column(DECIMAL(10,2), nullable=False)
    last = Column(DECIMAL(10,2), nullable=False)
    open_interest = Column(Integer, nullable=False)
    volume = Column(Integer, nullable=False)
    ivol = Column(DECIMAL(10,2), nullable=False)
    delta = Column(DECIMAL(10,2), nullable=False)
    gamma = Column(DECIMAL(10,2), nullable=False)
    theta = Column(DECIMAL(10,2), nullable=False)
    vega = Column(DECIMAL(10,2), nullable=False)
    rho = Column(DECIMAL(10,2), nullable=False)

class Calendar(BaseModel):
    __tablename__ = 'calendar'
    date = Column(Date, primary_key=True)
    year = Column(Integer)
    quarter = Column(Integer)
    month = Column(Integer)
    month_name = Column(String(255))
    short_month_name = Column(String(255))
    day = Column(Integer)
    week = Column(Integer)
    weekday = Column(Integer)
    day_name = Column(String(255))
    is_weekday = Column(Boolean)
    is_holiday = Column(Boolean)
    is_current_year = Column(Boolean)
    is_current_month = Column(Boolean)
    is_market_open = Column(Boolean)
    
class Position(BaseModel):
    __tablename__ = 'positions'
    position_id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('accounts.account_id'), nullable=False)
    date = Column(DateTime, nullable=False)
    asset_type = Column(String(255))
    short_quantity = Column(DECIMAL(10, 2))
    long_quantity = Column(DECIMAL(10, 2))
    average_price = Column(DECIMAL(10, 2))
    current_day_profit_loss = Column(DECIMAL(10, 2))
    current_day_profit_loss_percentage = Column(DECIMAL(10, 2))
    market_value = Column(DECIMAL(10, 2))
    net_change = Column(DECIMAL(10, 2))
    maintenance_requirement = Column(DECIMAL(10, 2))
    cusip = Column(String(255))
    symbol = Column(String(255))
    underlying = Column(String(255))
    description = Column(Text)
    maturity_date = Column(DateTime)
    variable_rate = Column(DECIMAL(10, 2))
    latest = Column(CHAR(1), default='N')
    account = relationship("Account")

class Order(BaseModel):
    __tablename__ = 'orders'
    account_id = Column(Integer, ForeignKey('accounts.account_id'), primary_key=True)
    entered_time = Column(DateTime)
    close_time = Column(DateTime)
    order_id = Column(BigInteger, primary_key=True)
    order_type = Column(String(255))
    cancel_time = Column(DateTime)
    quantity = Column(DECIMAL(10, 2))
    filled_quantity = Column(DECIMAL(10, 2))
    remaining_quantity = Column(DECIMAL(10, 2))
    requested_destination = Column(String(255))
    order_strategy_type = Column(String(255))
    status = Column(String(255))
    price = Column(DECIMAL(10, 2))
    order_duration = Column(String(255))
    order_class = Column(String(255))
    account = relationship("Account")

class OrderItem(BaseModel):
    __tablename__ = 'order_items'
    account_id = Column(Integer, primary_key=True)
    order_id = Column(BigInteger, ForeignKey('orders.order_id'), primary_key=True)
    order_leg_type = Column(String(255))
    instruction = Column(String(255))
    quantity = Column(DECIMAL(10, 2))
    asset_type = Column(String(255))
    symbol = Column(String(255))
    description = Column(String(255))
    cusip = Column(String(255))
    put_call = Column(String(255))
    underlying = Column(String(255))
    maturity_date = Column(Date)
    strike_price = Column(DECIMAL(10, 2))
    multiplier = Column(Integer)
    order_item_id = Column(Integer, primary_key=True)
    order = relationship("Order", backref="order_items")

class Security(BaseModel):
    __tablename__ = 'securities'
    symbol = Column(String(255), primary_key=True)
    description = Column(String(255), nullable=False)
    exchange = Column(String(255), nullable=False)
    asset_type = Column(String(255), nullable=False)

class TransactionView(BaseModel):
    __tablename__ = 'transaction_view'
    transaction_id = Column(BigInteger, primary_key=True)
    account_id = Column(Integer)
    date = Column(Date)
    month = Column(String(3))
    year = Column(Integer)
    position_id = Column(BigInteger)
    trade_id = Column(BigInteger)
    order_id = Column(BigInteger)
    description = Column(String(255))
    quantity = Column(Integer)
    symbol = Column(String(255))
    underlying = Column(String(255))
    amount = Column(DECIMAL(10, 2))
    commission = Column(DECIMAL(10, 2))
    fees = Column(DECIMAL(10, 2))
    transaction = Column(String(255))
    asset_type = Column(String(255))
    expiration_date = Column(Date)
    strike_price = Column(DECIMAL(10, 2))
    extended_amount = Column(DECIMAL(10, 2))
                             
    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
     