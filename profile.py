from datetime import datetime, date, timedelta
from typing import Union, Optional

from api_utils import ApiResponse, ApiPool
from asyncpg import UniqueViolationError
from loguru import logger
from pydantic import BaseModel, EmailStr, ValidationError

from queries import UPDATE_PROFILE_QUERY_SEARCH_PROFILE_BY_UIID
from settings import POOL, FORMAT_DATE
from tools import generate_uuid5, generate_new_pqr, date_now


# pool = ApiPool.get_pool(POOL)

class Settings(BaseModel):
    language_id: int


class OnpassData(BaseModel):
    pass_count_1: Optional[int]
    pass_count_2: Optional[int]
    pass_count_3: Optional[int]


class UserStatus(BaseModel):
    name: Optional[str]
    conversion_rate: Optional[float]
    minimum_conversion_threshold: Optional[float]


MY_LANGUAGE_QUERY = (
    'select l.id, sid, profile_id '
    'from languages l '
    'inner join sessions s on code = locale '
    'inner join profiles p on s.profile_id = p.id '
    'where s.active = True')


class Profile(BaseModel):
    # pool = ApiPool.get_pool(POOL)

    _get_query = f"""with my_language as ({MY_LANGUAGE_QUERY})
        SELECT uid as customer_id,  
               phone_number,  
               first_name,  
               last_name,  
               patronymic,  
               email,  
               birth_date,  
               mile_count,
               unread_banners_count,
               ust.name,  
               conversion_rate,  
               minimum_conversion_threshold,  
               my_language.id as language_id, 
               pqr, 
               pass_count_1, 
               pass_count_2, 
               pass_count_3,
               last_time_sent_email as resend_confirmation_email_date,
               email_confirmed as is_email_confirmed
        FROM profiles p  
          
                 inner join user_status us on p.user_status_id = us.id  
                 inner join my_language on p.id = my_language.profile_id  
                 left outer join user_status_translate ust on us.id = ust.user_status_id 
                      and ust.language_id = my_language.id  
        where sid = $1;"""

    _update_query = """UPDATE "profiles"
SET first_name  = $1,
    last_name   = $2,
    patronymic  = $3,
    birth_date  = $4,
    email       = $5,
    update_date = $6
WHERE id = (SELECT profile_id FROM sessions WHERE sid = $7);
"""

    customer_id: str
    phone_number: str
    birth_date: Union[str, None]
    first_name: Union[str, None]
    birth_date: Union[date, None]
    patronymic: Optional[str]
    last_name: Union[str, None]
    mile_count: int
    unread_banners_count: int = 0
    pqr: str
    email: Union[EmailStr, None]
    user_status: Union[UserStatus, None]
    settings: Union[Settings, None]
    onpass_data: Union[OnpassData, None]
    resend_confirmation_email_date: Union[datetime, None]
    is_email_confirmed: bool = False

    def __init__(self, **kwargs):
        if kwargs.get('unread_banners_count') is None:
            kwargs['unread_banners_count'] = 0
        kwargs.update({'onpass_data': OnpassData(**kwargs)})
        kwargs.update({'settings': Settings(**kwargs)})
        kwargs.update({'user_status': UserStatus(**kwargs)})
        super().__init__(**kwargs)

    class ProfileUpdateSchema(BaseModel):

        first_name: Optional[str]
        last_name: Optional[str]
        patronymic: Optional[str]
        email: Optional[EmailStr]
        birth_date: Optional[date]

    @classmethod
    async def get_by_session(cls, session_id):
        pool = ApiPool.get_pool(POOL)
        async with pool.acquire() as connection:
            profile_query_result = await connection.fetchrow(cls._get_query, session_id)
            try:
                if profile_query_result is not None:
                    profile = Profile(**profile_query_result)
                    _time_interval = await connection.fetchval(''' select value from system_parameters 
                                                                where name=$1''', 'timeout_email')
                    if profile.resend_confirmation_email_date is not None:
                        profile.resend_confirmation_email_date = profile.resend_confirmation_email_date + timedelta(seconds=int(_time_interval))
                else:
                    raise ApiResponse(21)
            except ValidationError as err:
                query_res = None if profile_query_result is None else dict(profile_query_result)
                logger.debug(f'session_id: {session_id} profile query result: {query_res}')
                raise ApiResponse(90, exc=err)
            return profile

    @classmethod
    async def create_new(cls, phone, active=False, first_name=None, last_name=None):
        pool = ApiPool.get_pool(POOL)
        error = None
        profile_id = None
        uid_new = generate_uuid5(phone, date_now())
        pqr = generate_new_pqr(phone)
        try:
            async with pool.acquire() as connection:
                async with connection.transaction():
                    profile_id = await connection.fetchval(f'INSERT INTO profiles '
                                                           f'(uid, phone_number, active, first_name, last_name, pqr) '
                                                           f'VALUES '
                                                           f'($1, $2, $3, $4, $5, $6) RETURNING id',
                                                           uid_new, phone, active, first_name, last_name, pqr)
        except Exception as exc:
            error = f'register_new_user: Исключение (phone={phone}): {exc}'
            logger.error(error)
        return profile_id, error

    async def update(self, params):
        pool = ApiPool.get_pool(POOL)
        first_name = params.get('first_name', self.first_name)
        last_name = params.get('last_name', self.last_name)
        patronymic = params.get('patronymic', self.patronymic)
        resend_confirmation_email_date = params.get('resend_confirmation_email_date', self.resend_confirmation_email_date)
        is_email_confirmed = params.get('is_email_confirmed', self.is_email_confirmed)
        if self.birth_date is None and params.get('birth_date') is not None:
            birth_date = datetime.strptime(params.get('birth_date'), FORMAT_DATE)
        else:
            birth_date = self.birth_date
        email = params.get('email', self.email)
        update_date = None
        async with pool.acquire() as conn:
            async with conn.transaction():
                try:
                    await conn.execute(
                        UPDATE_PROFILE_QUERY_SEARCH_PROFILE_BY_UIID,
                        first_name,
                        last_name,
                        patronymic,
                        birth_date,
                        email,
                        update_date,
                        resend_confirmation_email_date,
                        is_email_confirmed,
                        self.customer_id)
                except UniqueViolationError as exc:
                    raise ApiResponse(13, exc=exc)


class EmailAddress(BaseModel):
    email: EmailStr
