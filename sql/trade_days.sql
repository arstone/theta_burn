-- Trading Days per Year
select year, account, count(distinct date) from (
select 
   year(date) year,
   date,
   position_id, 
   a.name account
from 
   transactions t 
   join transaction_items ti using (transaction_id)
   join accounts a using (account_id)
where 
   year(date) in (2023, 2024) and t.type = 'TRADE'
   and transaction in ('SELL', 'BUY')
group by 1, 2, 3,4
) a
group by 1,2
