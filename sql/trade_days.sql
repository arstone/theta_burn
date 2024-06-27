-- Number of Days with a buy or sell transaction for current year
-- Includes ratio of days traded to ytd days market was open
-- Includes ratio of days traded to total market days for the current year

-- These ratio are important for maintaining professional trader status.
-- IRS requires a trade on at least 75% of the open market days
select 
    a.year, 
    a.account, 
    count(distinct a.date) as days_with_trade,
    round(count(distinct a.date) / market.completed_days, 3) * 100 as ytd_ratio,
    round(count(distinct a.date) / market.total_days, 3) * 100 as total_year_ratio
from (
    select 
        year(date) as year,
        date,
        position_id, 
        a.name as account
    from 
        transactions t 
        join transaction_items ti using (transaction_id)
        join accounts a using (account_id)
    where 
        year(date) = year(now())
        and t.type = 'TRADE'
        and transaction in ('SELL', 'BUY')
    group by 
        year(date), date, position_id, account
) a
join (
    select 
        year(date) as year,
        count(*) as total_days,
        sum(if(date <= now(), 1, 0)) as completed_days
    from 
        calendar 
    where 
        is_market_open = true
    group by 
        year(date)
) market on (market.year = a.year)
group by 
    a.year, a.account