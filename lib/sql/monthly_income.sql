-- Income (wheel, dividend, interest) trades
select 
   year(date) year,
   date_format(date, '%b') month,
   format(sum(extended_amount - commission - fees),2) income,
   count(distinct position_id) trades
from 
   transaction_view
   join calendar c using (date)
where 
    asset_type in ('CURRENCY', 'CALL', 'PUT')
   and underlying not in ('SPX', 'SPXW', 'VIX')
   and symbol not like '/%'
group by 1,2
order by c.year, c.month
