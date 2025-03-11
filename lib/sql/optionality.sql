# Create mariadb optionality database
create database optionality;

# brokers table
create table brokers (
    broker_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL);

create table users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash CHAR(128),
    phone VARCHAR(255) NOT NULL,
    address VARCHAR(255) NOT NULL,
    city VARCHAR(255) NOT NULL,
    state VARCHAR(255) NOT NULL,
    zip VARCHAR(255) NOT NULL,
    country VARCHAR(255) NOT NULL
);

create table accounts (
    account_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    account_number  bigint,
    broker_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(255) NOT NULL,
    balance DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (broker_id) REFERENCES brokers(broker_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE account_balances (
    id INT AUTO_INCREMENT,
    account_id INT,
    balance DECIMAL(15, 2),
    date DATE,
    PRIMARY KEY (id),
    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE
);

create table strategies (
    strategy_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    description VARCHAR(255) NOT NULL,
    author VARCHAR(255) NOT NULL,
    link VARCHAR(255),
    UNIQUE (user_id, name),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

    create table trades (
        trade_id bigint AUTO_INCREMENT PRIMARY KEY,
        user_trade_id INT NOT NULL default 0,
        strategy_id INT NOT NULL,
        user_id INT NOT NULL,
        account_id INT NOT NULL,
        open_date DATE NOT NULL,
        close_date DATE NOT NULL,
        type VARCHAR(255) NOT NULL,
        status VARCHAR(255) NOT NULL,   amount DECIMAL(10,2) NOT NULL,
    profit_target DECIMAL(10,2) NOT NULL,
    stop_loss_target DECIMAL(10,2) NOT NULL,
    starting_margin DECIMAL(10,2) NOT NULL,
    ending_margin DECIMAL(10,2) NOT NULL,
    max_margin DECIMAL(10,2) NOT NULL,
    adjustments INT default 0,
    comment VARCHAR(1024), 
    description VARCHAR(255) NOT NULL,
    FOREIGN KEY (strategy_id) REFERENCES strategies(strategy_id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

DELIMITER //
CREATE TRIGGER increment_based_on_other BEFORE INSERT ON trades
FOR EACH ROW
BEGIN
   SET NEW.user_trade_id = (SELECT MAX(user_trade_id) FROM trades WHERE user_id = NEW.user_id) + 1;
END;//
DELIMITER ;

create table transactions (
    transaction_id bigint,
    account_id INT NOT NULL,
    trade_id BIGINT,
    date DATE NOT NULL,
    type VARCHAR(255) NOT NULL,
    status VARCHAR(255) NOT NULL,
    order_id bigint,
    position_id bigint,
    amount DECIMAL(10,2) NOT NULL,
    description VARCHAR(255),
    PRIMARY KEY (transaction_id, account_id),
    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE);

create table transaction_items (
    item_id bigint AUTO_INCREMENT PRIMARY KEY,
    transaction_id bigint,
    asset_type VARCHAR(255) NOT NULL,
    transaction VARCHAR(255),
    amount DECIMAL(10,2),
    quantity DECIMAL(10,2),
    symbol VARCHAR(255),
    description VARCHAR(255),
    strike_price DECIMAL(10,2),
    expiration_date DATE,
    underlying VARCHAR(255),
    extended_amount DECIMAL(10,2),
    position_effect VARCHAR(255),
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id) ON DELETE CASCADE);

create table quotes (
    quote_id bigint AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(255) NOT NULL,
    date DATE NOT NULL,
    bid DECIMAL(10,2) NOT NULL,
    ask DECIMAL(10,2) NOT NULL,
    last DECIMAL(10,2) NOT NULL,
    open_interest INT NOT NULL,
    volume INT NOT NULL,
    ivol DECIMAL(10,2) NOT NULL,
    delta DECIMAL(10,2) NOT NULL,
    gamma DECIMAL(10,2) NOT NULL,
    theta DECIMAL(10,2) NOT NULL,
    vega DECIMAL(10,2) NOT NULL,
    rho DECIMAL(10,2) NOT NULL
);

create table calendar (
    date DATE PRIMARY KEY,
    year INT,
    quarter INT,
    month INT,
    month_name VARCHAR(255),
    short_month_name VARCHAR(255),
    day INT,
    week INT,
    weekday INT,
    day_name VARCHAR(255),
    is_weekday BOOLEAN,
    is_holiday BOOLEAN,
    is_current_year BOOLEAN AS (YEAR(date) = YEAR(CURDATE())),
    is_current_month BOOLEAN AS (YEAR(date) = YEAR(CURDATE()) AND MONTH(date) = MONTH(CURDATE()),
    is_market_open BOOLEAN)
);


create table positions (
    position_id bigint AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    date datetime NOT NULL,
    asset_type VARCHAR(255),
    short_quantity DECIMAL(10, 2),
    long_quantity DECIMAL(10, 2),
    average_price DECIMAL(10, 2),
    current_day_profit_loss DECIMAL(10, 2),
    current_day_profit_loss_percentage DECIMAL(10, 2),
    market_value DECIMAL(10, 2),
    net_change DECIMAL(10, 2),
    maintenance_requirement DECIMAL(10, 2),
    cusip VARCHAR(255),
    symbol VARCHAR(255),
    underlying_symbol VARCHAR(255),
    description TEXT,
    maturity_date DATETIME,
    variable_rate DECIMAL(10, 2),
    latest CHAR(1) DEFAULT 'N',
    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE
);

CREATE TABLE orders (
    account_id INT,
    entered_time DATETIME,
    close_time DATETIME,
    order_id BIGINT,
    order_type VARCHAR(255),
    cancel_time DATETIME,
    quantity DECIMAL(10, 2),
    filled_quantity DECIMAL(10, 2),
    remaining_quantity DECIMAL(10, 2),
    requested_destination VARCHAR(255),
    order_strategy_type VARCHAR(255),
    status VARCHAR(255),
    price DECIMAL(10, 2),
    order_duration VARCHAR(255),
    order_class VARCHAR(255),
    PRIMARY KEY (account_id, order_id),
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
);

CREATE TABLE order_items (
    account_id INT,
    order_id BIGINT,
    order_leg_type VARCHAR(255),
    instruction VARCHAR(255),
    quantity DECIMAL(10, 2),
    asset_type VARCHAR(255),
    symbol VARCHAR(255),
    description VARCHAR(255),
    cusip VARCHAR(255),
    put_call VARCHAR(255),
    underlying_symbol VARCHAR(255),
    maturity_date DATE,
    strike_price DECIMAL(10, 2),
    multiplier INT,
    order_item_id INT,
    PRIMARY KEY (account_id, order_id, order_item_id),
    FOREIGN KEY (account_id, order_id) REFERENCES orders(account_id, order_id) ON DELETE CASCADE
);

CREATE TABLE securities (
    symbol VARCHAR(255) PRIMARY KEY,
    description VARCHAR(255) NOT NULL,
    exchange VARCHAR(255) NOT NULL,
    asset_type VARCHAR(255) NOT NULL
);


create or replace view transaction_view as (
select
   a.account_id, 
   t.date, 
   date_format(t.date, '%b') month,
   year(t.date) year,
   t.transaction_id,
   t.position_id,
   t.trade_id,
   t.order_id,
   o.close_time order_date,
   ifnull(ti.description,t.description) description,
   ti.quantity,
   ifnull(ti.symbol,'') symbol,
   ifnull(ti.underlying, '') underlying,
   ti.amount,
   ifnull((fees.commission / fees.quantity * ti.quantity * -1),0) commission,
   ifnull((fees.other / fees.quantity * ti.quantity * -1),0) fees,
   ti.transaction,
   ti.asset_type,
   ti.expiration_date,
   ti.strike_price,
   round(ti.extended_amount,2) extended_amount
from 
   accounts a
   join transactions t using (account_id)
   join transaction_items ti using (transaction_id)
   left join orders o using (order_id)
   join (select
            transaction_id, 
            sum(quantity) quantity,
            sum(if(ti.description = 'COMMISSION', ti.amount,0)) commission,
            sum(if(transaction = 'FEE' and ti.description != 'COMMISSION',ti.amount,0)) other
         from 
            transactions t
            join transaction_items ti using (transaction_id)
         group by 1) fees using (transaction_id)
where 
   ti.transaction in ('BUY', 'SELL', 'INTEREST', 'DIVIDEND')   
);

CREATE INDEX idx_account_symbol_latest ON positions (account_id, symbol, latest);
