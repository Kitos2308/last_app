from typing import List

from pydantic import BaseModel


class InfoGetModel(BaseModel):
    qr: str


class ConfirmationCodeMixin(BaseModel):
    confirmation_code: str = '2222'


class BaseCassaModel(BaseModel):
    testing: str = 'true'
    transaction_uuid: str


class BaseCassaModelTestingFalse(BaseModel):
    transaction_uuid: str

class RccPostModel(BaseCassaModel):
    mile_count: int
    organization_name: str
    point_name: str


class FreezePostModel(BaseCassaModel, ConfirmationCodeMixin):
    pass


class Product(BaseModel):
    id: str
    name: str
    quantity: float
    price: int
    amount: int


class Receipt(BaseModel):
    fn_number: str
    date: str
    organization_name: str
    organization_inn: str
    point_name: str
    kkt_number: str
    operator: str
    type: int
    amount: int
    url: str
    products: List[Product]


class CollectPostModel(BaseCassaModelTestingFalse):
    receipt: Receipt


class CollectPostModelFalse(BaseCassaModelTestingFalse):
    receipt: Receipt


class RedeemPutModel(CollectPostModelFalse, ConfirmationCodeMixin):
    pass


class UnfreezePostModel(BaseModel):
    transaction_uuid: str
