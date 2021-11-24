from typing import Optional, List

from pydantic import BaseModel, validator


class Product(BaseModel):
    id: int
    quantity: int
    price: Optional[int]


class Products(BaseModel):
    products: Optional[List[Product]]


class PostOrderInput(Products):
    brand_tag: str
    airport_code: str
    stock_id: Optional[int]
    cart_id: Optional[int]
    profile_phone: Optional[str]
    profile_fn: Optional[str]
    profile_ln: Optional[str]


class OnpassPostOrderInput(PostOrderInput):
    airport_code: Optional[str]
    profile_phone: str
    profile_fn: str
    profile_ln: str


class OrderGetInput(BaseModel):
    qr: str
    #
    # class Config:
    #     fields = {
    #         'qr': 'pss_qr'
    #     }


class BindCardModels:
    class Post:
        class Input(BaseModel):

            @validator('expire_date', pre=True)
            def expire_date_validator(cls, v):
                return v.strftime('%m/%y')

            customer_id: str
            masked_bin: str
            expire_date: str
            holder_name: str
            binding_id: str
            allow_duplicates: Optional[bool] = False

        class Output(BaseModel):
            hash_value: str
            card_type: str


class UnBindCardModels:
    class Post:
        class Input(BaseModel):
            hash_value: str


class PacketsModels:
    class Post:
        class Input(BaseModel):
            hash_value: str
            language_code: str = 'ru'


class PremOrderModels:
    class Post:
        class Input(BaseModel):
            stock_id: int
            language_code: str
            customer_id: str
            count: int
            profile_phone: str
            profile_fn: str
            profile_ln: str


class PremOrdersModels:
    class Get:
        class Input(BaseModel):
            language_code: str
            customer_id: str
            active: Optional[str]
