import asyncio

import aiohttp
from loguru import logger

import tools
from api_utils import ApiResponse
from queries import *
from settings import *
from utils import convert_data, get_language_id, rename_field


async def get_photo_to_point(request, point_id=None):
    pool = tools.get_pool_from_request(request)
    async with pool.acquire() as conn:
        photo_to_points = await conn.fetch(
            '''
            select photo_to_point.photo as photo_paths
            from photo_to_point where point_id =$1
            order by id
            ''', point_id)
    return photo_to_points


async def get_resource_server_url(request):
    pool = tools.get_pool_from_request(request)
    async with pool.acquire() as conn:
        resource_url = await conn.fetchval('''
                            select value from system_parameters where name = $1 ''', 'resource_server_url')

    return resource_url


async def get_brands(request, language_code, testing=False, airport_id=None, category_id=None, city_id=None, limit=20,
                     offset=0, point_id=None):
    language_id = await get_language_id(request)
    pool = tools.get_pool_from_request(request)
    async with pool.acquire() as conn:
        brands = await conn.fetch(
            GET_BRANDS_LIST_QUERY,
            language_code,
            testing,
            airport_id,
            category_id,
            city_id,
            limit,
            offset,
            point_id
        )

        prepared_point = await conn.prepare(GET_POINT_QUERY)
        brands = convert_data(brands, formatting_datetime=FORMAT_DATE_TIME, formatting_float=2)
        for brand in brands:
            point = await prepared_point.fetchrow(language_id, brand['points'][0])
            brand.update(point)
            brand.pop('points')
    return brands


async def stock_gen(stocks_id_list, conn, language_id, active):
    prepared_stock = await conn.prepare(GET_STOCK_QUERY)
    prepared_cart = await conn.prepare(GET_CART_QUERY)
    prepared_products = await conn.prepare(GET_PRODUCTS_QUERY)
    prepared_point = await conn.prepare(GET_PARTNER_BY_STOCK_QUERY)
    prepared_partner_info = await conn.prepare(GET_POINT_QUERY)
    prepared_brand_info = await conn.prepare(GET_BRAND_QUERY)
    for stock_id in stocks_id_list:
        stock = await prepared_stock.fetchrow(language_id, stock_id, active)
        stock = convert_data(stock, formatting_datetime=FORMAT_DATE)
        cart = await prepared_cart.fetchrow(stock_id)
        cart = convert_data(cart, formatting_float=2)
        products = await prepared_products.fetch(language_id, cart.get('id'))
        products = convert_data(products, formatting_float=2)
        for product in products:
            product['product_amount'] = product.pop('amount')
        point = await prepared_point.fetchrow(stock_id)
        if point is None:
            raise ApiResponse(13)
        partner = await prepared_partner_info.fetchrow(language_id, point.get('id'))
        partner = convert_data(partner, formatting_datetime=FORMAT_DATE_TIME)
        brand = await prepared_brand_info.fetchrow(language_id, point.get('brand_id'))
        brand = convert_data(brand)
        partner.update(brand)
        airport_id = point.get('airport_id')
        cart['products'] = products
        stock['cart'] = cart
        custom_stock = dict(airport_id=airport_id, custom_stock=stock, partner=partner)
        yield custom_stock


async def wallet(logger, pool, request):
    moa_sid = tools.get_moa_sid_from_req(request)

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow('select pqr, first_name, last_name, phone_number, os, os_version from profiles '
                                      'inner join sessions on profiles.id = sessions.profile_id '
                                      'inner join devices on sessions.device_id = devices.id where sid = $1', moa_sid)
            pqr = row.get('pqr')
            first_name = row.get('first_name')
            last_name = row.get('last_name')
            phone_number = row.get('phone_number')
            operating_system = row.get('os')
            os_version = row.get('os_version')

            async with aiohttp.ClientSession() as session:
                request_body = {
                    "pqr": pqr,
                    'first_name': first_name,
                    'last_name': last_name,
                    'phone_number': phone_number,
                    'os': operating_system,
                    'os_version': os_version
                }

                resp = await session.post(f'https://{IS_DEV_PREFIX}cl.maocloud.ru/api/v1/walletCard', json=request_body)
                try:
                    json = await resp.json()
                    url = json['data']['url']
                except Exception:
                    raise ApiResponse(30)
        return {'url': url}

    return {'pqr': pqr}


async def get_st(request, stock_id, language_code, airport_id=None):
    pool = tools.get_pool_from_request(request)
    if airport_id is not None:
        async with pool.acquire() as conn:
            async with conn.transaction():
                airport_code = await conn.fetchval(GET_AIRPORT_CODE, airport_id)
                params = dict(stock_id=stock_id, language_code=language_code, airport_code=airport_code)
    else:
        params = dict(stock_id=stock_id, language_code=language_code)

    headers = {'Authorization': f'Bearer {config.pss_service.token}'}

    async with aiohttp.ClientSession() as session:
        url = config.pss_service.url + 'seller/stock'
        logger.info(f'запрос на url {url}, params: {params}')
        stock = asyncio.create_task(
            get_api_response_json(request, session, url, 'get', headers, params=params))
        stock_info = await stock
        brand_tag = stock_info['stock'].get('brand_tag')
        async with pool.acquire() as conn:
            brand_id = await conn.fetchval(GET_BRAND_ID_QUERY, brand_tag)

        point_id = stock_info['stock']['points'][0]['point_id']
        url = config.pss_service.url + 'seller/point'
        params = dict(point_id=point_id, language_code=language_code)
        logger.info(f'запрос на url {url}, params: {params}')
        point = asyncio.create_task(
            get_api_response_json(request, session, url, 'get', headers, params=params))

        url = config.pss_service.url + 'seller/brand'

        params = dict(brand_tag=brand_tag, language_code=language_code)
        logger.info(f'запрос на url {url}, params: {params}')
        brand = asyncio.create_task(
            get_api_response_json(request, session, url, 'get', headers, params=params))
        brand_info = (await brand).get('brand')
        point_info = (await point).get('point')
        stock_info = (await stock).get('stock')
        rename_field(stock_info, ('stock_id', 'id'))
        rename_field(stock_info['cart'], [('cart_id', 'id'), ('cart_amount', 'amount')])
        for product in stock_info['cart']['products']:
            rename_field(product, ('product_amount', 'amount'))
        partner = dict(
            address_short=point_info.get('point_info'),
            open_partner_schedule=point_info.get('open_partner_schedule'),
            close_partner_schedule=point_info.get('close_partner_schedule'),
            logo_path=brand_info.get('logo_path'),
            name=brand_info.get('title'),
            id=brand_id
        )
        stock_info.pop('points')
        stock_info.pop('brand_tag')
        data = dict(stock=stock_info, partner=partner)
    return data


async def get_api_response_json(base_request, session, url, method, headers=None, params=None, json=None):
    try:
        if method.lower() == 'get':
            response = await session.get(url, headers=headers, params=params, json=json)
        elif method.lower() == 'post':
            response = await session.post(url, headers=headers, params=params, json=json)
        else:
            raise NotImplementedError
    except Exception as ex:
        raise ApiResponse(31, exc=ex, log_message=f"не удалось выполнить запрос к партнёрскму сервису: "
                                                  f"{method.upper()}: {url} : {ex}")
    try:
        response = await response.json()
    except Exception as ex:
        raise ApiResponse(90, exc=ex, log_message=f"не удалось распарсить json: {url}")
    if response.get('responseCode') != 0:
        raise ApiResponse(30, log_message=f"Ответ от стороннего сервиса не 0: {url} : "
                                          f"responseCode = {response.get('responseCode')}")
    return response.get('data')
