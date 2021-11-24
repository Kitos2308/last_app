from datetime import datetime
from typing import Optional, List, Union

from pydantic.main import BaseModel


class Product(BaseModel):
    id: int
    quantity: int


class BasePostOrderModel(BaseModel):
    cart_id: Optional[int]
    products: List[Product] = []
    mile_count: Optional[int]

    payment_type: Optional[str]
    payment_token: Optional[str]

    class Config:
        extra = 'forbid'


class PostOrderModel(BasePostOrderModel):
    partner_id: int
    airport_id: int


class OrderModel(BaseModel):
    id: int
    point_id: Union[int, None]
    qr: Union[str, None]
    profile_id: int
    sold_date: Union[datetime, None]
    sum: int
    estimated_date: Union[datetime, None]
    type: int
    created_date: Union[datetime, None]
    used: Union[bool, None] = False
    used_date: Union[datetime, None]
    stock_id: Union[int, None]
    paid: Union[bool, None] = False
    sent: Union[bool, None] = False
    confirmed_date: Union[datetime, None]
    refunded_date: Union[datetime, None]
    custom: Union[bool, None] = False
    pss_qr: Union[str, None]
    pss_stock_id: Union[int, None]
    confirmed: Union[bool, None] = False
    refunded: Union[bool, None] = False
    pss_point_id: Union[int, None]
    expiration_date: Union[datetime, None]
    processed: Union[bool, None] = False
    uuid_relation: Union[str, None]
