from typing import List, Union

from pydantic import BaseModel

from auth import config_json


class DatabaseConfig(BaseModel):
    db_host: Union[str, None]
    db_port: Union[int, None]
    db_name: Union[str, None]
    db_user: Union[str, None]
    db_pass: Union[str, None]

    command_timeout: int = 30
    min_size: int = 10
    max_size: int = 100
    max_queries: int = 23456
    max_inactive_connection_lifetime: int = 60


class MailConfig(BaseModel):
    host:str
    user: str  # email отправителя (логин) smtp сервера
    password: str  # email получателя фидбеков
    receiver: str  #


class ServicesConfig(BaseModel):
    url: str
    token: str


class AlphaBankConfig(ServicesConfig):
    merchant: str
    login: str
    password: str


class KassaConfig(ServicesConfig):
    confirm_code: int


class Redis(BaseModel):
    url: str


class AuthModel(BaseModel):
    is_dev: bool
    media_url: str
    feedback_images_folder: str
    exp_orders_days: int
    sha_secret_addition: str
    exclude_phones: List[str] = []
    database: DatabaseConfig
    log_database: DatabaseConfig
    mail: MailConfig
    sms_service: ServicesConfig
    pss_service: ServicesConfig
    callback_service: ServicesConfig
    kassa_service: KassaConfig
    alpha_bank_service: AlphaBankConfig
    onpass_acq_point_id: int
    organization_name: str
    point_name: str
    qr_secret_key: str
    redis: Redis


config = AuthModel(**config_json)
