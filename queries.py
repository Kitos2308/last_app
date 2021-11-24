MY_LANGUAGE_QUERY = (
    'select l.id, sid, profile_id '
    'from languages l '
    'inner join sessions s on code = locale '
    'inner join profiles p on s.profile_id = p.id '
    'where s.active = True')


async def custom_stock_query(connection):
    return await connection.prepare(
        f'with my_carts as (select custom_stock_id,  '  # noqa
        f'                         ptc.custom_cart_id, '
        f'                         \'osn\'                         as Taxation, '
        f'                         sum(online_price * quantity)  as amount, '
        f'                         sum(offline_price * quantity) as amount_offline '
        f' '
        f'                  from custom_product_to_custom_cart ptc '
        f'                           inner join custom_products p on ptc.custom_product_id = p.id '
        f'                           inner join custom_carts c on ptc.custom_cart_id = c.id '
        f'                  group by ptc.custom_cart_id, custom_stock_id '
        f'), '
        f'     my_products as (select * '
        f'                     from custom_product_to_custom_cart ptc '
        f'                              inner join custom_products p on ptc.custom_product_id = p.id '
        f'                              inner join product_units pu on p.product_unit_id = pu.id '
        f'     ), '
        f'     my_language as ({MY_LANGUAGE_QUERY}) '
        f'select s.id as stock_id, '
        f'       title, '
        f'       title_short, '
        f'       note, '
        f'       purchase_terms, '
        f'       concat('
        f'              (select value from system_parameters where name = \'resource_server_url\'),'
        f'               s.photo_path) as photo_path, '
        f'       start_date, '
        f'       end_date, '
        f'       mc.custom_cart_id         as id, '
        f'       taxation, '
        f'       amount, '
        f'       amount_offline, '
        f'       put.name, '
        f'       quantity, '
        f'       online_price               as price, '
        f'       online_price * quantity    as product_amount, '
        f'       \'vat20\'                  as tax, '
        f'       mp.payment_object          as payment_object, '
        f'       mp.payment_method          as payment_method, '
        f'       partners.id as partner_id, '
        f'       partners.cashback_part as cashback_part, '
        f'       partners_translate.name as partner_name, '
        f'       partners_translate.address_short, '
        f'       partners_translate.open_partner_schedule, '
        f'       partners_translate.close_partner_schedule, '
        f'       partners_translate.description_short, '
        f'       partners_translate.description, '
        f'       concat('
        f'              (select value from system_parameters where name = \'resource_server_url\'),'
        f'               partners.photo_path) as partner_photo_path, '
        f'       concat('
        f'              (select value from system_parameters where name = \'resource_server_url\'),'
        f'               partners.logo_path) as logo_path, '
        f'       points.airport_id '
        f'from custom_stocks s '
        f'         inner join points on s.point_id = points.id '
        f'         inner join partners on points.partner_id = partners.id '
        f'         inner join my_carts mc on mc.custom_stock_id = s.id '
        f'         inner join my_products mp on mc.custom_cart_id = mp.custom_cart_id '
        f'         inner join my_language on true '
        f'         inner join custom_stocks_to_profile cstp on cstp.custom_stock_id = s.id '
        f'                          and cstp.profile_id = my_language.profile_id '
        f'         left outer join partners_translate '
        f'                          on partners_translate.partner_id = partners.id '
        f'                          and partners_translate.language_id = my_language.id '
        f'         left outer join product_units_translate put '
        f'                          on mp.product_unit_id = put.product_unit_id and put.language_id = my_language.id '
        f'         left outer join custom_stocks_translate st '
        f'                          on s.id = st.custom_stock_id and st.language_id = my_language.id '
        f'where s.id = $1 '
        f'  and s.active = $2 '
        f'and sid = $3; '
    )


async def stock_query(connection, stock_id, active, moa_sid, custom=False):
    prefix = 'custom_' if custom else ''
    extra_join = 'inner join custom_stocks_to_profile cstp on cstp.custom_stock_id = ' \
                 's.id and cstp.profile_id = my_language.profile_id' if custom else ''

    return await connection.fetch(
        f'with my_carts as (select {prefix}stock_id,  '  # noqa
        f'                         ptc.{prefix}cart_id, '
        f'                         \'osn\'                         as Taxation, '
        f'                         sum(online_price * quantity)  as amount, '
        f'                         sum(offline_price * quantity) as amount_offline '
        f' '
        f'                  from {prefix}product_to_{prefix}cart ptc '
        f'                           inner join {prefix}products p on ptc.{prefix}product_id = p.id '
        f'                           inner join {prefix}carts c on ptc.{prefix}cart_id = c.id '
        f'                  group by ptc.{prefix}cart_id, {prefix}stock_id '
        f'), '
        f'     my_products as (select * '
        f'                     from {prefix}product_to_{prefix}cart ptc '
        f'                              inner join {prefix}products p on ptc.{prefix}product_id = p.id '
        f'                              inner join product_units pu on p.product_unit_id = pu.id '
        f'     ), '
        f'     my_language as ({MY_LANGUAGE_QUERY}) '
        f'select s.id as id_stock, '
        f'       title, '
        f'       title_short, '
        f'       note, '
        f'       purchase_terms, '
        f'       concat('
        f'              (select value from system_parameters where name = \'resource_server_url\'),'
        f'               s.photo_path) as photo_path, '
        f'       start_date, '
        f'       end_date, '
        f'       mc.{prefix}cart_id         as id, '
        f'       Taxation, '
        f'       amount, '
        f'       amount_offline, '
        f'       put.name, '
        f'       quantity, '
        f'       online_price               as price, '
        f'       online_price * quantity    as product_amount, '
        f'       \'vat20\'                  as tax, '
        f'       mp.payment_object          as payment_object, '
        f'       mp.payment_method          as payment_method, '
        f'       partners.id as partner_id, '
        f'       partners_translate.name as partner_name, '
        f'       partners_translate.address_short, '
        f'       partners_translate.open_partner_schedule, '
        f'       partners_translate.close_partner_schedule, '
        f'       concat('
        f'              (select value from system_parameters where name = \'resource_server_url\'),'
        f'               partners.logo_path) as logo_path, '
        f'       points.airport_id '
        f'from {prefix}stocks s '
        f'         inner join points on s.point_id = points.id '
        f'         inner join partners on points.partner_id = partners.id '
        f'         inner join my_carts mc on mc.{prefix}stock_id = s.id '
        f'         inner join my_products mp on mc.{prefix}cart_id = mp.{prefix}cart_id '
        f'         inner join my_language on true '
        f'         {extra_join} '
        f'         left outer join partners_translate '
        f'                          on partners_translate.partner_id = partners.id '
        f'                          and partners_translate.language_id = my_language.id '
        f'         left outer join product_units_translate put '
        f'                          on mp.product_unit_id = put.product_unit_id and put.language_id = my_language.id '
        f'         left outer join {prefix}stocks_translate st '
        f'                          on s.id = st.{prefix}stock_id and st.language_id = my_language.id '
        f'where s.id = $1 '
        f'  and s.active = $2 '
        f'and sid = $3; ',
        stock_id,
        active,
        moa_sid
    )


async def get_profile_query(connection, moa_sid):
    return await connection.fetch(
        f'with my_language as ({MY_LANGUAGE_QUERY}) '  # noqa
        f'SELECT uid as customer_id,  '
        f'       phone_number,  '
        f'       first_name,  '
        f'       last_name,  '
        f'       patronymic,  '
        f'       email,  '
        f'       birth_date,  '
        f'       mile_count,  '
        f'       ust.name,  '
        f'       conversion_rate,  '
        f'       minimum_conversion_threshold,  '
        f'       my_language.id as language_id, '
        f'       pqr, '
        f'       pass_count_1, '
        f'       pass_count_2, '
        f'       pass_count_3  '
        f'FROM profiles p  '
        f'  '
        f'         inner join user_status us on p.user_status_id = us.id  '
        f'         inner join my_language on p.id = my_language.profile_id  '
        f'         left outer join user_status_translate ust on us.id = ust.user_status_id '
        f'              and ust.language_id = my_language.id  '
        f'where sid = $1;', moa_sid)


async def show_cards_query(connection, moa_sid, limit, offset):
    return await connection.fetch(
        f'SELECT number, money_balance FROM "cards" '
        f'WHERE "profile_id"=(select profile_id from sessions where sid = $1) LIMIT $2 OFFSET $3;',
        moa_sid, limit, offset)


async def show_transactions_query(connection, card_number, moa_sid, limit, offset):
    return await connection.fetch(
        f'SELECT c.number, transaction_type, count, t.created_date FROM cards c '
        f'inner join sessions s on c.profile_id = s.profile_id '
        f'left outer join transactions t on t.card_id = c.id '
        f'WHERE c.number=$1 and s.sid = $2 '
        f'order by t.created_date desc LIMIT $3 OFFSET $4;',
        card_number, moa_sid, limit, offset
    )


GET_BRAND_QUERY = '''
select distinct brand_relations.brand_category_id as category_id,
                brands.id,
                coalesce(point_translates.title, 'none') as name,
                concat(
                            (select value from system_parameters where name = 'resource_server_url'),
                            brands.logo_path)               as logo_path,
                concat(
                            (select value from system_parameters where name = 'resource_server_url'),
                            brands.photo_path)              as photo_path,
                brand_relations.ord
from brands
         inner join brand_relations on brands.id = brand_relations.brand_id
         inner join points on brands.id = points.brand_id
         inner join airports on points.airport_id = airports.id
         inner join partners on points.partner_id = partners.id
         left outer join brands_translate on brands.id = brands_translate.brand_id 
            and brands_translate.language_code = (select code from languages where id = $1)
         left outer join point_translates on points.id = point_translates.point_id 
            and point_translates.language_code = (select code from languages where id = $1)
    
where brands.id = $2
'''
GET_BRANDS_LIST_QUERY = '''
select distinct brand_relations.brand_category_id as category_id,
                brands.id,
                points.id as point_id,
                points.is_scannable,
                points.is_scanning_pqr,
                coalesce(point_translates.title, 'none') as name,
                coalesce(point_translates.description_short, 'none') as description_short, 
                coalesce(point_translates.description, 'none') as description,
                concat(
                            (select value from system_parameters where name = 'resource_server_url'),
                            brands.logo_path)               as logo_path,
                            
           case
           when  (select photo from photo_to_point where points.id = photo_to_point.point_id limit 1) is null then  null
           when  (select photo from photo_to_point where points.id = photo_to_point.point_id limit 1) LIKE 'http%' then 
           (select photo from photo_to_point where points.id = photo_to_point.point_id limit 1)
           else
               concat((select value from system_parameters where name = 'resource_server_url'),
                       (select photo from photo_to_point where points.id = photo_to_point.point_id limit 1))
           end                  as photo_path,
           
           
                array_agg(points.id)                        as points,
                brand_relations.ord
from brands
         inner join points on brands.id = points.brand_id
         inner join airports on points.airport_id = airports.id
         inner join partners on points.partner_id = partners.id
         inner join brand_relations on brands.id = brand_relations.brand_id and coalesce(airports.parent_id, airports.id) = brand_relations.airport_id
         left outer join brands_translate on brands.id = brands_translate.brand_id and brands_translate.language_code = $1
         left outer join point_translates on points.id = point_translates.point_id and point_translates.language_code = $1
    
where brands.active 
  and partners.active
  and points.visible
  and partners.testing = $2
  and case when bool($3::int is not null::int) then (airports.id = $3::int or airports.parent_id = $3::int) else true end
  and case when bool($4::int is not null::int) then brand_relations.brand_category_id = $4::int else true end
  and case when bool($5::int is not null::int) then airports.city_id = $5::int else true end
  and case when bool($8::int is not null::int) then points.id = $8::int else true end
  group by category_id,
         brands.id,
         points.id,
         point_translates.title,
         point_translates.description_short,
         point_translates.description,
         brands.logo_path,
         brands.photo_path,
         brand_relations.ord
order by brand_relations.ord 
limit $6::int offset $7::int;
'''

QR_CODES_QUERY = '''
        select array_agg(pss_qr) from orders where pss_point_id = $1 and profile_id = $2
        and (      
                  coalesce(used, false) = false
                  and used_date is null
                  and (estimated_date >= now() or estimated_date is null)
                  and (expiration_date >= now() or expiration_date is null)
                  and paid
                  and not refunded
              ) = true
        group by pss_point_id;
'''

GET_POINT_QUERY = '''
select coalesce(open_partner_schedule, '') as open_partner_schedule,
       coalesce(close_partner_schedule, '') as close_partner_schedule,
       coalesce(address_short, '') as address_short,
       coalesce(address, '') as address,
       coalesce(point_translates.description_short, 'none') as description_short, 
       coalesce(point_translates.description, 'none') as description,
       coalesce(cashback_part, 0) as cashback_part
from points
         inner join partners on points.partner_id = partners.id
         left outer join point_translates on points.id = point_translates.point_id and language_code = 
         (select code from languages where id = $1)
where points.id = $2;
'''

SYSTEM_PARAMETERS_QUERY = '''
select name, description, value            
from system_parameters where public is true
'''

LANGUAGES_QUERY = 'select id, name, code from languages where public'

GET_LANGUAGE_CODE = 'select code from languages where id = $1'

SET_LOCALE_IN_DEVICES_QUERY = '''
UPDATE devices SET locale = $1 
WHERE id = (select device_id from sessions where sid = $2);
'''
SET_LOCALE_IN_SESSIONS_QUERY = 'UPDATE sessions SET locale = $1 WHERE sid = $2;'

PARTNER_CATEGORIES = '''
SELECT brand_categories_translate.id, 
       brand_categories.id as partner_category_id, 
       brand_categories_translate.name, 
       brand_categories_translate.language_id
from brand_categories
         left outer join brand_categories_translate on brand_categories.id = brand_categories_translate.brand_category_id;
'''

GET_HASHES_QUERY = 'select table_name, value from hashes where enabled = true;'

CREATE_FEEDBACK_QUERY = 'INSERT INTO feedback (profile_id, message, email) VALUES ($1, $2, $3) returning id;'

CREATE_PHOTO_TO_FEEDBACK_QUERY = 'INSERT INTO photos_to_feedback (feedback_id, photo_path) VALUES ($1, $2) returning id;'

GET_FAQ_QUERY = '''
SELECT ord,
       question,
       answer,
       concat((select value from system_parameters where name = 'resource_server_url'), ico_path) as ico_path
from faq left outer join faq_translate ft on faq.id = ft.faq_id and ft.language_id = $1
where public
order by ord
'''
GET_NOTIFICATIONS_QUERY = '''
SELECT message, created_date from notifications 
where profile_id = $1 order by created_date desc 
limit $2 offset $3;
'''

POST_QR_QUERY = 'update profiles set mile_count=mile_count+0 where id = $1;'

GET_PROFILE_BY_DEVICE = 'select id from devices where guid = $1;'

POST_GEO_QUERY = 'INSERT INTO geo_data (device_id, latitude, longitude) VALUES ($1, $2, $3);'

GET_INFORMATION_QUERY = '''
SELECT it.id, i.name, i.created_date, title, body, language_id
FROM information i
         INNER JOIN information_translate it on i.id = it.information_id
         inner join languages l on it.language_id = l.id
WHERE code = $1
  and case when $2::text isnull then true else i.name = $2::text end;
'''


async def show_partners_in_airport_query(connection, airport_id, testing, partner_category_id, moa_sid, limit, offset):
    return await connection.fetch(
        f'with my_language as ({MY_LANGUAGE_QUERY}) '  # noqa
        f'select partner_category_id as category_id, '
        f'p.id, '
        f'name, '
        f'description_short, '
        f'description, '
        f'open_partner_schedule, '
        f'close_partner_schedule, '
        f'address_short, '
        f'address, '
        f'cashback_part, '
        f'       concat('
        f'              (select value from system_parameters where name = \'resource_server_url\'),'
        f'               logo_path) as logo_path, '
        f'       concat('
        f'              (select value from system_parameters where name = \'resource_server_url\'),'
        f'               p.photo_path) as photo_path '
        f'from partners p '
        f'inner join partner_to_airport pta on p.id = pta.partner_id '
        f'inner join airports a on pta.airport_id = a.id '
        f'inner join my_language on true '
        f'left outer join partners_translate pt on p.id = pt.partner_id and language_id = my_language.id '
        f'where (a.id = $1 or a.parent_id = $1) '
        f'and testing = $2 '
        f'and case when $3 != 0 then partner_category_id = $3 '
        f'else true end '
        f'and my_language.sid = $4 '
        f'and partner_category_id <> 4 '
        f'limit $5 offset $6;',
        airport_id, testing, partner_category_id, moa_sid, limit, offset)


GET_PROMOTIONS_QUERY = '''
SELECT title, 
description_short, 
description, 
concat((select value from system_parameters where name = 'resource_server_url'), photo_path) as photo_path,
start_date, 
end_date
FROM promotions
         INNER JOIN promotions_translate ON promotions.id = promotions_translate.promotion_id
WHERE active = $1
  AND language_id = $2
LIMIT $3 OFFSET $4;
'''

GET_STOCK_QUERY = '''
select stocks.id,
       stocks.ord,
       stocks_translate.title,
       stocks_translate.title_short,
       stocks_translate.note,
       stocks_translate.purchase_terms,
       concat(
           (select value from system_parameters where name = 'resource_server_url'), stocks.photo_path) as photo_path,
       stocks.start_date,
       stocks.end_date
from stocks
         left outer join stocks_translate on stocks_translate.stock_id = stocks.id and stocks_translate.language_id = $1
where stocks.id = $2
and stocks.active = $3;
'''

GET_AIRPORT_BY_STOCK_QUERY = '''
select airport_id
from points
         inner join stocks on points.id = stocks.point_id
where stocks.id = $1;
'''
GET_PARTNER_BY_STOCK_QUERY = '''
with products_in_points as (
    select array_agg(products.id) as products_list,
           coalesce(parent.id, airports.id) as airport_id,
           points.id              as point_id,
           brands.id              as brand_id
    from product_to_point
             inner join points on product_to_point.point_id = points.id
             inner join brands on points.brand_id = brands.id
             inner join partners on points.partner_id = partners.id
             inner join airports on points.airport_id = airports.id
             left outer join airports parent on airports.parent_id = parent.id
             inner join products on product_to_point.product_id = products.id
             inner join product_units
                        on partners.id = product_units.partner_id and
                           products.product_unit_id = product_units.id

    group by points.id,
             brands.logo_path,
             partners.cashback_part,
             brands.id,
             coalesce(parent.id, airports.id)),
     products_in_stocks as (
         select stocks.id              as stock_id,
                array_agg(products.id) as products_list
         from products
                  inner join product_to_cart on products.id = product_to_cart.product_id
                  inner join carts on product_to_cart.cart_id = carts.id
                  inner join stocks on carts.stock_id = stocks.id

         group by stocks.id
     )
select products_in_points.point_id as id,
       airport_id, 
       brand_id

from products_in_points
         inner join products_in_stocks on products_in_points.products_list @> products_in_stocks.products_list
where stock_id = $1
limit 1;

'''

CHECK_CUSTOM_STOCK_OWNER_QUERY = '''
select count(*)>0 from stocks 
inner join stock_to_profile on stocks.id = stock_to_profile.stock_id
 where stock_id = $1 and stock_to_profile.profile_id = $2
'''

GET_CUSTOM_STOCKS_QUERY = '''
with products_in_points as (
    select array_agg(products.id) as products_list,
           array_to_string(array_agg(distinct coalesce(parent.id, airports.id)), ', ' ) as airport_id,
           points.id              as point_id,
           brands.id              as brand_id,
           brands.logo_path
    from product_to_point

             inner join points on product_to_point.point_id = points.id
             inner join brands on points.brand_id = brands.id
             inner join partners on points.partner_id = partners.id
             inner join airports on points.airport_id = airports.id
             left outer join airports parent on airports.parent_id = parent.id
             inner join brand_relations on brands.id = brand_relations.brand_id
                                    and brand_relations.airport_id = coalesce(parent.id, airports.id)
             inner join products on product_to_point.product_id = products.id
             inner join product_units
                        on partners.id = product_units.partner_id and
                           products.product_unit_id = product_units.id
    where 
    coalesce(parent.id, airports.id) = $1 
       and case when bool($2::int is not null::int) then brands.id = $2::int else true end
        and (points.active
        and brands.active
        and partners.active
        and airports.active
        and products.active
        and product_units.active) = $3

    group by points.id,
             brands.logo_path,
             brands.id),

     products_in_stocks as (
         select stocks.id              as stock_id,
                stocks.ord,
                array_agg(products.id) as products_list,
                stocks.custom          as stock_is_custom
         from products
                  inner join product_to_cart on products.id = product_to_cart.product_id
                  inner join carts on product_to_cart.cart_id = carts.id
                  inner join stocks on carts.stock_id = stocks.id
                  inner join stock_to_profile on stocks.id = stock_to_profile.stock_id
         where (stocks.active and coalesce(start_date < now(), true) and coalesce(end_date > now(), true)) = $3
           and coalesce(stocks.custom, false) = true
           and stock_to_profile.profile_id = $4

         group by stocks.id, stock_is_custom
     )
select array_agg(s.stock_id) as stocks_list
from (select distinct stock_id, products_in_stocks.ord
      from products_in_points
               inner join products_in_stocks on products_in_points.products_list @> products_in_stocks.products_list
      order by products_in_stocks.ord
      limit $5::int offset $6::int) s;
'''

GET_CART_QUERY = '''
select carts.id                                               as id,
       'osn'                                                  as Taxation,
       sum(products.online_price * product_to_cart.quantity)  as amount,
       sum(products.offline_price * product_to_cart.quantity) as amount_offline
from carts
         inner join product_to_cart on carts.id = product_to_cart.cart_id
         inner join products on product_to_cart.product_id = products.id
where stock_id = $1
group by carts.id;
'''

CREATE_ORDER_QUERY_OLD = '''
INSERT INTO orders (profile_id, qr, pss_qr, pss_stock_id, confirmed, sent, refunded, type, pss_point_id, expiration_date,uuid_relation) 
VALUES ($1, $2, $3, $4, $5, $6, $7, 1, $8, $9, $10) 
returning id;
'''
CREATE_ORDER_QUERY = '''
INSERT INTO orders (profile_id, sum, qr, pss_qr, pss_stock_id, confirmed, sent, refunded, type, pss_point_id, expiration_date,uuid_relation) 
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 1, $9, $10, $11) 
returning *;
'''

CREATE_PRODUCT_TO_ORDER = '''
INSERT INTO product_to_order (order_id, product_id, quantity, price) 
VALUES ($1, $2, $3, $4) ;
'''

GET_ORDERS_QUERY = '''
select pss_qr, id as order_id, qr
from orders
where profile_id = $1
  and (
              coalesce(used, false) = false
              and used_date is null
              and (estimated_date >= now() or estimated_date is null)
          ) = $2
          limit $3 offset $4
'''

GET_PRODUCTS_QUERY = '''
select name,
       quantity,
       online_price                 as price,
       online_price * quantity      as amount,
       'vat20'                      as tax,
       product_units.payment_object as payment_object,
       product_units.payment_method as payment_method
from product_to_cart
         inner join products on product_to_cart.product_id = products.id
         inner join product_units on products.product_unit_id = product_units.id
         left outer join product_units_translate
                         on product_units.id = product_units_translate.product_unit_id and language_id = $1
where cart_id = $2;
'''


async def show_orders_query(connection, is_custom, moa_sid=None, active=False, limit=20, offset=0, order_id=0):
    if is_custom:
        prefix = "custom_"
    else:
        prefix = ""

    order_by = 'DESC'
    if not active:
        condition = "or estimated_date < now()"
    else:
        condition = "and estimated_date >= now()"
        order_by = 'ASC'

    return await connection.fetch(
        f'with my_language as ({MY_LANGUAGE_QUERY}) '  # noqa
        f'select custom, '
        f'qr, '
        f'estimated_date, '
        f'used_date, '
        f'title, '
        f'concat((select value from system_parameters where name = \'resource_server_url\'), s.photo_path) '
        f'      as photo_path,'
        f'st.purchase_terms, '
        f'name, '
        f'concat((select value from system_parameters where name = \'resource_server_url\'), logo_path) '
        f'      as logo_path, '
        f'sum, '
        f'open_partner_schedule, '
        f'close_partner_schedule, '
        f'address_short, '
        f'p2.id as partner_id '
        f'FROM orders '
        f'inner join my_language on my_language.profile_id = orders.profile_id '
        f'inner join {prefix}stocks s on orders.stock_id = s.id '
        f'left outer join {prefix}stocks_translate st on s.id = st.{prefix}stock_id '
        f'and st.language_id = my_language.id '
        f'inner join points p on orders.point_id = p.id '
        f'inner join partners p2 on p.partner_id = p2.id '
        f'left outer join partners_translate pt on p2.id = pt.partner_id and pt.language_id = my_language.id '
        f'where my_language.sid = $1 '
        f'and case when $5 != 0 then orders.id = $5 '
        f'else (used = $2 {condition}) '
        f'and custom = {is_custom} '
        f'and orders.paid=true '
        f'end '
        f'order by orders.estimated_date {order_by} '
        f'limit $3 offset $4;', moa_sid, not active, limit, offset, order_id
    )


async def create_order_query(connection, is_custom, moa_sid, airport_id, partner_id, cart_id):
    if is_custom:
        prefix = "custom_"
    else:
        prefix = ""
    return await connection.fetchrow(
        f'with stock as (select {prefix}stock_id, validity, c.id as cart_id '  # noqa
        f'from {prefix}carts c '
        f'inner join {prefix}stocks s '
        f'on c.{prefix}stock_id = s.id '
        f'where s.active) '
        f'INSERT INTO orders (profile_id, '
        f'point_id, '
        f'sum, '
        f'type, '
        f'used, '
        f'stock_id, '
        f'estimated_date, '
        f'custom) '
        f'(select  '
        f'(select profile_id from sessions where sid = $1), '
        f'(select p.id from points p where airport_id = $2 and partner_id = $3 and p.active is true), '
        f'(select sum(online_price * quantity) '
        f'from {prefix}carts '
        f'inner join {prefix}product_to_{prefix}cart ptc on {prefix}carts.id = ptc.{prefix}cart_id '
        f'inner join {prefix}products p on ptc.{prefix}product_id = p.id '
        f'where {prefix}cart_id = $4), '
        f'0, '
        f'FALSE, '
        f'(select {prefix}stock_id from stock where cart_id = $4), '
        f'date(now()) + (select validity from stock where cart_id = $4), '
        f'$5 where exists(select {prefix}stock_id from stock where cart_id = $4)) '
        f'RETURNING id, created_date;', moa_sid, airport_id, partner_id, cart_id, is_custom)


async def update_product_query(connection, custom_q: bool, order_id, cart_id):
    prefix = "custom_" if custom_q else ""
    await connection.execute(
        f'insert into {prefix}product_to_order (order_id, {prefix}product_id, quantity, price) '  # noqa
        f'select $1, {prefix}product_id, quantity, online_price from {prefix}product_to_{prefix}cart '
        f'inner join {prefix}products '
        f'on {prefix}product_to_{prefix}cart.{prefix}product_id = {prefix}products.id '
        f'where {prefix}cart_id = $2;', order_id, cart_id)


async def add_qr_to_order_query(connection, qr, order_id):
    await connection.execute(f'UPDATE orders set qr = $1 where id = $2', qr, order_id)


async def get_onpass_products_query(connection):
    return await connection.fetch(
        f'SELECT pu.id_1c as type_id, put.name, l.code '
        f'FROM partners p '
        f'inner join product_units pu on p.id = pu.partner_id '
        f'left outer join product_units_translate put on pu.id = put.product_unit_id '
        f'inner join languages l on put.language_id = l.id '
        f'where login = \'onpass\' '
        f'and pu.active;'
    )


UPDATE_PROFILE_QUERY = '''
UPDATE "profiles"
SET first_name  = $1,
    last_name   = $2,
    patronymic  = $3,
    birth_date  = $4,
    email       = $5,
    update_date = $6
WHERE id = (SELECT profile_id FROM sessions WHERE sid = $7);
'''

UPDATE_PROFILE_QUERY_SEARCH_PROFILE_BY_UIID = '''
UPDATE "profiles"
SET first_name  = $1,
    last_name   = $2,
    patronymic  = $3,
    birth_date  = $4,
    email       = $5,
    update_date = $6,
    last_time_sent_email=$7,
    email_confirmed=$8
WHERE uid = $9;
'''
# """
# airport_id,
#             category_id,
#             city_id,
# """
GET_AIRPORTS = '''
SELECT a.id,
       a.city_id,
       a.code_iata,
       a.latitude,
       a.longitude,
       concat((select value from system_parameters where name = 'resource_server_url'), a.photo_path)
                                                                         as photo_path,
       a.active                                                            as available,
       a.ord,
       (select count(*) from brands
         inner join brand_relations on brands.id = brand_relations.brand_id
         inner join points on brands.id = points.brand_id
         inner join airports on points.airport_id = airports.id and coalesce(airports.parent_id, airports.id) = brand_relations.airport_id
         inner join partners on points.partner_id = partners.id
         where brands.active 
  and partners.active
  and points.visible
  and a.parent_id is null
  and partners.testing = false
  and ((airports.id = a.id and airports.city_id = a.city_id) or airports.parent_id = a.id))
    as partners_count 
FROM airports a
WHERE a.parent_id is null
and a.visible
ORDER BY a.ord;
'''

GET_TERMINALS = '''
SELECT airports.id,
       city_id,
       latitude,
       longitude,
       concat((select value from system_parameters where name = 'resource_server_url'), airports.photo_path)
                                                                         as photo_path,
       active                                                            as available,
       airports.ord,
       (select count(distinct brand_id) from points where airport_id = airports.id) as partners_count
FROM airports
WHERE parent_id =$1::int
and visible
ORDER BY airports.ord;
'''

GET_AIRPORTS_TRANSLATE = '''
SELECT airports_translate.*
FROM airports_translate
         inner join airports on airports.id = airports_translate.airport_id
         left outer join airports parent on airports.parent_id = parent.id
WHERE airports.visible and 
((airports.id = ANY ($1::int[])) or case when parent.id = ANY ($1::int[]) then parent.visible  else false end) 
'''

GET_ONPASS_POINT_QUERY = '''
select coalesce(point_translates.title, 'null')                 as name,
       coalesce(point_translates.address, 'null')  as address,
       coalesce(point_translates.open_partner_schedule, 'null')  as schedule,
       coalesce(point_translates.description_short, 'null') as description_short,
       coalesce(point_translates.additional_info, 'null') as additional_info,
       (not points.active)                    as closed,
       case
           when array_length(array_agg(photo_to_point.photo), 1) > 0 and
                array_agg(photo_to_point.photo) <> array [null]::text[] then (array_agg(concat(
                       (select value from system_parameters where name = 'resource_server_url'),
                       photo_to_point.photo)))
           else (array []::text[])
           end                                as photo_paths

from points
         inner join brands on points.brand_id = brands.id
         inner join brand_to_brand_categories on brands.id = brand_to_brand_categories.brand_id
         inner join brand_categories on brand_to_brand_categories.brand_category_id = brand_categories.id
         INNER JOIN brand_relations ON brands.id = brand_relations.brand_id and
                                       brand_categories.id = brand_relations.brand_category_id and
                                       points.airport_id = brand_relations.airport_id
         left outer join photo_to_point on points.id = photo_to_point.point_id
         left outer join point_translates on points.id = point_translates.point_id and language_code = $1
where points.id = $2
  and brand_categories.id = $3
group by point_translates.title,
         point_translates.address,
         point_translates.open_partner_schedule,
         point_translates.description_short,
         point_translates.additional_info,
         points.id,
         closed;
'''

GET_PARTNER_SERVICES_QUERY = '''
select coalesce(point_service_translates.name, 'null') as name,
       case when point_services.ico_path is null then null
           else
       concat((select value from system_parameters where name = 'resource_server_url'),
              point_services.ico_path)
           end as ico_path
from service_to_point
         inner join point_services on service_to_point.point_service_id = point_services.id
         left outer join point_service_translates
                         on point_services.id = point_service_translates.point_service_id and language_code = $2
where point_id = $1;

'''

GET_ONPASS_PARTNERS_IN_AIRPORT = '''
select distinct points.id,
                coalesce(point_translates.title, 'none')               as name,
                coalesce(point_translates.address_short, 'none') as address_short,
                case
                    when airports.parent_id is null then null
                    else
                        airports_translate.title end as terminal,
       case
           when partners.photo_path is null then null
           else
               concat((select value from system_parameters where name = 'resource_server_url'),
                      partners.photo_path)
           end                  as photo_path,
                    (not partners.active)    as closed
from points
         inner join partners on points.partner_id = partners.id
         inner join brands on points.brand_id = brands.id
         inner join brand_relations on brands.id = brand_relations.brand_id
         inner join brand_to_brand_categories on brands.id = brand_to_brand_categories.brand_id
         inner join brand_categories on brand_relations.brand_category_id = brand_categories.id and
                                        brand_to_brand_categories.brand_category_id = brand_categories.id
         inner join airports on points.airport_id = airports.id and
                                brand_relations.airport_id = airports.id
         left outer join airports parent on airports.parent_id = parent.id
         left outer join photo_to_point on points.id = photo_to_point.point_id
         left outer join point_translates
                         on points.id = point_translates.point_id and point_translates.language_code = $4
         left outer join airports_translate
                         on airports.id = airports_translate.airport_id and airports_translate.language_id = 
                         (select id from languages where code = $4)

where coalesce(parent.id, airports.id) = $1
  and brand_categories.id = $2
  and partners.testing = $3


'''
GET_BRAND_TAG = '''
select tag from brands where id = $1
'''

GET_AIRPORT_CODE = '''
select coalesce(parent.code_iata, airports.code_iata) from airports 
left outer join airports parent on airports.parent_id = parent.id 
where airports.id = $1 or parent.id = $1
'''
# GET_ONPASS_PARTNERS_IN_TERMINAL = '''
# select partners.id,
#        partners_translate.name,
#        partners_translate.address_short,
#        airports_translate.title as terminal,
# case
# when
# partners.photo_path is null
# then
# null
# else
# concat((select value from system_parameters where name = 'resource_server_url'),
#        partners.photo_path)
# end                  as photo_path,
#        (not partners.active)    as closed
# from partner_to_airport
#          inner join airports on partner_to_airport.airport_id = airports.id
#          inner join partners on partner_to_airport.partner_id = partners.id
#          left outer join airports_translate
#                          on airports.id = airports_translate.airport_id and airports_translate.language_id = $4
#          left outer join partners_translate
#                          on partners.id = partners_translate.partner_id and partners_translate.language_id = $4
# where airports.parent_id = $1
#   and partners.partner_category_id = $2
#   and partners.testing = $3;
# '''

GET_BRAND_ID_QUERY = '''
select id from brands where tag = $1;
'''
