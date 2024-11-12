-- Number of Days with a buy or sell transaction for current year
-- Includes ratio of days traded to ytd days market was open
-- Includes ratio of days traded to total market days for the current year

-- These ratio are important for maintaining professional trader status.
-- IRS requires a buy or sell transaction on at least 75% of the open market days
select 
    a.year, 
    a.account, 
    market.days_completed market_days_completed,
    (market.days_total - market.days_completed) market_days_left,
    count(distinct a.date) as days_with_trade,
    concat(round((count(distinct a.date) / market.days_completed) * 100 , 1),'%') as trading_ratio_ytd,
    concat(round((count(distinct a.date) / market.days_total) * 100, 1),'%') as trading_ratio,
    sum(a.transactions) transactions,
    round(sum(a.transactions) / market.days_completed,2) avg_daily_transactions,
    max(date) last_trade,
    concat(75, '%') target_trading_ratio,
    ceil((market.days_total * .75)) target_trading_days,
    (market.days_total - market.days_completed) - (ceil((market.days_total * .75)) - count(distinct a.date)) as days_allowed_with_no_trade
from (
    select 
        year(date) as year,
        date,
        position_id, 
        a.name as account,
        count(*) transactions
    from 
        transactions t 
        join transaction_items ti using (transaction_id)
        join accounts a using (account_id)
    where 
        year(date) = year(now())
        and t.type = 'TRADE'
        and transaction in ('SELL', 'BUY')
        and a.type = 'TAXABLE'
    group by 
        year(date), date, position_id, account
) a
join (
    select 
        year(date) as year,
        count(*) as days_total,
        sum(if(date <= now(), 1, 0)) as days_completed
    from 
        calendar 
    where 
        is_market_open = true
    group by 
        year(date)
) market on (market.year = a.year)
group by 
    a.year, a.account, market_days_left,market_days_completed
