import hashlib
import json
import re
import uuid
from asyncio import CancelledError
from contextlib import closing
from datetime import datetime, timedelta
from json import JSONDecodeError
from random import choice

import psycopg2
from aiohttp import web
from aiohttp_session import get_session
from loguru import logger
from psycopg2.extras import DictCursor

from api_utils import ApiResponse, ApiPool

from settings import *
from sms import send_sms
from user.models import User, NoneUser


def date_now():
    return datetime.now()


def get_response_json(code, message, data=None):
    if data is None:
        data = {}
    response_obj = {RESPONSE_CODE: code, RESPONSE_MESSAGE: message}
    if len(data) > 0:
        response_obj[RESPONSE_DATA] = data
    return response_obj


def get_sys_param(param_name):
    res = None
    try:
        with closing(psycopg2.connect(**DATABASE_LOCAL)) as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor_local:
                conn.autocommit = True
                cursor_local.execute(f'SELECT value FROM system_parameters WHERE name=\'{param_name}\'')
                for row in cursor_local:
                    res = row.get('value', None)
    except Exception as exc:
        logger.error(f'Ошибка в функции get_sys_param: {exc}')
        raise ApiResponse(90, exc=exc)
    return res


def read_sys_params(app):
    error = None
    try:
        type_logging = get_sys_param(TYPE_OF_LOGGING_SYS)
        app[LOGGING_TYPE] = type_logging if type_logging is not None else TYPE_OF_LOGGING

        app[SP_SMS_STATUS] = True if str(get_sys_param(SP_SMS_STATUS)).upper() == 'TRUE' else SMS_ENABLE

        life_time = get_sys_param(LIFE_TIME_LONG_TOKEN)
        app[LIFE_TIME_LONG_TOKEN] = int(life_time) if life_time is not None else LOC_LIFE_TIME_LONG_TOKEN

        life_time_s = get_sys_param(LIFE_TIME_SESSION)
        app[LIFE_TIME_SESSION] = int(life_time_s) if life_time_s is not None else LOC_LIFE_TIME_SESSION

        code_lt = get_sys_param(CONFIRMATION_CODE_LIFETIME)
        app[CONFIRMATION_CODE_LIFETIME] = int(code_lt) if code_lt is not None else LOC_CONFIRMATION_CODE_LIFETIME

        app[RESOURCE_URL] = get_sys_param(RESOURCE_URL)
    except web.HTTPException:
        raise
    except Exception as err:
        raise
    log = f'Запуск экземпляра приложения. Считаны системные параметры: {LOGGING_TYPE}={type_logging}, ' \
          f'{SP_SMS_STATUS}={app[SP_SMS_STATUS]}, {LIFE_TIME_LONG_TOKEN}={life_time}, ' \
          f'{LIFE_TIME_SESSION}={life_time_s}, {CONFIRMATION_CODE_LIFETIME}={code_lt}, ' \
          f'{RESOURCE_URL}={app[RESOURCE_URL]}. Ошибки: {error}'
    print(log)
    return log


async def get_data_from_request(request) -> dict:
    try:
        data = await request.json()
    except JSONDecodeError as e:
        d = await request.read()
        logger.error(f'Ошибка при декодировании JSON запроса: {e}: {d}')
        raise ApiResponse(11)
    except Exception as ex:
        logger.error(f'Ошибка при обращении к JSON из запроса: {ex}')
        raise ApiResponse(14)
    if data is None:
        logger.warning('Пустой JSON в запросе')
        raise ApiResponse(14)
    return data


def get_pool_from_request(request):
    pool = ApiPool.get_pool(POOL)
    if pool is None:
        logger.critical('Не настроено подключение к БД')
        raise ApiResponse(90)
    return pool


async def is_valid(phone):
    """
    Проверка на корректность номера телефона
    """
    if not re.match(r'^((\+7)[\- ]?)?(\(?\d{3}\)?[\- ]?)?[\d\- ]{7,10}$',
                    phone):  # регулярка на валиюацию номера телефона
        return False
    return True


async def check_user(request, phone):
    pool = get_pool_from_request(request)
    user = None
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                user = await connection.fetchrow(f'SELECT * FROM profiles '
                                                 f'WHERE phone_number=$1 and is_deleted=False', phone)
    except CancelledError:
        raise
    except Exception as exc:
        logger.error(f'Исключение в check_user (phone={phone}): {exc}')
    return user


async def get_profile_id_from_phone(request, phone):
    pool = get_pool_from_request(request)
    profile_id = None
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                profile_id = await connection.fetchval(f'SELECT id FROM profiles '
                                                       f'WHERE phone_number=$1 and is_deleted=False', phone)
    except CancelledError:
        raise
    except Exception as exc:
        logger.error(f'Исключение в get_profile_id_from_phone: {exc}')
    return profile_id


async def get_device_id_from_gsid(request, gsid):
    pool = get_pool_from_request(request)
    device = None
    try:
        dt = date_now()
        async with pool.acquire() as connection:
            device = await connection.fetchrow(f'SELECT * FROM devices '
                                               f'WHERE guid=$1 AND exp_date>$2 AND active=true', str(gsid), dt)
        if device is not None:
            logger.debug(f'Запрос девайса в БД: gsid={str(gsid)}: device_id={device.get("id")}, '
                         f'model={device.get("device_model")}, os={device.get("os")}, '
                         f'os_version={device.get("os_version")}')
        else:
            logger.debug(f'Запрос девайса в БД: gsid={str(gsid)}: device={device}')
    except CancelledError:
        raise
    except Exception as exc:
        logger.error(f'Исключение в get_device_id_from_gsid gsid={str(gsid)}: {exc}')
    return device


async def get_device_row(request, gsid):
    pool = get_pool_from_request(request)
    device_row = None
    try:
        logger.debug(f'Запрос device в базе для gsid={gsid}...')
        async with pool.acquire() as connection:
            device_row = await connection.fetchrow(f'SELECT * FROM devices WHERE guid=$1', str(gsid))
    except CancelledError:
        raise
    except Exception as exc:
        logger.error(f'Исключение в get_device_row gsid={gsid}: {exc}')
    return device_row


def get_ip_from_request(request):
    ip_client = None
    if request is not None:
        ip_remote = request.remote if request.remote is not None else ''
        ip_client = request.headers.get('X-FORWARDED-FOR', ip_remote)
    return ip_client


def get_user_agent_from_request(request):
    user_agent = None
    if request is not None:
        user_agent = request.headers.get('User-Agent', None)
    return user_agent


async def set_moa_sid_in_coockie(request, moa_sid):
    """
    Установить указанный moa_sid  в куки
    :param request:
    :param moa_sid:
    :return: True  в случае удачной операции
    """
    session = await get_session(request)
    session['moa_sid'] = moa_sid
    session.update()


async def del_coockie(request):
    """
    Удалить куки из запроса
    :param request:
    :return: True  в случае удачной операции
    """
    res = False
    if request is not None:
        # session = await new_session(request)
        session = await get_session(request)
        session.clear()
        res = True

    return res


async def renew_moa_in_coockie(request, moa_sid=None):
    if moa_sid is not None:
        # повторная регистрация деактивировать (exp_date=now-10 и active=false) старую сессию с moa_sid
        await update_active_session(request, False)
    # создать запись сессии в sessions и ее sid обновить её значение в куке
    moa_sid_new = await create_session(request)
    await set_moa_sid_in_coockie(request, moa_sid_new)
    request['moa_sid'] = moa_sid_new
    return moa_sid_new


def get_moa_sid_from_req(request):
    if request is None:
        return None
    return request['moa_sid'] if 'moa_sid' in request else None


async def have_ip_in_blacklist(ip, request):
    pool = get_pool_from_request(request)

    res = False

    async with pool.acquire() as connection:
        async with connection.transaction():
            count = await connection.fetchval(f'SELECT COUNT(id) FROM ip_blacklist '
                                              f'WHERE ip_address=$1', ip)
            res = (count > 0) if count is not None else res

    return res


async def have_abnormal_actions(request, ip):
    res = False

    pass

    return res


async def have_any_problem(request, ip):
    in_blacklist = await have_ip_in_blacklist(ip, request)
    if in_blacklist:
        logger.warning('have_any_problem: IP находится в черном списке, отказано в доступе')
        raise ApiResponse(22)
    have_abnormal = await have_abnormal_actions(request, ip)
    if have_abnormal:
        logger.warning('have_any_problem: Выявлено аномальное поведение. Отказано в доступе')
        raise ApiResponse(22)


async def get_dev_prof(request):
    """
    Получить device_id, locale, profile_id и все остальные поля сущности profiles по moa_sid,
    результат прикрпляется к словарю request
    :param request:
    :return:
    """
    moa_sid = request.get('moa_sid')
    pool = get_pool_from_request(request)

    async with pool.acquire() as connection:
        async with connection.transaction():
            query = f'SELECT devices.id AS device_id, ' \
                    f'  devices.fcm_token AS fcm_token, ' \
                    f'  devices.locale AS locale, ' \
                    f'  profiles.* ' \
                    f'FROM public.sessions ' \
                    f'  LEFT OUTER JOIN devices ON devices.id=sessions.device_id ' \
                    f'  LEFT OUTER JOIN profiles ON profiles.id=sessions.profile_id ' \
                    f'WHERE sessions.active=true ' \
                    f'  AND sessions.sid=$1 ' \
                    f'ORDER BY sessions.exp_date DESC LIMIT 1'
            row = await connection.fetchrow(query, moa_sid)
            if row is not None:
                for column in row.keys():
                    if column == 'id':
                        request['profile_id'] = row.get(column, None)
                    else:
                        request[column] = row.get(column, None)
                if row.get('id') is not None:
                    user = User(**row)
                else:
                    user = NoneUser(**row)
            else:
                user = NoneUser()
            user.set_context()
    return None


async def session_is_active(request):
    """
    возвращает True если сессия в БД активна.
    :param request:
    :return:
    """
    pool = get_pool_from_request(request)

    async with pool.acquire() as connection:
        async with connection.transaction():
            dt = date_now()

            query = f'SELECT * FROM sessions WHERE sid=$1 ORDER BY exp_date DESC LIMIT 1'
            row = await connection.fetchrow(query, request.get('moa_sid'))
            if row is None:
                return None
            exp_date = row.get('exp_date', dt - timedelta(seconds=1))
            active = row.get('active', False)
            return (exp_date > dt) and active


async def check_blocked_session(request):
    """
    генерирует response 22 если заблокирована сессия
    :param request:
    :return:
    """
    pool = get_pool_from_request(request)
    async with pool.acquire() as connection:
        async with connection.transaction():
            blocked = await connection.fetchval(f'SELECT blocked '
                                                f'FROM sessions '
                                                f'WHERE sid=$1 AND active=True '
                                                f'ORDER BY exp_date DESC '
                                                f'LIMIT 1', request.get('moa_sid'))
            blocked = blocked if blocked is not None else True
            if blocked:
                logger.warning(f'check_blocked_session: Сессия заблокирована, отказ в доступе')
                raise ApiResponse(22)


async def check_register_req_count_session(request):
    """
    генерирует response 22 если счетчики истекли или заблокирована сессия, вызывать только с роута register
    :param request:
    :return:
    """
    pool = get_pool_from_request(request)
    res = False
    async with pool.acquire() as connection:
        async with connection.transaction():
            query = f'SELECT register_req_count ' \
                    f'FROM sessions ' \
                    f'WHERE sid=$1 ORDER BY exp_date DESC ' \
                    f'LIMIT 1'
            register_req_count = await connection.fetchval(query, request.get('moa_sid'))
            if register_req_count is None:
                logger.warning('check_register_req_count_session: Сессия не найдена, отказ в доступе')
                raise ApiResponse(22)
            register_req_count -= 1
            if register_req_count < 1:
                query = f'UPDATE sessions SET register_req_count=$1, blocked=true WHERE sid=$2 '
            else:
                query = f'UPDATE sessions SET register_req_count=$1 WHERE sid=$2 '
                logger.warning(f'check_register_req_count_session: уменьшен счетчик rrc')
            result = await connection.execute(query, register_req_count, request.get('moa_sid'))
            res = result == 'UPDATE 1'
            if not result:
                logger.warning(
                    f'check_register_req_count_session: неудачное обновление записи в sessions: res={result}')
    if register_req_count < 1:
        logger.info('check_register_req_count_session: уменьшен счетчик rrc, сессия заблокирована')
        raise ApiResponse(22)
    return res


async def check_bad_register_req_count_session(request):
    """
    генерирует response 22 если счетчики неудачных запросов истекли, вызывать только с роута register
    :param request:
    :return:
    """
    pool = get_pool_from_request(request)
    res = False
    async with pool.acquire() as connection:
        async with connection.transaction():
            query = f'SELECT bad_register_req_count ' \
                    f'FROM sessions ' \
                    f'WHERE sid=$1 ORDER BY exp_date DESC ' \
                    f'LIMIT 1'
            bad_register_req_count = await connection.fetchval(query, request.get('moa_sid'))
            if bad_register_req_count is None:
                raise ApiResponse(22, log_message=f'check_bad_register_req_count_session: Сессия не найдена, '
                                                  f'отказ в доступе')
            bad_register_req_count -= 1
            if bad_register_req_count < 1:
                query = f'UPDATE sessions SET bad_register_req_count=$1, blocked=true WHERE sid=$2 '
            else:
                query = f'UPDATE sessions SET bad_register_req_count=$1 WHERE sid=$2 '
                logger.warning(f'check_bad_register_req_count_session: уменьшен счетчик brrc')
            result = await connection.execute(query, bad_register_req_count, request.get('moa_sid'))
            res = result == 'UPDATE 1'
            if not result:
                logger.warning(f'check_bad_register_req_count_session: неудачное обновление записи в sessions: '
                               f'res={result}')
    if bad_register_req_count < 1:
        raise ApiResponse(22, log_message=f'check_bad_register_req_count_session: уменьшен счетчик brrc, '
                                          f'сессия заблокирована')
    return res


async def set_blocked_session(request, block):
    pool = get_pool_from_request(request)
    async with pool.acquire() as connection:
        async with connection.transaction():
            query = f'UPDATE sessions SET blocked=$1 WHERE sid=$2 '
            result = await connection.execute(query, block, request.get('moa_sid'))
            if not result:
                logger.warning(f'set_blocked_session: неудачное обновление записи в sessions: result={result}')
            return True


async def get_phone_from_session(request):
    phone = None
    error = None
    pool = get_pool_from_request(request)
    try:
        moa_sid = request.get('moa_sid')
        if moa_sid is None:
            error = 'Отсутствует sid в сессии'
            return phone, error
        async with pool.acquire() as connection:
            async with connection.transaction():
                phone = await connection.fetchval(f'SELECT profiles.phone_number FROM sessions INNER JOIN profiles '
                                                  f'ON profiles.id=sessions.profile_id '
                                                  f'WHERE sessions.sid=\'{moa_sid}\' ORDER BY sessions.id DESC LIMIT 1')
    except CancelledError:
        raise
    except Exception as exc:
        error = f'get_phone_from_session: Исключение: {exc}'
    return phone, error


async def get_code(request):
    """
    Считать из БД сохраненный код СМС/пуш
    :param request:
    :return: tuple: code, error
    """
    error = None
    code = None
    code_13 = False
    pool = get_pool_from_request(request)
    try:
        moa_sid = request.get('moa_sid')
        if moa_sid is None:
            error = 'Отсутствует sid в сессии'
            return code, error, code_13
        async with pool.acquire() as connection:
            async with connection.transaction():
                row = await connection.fetchrow(f'SELECT confirmation_codes.code AS code, '
                                                f'  confirmation_codes.exp_date AS c_exp_date '
                                                f'FROM sessions '
                                                f'  INNER JOIN confirmation_codes ON confirmation_codes.sid=sessions.sid '
                                                f'WHERE sessions.sid=$1 '
                                                f'  AND confirmation_codes.confirmed=false '
                                                f'ORDER BY confirmation_codes.id DESC '
                                                f'LIMIT 1', str(moa_sid))
                if row is not None:
                    exp_date = row.get('c_exp_date', None)
                    if exp_date is not None:
                        tm = date_now()
                        if exp_date > tm:
                            code = row.get('code', None)
                        else:
                            code_13 = True
                            error = 'Время жизни кода истекло'
                else:
                    code_13 = True
                    error = 'Код не найден для текущей сессии'
    except CancelledError:
        raise
    except Exception as exc:
        error = f'get_code: Исключение: {exc}'
    return code, error, code_13


async def set_confirmed_code(request, confirmed, code):
    """
    Установить свойство confirmed у кода
    :param confirmed:
    :param request:
    :param code:
    :return: tuple: res, error
    """
    error = None
    res = False
    pool = get_pool_from_request(request)
    moa_sid = request.get('moa_sid')
    if moa_sid is None:
        error = 'Отсутствует sid в сессии'
        return res, error
    if not isinstance(confirmed, bool):
        error = 'Некорректный параметр confirmed'
        return res, error
    if code is None or not isinstance(code, str):
        return res, error
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                result = await connection.execute(f'UPDATE confirmation_codes '
                                                  f'SET confirmed=$1 '
                                                  f'WHERE id IN (SELECT id '
                                                  f'             FROM confirmation_codes '
                                                  f'             WHERE sid=$2 '
                                                  f'               AND code=$3 '
                                                  f'               AND confirmed<>$1 '
                                                  f'             ORDER BY id DESC LIMIT 1)',
                                                  confirmed, str(moa_sid), str(code))
                res = result == 'UPDATE 1'
                if not result:
                    error = 'set_confirmed_code: неудачное обновление записи: result={result}'
    except CancelledError:
        raise
    except Exception as exc:
        logger.error(f'set_confirmed_code: Исключение: {exc}')
    return res, error


async def set_confirmed_code_not_active(request):
    """
    Установить свойство confirmed  у кода
    :param request:
    :return:
    """

    pool = get_pool_from_request(request)
    error = None
    res = False
    moa_sid = request.get('moa_sid')
    if moa_sid is None:
        error = 'Отсутствует sid в сессии'
        return res
    exp_date = date_now() - timedelta(seconds=10)
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                result = await connection.execute(f'UPDATE confirmation_codes '
                                                  f'SET exp_date=$1 '
                                                  f'WHERE id IN (SELECT id '
                                                  f'             FROM confirmation_codes '
                                                  f'             WHERE sid=$2 '
                                                  f'             ORDER BY id DESC LIMIT 1)', exp_date, moa_sid)
                res = result == 'UPDATE 1'
                if not result:
                    error = f'set_confirmed_code_not_active: неудачное обновление записи: moa_sid={moa_sid}, ' \
                            f'result={result}, обработка запроса продолжится...'
                    logger.warning(error)
    except CancelledError:
        raise
    except Exception as exc:
        logger.error(f'set_confirmed_code_not_active: Исключение: {exc}')
    return res


async def have_devices(request) -> bool:
    pool = get_pool_from_request(request)
    moa_sid = request.get('moa_sid')
    async with pool.acquire() as connection:
        async with connection.transaction():
            cnt = await connection.fetchval(f'SELECT count(*) FROM sessions '
                                            f'WHERE (sid=$1) AND (device_id is not NULL) '
                                            f'AND (active=True)', moa_sid)
            return cnt > 0


async def have_profile(request) -> bool:
    pool = get_pool_from_request(request)
    moa_sid = request.get('moa_sid')
    async with pool.acquire() as connection:
        async with connection.transaction():
            return await connection.fetchval('select exists(select * from sessions where '
                                             'sid=$1 and active=True AND profile_id is not NULL)', moa_sid)


async def update_lifetime_session(request):
    pool = get_pool_from_request(request)
    moa_sid = request.get('moa_sid')

    lt_session = request.app[LIFE_TIME_SESSION]
    async with pool.acquire() as connection:
        async with connection.transaction():
            exp_date = date_now() + timedelta(seconds=int(lt_session))
            await connection.execute(
                f'UPDATE sessions SET exp_date=$1 WHERE sid=$2 returning *', exp_date, moa_sid)


async def update_lifetime_in_device(request, device_id):
    pool = get_pool_from_request(request)
    async with pool.acquire() as connection:
        async with connection.transaction():
            lt_long_token = request.app[LIFE_TIME_LONG_TOKEN]
            exp_date = date_now() + timedelta(hours=int(lt_long_token))
            result = await connection.execute(f'UPDATE devices SET exp_date=$1 WHERE id=$2', exp_date, device_id)
            res = result == 'UPDATE 1'
            if not result:
                logger.error(f'update_lifetime_in_device: неудачное обновление записи: result={result}')
    return res


async def update_app_version_in_device(request, device_id, app_version):
    try:
        pool = get_pool_from_request(request)
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute('update devices set app_version = $1 where id = $2', app_version, device_id)
    except CancelledError:
        raise
    except Exception as ex:
        logger.error(f'update_app_version_in_device: неудачное обновление записи: {ex}')


async def update_active_session(request, active: bool) -> None:
    moa_sid = request.get('moa_sid')
    pool = get_pool_from_request(request)
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(f'UPDATE sessions SET active=$1 WHERE sid=$2', active, moa_sid)
    except CancelledError:
        raise
    except Exception as ex:
        logger.error(f'Исключение: update_active_session: неудачное обновление sessions active={active}: {ex}')


async def update_locale_session(request, locale):
    pool = get_pool_from_request(request)
    moa_sid = request.get('moa_sid')
    res = False
    if locale is not None:
        try:
            async with pool.acquire() as connection:
                async with connection.transaction():
                    result = await connection.execute(f'UPDATE sessions SET locale=$1 WHERE sid=$2', locale, moa_sid)
                    res = result == 'UPDATE 1'
                    if not result:
                        logger.error(f'update_locale_session: неудачное обновление записи: result={result}')
        except CancelledError:
            raise
        except Exception as exc:
            logger.error(f'update_locale_session: {exc}')
    return res


async def update_locale_device(device_id, locale, request):
    pool = get_pool_from_request(request)

    res = False
    if (locale is not None) and (device_id is not None):
        try:
            async with pool.acquire() as connection:
                async with connection.transaction():
                    result = await connection.execute(f'UPDATE devices SET locale=$1 WHERE id=$2', locale, device_id)
                    res = result == 'UPDATE 1'
                    if not result:
                        logger.error(f'update_locale_device: неудачное обновление записи: result={result}')
        except CancelledError:
            raise
        except Exception as exc:
            logger.error(f'update_locale_device: Исключение: {exc}')
    return res


async def update_device_id_in_session(request, device_id):
    res = False
    pool = get_pool_from_request(request)
    try:
        moa_sid = request.get('moa_sid')
        if moa_sid is None:
            return res
        async with pool.acquire() as connection:
            async with connection.transaction():
                lt_session = request.app[LIFE_TIME_SESSION]
                exp_date = date_now() + timedelta(seconds=int(lt_session))
                result = await connection.execute(f'UPDATE sessions '
                                                  f'SET device_id=$1, '
                                                  f'    exp_date=$2 '
                                                  f'WHERE sid=$3 ',
                                                  device_id, exp_date, moa_sid)
                res = result == 'UPDATE 1'
                if not result:
                    logger.error(f'update_device_id_in_session: неудачное обновление записи: result={result}')
    except CancelledError:
        raise
    except Exception as exc:
        logger.error(f'update_device_id_in_session: Исключение: {exc}')
    return res


async def update_profile_id_in_session(request, profile_id):
    res = False
    moa_sid = get_moa_sid_from_req(request)
    if moa_sid is None:
        return res
    pool = get_pool_from_request(request)
    if pool is None:
        logger.error(f'update_profile_id_in_session: pool is None')
        return res
    try:
        lt_session = request.app[LIFE_TIME_SESSION]
        async with pool.acquire() as connection:
            async with connection.transaction():
                exp_date = date_now() + timedelta(seconds=int(lt_session))
                result = await connection.execute(f'UPDATE sessions SET profile_id=$1, exp_date=$2 WHERE sid=$3',
                                                  profile_id, exp_date, moa_sid)
                res = result == 'UPDATE 1'
                if not result:
                    logger.error(f'update_profile_id_in_session: неудачное обновление записи: result={result}')
    except CancelledError:
        raise
    except Exception as exc:
        logger.error(f'update_profile_id_in_session: Исключение: {exc}')
    return res


async def set_active_user(pool, phone, active):
    res = False
    error = None
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                result = await connection.execute(f'UPDATE profiles SET active=$1 WHERE phone_number=$2', active, phone)
                res = result == 'UPDATE 1'
                if not result:
                    error = f'set_active_user: неудачное обновление записи: result={result}'
    except CancelledError:
        raise
    except Exception as exc:
        error = f'set_active_user: Исключение (active={active}, phone={phone}): {exc}'
    return res, error


async def set_name_user(pool, phone, first_name, last_name):
    res = False
    error = None
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                result = await connection.execute(f'UPDATE profiles SET first_name=$1, last_name=$2 '
                                                  f'WHERE phone_number=$3', first_name, last_name, phone)
                res = result == 'UPDATE 1'
                if not result:
                    error = f'set_name_user: неудачное обновление записи: result={result}'
    except CancelledError:
        raise
    except Exception as exc:
        error = f'set_name_user: Исключение: (first_name={first_name}, last_name={last_name}): {exc}'
    return res, error


async def get_phone_from_request(request):
    phone = None
    data = await get_data_from_request(request)
    return data.get('phone', None), None


async def create_session(request):
    pool = get_pool_from_request(request)
    active = True
    profile_id = None
    count = 0
    while count < 3:
        sid_new = generate_sid()
        count += 1
        user_agent = get_user_agent_from_request(request)
        ip_client = get_ip_from_request(request)
        dt = date_now()
        lt_session = request.app[LIFE_TIME_SESSION]
        exp_date = (dt + timedelta(seconds=int(lt_session))) if active else dt
        try:
            async with pool.acquire() as connection:
                async with connection.transaction():
                    sid_res = await connection.fetchval(f'INSERT INTO sessions '
                                                        f'(profile_id, user_agent, ip_address, sid, exp_date, active) '
                                                        f'VALUES ($1, $2, $3, $4, $5, $6) '
                                                        f'RETURNING sid',
                                                        profile_id,
                                                        user_agent,
                                                        ip_client,
                                                        sid_new,
                                                        exp_date,
                                                        active
                                                        )
            break
        except CancelledError:
            raise
        except Exception as exc:
            error = f'create_session: (profile_id={profile_id}, ip={ip_client}): {exc}: {exc.args}'  # NOQA
            logger.error(error)
    else:
        raise ApiResponse(90, log_message='async def create_session(request): exc')
    return sid_res


async def get_column_from_devices(request, gsid, column):
    pool = get_pool_from_request(request)

    result = None
    error = None
    try:
        dt = date_now()
        async with pool.acquire() as connection:
            async with connection.transaction():
                row = await connection.fetchrow(f'SELECT {column} FROM devices '
                                                f'WHERE guid=$1 '
                                                f'  AND exp_date>$2 '
                                                f'  AND active=true ORDER BY id DESC LIMIT 1',
                                                gsid, dt)
                if row is None:
                    error = 'Недействительный токен gsid'
                    return result, error
                else:
                    result = row.get(column, None)
    except CancelledError:
        raise
    except Exception as exc:
        logger.error(f'get_column_from_devices: Исключение: {exc}')
    return result, error


def get_random_code(sms_enable, num=5):
    code = ''
    for x in range(num):
        code = code + choice(list('1234567890'))
    return code if sms_enable else '22222'


def generate_uuid5(salt_one, salt_two):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, str(salt_one) + str(salt_two) + str(uuid.uuid4()))).replace("-", "")
    # return str(uuid.uuid4())


def generate_sid():
    return str(uuid.uuid4())


async def create_device(request, phone):
    pool = get_pool_from_request(request)

    error = None
    gsid = None
    try:
        profile_id = await get_profile_id_from_phone(request, phone)
        user_agent = get_user_agent_from_request(request)
        tm = date_now()
        life_time_ltoken = request.app[LIFE_TIME_LONG_TOKEN]
        exp_date = tm + timedelta(hours=int(life_time_ltoken))
        tmp_sid = generate_uuid5(profile_id, tm)
        async with pool.acquire() as connection:
            async with connection.transaction():
                gsid = await connection.fetchval(f'INSERT INTO devices ('
                                                 f'profile_id,'
                                                 f'name,'
                                                 f'guid,'
                                                 f'exp_date,'
                                                 f'active) '
                                                 f'VALUES ($1, $2, $3, $4, $5) RETURNING guid',
                                                 profile_id,
                                                 str(user_agent),
                                                 tmp_sid,
                                                 exp_date,
                                                 True)
    except CancelledError:
        raise
    except Exception as exc:
        error = f'create_device: Исключение (phone={phone}): {exc}'
        logger.error(error)
    return gsid, error


async def register_new_user(request, phone, active=False, first_name=None, last_name=None):
    pool = get_pool_from_request(request)
    error = None
    profile_id = None
    if phone is None:
        return profile_id, error
    uid_new = generate_uuid5(phone, date_now())
    pqr = generate_new_pqr(phone)
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                profile_id = await connection.fetchval(f'SELECT id FROM profiles WHERE phone_number=$1 AND '
                                                       f'is_deleted=false', phone)
                if profile_id is not None:
                    logger.error(f'register_new_user: Пользователь phone={phone} уже есть profile_id={profile_id}')
                    return profile_id, error
                profile_id = await connection.fetchval(f'INSERT INTO profiles '
                                                       f'(uid, phone_number, active, first_name, last_name, pqr) '
                                                       f'VALUES '
                                                       f'($1, $2, $3, $4, $5, $6) RETURNING id',
                                                       uid_new, phone, active, first_name, last_name, pqr)
    except CancelledError:
        raise
    except Exception as exc:
        error = f'register_new_user: Исключение (phone={phone}, active={active}): {exc}'
        logger.error(error)
    return profile_id, error


async def get_time_left(sid, request):
    """
    Получить остаток времени до возможности отправить код по смс/пуш повторно
    Если время вышло или код данному телефону не выдавался, то вернет 0, иначе вернет остаток в cекундах
    :param sid:
    :param request:
    :return:
    """
    pool = get_pool_from_request(request)
    exp_date = None
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                exp_date = await connection.fetchval(f'SELECT exp_date '
                                                     f'FROM confirmation_codes '
                                                     f'WHERE sid=$1 '
                                                     f'ORDER BY id DESC '
                                                     f'LIMIT 1', str(sid))
    except CancelledError:
        raise
    except Exception as exc:
        logger.error(f'get_time_left: Исключение: {exc}')
        return 0, exp_date
    if exp_date is not None:
        now = date_now()
        res = (exp_date - now).total_seconds() if exp_date >= now else 0
        exp_date = exp_date.strftime(FORMAT_DATE_TIME)
        # res = tmp if tmp > 0 else 0
        return res, exp_date
    else:
        exp_date = ''
    return 0, exp_date


def can_send_push(phone, request):  # NOQA
    # проверить можно ли отправить данному клиенту пуш
    return request.get('fcm_token', None) is not None


async def send_push(phone, code, request):  # NOQA
    error = None
    # return 0 - не удалось отправить пуш, return 2 если успешно отправлено
    return 0


async def send_code(request, phone, check_before_send=True):
    pool = get_pool_from_request(request)

    """
     Отправить код СМС/пуш и записать его в БД. Перед отправкой проверяется, нет ли активного кода в БД
    :param pool:
    :param request:
    :param phone:
    :param check_before_send:
    :return:
    """
    life_time_code = request.app[CONFIRMATION_CODE_LIFETIME]
    moa_sid = get_moa_sid_from_req(request)

    if check_before_send:
        last_delta, exp_date = await get_time_left(phone, request)
        if last_delta > 0:
            logger.error(f'Код не будет отправлен, время предыдущей отправки не вышло '
                         f'(phone={phone})')
    sms_enable = request.app[SP_SMS_STATUS]
    sms_enable = not sms_enable if ((phone in config.exclude_phones) and sms_enable) else sms_enable
    code = get_random_code(sms_enable)
    text_template = 'Добро пожаловать в мир выгодных путешествий! Код подтверждения: {code}'
    text_message = text_template.format(code=code)
    tm = date_now()
    res = await send_sms(request, phone, text_message, sms_enable)
    if res is not None:
        if res > 0:
            exp_date = tm + timedelta(seconds=int(life_time_code))
            async with pool.acquire() as connection:
                async with connection.transaction():
                    await connection.execute(f'INSERT INTO confirmation_codes '
                                             f'(sid, code, exp_date, confirmed) '
                                             f'VALUES '
                                             f'($1, $2, $3, False)',
                                             str(moa_sid), str(code), exp_date)
            return res
    return 0


async def set_device_info(request, device_id, device_info):
    pool = get_pool_from_request(request)
    res = False
    if not device_info:
        return res
    do_update = {}
    for param in device_info:
        if param in DEVICE_INFO_LIST and param not in DEVICE_INFO_NOT_USING:
            if param == 'fcm_token':
                if device_info[param] is None or device_info[param] == '':
                    continue
            do_update[param] = device_info[param]
    if not do_update:
        return res
    col = ', '.join(do_update.keys())
    val = "'" + "', '".join(map(str, do_update.values())) + "'"
    if (col is not None) and (device_id is not None):
        try:
            async with pool.acquire() as connection:
                if len(do_update) > 1:
                    await connection.execute(f'UPDATE devices SET ({col})=({val}) WHERE id={device_id}')
                else:
                    await connection.execute(f'UPDATE devices SET {col}={val} WHERE id={device_id}')
                res = True
        except CancelledError:
            raise
        except Exception as exc:
            logger.error(f'Исключение в set_device_info (device_id={device_id}, '
                         f'({col})=({val})): {exc}')
    return res


def generate_new_pqr(phone):
    # f'{phone}:{date_now()}'
    return hashlib.sha256(f'{phone}:{config.sha_secret_addition}'.encode("utf_8")).hexdigest()


async def generate_pqr(request, phone):
    error = None
    pqr = None
    pool = get_pool_from_request(request)

    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                pqr_exist = await connection.fetchval(f'SELECT pqr FROM profiles WHERE phone_number=$1', phone)
        if pqr_exist is None:
            pqr = generate_new_pqr(phone)
            async with pool.acquire() as connection:
                result = await connection.execute(f'UPDATE profiles set pqr = $1 where phone_number = $2', pqr, phone)
                if not (result == 'UPDATE 1'):
                    logger.error(f'generate_pqr: неудачное обновление записи: result={result}')
    except CancelledError:
        raise
    except Exception as exc:
        error = f'generate_pqr: Исключение (pqr={pqr}): {exc}'
        logger.error(error)
    return pqr, error


async def get_data_by_name(request, name, default=None, required=True):
    result = default
    data = await get_data_from_request(request)
    # print(f"{data} {resp.text}")
    if required and data is None:
        logger.warning(f'Отсутствуют параметры в запросе')
        raise ApiResponse(12)
    result = data.get(name, default)
    if required and result is None:
        logger.warning(f'Отсутствует обязательный параметр {name} в запросе')
        raise ApiResponse(12)
    return result, None


async def check_need_to_fill_profile(request, phone):
    if phone is None:
        phone = request.get('phone_number')
        if phone is None:
            return False
    pool = get_pool_from_request(request)
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                row = await connection.fetchrow(f'SELECT first_name,last_name, email '
                                                f'FROM profiles '
                                                f'WHERE phone_number=$1 '
                                                f'  and is_deleted=False', phone)
                fn = row.get('first_name')
                ln = row.get('last_name')
                email = row.get('email')
                return fn is None or len(fn) == 0 or ln is None or len(ln) == 0 or email is None or len(email) == 0
    except CancelledError:
        raise
    except Exception as exc:
        raise ApiResponse(90, exc=exc, log_message=f'check_need_to_fill_profile: Исключение (phone={phone}): {exc}')


async def add_mile_transaction(request, profile_id, mile_count, mile_general_count, transaction_type_id, receipt=None):
    pool = get_pool_from_request(request)
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                query = f'INSERT INTO mile_transactions ' \
                        f'  (mile_count, ' \
                        f'   transaction_type_id, ' \
                        f'   mile_general_count, ' \
                        f'   profile_id, ' \
                        f'   receipt, ' \
                        f'   isprocessed) ' \
                        f'VALUES ($1, $2, $3, $4, $5, $6) ' \
                        f'RETURNING id'
                mile_transaction_id = await conn.fetchval(query,
                                                          mile_count,
                                                          transaction_type_id,
                                                          mile_general_count,
                                                          profile_id,
                                                          str(receipt).replace("'",
                                                                               '"') if receipt is not None else None,
                                                          True)
                if mile_transaction_id is not None:
                    return mile_transaction_id
                else:
                    logger.error(f'Не удалось добавить mile_transaction (profile_id={profile_id}, '
                                 f'mile_count={mile_count})')
                    return None
    except CancelledError:
        raise
    except Exception as exc:
        raise ApiResponse(90, exc=exc, log_message=f'add_mile_transaction: Исключение (profile_id={profile_id}, '
                                                   f'mile_count={mile_count}): {exc}')


async def get_codephone(request):
    pool = get_pool_from_request(request)
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                countries = await connection.fetch(f'select countries.id,  countries.iso2, countries.iso3, '
                                                   f'countries.phone_mask,countries.flag_url '
                                                   f'from countries where active=true order by countries.flag_url')

                translates = await connection.fetch(f'select country_translates.id,country_translates.name, '
                                                    f'country_translates.language_code, '
                                                    f'country_translates.country_id '
                                                    f'from countries inner join country_translates on '
                                                    f'country_translates.country_id=countries.id where active=true '
                                                    f'order by country_translates.name')
                return countries, translates
    except CancelledError:
        raise
    except Exception as e:
        raise ApiResponse(90, exc=e, log_message='Исключение в вызове словаря для стран')


async def get_banner(request, _id, language_code):
    pool = get_pool_from_request(request)
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                banner = await connection.fetch(
                    f'select  banner_translates.title, banner_translates.long_description,  banners.promotion_id, '
                    f' banner_translates.button_enable, banner_translates.button_disable,'
                    f' airport_banner.action, banners.redirect, '
                    f' banner_translates.short_description, banners.type, promotions.promotion_conditions,'
                    f' concat((select value from system_parameters where name = $3),'
                    f' banners.image_url)               as image_url,'
                    f' concat((select value from system_parameters where name = $3),'
                    f' banners.image_url)               as photo_path,'
                    f' concat((select value from system_parameters where name = $3),'
                    f' banners.preview_rectangle_image_url)               as preview_rectangle_image_url,'
                    f' concat((select value from system_parameters where name = $3),'
                    f' banners.preview_square_image_url)               as preview_square_image_url,'
                    f'case'
                    f'   when banners.promotion_id is null then null '
                    f'    when  promotions.photo_path_for_banner is null then null '
                    f' when  promotions.photo_path_for_banner = $5 then null '
                    f' else'
                    f' concat((select value from system_parameters where name = $3), '
                    f'  promotions.photo_path_for_banner) '
                    f' end as logo_path,'
                    f'case'
                    f' when banners.promotion_id is null then null '
                    f' else'
                    f' concat((select value from system_parameters where name = $4),'
                    f' null) '
                    f' end as promotion_url'
                    f' from banners '
                    f' inner join banner_translates on banners.id = banner_translates.banner_id '
                    f' left outer join promotions on banners.promotion_id = promotions.id '
                    f' left outer join airport_banner on banners.id = airport_banner.banner_id'
                    f' where banners.active=true and  banners.visible=true and banners.id=$1 and '
                    f'banner_translates.language_code=$2',
                    _id, language_code, 'resource_server_url', 'participate_in_promotion', ''
                )
                return banner

    except CancelledError:
        raise
    except Exception as e:
        raise ApiResponse(90, exc=e, log_message='Исключение при обращении к  banner get_banner ' + str(e))


async def get_banners_category_airport(request, airport_id, language_code, category_id, limit_offset, offset):
    pool = get_pool_from_request(request)
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                banners = await connection.fetch(
                    f'select banners.id, banner_translates.title '
                    f', banner_translates.short_description, '
                    f'(select count(*) from banners '
                    f' left outer join airport_banner on banners.id = airport_banner.banner_id '
                    f' where (airport_banner.airport_id=$1 or airport_banner.airport_id is null)'
                    f'  and banners.category_id=$3)'
                    f' as total_count, '
                    f' concat((select value from system_parameters where name = $6),'
                    f' banners.image_url)               as image_url,'
                    f' concat((select value from system_parameters where name = $6),'
                    f' banners.image_url)               as photo_path,'
                    f' concat((select value from system_parameters where name = $6),'
                    f' banners.preview_rectangle_image_url)               as preview_rectangle_image_url,'
                    f' concat((select value from system_parameters where name = $6),'
                    f' banners.preview_square_image_url)               as preview_square_image_url,'
                    f'case'
                    f'   when banners.promotion_id is null then null '
                    f' else'
                    f' concat((select value from system_parameters where name = $6), '
                    f'  promotions.photo_path)'
                    f' end as logo_path'
                    f' from banners '
                    f' inner join banner_translates on banners.id = banner_translates.banner_id'
                    f' inner join banner_categories on banners.category_id = banner_categories.id'
                    f' left outer join  promotions on banners.promotion_id = promotions.id '
                    f' left outer join airport_banner on banners.id = airport_banner.banner_id'
                    f' where banners.active=true and  banners.visible=true   '
                    f' and banner_translates.language_code=$2 and '
                    f' banners.category_id =$3 and (airport_banner.airport_id=$1 or airport_banner.airport_id is null) '
                    f'  order by banners.id desc limit $4::int offset $5::int;',
                    airport_id, language_code, category_id, limit_offset, offset, 'resource_server_url'
                )
                return banners

    except CancelledError:
        raise
    except Exception as e:
        raise ApiResponse(90, exc=e,
                          log_message='Исключение при обращении к banners get_banners_category_airport' + str(e))


async def get_banners_airport(request, airport_id, language_code, limit_offset, offset):
    pool = get_pool_from_request(request)
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                banners = await connection.fetch(
                    f'select banners.id, banner_translates.title, '
                    f' banner_translates.short_description, '
                    f'(select count(*) from banners '
                    f' left outer join airport_banner on banners.id = airport_banner.banner_id '
                    f' where (airport_banner.airport_id=$1 or airport_banner.airport_id is null))'
                    f' as total_count,'
                    f' concat((select value from system_parameters where name = $5),'
                    f' banners.image_url)               as image_url,'
                    f' concat((select value from system_parameters where name = $5),'
                    f' banners.image_url)               as photo_path,'
                    f' concat((select value from system_parameters where name = $5),'
                    f' banners.preview_rectangle_image_url)               as preview_rectangle_image_url,'
                    f' concat((select value from system_parameters where name = $5),'
                    f' banners.preview_square_image_url)               as preview_square_image_url,'
                    f' case '
                    f'   when banners.promotion_id is null then null '
                    f' else'
                    f' concat((select value from system_parameters where name = $5), '
                    f'  promotions.photo_path)'
                    f' end as logo_path'
                    f' from banners '
                    f' inner join banner_translates on banners.id = banner_translates.banner_id'
                    f' left outer join promotions on banners.promotion_id = promotions.id '
                    f' left outer join airport_banner on banners.id = airport_banner.banner_id'
                    f' where banners.active=true and  banners.visible=true and (airport_banner.airport_id=$1 or '
                    f' airport_banner.airport_id is null)  and banner_translates.language_code=$2'
                    f'  order by banners.id desc limit $3::int offset $4::int;'

                    , airport_id, language_code, limit_offset, offset, 'resource_server_url'
                )
                return banners

    except CancelledError:
        raise
    except Exception as e:
        raise ApiResponse(90, exc=e, log_message='Исключение при обращении к banners get_banners_airport')


async def get_all_banners(request, language_code, limit_offset, offset):
    pool = get_pool_from_request(request)
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                banners = await connection.fetch(
                    f'select  banners.id, banner_translates.title,  '
                    f' banner_translates.short_description,  (select count(*) from banners ) '
                    f' as total_count, '
                    f' concat((select value from system_parameters where name = $4),'
                    f' banners.image_url)               as image_url,'
                    f' concat((select value from system_parameters where name = $4),'
                    f' banners.image_url)               as photo_path,'
                    f' concat((select value from system_parameters where name = $4),'
                    f' banners.preview_rectangle_image_url)               as preview_rectangle_image_url,'
                    f' concat((select value from system_parameters where name = $4),'
                    f' banners.preview_square_image_url)               as preview_square_image_url,'
                    f'case'
                    f'   when banners.promotion_id is null then null '
                    f' else'
                    f' concat((select value from system_parameters where name = $4), '
                    f'  promotions.photo_path)'
                    f' end as logo_path'
                    f' from banners '
                    f' inner join banner_translates on banners.id = banner_translates.banner_id'
                    f' left outer join  promotions on banners.promotion_id = promotions.id '
                    f' where banners.active=true and  banners.visible=true and banner_translates.language_code=$1'
                    f'  order by banners.id desc limit $2::int offset $3::int;'

                    , language_code, limit_offset, offset, 'resource_server_url'
                )
                return banners

    except CancelledError:
        raise
    except Exception as e:
        raise ApiResponse(90, exc=e, log_message='Исключение при обращении к  banners get_all_banners')


async def get_banner_category(request, category_id, language_code, limit_offset, offset):
    pool = get_pool_from_request(request)
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                banners = await connection.fetch(
                    f'select banners.id, banner_translates.title, '
                    f' banner_translates.short_description, '
                    f'(select count(*) from banners  where banners.category_id=$2 ) as total_count,'
                    f' concat((select value from system_parameters where name = $5),'
                    f' banners.image_url)               as image_url,'
                    f' concat((select value from system_parameters where name = $5),'
                    f' banners.image_url)               as photo_path,'
                    f' concat((select value from system_parameters where name = $5),'
                    f' banners.preview_rectangle_image_url)               as preview_rectangle_image_url,'
                    f' concat((select value from system_parameters where name = $5),'
                    f' banners.preview_square_image_url)               as preview_square_image_url,'
                    f'case'
                    f'   when banners.promotion_id is null then null '
                    f' else'
                    f' concat((select value from system_parameters where name = $5), '
                    f'  promotions.photo_path)'
                    f' end as logo_path'
                    f' from banners '
                    f' inner join banner_translates on banners.id = banner_translates.banner_id'
                    f' inner join banner_categories on banners.category_id = banner_categories.id'
                    f' left outer join promotions on banners.promotion_id = promotions.id '
                    f' where banners.active=true and  banners.visible=true and banner_translates.language_code=$1 '
                    f' and banners.category_id=$2'
                    f'  order by banners.id desc limit $3::int offset $4::int;'

                    , language_code, category_id, limit_offset, offset, 'resource_server_url'
                )
                return banners

    except CancelledError:
        raise
    except Exception as e:
        raise ApiResponse(90, exc=e, log_message='Исключение при обращении к  banners get_banner_category')


async def get_categories(request, language_code):
    pool = get_pool_from_request(request)
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                banner_categories = await connection.fetch(
                    f' select banner_categories_translate.category_id as id, banner_categories_translate.name'
                    f' from banner_categories_translate where banner_categories_translate.language_code=$1'

                    , language_code
                )
                return banner_categories

    except CancelledError:
        raise
    except Exception as e:
        raise ApiResponse(90, exc=e, log_message='Исключение при обращении к бд banners')


async def update_status_banner_to_profile(request):
    pool = get_pool_from_request(request)
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    f'UPDATE banners_to_profiles SET read_banner=True where profile_id=$1 ',
                    request.get("profile_id")
                )
    except CancelledError:
        raise
    except Exception as e:
        raise ApiResponse(90, exc=e, log_message='Исключение при обновлении к бд banners_to_profiles')


# async def update_banner_count_to_profile(request):
#     pool = get_pool_from_request(request)
#     try:
#         async with pool.acquire() as connection:
#                 await connection.execute(
#                     f'UPDATE profiles SET unread_banners_count=$2 where id=$1 ',
#                     request.get("profile_id"), 0
#                 )
#     except CancelledError:
#         raise
#     except Exception as e:
#         raise ApiResponse(90, exc=e, log_message='Исключение при обнулениии счетчика в profiles')

async def check_banners(request):
    pool = get_pool_from_request(request)
    try:
        async with pool.acquire() as connection:
            await connection.execute(
                f'UPDATE profiles SET unread_banners_count='
                f'(select count(*) from banners_to_profiles where profile_id=$1 and read_banner=$2) where id=$1',
                request.get("profile_id"), False
            )
    except CancelledError:
        raise
    except Exception as e:
        raise ApiResponse(90, exc=e, log_message='Исключение при обнулениии или пополнения счетчика в profiles для '
                                                 'banners')


async def check_confirm_banners(request):
    pool = get_pool_from_request(request)
    try:
        async with pool.acquire() as connection:
            result = await connection.fetch(
                f'select id from banners_to_profiles where profile_id=$1',
                request.get("profile_id")
            )
        return result

    except CancelledError:
        raise
    except Exception as e:
        raise ApiResponse(90, exc=e, log_message='Исключение при проверке баннеров при confirm')


async def get_list_id_banners(request):
    pool = get_pool_from_request(request)
    try:
        async with pool.acquire() as connection:
            result = await connection.fetch(
                f'select id from banners where active=$1 and visible=$1',
                True

            )
        return result
    except CancelledError:
        raise
    except Exception as e:
        raise ApiResponse(90, exc=e, log_message='Исключение при взятии листа id в banners смотри route confirm')


async def insert_into_banners_to_profiles(request, banner_id):
    pool = get_pool_from_request(request)
    try:
        async with pool.acquire() as connection:
            await connection.execute(
                f'insert into banners_to_profiles (profile_id, read_banner, banner_id)'
                f'values($1, $2, $3)',
                request.get("profile_id"), False, banner_id

            )

    except CancelledError:
        raise
    except Exception as e:
        raise ApiResponse(90, exc=e, log_message='Исключение при взятии листа id в banners смотри route confirm')


async def check_promotion(request, banner_id, dict_data):
    try:
        if dict_data['action']:
            tmp = dict_data['action'].replace("'", "\"")
            tmp_ = json.loads(tmp)
            dict_data['action'] = tmp_
        else:
            dict_data['action'] = None
    except KeyError:
        pass

    try:
        if dict_data['redirect']:
            tmp = dict_data['redirect'].replace("'", "\"")
            tmp_ = json.loads(tmp)
            dict_data['redirect'] = tmp_
        else:
            dict_data['redirect'] = None
    except KeyError:
        pass

    # if dict_data['promotion']:
    #     tmp = dict_data['promotion'].replace("'", "\"")
    #     tmp_ = json.loads(tmp)
    #     dict_data['promotion'] = tmp_
    # else:
    #     dict_data['promotion'] = None

    # if dict_data['button']:
    #     tmp = dict_data['button'].replace("'", "\"")
    #     tmp_ = json.loads(tmp)
    #     dict_data['button'] = tmp_

    try:
        pool = get_pool_from_request(request)
        async with pool.acquire() as connection:

            promotion_id = await connection.fetch(
                f'select promotion_id from banners where id=$1',
                banner_id
            )
            promo_id = dict(promotion_id[0])
            if promo_id['promotion_id']:
                result = await connection.fetch(
                    f'select * from promotions_to_profiles where profile_id=$1 and promotion_id=$2',
                    request.get("profile_id"), promo_id['promotion_id'])

                dict_data['promotion'] = {}
                dict_data['promotion']['id'] = dict_data.pop('promotion_id')
                dict_data['promotion']['conditions'] = dict_data.pop('promotion_conditions')
                dict_data['promotion']['route'] = dict_data.pop('promotion_url')
                dict_data['button'] = {}

                if result:
                    dict_data['button']['is_enabled'] = False
                    dict_data['button']['text'] = dict_data.pop('button_disable')
                    dict_data.pop('button_enable')

                else:
                    dict_data['button']['is_enabled'] = True
                    dict_data['button']['text'] = dict_data.pop('button_enable')
                    dict_data.pop('button_disable')

            else:
                dict_data['button'] = {}
                dict_data['promotion'] = None
                dict_data['button']['text'] = dict_data.pop('button_enable')
                dict_data['button']['is_enabled'] = True
                dict_data.pop('button_disable')
                dict_data.pop('promotion_url')
                dict_data.pop('promotion_id')
                dict_data.pop('promotion_conditions')

    except CancelledError:
        raise
    except Exception as e:
        raise ApiResponse(90, exc=e, log_message='Исключение при проверке кнопки участовать ' + str(e))

    return dict_data


async def insert_promotion_to_profiles(request, promotion_id):
    pool = get_pool_from_request(request)
    try:
        async with pool.acquire() as connection:
            await connection.execute(
                f'insert into promotions_to_profiles (profile_id, promotion_id)'
                f'values($1, $2)',
                request.get("profile_id"), promotion_id

            )
    except CancelledError:
        raise
    except Exception as e:
        raise ApiResponse(90, exc=e, log_message='Исключение добавления profile к участии в акциии')


async def get_popup_banner(request,  language_code):
    pool = get_pool_from_request(request)
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                popup_banners = await connection.fetch(
                    '''  select  banner_popup_view_translates.title, banner_popup_view_translates.description,  
                       banners.promotion_id, banner_translates.button_enable, banner_translates.button_disable,
                       banners.redirect , promotions.promotion_conditions, banner_popup_view.time_interval, 
                       banner_popup_view.popup_show_count, banners.id as banner_id,
                        banner_popup_view.id as popup_banner_id, airport_banner.action,
                       concat((select value from system_parameters where name = $3),
                       banner_popup_view.image_path)               as image_url,
                       concat((select value from system_parameters where name = $3),
                       banner_popup_view.logo_path)               as logo_url,
                     case
                      when banners.promotion_id is null then null
                      else
                      concat((select value from system_parameters where name = $2),
                      null)
                      end as promotion_url
                      from banners
                      inner join banner_translates on banners.id = banner_translates.banner_id
                      left outer join promotions on banners.promotion_id = promotions.id
                      left outer join airport_banner on banners.id = airport_banner.banner_id
                      left outer join banner_popup_view on banners.banner_popup_view_id = banner_popup_view.id
                      left outer join banner_popup_view_translates on banner_popup_view.id = banner_popup_view_translates.banner_popup_view_id
                      where   banner_translates.language_code=$1 and
                            banner_popup_view_translates.language_code=$1 and banners.active=$4 and banners.visible=$4 order by banners.id desc''',
                    language_code, 'participate_in_promotion', 'resource_server_url', True
                )
                return popup_banners

    except CancelledError:
        raise
    except Exception as e:
        logger.error(f'Исключение при обращении к popup banner get_popup_banner ' + str(e))
        raise ApiResponse(90, exc=e, log_message='Исключение при обращении к popup banner get_popup_banner ' + str(e))


async def check_show_popup(request, dict_data):

    show_count = dict_data.pop('popup_show_count')
    time_interval = dict_data.pop('time_interval')
    # banner_id = dict_data.pop('banner_id')
    # banner_popup_id = dict_data.pop('banner_popup_id')
    date_start = date_now() - time_interval

    profile_id = request.get('profile_id')

    pool = get_pool_from_request(request)
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                count_db = await connection.fetch(
                    ''' select count(banner_popup_view_id) from profile_banner_popup_view_shows 
                        where profile_banner_popup_view_shows.created_date > $1 and  
                        profile_banner_popup_view_shows.created_date < $2 and 
                        profile_banner_popup_view_shows.profile_id=$3''',
                    date_start, date_now(), profile_id
                )
                if dict(count_db[0])['count'] <= show_count:
                    await connection.execute(
                        f'insert into profile_banner_popup_view_shows (profile_id, banner_popup_view_id, created_date)'
                        f'values($1, $2, $3)',
                        profile_id, dict_data['popup_banner_id'], date_now())

    except CancelledError:
        raise
    except Exception as e:
        logger.error(f'Исключение при  проверке показа popup banner  ' + str(e))
        raise ApiResponse(90, exc=e, log_message='Исключение при  проверке показа popup banner  popup banner '
                                                 'get_popup_banner ' + str(e))
    try:
        if dict(count_db[0])['count'] <= show_count:
            return True
        else:
            return False
    except Exception as e:
        logger.error(f'Исключение при сравнение количества показов popup banner  ' + str(e))
        raise ApiResponse(90, exc=e, log_message='Исключение при сравнение количества показов popup banner ' + str(e))


async def get_single_square_image_url(request, banner_id):
    pool = get_pool_from_request(request)
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                single_image = await connection.fetchval(
                    ''' select  
                    case
                      when single_preview_square_image_url is null then null
                      else
                    concat((select value from system_parameters where name = $2),
                       single_preview_square_image_url) 
                    end
                    from banners where id=$1 ''', banner_id, 'resource_server_url'

                )
    except CancelledError:
        raise
    except Exception as e:
        logger.error(f'Исключение при получении single_preview_square_image_url  ' + str(e))
        raise ApiResponse(90, exc=e, log_message='Исключение при получении single_preview_square_image_url '
                                                  + str(e))
    return single_image

async def max_count(request):
    pool = get_pool_from_request(request)
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                count_db = await connection.fetchval(
                    ''' select value from system_parameters where name = 'popup_max_count' '''

                )

    except CancelledError:
        raise
    except Exception as e:
        logger.error(f'Исключение при  проверке максимального колличества показов попапов в системных параметрах  ' + str(e))
        raise ApiResponse(90, exc=e, log_message='Исключение при  проверке показа popup banner  popup banner '
                                                 'get_popup_banner ' + str(e))

    return count_db

def change_title_for_redirect_banner(dict_banner_, language_code, params_banner_id=None):

    if dict_banner_["redirect"]== None:
        return dict_banner_

    if language_code == 'ru' and "title_ru" in dict_banner_["redirect"]:
        dict_banner_["redirect"]["title"] = dict_banner_["redirect"].pop("title_ru")
        dict_banner_["redirect"].pop("title_en")

    elif language_code == 'en' and "title_en" in dict_banner_["redirect"]:
        dict_banner_["redirect"]["title"] = dict_banner_["redirect"].pop("title_en")
        dict_banner_["redirect"].pop("title_ru")

    else:
        dict_banner_["redirect"]["title"] = "Problem with title"
        try:
            logger.error(f'Для баннера типа редирект с id {dict_banner_["banner_id"]} не указан перевод для title')
        except KeyError:
            logger.error(f'Для баннера типа редирект с id {params_banner_id} не указан перевод для title')

    return dict_banner_
