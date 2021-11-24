from abc import ABC
from contextvars import ContextVar
from datetime import date, datetime
from functools import wraps
from typing import Union, Any

from api_utils import ApiResponse, ApiPool
from loguru import logger
from pydantic import BaseModel


class AbstractProfile(BaseModel, ABC):
    id: int
    uid: str
    first_name: Union[str, None]
    last_name: Union[str, None]
    patronymic: Union[str, None]
    appeal_type_id: Union[int, None]
    birth_date: Union[date, None]
    phone_number: str
    email: Union[str, None]
    is_superuser: bool
    user_status_id: int
    active: bool
    is_deleted: bool = False
    created_date: datetime
    last_login: Union[datetime, None]
    mile_count: int
    pqr: str
    pass_count: int
    pass_count_1: int
    pass_count_2: int
    pass_count_3: int
    sent: bool
    channel_sms_enable: bool
    channel_push_enable: bool
    channel_email_enable: bool
    unread_banners_count: Union[int, None]
    resend_confirmation_email_date: Union[datetime, None]


class Profile(AbstractProfile):
    @classmethod
    async def find(cls, profile_id):
        async with ApiPool.get_pool().acquire() as conn:
            profile_row = await conn.fetchrow('select *, last_time_sent_email as resend_confirmation_email_date '
                                              'from profiles where id =$1', profile_id)
            if profile_row is None:
                return None
            return cls(**profile_row)


class User(AbstractProfile):
    device_id: Union[int, None]
    fcm_token: Union[str, None]
    locale: Union[str, None]

    @staticmethod
    def get():
        return user_context.get()

    def set_context(self):
        return user_context.set(self)

    @classmethod
    def superuser_only(cls, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = cls.get()
            if not user.is_superuser:
                logger.warning(f'попытка обратиться к привелегированому эндпоинту {user}')
                return ApiResponse(21)
            return await func(*args, **kwargs)

        return wrapper


class NoneUser(User):
    device_id: Any = None
    fcm_token: Any = None
    locale: Any = None
    id: Any = None
    uid: Any = None
    first_name: Any = None
    last_name: Any = None
    patronymic: Any = None
    appeal_type_id: Any = None
    birth_date: Any = None
    phone_number: Any = None
    email: Any = None
    is_superuser: Any = None
    user_status_id: Any = None
    active: Any = None
    is_deleted: Any = None
    created_date: Any = None
    last_login: Any = None
    mile_count: Any = None
    pqr: Any = None
    pass_count: Any = None
    pass_count_1: Any = None
    pass_count_2: Any = None
    pass_count_3: Any = None
    sent: Any = None
    channel_sms_enable: Any = None
    channel_push_enable: Any = None
    channel_email_enable: Any = None
    unread_banners_count: Any = None


user_context: ContextVar[User] = ContextVar('user', default=NoneUser())
