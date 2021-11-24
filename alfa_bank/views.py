from json import JSONDecodeError
from typing import TypeVar

import aiohttp
from aiohttp import ClientError
from api_utils import ApiResponse
from loguru import logger
from pydantic import ValidationError, BaseModel

from alfa_bank.models import WebPaymentData, MobilePaymentResponse, ApplePaymentData, GooglePaymentData, \
    WebPaymentResponse, GetOrderStatusExtendedData, GetOrderStatusExtendedDataResponse, OrderBundle, CartItems, \
    CartItem, CartItemQuantity, RegisterPreAuthModel, ReverseModel, WebPaymentError, CustomerDetails, UnbindModel
from auth_model import config
from utils import DecodingStreamReader, mask_pans


def create_bundle(products, email):
    bundle = OrderBundle(
        customerDetails=CustomerDetails(email=email),
        cartItems=CartItems(
            items=[CartItem(
                positionId=str(position_id + 1),
                name=products[position_id].get('bundle_name'),
                quantity=CartItemQuantity(
                    value=products[position_id].get('quantity')
                ),
                itemAmount=products[position_id].get('product_amount'),
                itemPrice=products[position_id].get('price'),
                itemCode='_'.join(map(str, [products[position_id].get('id'), products[position_id].get('price')]))
            ) for position_id in range(len(products))]
        )
    )
    if email is not None:
        bundle.customerDetails = CustomerDetails(email=email)
    return bundle


T = TypeVar('T', bound=BaseModel)


class AlfaBankPay:
    __token: str = config.alpha_bank_service.token
    url = NotImplemented
    input_post_model = NotImplemented
    payment_response = NotImplemented
    params_name = 'json'

    @classmethod
    def make_request_params(cls, params):
        return {cls.params_name: params}

    @classmethod
    async def post(cls, params: input_post_model, raise_api_response: bool = True) -> T:
        async with aiohttp.ClientSession() as session:
            try:

                logger.debug(f'запрос на альфу {cls.url}, с параметрами {params}')
                foo = cls.make_request_params(params.dict(exclude_none=True))
                response_content = await session.post(
                    cls.url,
                    **foo
                )
            except ClientError as exc:
                logger.error(f'не удалось получить ответ от альфы; {exc}')
                if raise_api_response:
                    raise ApiResponse(30, exc=exc)
            try:
                response_raw = await DecodingStreamReader(response_content.content).read()
                logger.debug(f'получен ответ {mask_pans(response_raw)}')
                payment_response: T = cls.payment_response.parse_raw(response_raw)

            except ValidationError as exc:
                logger.error(f'ответ от альфы на {cls.url}: {mask_pans(response_raw)} exc: {exc}')
                if raise_api_response:
                    raise ApiResponse(30, exc=exc)
            except JSONDecodeError as exc:
                raise ApiResponse(30, exc=exc,
                                  log_message=f'(JSONDecodeError, ClientError), {response_content.content}')
            except Exception as exc:
                logger.exception(exc)
                raise ApiResponse(90, exc=exc)

            return payment_response


class WebPay(AlfaBankPay):
    url = config.alpha_bank_service.url + 'rest/register.do'
    input_post_model = WebPaymentData
    payment_response = WebPaymentResponse
    params_name = 'params'

    @classmethod
    def make_request_params(cls, params: dict):
        params['orderBundle'] = OrderBundle(**params['orderBundle']).json()
        return {cls.params_name: params}


class ApplePay(AlfaBankPay):
    url = config.alpha_bank_service.url + 'applepay/payment.do'
    input_post_model = ApplePaymentData
    payment_response = MobilePaymentResponse


class GooglePay(AlfaBankPay):
    url = config.alpha_bank_service.url + 'google/payment.do'
    input_post_model = GooglePaymentData
    payment_response = MobilePaymentResponse


class GetOrderStatusExtended(AlfaBankPay):
    url = config.alpha_bank_service.url + 'rest/getOrderStatusExtended.do'
    input_post_model = GetOrderStatusExtendedData
    params_name = 'params'
    payment_response = GetOrderStatusExtendedDataResponse



class RegisterPreAuth(AlfaBankPay):
    @classmethod
    def make_request_params(self, params: dict):
        if params.get('orderBundle') is not None:
            params['orderBundle'] = OrderBundle(**params['orderBundle']).json()
        return {self.params_name: params}

    url = config.alpha_bank_service.url + 'rest/registerPreAuth.do'
    input_post_model = RegisterPreAuthModel
    params_name = 'params'
    payment_response = WebPaymentResponse


class Reverse(AlfaBankPay):
    url = config.alpha_bank_service.url + 'rest/reverse.do'
    input_post_model = ReverseModel
    params_name = 'params'
    payment_response = WebPaymentError


class Unbind(AlfaBankPay):
    url = config.alpha_bank_service.url + 'rest/unBindCard.do'
    input_post_model = UnbindModel
    params_name = 'params'
    payment_response = WebPaymentError