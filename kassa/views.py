from json import JSONDecodeError
from typing import Optional, Union

import aiohttp
from aiohttp import ClientError
from api_utils import ApiResponse
from pydantic import ValidationError, BaseModel, validator

from auth_model import config
from kassa import InfoGetModel, RccPostModel, FreezePostModel, CollectPostModel
from kassa.models import RedeemPutModel, UnfreezePostModel


class KassaResponse(BaseModel):
    code: int
    message: str
    data: Optional[Union[dict, list]]

    class Config:
        fields = {
            'code': 'responseCode',
            'message': 'responseMessage'
        }

    @validator('code')
    def success_response(cls, v):
        if v != 0:
            raise ValueError('Ответ от партнёрского сервиса не 0')
        return v


class BaseKassaRequest:
    input_get_model = NotImplemented
    input_post_model = NotImplemented
    url = NotImplemented
    headers = {'Authorization': f'Bearer {config.kassa_service.token}'}

    @staticmethod
    def make_request_params(method, params):
        params_name = {
            'get': 'params',
            'post': 'json',
            'put': 'json'
        }
        return {params_name[method]: params}

    @classmethod
    async def _make_request(cls, method, params):
        async with aiohttp.ClientSession() as session:
            try:
                if isinstance(params, dict):
                    response = await session.__getattribute__(method)(
                        cls.url,
                        headers=cls.headers,
                        **cls.make_request_params(method, params))
                else:
                    response = await session.__getattribute__(method)(
                        cls.url,
                        headers=cls.headers,
                        **cls.make_request_params(method, params.dict(exclude_none=True)))
                response_json = await response.json()
                data = KassaResponse(**response_json)
            except ValidationError as exc:
                raise ApiResponse(30, exc=exc, log_message=response_json)
            except (JSONDecodeError, ClientError)as exc:
                raise ApiResponse(30, exc=exc)

            return data.data

    @classmethod
    async def get(cls, params: input_get_model):
        return await cls._make_request('get', params)

    @classmethod
    async def post(cls, params: input_post_model):
        return await cls._make_request('post', params)

    @classmethod
    async def put(cls, params: input_post_model):
        return await cls._make_request('put', params)


class Info(BaseKassaRequest):
    url = config.kassa_service.url + 'qr/info'
    input_get_model = InfoGetModel


class RCC(BaseKassaRequest):
    url = config.kassa_service.url + 'rcc'
    input_post_model = RccPostModel


class Freeze(BaseKassaRequest):
    url = config.kassa_service.url + 'miles/freeze'
    input_post_model = FreezePostModel


class Collect(BaseKassaRequest):
    url = config.kassa_service.url + 'miles/collect'
    input_post_model = CollectPostModel


class Redeem(BaseKassaRequest):
    url = config.kassa_service.url + 'miles/redeem'
    input_post_model = RedeemPutModel


class Unfreeze(BaseKassaRequest):
    url = config.kassa_service.url + 'miles/unfreeze'
    input_post_model = UnfreezePostModel
