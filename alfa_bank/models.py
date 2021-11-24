from datetime import datetime
from typing import Optional, Any, List

from pydantic import validator
from pydantic.main import BaseModel


from auth_model import config


class CartItemQuantity(BaseModel):
    measure: str = "шт."
    value: float


class CartItem(BaseModel):
    positionId: str
    name: str
    quantity: CartItemQuantity
    itemAmount: int
    itemPrice: int
    itemCode: str


class CartItems(BaseModel):
    items: List[CartItem]


class CustomerDetails(BaseModel):
    email: Optional[str]


class ResponseOrderBundle(BaseModel):
    customerDetails: Optional[CustomerDetails] = dict()


class OrderBundle(BaseModel):
    cartItems: Optional[CartItems]
    customerDetails: Optional[CustomerDetails] = dict()

    def add_item(self, bundle_name, price, item_code, quantity=1, product_measure='шт'):
        if self.cartItems is None:
            self.cartItems = CartItems(items=list())
            pass
        cart_item = CartItem(
            positionId=str(len(self.cartItems.items) + 1),
            name=bundle_name,
            quantity=CartItemQuantity(
                measure=product_measure,
                value=quantity
            ),
            itemAmount=quantity * price,
            itemPrice=price,
            itemCode=str(item_code) + '_' + str(price))
        self.cartItems.items.append(
            cart_item
        )


class GooglePaymentData(BaseModel):
    ip: str
    merchant: str = config.alpha_bank_service.merchant
    paymentToken: str
    orderNumber: str
    orderBundle: Optional[OrderBundle]
    amount: int
    returnUrl: str

    class Config:
        fields = {
            'orderNumber': 'order_id',
            'returnUrl': 'return_url'
        }


class ApplePaymentData(BaseModel):
    merchant: str = config.alpha_bank_service.merchant
    paymentToken: str
    orderNumber: str
    orderBundle: Optional[OrderBundle]


class WebPaymentData(BaseModel):
    token: str = config.alpha_bank_service.token
    clientId: Optional[str]
    orderNumber: str
    orderBundle: Optional[OrderBundle]
    amount: int
    returnUrl: str
    language: str


class WebPaymentResponse(BaseModel):
    order_id: Optional[str]
    formUrl: Optional[str]
    error_code: Optional[Any]
    error_message: Optional[Any]

    class Config:
        fields = {
            'order_id': 'orderId',
            'error_code': 'errorCode',
            'error_message': 'errorMessage',
        }

    @validator('error_code')
    def success_response(cls, v):
        if v is not None:
            raise ValueError(f'не удалось зарегестрировать заказа в альфе: {v}')
        return v


class WebPaymentError(BaseModel):
    errorCode: int
    errorMessage: str


class MobilePaymentResponse(BaseModel):
    class Data(BaseModel):
        orderId: str = None

    class Error(BaseModel):
        code: int
        description: str
        message: str

    success: bool
    data: Optional[Data]
    error: Optional[Error]


class GetOrderStatusExtendedData(BaseModel):
    token: str = config.alpha_bank_service.token
    orderId: str


class CardAuthInfo(BaseModel):
    maskedPan: Optional[str]
    expiration: Optional[str]
    cardholderName: Optional[str]
    approvalCode: Optional[str]
    paymentSystem: Optional[str]
    pan: Optional[str]


class BindingInfo(BaseModel):
    clientId: Optional[str]
    bindingId: Optional[str]


class GetOrderStatusExtendedDataResponse(BaseModel):
    order_status: Optional[int]
    error_code: Optional[int]
    error_message: Optional[str]
    order_number: str
    action_code: Optional[int]
    action_code_description: Optional[str]
    amount: Optional[int]
    currency: Optional[str]
    date: Optional[datetime]
    cardAuthInfo: Optional[CardAuthInfo]
    bindingInfo: Optional[BindingInfo]
    orderBundle: Optional[ResponseOrderBundle] = dict()

    class Config:
        fields = {
            'order_status': 'orderStatus',
            'error_code': 'errorCode',
            'error_message': 'errorMessage',
            'order_number': 'orderNumber',
            'action_code': 'actionCode',
            'action_code_description': 'actionCodeDescription'
        }


class RegisterPreAuthModel(BaseModel):
    userName: str = config.alpha_bank_service.login
    password: str = config.alpha_bank_service.password
    clientId: str
    orderNumber: str
    amount: int
    returnUrl: str
    language: str
    orderBundle: Optional[OrderBundle]


class ReverseModel(BaseModel):
    userName: str = config.alpha_bank_service.login
    password: str = config.alpha_bank_service.password
    orderId: str


class UnbindModel(BaseModel):
    userName: str = config.alpha_bank_service.login
    password: str = config.alpha_bank_service.password
    bindingId: str
