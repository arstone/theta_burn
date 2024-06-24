-- Days in Trade   
select year, account, sum(transactions) transactions, avg(days) from (
select 
   year(date) year,
   position_id, 
   a.name account,
   count(*) transactions, 
   datediff( MAX(date), min(date)) days
from 
   transactions t 
   join transaction_items ti using (transaction_id)
   join accounts a using (account_id)
where 
   year(date) in (2023, 2024) and t.type = 'TRADE'
   and transaction in ('SELL', 'BUY')
group by 1, 2, 3
having transactions > 1
) a
group by 1,2
