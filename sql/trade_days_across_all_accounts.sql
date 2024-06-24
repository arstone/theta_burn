-- Trading Days across all accounts

select year, count(distinct date) from (
select 
   year(date) year,
   date,
   position_id
from 
   transactions t 
   join transaction_items ti using (transaction_id)
   join accounts a using (account_id)
where 
   year(date) in (2023, 2024) and t.type = 'TRADE'
   and transaction in ('SELL', 'BUY')
   and a.account_id in (1,2,3)
group by 1, 2, 3
) a
group by 1
