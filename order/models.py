import datetime
from typing import Optional, Union, List, Any

from api_utils import ApiPool
from api_utils import ApiResponse
from asyncpg import Connection
from loguru import logger
from pydantic import root_validator, conlist
from pydantic.main import BaseModel

import kassa
import pss
import settings
from user.models import User
from auth_model import config
from queries import CREATE_ORDER_QUERY
from settings import ONPASS_BRAND_TAG, ORGANISATION_NAME, POINT_NAME, KASSA_CONFIRM_CODE


class Product(BaseModel):
    id: int
    quantity: int
    price: int = 0


class Products(BaseModel):
    products: Optional[conlist(Product, min_items=1)]


class PostInput(Products):
    cart_id: Optional[int]
    mile_count: int = 0

    @root_validator
    def one_of(cls, v):
        keys_list = ['cart_id', 'products']
        if not len([k for k in [v.get(x) for x in keys_list] if k is not None]) == 1:
            raise ValueError(f'only one of {keys_list} must have a value')
        return v


class Order:
    input_model = PostInput
    params: PostInput
    _id: int
    _brand_tag: str
    _user: User
    _pss_order: dict
    _transaction_uuid: Union[str, None] = None
    _conn: Connection
    _amount: int

    @property
    def miles(self):
        return self.params.mile_count * 100

    def __init__(self, user: User):
        self._user = user

    async def create(self, input_params):
        pool = ApiPool.get_pool()
        async with pool.acquire() as self._conn:
            await self.collect_params(input_params)
            await self.collect_sum()
            await self.freeze_miles()
            await self.register_in_pss()
            await self.register_in_moa()
            return await self.make_response()

    async def collect_params(self, params):
        self.params = self.input_model(**params)
        self._brand_tag = ONPASS_BRAND_TAG

    async def collect_sum(self):
        products = list()
        product = self.params.products[0].copy()
        pss_response = (await pss.Product.pss_get(pss.Product.input_get_model(id=product.id)))
        if pss_response.code != 0:
            logger.error(f'ответ партнёрского сервиса не 0 а {pss_response.code}')
            raise ApiResponse(30)
        pss_product = pss_response.data
        price = pss_product['price']
        amount = price * product.quantity

        if self.miles == 0:
            product.price = price
            products.append(product)
        else:
            discount_amount = amount - self.miles
            division_remainder = discount_amount // 100 % product.quantity
            if division_remainder == 0:
                discount_price_per_product = discount_amount / product.quantity
                product.price = discount_price_per_product
                products.append(product)
            else:
                discount_price_per_product = discount_amount // 100 // product.quantity * 100
                first_product = Product(
                    id=product.id,
                    price=discount_price_per_product + 100,
                    quantity=division_remainder
                )
                another_products = Product(
                    id=product.id,
                    price=discount_price_per_product,
                    quantity=product.quantity - division_remainder
                )
                products.append(first_product)
                products.append(another_products)
        # discount_amount % 100
        self.params.products = products

    async def freeze_miles(self):
        kassa_response = await kassa.Info.get(kassa.models.InfoGetModel(qr=self._user.pqr))
        self._transaction_uuid = kassa_response['transaction_uuid']
        if self.params.mile_count != 0:
            data_rcc = kassa.models.RccPostModel(
                testing=str(config.is_dev).lower(),
                transaction_uuid=self._transaction_uuid,
                mile_count=self.params.mile_count,
                organization_name=ORGANISATION_NAME,
                point_name=POINT_NAME
            )
            await kassa.RCC.post(data_rcc)

            data_freeze = kassa.models.FreezePostModel(
                testing=str(config.is_dev).lower(),
                transaction_uuid=self._transaction_uuid,
                confirmation_code=KASSA_CONFIRM_CODE
            )
            await kassa.Freeze.post(data_freeze)

    async def register_in_pss(self):
        request_body = pss.OnpassOrder.input_post_model(
            products=self.params.products,
            brand_tag=self._brand_tag,
            profile_phone=self._user.phone_number,
            profile_fn=self._user.first_name,
            profile_ln=self._user.last_name,
        )
        pss_response = await pss.OnpassOrder.pss_post(request_body)
        if pss_response.code != 0:
            logger.error(f'ответ партнёрского сервиса не 0 а {pss_response.code}')
            raise ApiResponse(30)

        self._pss_order = pss_response.data

    async def register_in_moa(self):
        pss_qr = self._pss_order['order']['qr']
        point_id = int(self._pss_order['order']['products'][0]['points'][0]['point_id'])
        self._amount = self._pss_order['order'].get('sum')
        row = await self._conn.fetchrow(
            CREATE_ORDER_QUERY,
            self._user.id,
            self._amount,
            None,
            pss_qr,
            self._pss_order['order']['stock_id'],
            False,
            False,
            False,
            point_id,
            datetime.datetime.now() + datetime.timedelta(days=settings.EXP_ORDER_DAYS),
            self._transaction_uuid
        )

        self._id = row.get('id')

    async def make_response(self):
        response_order = ResponsePostModel(
            order_id=self._id,
            sum=self._amount,
            estimated_date=self._pss_order['order']['estimated_date'],
            refunded=self._pss_order['order']['refunded'],
            products=self._pss_order['order']['products'],
            stock=self._pss_order['order'].get('stock'),
        )
        return response_order


class OnpassOrder(Order):
    input_model = PostInput
    _brand_tag = ONPASS_BRAND_TAG


class ResponsePostModel(BaseModel):
    order_id: int
    qr: Union[str, None]
    sum: int
    estimated_date: Union[datetime.datetime, None]
    refunded: bool = False
    products: List[Any]
    custom: bool = False
    used_date: Union[datetime.datetime, None]
    stock: Optional[Any]
