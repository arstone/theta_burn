-- Underlying Lifetime P/L
select
   t.account_id,
   t.underlying,
   sum(t.extended_amount) + sum(ifnull(p.market_value,0)) "P/L"
from (   
      select
         tv.account_id, 
         tv.underlying,
         tv.asset_type,
         sum(extended_amount) extended_amount
      from
         transaction_view tv
      group by 1,2,3) t
     left join positions p on (t.account_id = p.account_id 
                               and t.underlying = p.underlying 
                               and t.asset_type = p.asset_type 
                               and latest = 'Y') 
group by 1,2