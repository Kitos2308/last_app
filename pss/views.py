from datetime import datetime
from enum import Enum
from json import JSONDecodeError
from typing import Optional, Union, List, Any

import aiohttp
from aiohttp import ClientError, ServerDisconnectedError, ClientConnectionError
from api_utils import ApiResponse
from loguru import logger
from pydantic import BaseModel

from auth_model import config
from pss.models import OnpassPostOrderInput, PostOrderInput, OrderGetInput, BindCardModels, UnBindCardModels, \
    PacketsModels, PremOrderModels, PremOrdersModels
from settings import ONPASS_BRAND_TAG


class PssResponse(BaseModel):
    code: int
    message: str
    data: Optional[Union[dict, list]]

    class Config:
        fields = {
            'code': 'responseCode',
            'message': 'responseMessage'
        }

    # @validator('code')
    # def success_response(cls, v):
    #     if v != 0:
    #         logger.warning(f'Ответ от партнёрского сервиса не 0 а {v}')
    #     return v


class BasePssRequest:
    input_get_model = NotImplemented
    input_post_model = NotImplemented
    path = NotImplemented
    headers = {'Authorization': f'Bearer {config.pss_service.token}'}

    @classmethod
    async def pss_get(cls, params: input_get_model) -> PssResponse:
        async with aiohttp.ClientSession() as session:
            try:
                url = config.pss_service.url + cls.path
                response = await session.get(url, headers=cls.headers, params=params.dict(exclude_none=True))
                response_json = await response.json()
                data = PssResponse(**response_json)
            except (ServerDisconnectedError, ClientConnectionError):
                logger.error('сервер псс не отвечает либо разорвал соединение')
                raise ApiResponse(31)
            except (JSONDecodeError, ClientError)as exc:
                logger.exception(exc)
                raise ApiResponse(30, exc=exc)

            return data

    @classmethod
    async def pss_post(cls, params: input_post_model):
        async with aiohttp.ClientSession() as session:
            try:
                url = config.pss_service.url + cls.path
                response = await session.post(
                    url,
                    headers=cls.headers,
                    json=params.dict(exclude_none=True))
                response_json = await response.json()
                data = PssResponse(**response_json)
            except (ServerDisconnectedError, ClientConnectionError):
                logger.error('сервер псс не отвечает либо разорвал соединение')
                raise ApiResponse(31)
            except (JSONDecodeError, ClientError) as exc:
                logger.error(f'ошибка декодирования ответа от ПСС. Запрос:{params} ответ {response.content}')
                raise ApiResponse(30, exc=exc)

            return data


class PointsModel(BaseModel):
    class Point(BaseModel):
        id: int
        name: str
        airport_code: str
        terminal: Union[str, None]
        address_short: Union[str, None]
        floor: Union[str, None]
        photo_path: Union[str, None]
        active: bool
        closed: bool
        brand_tag: str
        custom_info: Union[dict, None]
        price: int = 0
        purchased_visits_count: int = 0

    points: List[Point]


class Points(BasePssRequest):
    path = 'seller/points'

    class InputGetData(BaseModel):
        brand_tag: str = ONPASS_BRAND_TAG
        language_code: Optional[str]
        airport_code: Optional[str]

    input_get_model = InputGetData


class OrdersModel(BaseModel):
    class Order(BaseModel):

        class Product(BaseModel):
            class Point(BaseModel):
                id: int
                airport_code: str
                terminal: Union[str, None]

                class Config:
                    fields = {
                        'id': 'point_id'
                    }

            id: int
            quantity: int
            remainder: Union[int, None]
            product_amount: int
            tax: str = 'vat20'
            payment_object: Optional[str]
            payment_method: Optional[str]
            name: Union[str, None]
            price: int
            points: List[Point]

        products: List[Product]

        id: int
        qr: str
        sum: int
        profile_phone: Union[str, None]
        profile_fn: Union[str, None]
        profile_ln: Union[str, None]
        created_date: datetime
        sold_date: Union[datetime, None]
        confirmed_date: Union[datetime, None]
        refunded_date: Union[datetime, None]
        estimated_date: Union[datetime, None]
        used: Optional[bool] = False
        paid: Optional[bool] = False
        sent: Optional[bool] = False
        brand_tag: Optional[str]

        class Config:
            fields = {
                'id': 'order_id'
            }

    orders: List[Order] = list()

    def _get_by_id(self, order_id):
        for order in self.orders:
            if order_id == order.id:
                return order

    def _get_by_qr(self, order_qr):
        for order in self.orders:
            if order_qr == order.qr:
                return order

    def find(self, order_id=None, order_qr=None):
        if order_id is not None:
            return self._get_by_id(order_id)
        elif order_qr is not None:
            return self._get_by_qr(order_qr)
        else:
            return None


class Orders(BasePssRequest):
    class InputGetData(BaseModel):
        def __init__(self, **data: Any):
            if data.get('phone') is not None:
                data['phone'] = data.get('phone').strip('+')
            if data.get('qr_codes') is not None:
                data['qr_codes'] = [x.strip() for x in data.get('qr_codes').split(',')]
            super().__init__(**data)

        class FilterEnum(str, Enum):
            all = 'all'
            actual = 'actual'
            archive = 'archive'

        class Config:
            use_enum_values = True

        brand_tag: Optional[str]
        airport_code: Optional[str]
        phone: Optional[str]
        qr_codes: Optional[List[str]]
        filter: FilterEnum = FilterEnum.all
        limit: int = 20
        offset: int = 0

    orders: List[OrdersModel] = list()

    path = 'seller/orders'
    input_get_model = InputGetData


class Order(BasePssRequest):
    path = 'seller/order'
    input_post_model = PostOrderInput
    input_get_model = OrderGetInput


class OnpassOrder(Order):
    path = 'seller/allOrder'
    input_post_model = OnpassPostOrderInput


class ProductGetInput(BaseModel):
    id: int


class Product(BasePssRequest):
    path = 'seller/product'
    input_get_model = ProductGetInput


class BindCard(BasePssRequest):
    path = 'privileges/bindCard'
    input_post_model = BindCardModels.Post.Input


class UnBindCard(BasePssRequest):
    path = 'privileges/unbindCard'
    input_post_model = UnBindCardModels.Post.Input


class CardPackets(BasePssRequest):
    path = 'privileges/packets'
    input_post_model = PacketsModels.Post.Input


class PremOrder(BasePssRequest):
    path = 'privileges/order'
    input_post_model = PremOrderModels.Post.Input

class PremOrders(BasePssRequest):
    path = 'privileges/orders'
    input_post_model = PremOrdersModels.Get.Input