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
    account_number  bigint NOT NULL,
    broker_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(255) NOT NULL,
    balance DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (broker_id) REFERENCES brokers(broker_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

create table strategies (
    strategy_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description VARCHAR(255) NOT NULL,
    author VARCHAR(255) NOT NULL
);

create table trades (
    trade_id bigint AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    user_trade_id INT NOT NULL default 0,
    strategy_id INT NOT NULL,
    account_id INT NOT NULL,
    open_date DATE NOT NULL,
    close_date DATE NOT NULL,
    type VARCHAR(255) NOT NULL,
    status VARCHAR(255) NOT NULL,
    order_id bigint,
    position_id bigint,
    amount DECIMAL(10,2) NOT NULL,
    profit_target DECIMAL(10,2) NOT NULL,
    stop_loss_target DECIMAL(10,2) NOT NULL,
    starting_margin DECIMAL(10,2) NOT NULL,
    ending_margin DECIMAL(10,2) NOT NULL,
    max_margin DECIMAL(10,2) NOT NULL,
    adjustments INT default 0,
    comment VARCHAR(1024), 
    description VARCHAR(255) NOT NULL,
    FOREIGN KEY (strategy_id) REFERENCES strategies(strategy_id),
    FOREIGN KEY (account_id) REFERENCES accounts(account_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

DELIMITER //
CREATE TRIGGER increment_based_on_other BEFORE INSERT ON trades
FOR EACH ROW
BEGIN
   SET NEW.user_trade_id = (SELECT MAX(user_trade_id) FROM trades WHERE user_id = NEW.user_id) + 1;
END;//
DELIMITER ;

create table transactions (
    transaction_id bigint PRIMARY KEY,
    account_id INT NOT NULL,
    date DATE NOT NULL,
    type VARCHAR(255) NOT NULL,
    status VARCHAR(255) NOT NULL,
    order_id bigint,
    position_id bigint,
    amount DECIMAL(10,2) NOT NULL,
    description VARCHAR(255),
    FOREIGN KEY (account_id) REFERENCES accounts(account_id));

create table transaction_items (
    item_id bigint AUTO_INCREMENT PRIMARY KEY,
    transaction_id bigint,
    asset_type VARCHAR(255) NOT NULL,
    transaction VARCHAR(255),
    amount DECIMAL(10,2),
    quantity INT,
    symbol VARCHAR(255),
    description VARCHAR(255),
    strike_price DECIMAL(10,2),
    expiration_date DATE,
    underlying VARCHAR(255),
    extended_amount DECIMAL(10,2),
    position_effect VARCHAR(255),
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id));

create table quotes (
    quote_id bigint PRIMARY KEY,
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
    is_current_month BOOLEAN AS (YEAR(date) = YEAR(CURDATE()) AND MONTH(date) = MONTH(CURDATE()))
);


create or replace view transaction_view as (
select
   a.account_number, 
   t.date, 
   date_format(t.date, '%b') month,
   year(t.date) year,
   t.transaction_id,
   t.position_id,
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



