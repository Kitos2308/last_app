from asyncio import CancelledError
from collections import deque
from datetime import datetime
from typing import Optional

from aiohttp import web
from aiohttp_session import get_session
from loguru import logger
from pydantic import BaseModel
import asyncio
import schemas
import tools
import utils
from api_utils import ApiResponse
from settings import *
import aiohttp_jinja2
from aiohttp.web_exceptions import HTTPNotFound


routes = web.RouteTableDef()


@routes.get(ROUTE_ROOT)
async def root_handler(request):
    session = await get_session(request)
    last_visit = session['last_visit'] if 'last_visit' in session else None
    session['last_visit'] = datetime.now().strftime(FORMAT_DATE_TIME)
    ip_a = request.remote
    peer_name = request.transport.get_extra_info('peername')
    host_r = request.headers.get('X-Real-IP', None)
    host_x = request.headers.get('X-FORWARDED-FOR', None)
    raise ApiResponse(0, dict(status='alive',
                              message='API-сервер Программы лояльности MileOnAir\n',
                              last_visited=last_visit,
                              ip_remote=ip_a,
                              ip_x_real_ip=host_r,
                              host_x_forwarded_for=host_x,
                              peer_name=peer_name))


@routes.post(ROUTE_REGISTER)
async def register_user(request):
    """
    @api {post} https://developer.mileonair.com/api/v1/register 1. Регистрация/восстановление доступа

    @apiName register_user
    @apiGroup Авторизация
    @apiVersion 1.0.0

    @apiParam {string {..25}} phone Номер телефона в формате +79999999999
    @apiParam {dict} deviceInfo Информация об устройстве
    @apiParamExample {json} Request-Example:
    {
        "phone": "+79001234567",
        "deviceInfo": {}
    }
    @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
    @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа

    @apiSuccessExample {json} Success-Response:
        HTTP/1.1 200 OK
        {
            "responseCode": 0,
            "responseMessage": "Запрос обработан успешно"
        }

    @apiDescription Регистрация/восстановление доступа
    Описание:
    1. Регистрация нового пользователя в программе лояльности, в запросе передается номер телефона,
       а также словарь с информацией об устройстве.
    2. Проверяется номер телефона:
        - если пользователя нет в БД, то начинается процедура регистрации, отправляется код клиенту
        - если пользователь есть в БД, начинается процедура восстановления, отправляется код клиенту

    """
    phone = None
    moa_sid = None
    phone_in_db = None
    try:
        logger.debug(f'register_user: Регистрация/восстановление уч.записи пользователя')

        await tools.check_register_req_count_session(request)
        # # проверка заблокированности сессии, если заблочена: 22 код
        # await tools.check_blocked_session(request)

        phone, resp = await tools.get_data_by_name(request, 'phone')
        if resp is not None:
            return resp
        device_info, resp = await tools.get_data_by_name(request, 'deviceInfo')
        await utils.validate_data_with_block(request, device_info, schemas.DEVICE_INFO_SCHEMA)

        if resp is not None:
            return resp
        else:
            logger.debug(f'register_user: deviceInfo={device_info}')
        # ==========
        # 1) создать в профиле номер телефона с active=False из запроса - выполняется в create_session (1.d.i, ii, )
        # ==========
        # создание записи в confirmation_codes и отправка на указанный phone push/sms с кодом
        # отправляем СМС после проверки, что код не был недавно уже отправлен
        # ждем следующий реквест от него, надо запомнить в базе сгенерированный код и время жизни смс-кода N мин
        moa_sid = tools.get_moa_sid_from_req(request)
        request['fcm_token'] = device_info.get('fcm_token', None) if device_info is not None else None

        async def reg_new(phone_new, first_n=None, last_n=None):
            profile_id_new, error_text = await tools.register_new_user(request, phone_new, False, first_n, last_n)
            if profile_id_new is None:
                raise ApiResponse(90, log_message=f'register_user: Ошибка при регистрации, phone={phone_new}, '
                                                  f'error={error_text}')
            await tools.add_mile_transaction(request, profile_id_new, 0, 0, 1)
            await tools.update_active_session(request, True)
            # пристегнуть новый профиль к сессии
            res_u = await tools.update_profile_id_in_session(request, profile_id_new)
            if not res_u:
                raise ApiResponse(90, log_message='Views.register_user.reg_new - not res_u = True')

        # проверка номера телефона на предмет изменения (например, не правильно ввел номер с первого раза)
        phone_in_db, error = await tools.get_phone_from_session(request)
        another_phone = False
        if phone_in_db is not None:
            # в этой сессии уже прикреплен тел через профиль! если это другой телефон то перепристегнуть
            if phone != phone_in_db:
                # номер другой прислали в рамках этой сессии, проверим есть ли он в бд, если нет создаем
                await tools.check_bad_register_req_count_session(request)
                another_phone = True
                user = await tools.check_user(request, phone)
                if user is None:
                    # создание записи в profiles по phone_number=phone и active=false
                    await reg_new(phone)
                else:
                    # если запись о пользователе в БД уже есть
                    await tools.update_active_session(request, True)
                    res_upd = await tools.update_profile_id_in_session(request, user.get('id'))
                    if not res_upd:
                        raise ApiResponse(90, log_message=f'register_user: update_profile_id_in_session '
                                                          f'res_upd is false')
                    # r, err = await tools.set_name_user(lgr, pool, phone, first_name, last_name)
                # убить confirmation_code старый в рамках сессии
                await tools.set_confirmed_code_not_active(request)
            # else:
            #     moa_sid = await tools.renew_moa_in_coockie(request, moa_sid)
        if not another_phone:
            user = await tools.check_user(request, phone)
            # в этой сессии еще нет связанного профиля(первая попытка в сессии направить телефон)
            if user is None:
                # создание записи в profiles по phone_number=phone и active=false
                await reg_new(phone)
            else:
                # если запись о пользователе в БД уже есть
                await tools.update_active_session(request, True)
                res_upd = await tools.update_profile_id_in_session(request, user['id'])
                if not res_upd:
                    raise ApiResponse(90, log_message='Views.register_user - not another_phone, not res_upd = True')
                # r, err = await tools.set_name_user(lgr, pool, phone, first_name, last_name)
                # assert r, f'Ошибка при обновлении профиля: {err}'

        time_left, exp_date = await tools.get_time_left(moa_sid, request)
        if time_left > 0:
            # реализовать счетчик
            logger.error(f'register_user: Код не отправлен, не прошло минимальное время между повторной отправкой'
                         f' phone={phone}, time_left={exp_date}')
            raise ApiResponse(21)
        snd = await tools.send_code(request, phone, False)
        if snd > 0:
            type_code = 'смс' if snd == 1 else 'push'
            logger.info(f'register_user: Направлен {type_code}-код на {phone}')
            raise ApiResponse(0)
        else:
            logger.error(f'register_user: Не удалось отправить код на {phone}')
            raise ApiResponse(30)
    except (ApiResponse, CancelledError):
        raise
    except Exception as exc:
        logger.error(f'register_user: Исключение (phone={phone}, phone_in_db={phone_in_db}): {exc}')
        raise ApiResponse(90, exc=exc)


@routes.post(ROUTE_CONFIRM)
async def confirm_code(request):
    """
    @api {post} https://developer.mileonair.com/api/v1/confirm 2. Проверка кода и выдача долгосрочного token
    @apiName confirm_code
    @apiGroup Авторизация
    @apiVersion 1.0.0

    @apiParam {string {..8}} code Проверочный код
    @apiParamExample {json} Request-Example:
    {
        "code": "12345"
    }
    @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
    @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
    @apiSuccess (200) {dict} data  Словарь с данными
    @apiSuccess (200) {string}   data.token   Долгосрочный токен

    @apiSuccessExample {json} Success-Response:
        HTTP/1.1 200 OK
        {
            "responseCode": 0,
            "responseMessage": "Запрос обработан успешно",
            "data":
            {
                "token": "38c71c8e-b6d5-41b3-873b-fa6414b36698",
                "need_to_fill_profile": true
            }
        }

    @apiDescription Проверка кода, если код совпадает пользователь в БД отмечается как active=True,
    выдается долгосрочный токен, который будет использоваться в сессионной авторизации
    """
    try:
        pool = tools.get_pool_from_request(request)
        data = await tools.get_data_from_request(request)
        code = data.get('code', None)
        logger.info(f'Проверка кода и выдача долгосрочного gsid (введен code={code})')
        if code is None:
            raise ApiResponse(12, log_message=f'confirm_code: отсутствует код в запросе')
        # получили не пустой код, проверить, если совпал, то авторизовать(выдать долгосрочный токен)
        # выяснить phone из сессии (sid - profile_id - phone)
        phone, error = await tools.get_phone_from_session(request)
        if phone is None:
            raise ApiResponse(90, log_message=f'confirm_code: phone={phone} не найден в БД: {error}')
        # считать из базы код отправленный в пуш/смс, если не найден error!=None
        code_from_db, error, resp_13 = await tools.get_code(request)
        if resp_13:
            raise ApiResponse(13, log_message=f'confirm_code: {error}')
        if (error is not None) or (code_from_db is None):
            raise ApiResponse(90, log_message=f'confirm_code: ошибка: {error}')
        if str(code) == code_from_db:
            res, error = await tools.set_confirmed_code(request, True, code)
            if (error is not None) or (not res):
                raise ApiResponse(90, log_message=f'confirm_code: set_confirmed_code: ошибка (phone={phone}): {error}')
            res, error = await tools.set_active_user(pool, phone, True)
            if (error is not None) or (not res):
                raise ApiResponse(90, log_message=f'confirm_code: set_active_user: ошибка (phone={phone}): {error}')
            gsid, error = await tools.create_device(request, phone)
            # device_id = await tools.get_device_id_from_gsid(lgr, pool, gsid)
            # await tools.update_device_id_in_session(lgr, pool, device_id, request)
            if gsid is not None:
                await tools.generate_pqr(request, phone)
                # проверить заполнены ли в профиле фамилия и имя
                need_to_fill_profile = await tools.check_need_to_fill_profile(request, phone)
                data_response = {SESSION_TOKEN: gsid, 'need_to_fill_profile': need_to_fill_profile}
                logger.info(f'confirm_code: 0: Код принят для phone={phone}, выдан токен token=...{gsid[-4:]}, '
                            f'need_to_fill_profile={need_to_fill_profile}')
                # ----------------проверка на наличие баннеров профиля
                result_b = await tools.check_confirm_banners(request)
                if not result_b:
                    list_id = await tools.get_list_id_banners(request)
                    list_id_ = utils.convert_data(list_id)
                    for banner_ in list_id_:
                        await tools.insert_into_banners_to_profiles(request, banner_['id'])
                else:
                    pass
                # --------------------------------------------------
                raise ApiResponse(0, data=data_response)
            else:
                raise ApiResponse(90, log_message=f'confirm_code: gsid is None (phone={phone}): {error}')
        else:
            logger.warning(f'confirm_code: Неверный СМС-код phone={phone}')
            raise ApiResponse(13)
    except ApiResponse:
        raise
    except Exception as exc:
        logger.error(f'confirm_code: Исключение в confirm_code: {exc}')
        raise ApiResponse(90, log_message=f'1087: Исключение в confirm_code: {exc}')


@routes.post(ROUTE_LOGIN)
async def do_login(request):
    """
    @api {post} https://developer.mileonair.com/api/v1/login 3. Сессионная авторизация пользователя
    @apiName do_login
    @apiGroup Авторизация
    @apiVersion 1.0.0

    @apiParam {string} token Долгосрочный токен
    @apiParam {dict} deviceInfo Информация об устройстве
    @apiParam {string{..2}} [locale] Код языка (ISO 639-1) ('ru', 'en', 'it', ..)

    @apiParamExample {json} Request-Example:
    {
        "token": "38c71c8e-b6d5-41b3-873b-fa6414b36698",
        "deviceInfo": {
            "app_version": "1.1.1"
            },
        "locale": "ru"
    }
    @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
    @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа

    @apiSuccessExample {json} Success-Response:
        HTTP/1.1 200 OK
        {
            "responseCode": 0,
            "responseMessage": "Запрос обработан успешно"
        }

    @apiDescription Авторизация пользователя по долгосрочному токену

    """
    try:
        data = await tools.get_data_from_request(request)

        gsid, resp = await tools.get_data_by_name(request, SESSION_TOKEN)
        if resp is not None:
            return resp
        # device_id = request.get('device_id')
        device = await tools.get_device_id_from_gsid(request, gsid)
        device_id = device.get('id') if device is not None else None
        device_info, resp = await tools.get_data_by_name(request, 'deviceInfo')

        await utils.validate_data_with_block(request, device_info, schemas.DEVICE_INFO_SCHEMA)

        if resp is not None:
            return resp
        else:
            logger.debug(f'do_login: deviceInfo: {device_info}')
            await tools.set_device_info(request, device_id, device_info)

        session = await get_session(request)
        logger.info(f'do_login: Авторизация session_id={session.identity}, получен gsid={gsid}')

        if device_id is not None:
            # если gsid нашли в devices
            await tools.update_device_id_in_session(request, device_id)
            profile_id = device.get('profile_id')
            if profile_id is not None:
                logger.info(f'do_login: profile_id={profile_id}')
                res_upd = await tools.update_profile_id_in_session(request, profile_id)
            else:
                raise ApiResponse(90, log_message=f'do_login: в девайсе не записан profile_id={profile_id}, '
                                                  f'нарушен процесс регистрации')

            await tools.update_active_session(request, True)
            await tools.update_lifetime_in_device(request, device_id)
            app_version = device_info.get('app_version')
            await tools.update_app_version_in_device(request, device_id, app_version)
            # ==== добавляем locale в сессию и девайс
            locale = data.get('locale', None)
            locale_success = ''
            if locale is not None:
                res = await tools.update_locale_session(request, locale)
                res_dev = await tools.update_locale_device(device_id, locale, request)
                if not res or not res_dev:
                    locale_success = '(ошибка при записи локали)'
            # ===============================
            logger.info(f'do_login: 0: Успешная авторизация profile_id={profile_id}{locale_success}')
            raise ApiResponse(0)
        else:
            device_row = await tools.get_device_row(request, gsid)
            if device_row is None:
                logger.error(f'do_login: Попытка авторизации в системе с несуществующим токеном gsid={gsid}, '
                             f'в БД запись: device_row={device_row}')
            else:
                logger.warning(f'do_login: Срок действия gsid={gsid} истёк, требуется его повторная выработка,'
                               f'exp_date={device_row.get("exp_date")}, active={device_row.get("active")}', )
            await tools.update_active_session(request, False)
            raise ApiResponse(22)

    except (ApiResponse, CancelledError):
        raise
    except Exception as exc:
        logger.error(f'do_login: Исключение: {exc}')
        raise ApiResponse(90, exc=exc)


# @routes.get('/confirmationCodeLeftTime')
# async def get_code_left_time(request):
#     lgr = request.app['logger']
#     try:
#         pool = tools.get_pool_from_request(request, lgr)
#         # data, resp = await tools.get_data_from_request(request, lgr)
#         # if resp is not None:
#         #     return resp
#         moa_sid = await tools.get_moa_sid_from_req(request)
#         last_delta, exp_date = await tools.get_time_left(lgr, pool, moa_sid)
#         logger.info(lgr, f'0: Время оставшееся до повторной отправки '
#                                 f'(moa_sid={moa_sid}) seconds={last_delta}')
#         return web.json_response(tools.get_response_json(0, RESPONSE_0, {'time_left': last_delta,
#                                                                         'exp_date': exp_date}),
#                                  status=RESPONSE_STATUS)
#     except Exception as exc:
#         logger.error(lgr, f'1101: Исключение в get_code_left_time: {exc}')
#         return web.json_response(
#             tools.get_response_json(90, RESPONSE_90, {}), status=RESPONSE_STATUS)


@routes.post(ROUTE_LOGOUT)
async def do_logout(request):
    """
    @api {post} https://developer.mileonair.com/api/v1/logout 4. Выход из учетной записи
    @apiName do_logout
    @apiGroup Авторизация
    @apiVersion 1.0.0

    @apiParamExample {json} Request-Example:
    {
    }
    @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
    @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа

    @apiSuccessExample {json} Success-Response:
        HTTP/1.1 200 OK
        {
            "responseCode": 0,
            "responseMessage": "Запрос обработан успешно"
        }

    @apiDescription Выход из учетной записи, завершение пользовательской сессии

    """
    try:
        await tools.update_active_session(request, False)
        res = await tools.del_coockie(request)
        if res:
            logger.info(f'0: Выход из УЗ')
            raise ApiResponse(0)
        raise ApiResponse(90, log_message=f'1111: Ошибка, Не удалось обновить сессию пользователя')
    except ApiResponse:
        raise
    except Exception as exc:
        raise ApiResponse(90, exc=exc, log_message=f'1112: Исключение в do_logout: {exc}')


def get_parameters_stub(request):
    """
    @api {get} https://api.mileonair.com/v1/config Параметры системы
    @apiDescription Получить внесессионный список системных параметров бонусной системы и их значения

    @apiName get_parameters_stub
    @apiGroup Инициализация
    @apiVersion 1.0.0
    
    @apiParam {bool} [dev_env] Среда разработки
    @apiExample Request-Example:
        https://api.mileonair.com/v1/config?dev_env=true

    @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
    @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
    @apiSuccess (200) {dict} data  Словарь с данными
    @apiSuccess (200) {list}   data.parameters   Список параметров
    @apiSuccess (200) {string}   data.parameters.name Название параметра
    @apiSuccess (200) {string}   data.parameters.description Краткое описание параметра
    @apiSuccess (200) {string}   data.parameters.value Значение параметра

    @apiSuccessExample Success-Response:
        HTTP/1.1 200 OK
        {
            "responseCode": 0,
            "responseMessage": "Запрос обработан успешно",
            "data": {
                "parameters": [
                    {
                        "name": "default_language_code",
                        "description": "локализация приложения по-умолчанию",
                        "value": "ru"
                    },
                    {
                        "name": "auth_api_url",
                        "description": "Корневой роут АПИ авторизации",
                        "value": "https://developer.mileonair.com/api/v1"
                    },
                    {
                        "name": "user_api_url",
                        "description": "Корневой роут пользовательского АПИ",
                        "value": "https://developer.mileonair.com/api/v1"
                    }
                ]
            }
        }
    """
    raise ApiResponse(0)


def get_languages_stub(request):
    """
    @api {get} https://api.mileonair.com/v1/supportedLanguages Языки системы
    @apiDescription Получить список языков системы
    @apiName get_system_languages
    @apiGroup Инициализация
    @apiVersion 1.0.0

    @apiDescription Возвращает доступные языки

    @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
    @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
    @apiSuccess (200) {dict} data  Словарь с данными
    @apiSuccess (200) {list}   data.languages   Список доступных языков
    @apiSuccess (200) {string}   data.languages.id id языка
    @apiSuccess (200) {string}   data.languages.name Название
    @apiSuccess (200) {string}   data.languages.code Код языка

    @apiSuccessExample Success-Response:
        HTTP/1.1 200 OK
        {
          "responseCode": 0,
          "responseMessage": "Запрос обработан успешно",
          "data": {
            "languages": [
              {
                "id": 1,
                "name": "русский",
                "code": "ru"
              },
              {
                "id": 2,
                "name": "english",
                "code": "en"
              },
              {
                "id": 3,
                "name": "italiano",
                "code": "it"
              }
            ]
          }
        }
    """
    raise ApiResponse(0)


@routes.post(ROUTE_REMOVE_PROFILE)
async def remove_profile(request):
    """

    """
    try:
        pool = tools.get_pool_from_request(request)
        data = await tools.get_data_from_request(request)

        gsid = data.get(SESSION_TOKEN, None)
        logger.info(f'Удаление профиля gsid={gsid}')
        phone = request.query.get('phone', None)
        if phone is None:
            logger.error(f'1991: Нет обязательного параметра phone, gsid={gsid}')
            raise ApiResponse(12)
        # /////
    except Exception as exc:
        logger.error(f'1992: Исключение в remove_profile: {exc}')
        raise ApiResponse(90, exc=exc)


@routes.get(ROUTE_LOGGER)
async def take_logs(request):
    error = ''
    last_lines = ''
    n = int(request.query.get('n', 20))
    try:
        with open(LOG_FILE_NAME, encoding='utf-8') as f:
            last_lines = list(deque(f, n))
    except Exception as exc:
        error = str(exc)
    return web.json_response(last_lines if error == '' else (error + '\n' + last_lines), status=RESPONSE_STATUS)


@routes.get(ROUTE_RELOAD_PARAMS)
async def reload_params(request):
    error = None
    try:
        res = tools.read_sys_params(request.app)
        logger.info(f'{res}')
    except Exception as exc:
        error = str(exc)
        logger.error(f'2222: Исключение в reload_params: {error}')
    status = 'OK' if error is None else 'ERROR'
    raise ApiResponse(0, data={'status': status})


# =================

@routes.get(ROUTE_CONFIG)
async def get_parameters(request):
    try:
        logger.debug(f'Запрос...')

        pool = tools.get_pool_from_request(request)
        async with pool.acquire() as conn:
            async with conn.transaction():
                data = await conn.fetch(f'SELECT name, description, value FROM system_parameters WHERE config=true')
        if data is not None:
            utils.convert_data(data, formatting_datetime=FORMAT_DATE_TIME)
        else:
            data = {}
        logger.info(f'Запрос выполнен')
        raise ApiResponse(0, {'parameters': data})
    except Exception as exc:
        logger.error(f'306 Исключение: {str(exc)}')
        raise ApiResponse(90, exc=exc)


@routes.get(ROUTE_SUP_LANGUAGES)
async def get_languages(request):
    logger.info(f'Запрос...')
    pool = tools.get_pool_from_request(request)
    async with pool.acquire() as conn:
        async with conn.transaction():
            data = await conn.fetch(f"select * from languages")
    if data is not None:
        utils.convert_data(data, formatting_datetime=FORMAT_DATE_TIME)
    else:
        data = {}
    logger.info(f'Запрос выполнен')
    raise ApiResponse(0, {'languages': data})


@routes.get(ROUTE_COUNTRIES)
async def code_phone(request):
    """
    @api {get} https://developer.mileonair.com/api/v1/countries Словарь стран
    @apiName code_phone
    @apiGroup Инициализация
    @apiVersion 1.0.0
    @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
    @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа

    @apiSuccessExample {json} Success-Response:
        HTTP/1.1 200 OK
     "responseCode": 0,
    "responseMessage": "Запрос обработан успешно",
    "data": {
        "countries": [
            {
                "id": 4,
                "iso2": "PF",
                "iso3": "PYF",
                "phone_mask": "+689-##-##-##",
                "flag_url": "https://developer.mileonair.com/resources/flag/french-polynesia.png"
            }],
              "translates": [
            {
                "name": "Французская Полинезия (Таити)",
                "language_code": "ru"
            },
            {
                "name": "French Polynesia",
                "language_code": "en"
            },

    @apiDescription Возвращения словаря стран с кодами и масками телефонов

    """

    countries, translates = await tools.get_codephone(request)

    list_countries = []
    list_translates = []
    for country in countries:
        list_countries.append(dict(country))

    for translate in translates:
        list_translates.append(dict(translate))
    raise ApiResponse(0, {'countries': list_countries, 'translates': list_translates})


# @routes.view(ROUTE_TEST_)
# class BannerView(web.View):
#
#     async def get(self):
#         try:
#             path = self.request.app.router['test_banner'].url_for(filename='index.html')
#             url = str(self.request.url.origin().join(path))
#         except Exception as ex:
#             url = None
#             print(ex)
#
#         return ApiResponse(0, {'url': url})
#
#     async def post(self):  # todo redirect in banner with certain product by active push
#         print('ok')
#         return ApiResponse(0, {'data': 'need to redirect #todo'})


@routes.view(ROUTE_BANNER)
class GetBanner(web.View):
    class InputGetData(BaseModel):
        banner_id: int
        # language_code: str #todo брать из сессии
        limit: int = 20
        offset: int = 0

        class Config:
            extra = 'forbid'

    """
       @api {get} https://developer.mileonair.com/api/v1/banner Информация о баннере
       @apiName get_banner
       @apiGroup Лента
       @apiVersion 1.0.0
       @apiParam {int} banner_id ID баннера
       @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
       @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
       @apiExample Request-Example:
            https://developer.mileonair.com/api/v1/banner?banner_id=2
       @apiSuccessExample {json} Success-Response:
           HTTP/1.1 200 OK
           
        Для PROMOTION
     {
    "responseCode": 0,
    "responseMessage": "Запрос обработан успешно",
    "data": {
        "title": "Promotions",
        "long_description": " ",
        "action": null,
        "short_description": "Баннер promotions",
        "type": "promotion",
        "photo_path": "https://developer.mileonair.com/resources/Banner/3_photo_path.png",
         "image_url": "https://developer.mileonair.com/resources/Banner/3_photo_path.png",
        "preview_rectangle_image_url": "https://developer.mileonair.com/resources/",
        "preview_square_image_url": "https://developer.mileonair.com/resources/",
        "logo_path": "https://developer.mileonair.com/resources/Promotion/1_photo_path.jpg",
        "promotion": {
            "id": 1,
            "conditions": "<p><strong>С 15 июня в Бургер Кинг действует акция от платежной системы JCB! </strong>Сделай любой заказ в ресторанах-участниках на кассе Оплати картой JCB Скидка 50% на твой заказ пройдет автоматически! Скидка распространяется на все меню Бургер Кинг Будь внимателен: Скидка не действует при оплате картой JCB-МИР Скидка не действует в киосках, мобильном приложении и доставке Правила акции размещены на сайте: www.specialoffers.jcb/ru/</p>",
            "route": "/participateInPromotion"
        },
        "button": {
            "is_enabled": false,
            "text": "Вы уже участвуете"
        },
        
        "redirect": null
    }
}

    Для ACTION
    {
    "responseCode": 0,
    "responseMessage": "Запрос обработан успешно",
    "data": {
        "title": "Mobile Box",
        "long_description": " ",
        "action": {
            "click_action": "partners",
            "airport_id": 33,
            "id": 10
        },
        "short_description": "Аксессуары для смартфонов",
        "type": "action",
         "photo_path": "https://developer.mileonair.com/resources/Banner/3_photo_path.png",
        "image_url": "https://developer.mileonair.com/resources/Banner/3_photo_path.png",
        "preview_rectangle_image_url": "https://developer.mileonair.com/resources/",
        "preview_square_image_url": "https://developer.mileonair.com/resources/",
        "logo_path": null,
        "button": {
            "text": "Показать",
            "is_enabled": true
        },
        "promotion": null,
        "redirect": null
    }
}

       Для EMPTY
       {
    "responseCode": 0,
    "responseMessage": "Запрос обработан успешно",
    "data": {
        "title": "Empty",
        "long_description": " ",
        "action": null,
        "short_description": "Баннер empty",
        "type": "empty",
         "photo_path": "https://developer.mileonair.com/resources/Banner/3_photo_path.png",
         "image_url": "https://developer.mileonair.com/resources/Banner/3_photo_path.png",
         "preview_rectangle_image_url": "https://developer.mileonair.com/resources/",
         "preview_square_image_url": "https://developer.mileonair.com/resources/",
        "logo_path": null,
        "button": {
            "text": null,
            "is_enabled": true
        },
        "promotion": null,
        "redirect": null
    }
}

 Для POPUP 
        
        {
    "responseCode": 0,
    "responseMessage": "Запрос обработан успешно",
    "data": {
        "title": "alfa travel",
        "long_description": "alfa travel",
        "action": {
            "click_action": "privileges"
        },
         "redirect":{
        "form_url": "https://alfabank.ru/everyday/debit-cards/travel/?platformId=google_cpc_g-cashback-dc-cobrand-msk-
        search_debit_card_mgcom_alfaid|kwd-451512215208|cid|10111053254|aid|527950058558|gid|101266738973|pos||src|g_|
        dvc|c|reg|9047030|rin|&gclid=EAIaIQobChMI16Drj9m38gIVk813Ch3-6AqzEAAYASAAEgLPV_D_BwE",
         "redirect_url": " "
         }
        "short_description": "alfa travel",
        "type": "action",
        "image_url": "https://developer.mileonair.com/resources/Banner/22e4e7cfa3853205604ec428484080fd.png",
        "photo_path": "https://developer.mileonair.com/resources/Banner/22e4e7cfa3853205604ec428484080fd.png",
        "preview_rectangle_image_url": "https://developer.mileonair.com/resources/Banner/22e4e7cfa3853205604ec428484080fd_rOdUOOv.png",
        "preview_square_image_url": "https://developer.mileonair.com/resources/Banner/22e4e7cfa3853205604ec428484080fd_yrgFnwm.png",
        "logo_url": null,
        "button": {
            "text": "Понятно",
            "is_enabled": true
        },
        "promotion": null,
        
    }
}

       @apiDescription Получение баннера



       """

    async def get(self):
        params = utils.validate_data(self.request.query, self.InputGetData)
        language_code = self.request.get('locale', 'ru')
        banners = await tools.get_banner(self.request, params.banner_id, language_code)

        if banners:
            for banner in banners:
                dict_banners = dict(banner)
                dict_banners_ = await tools.check_promotion(self.request, params.banner_id, dict_banners)
                if "redirect" in dict_banners_ :
                    dict_banners_ = tools.change_title_for_redirect_banner(dict_banners_, language_code, params.banner_id)
                else :
                    pass


                logger.info(f'Запрос выполнен')
        else:
            logger.error(f'Баннера с таким id не сущуствует')
            raise ApiResponse(13)

        # pool = tools.get_pool_from_request(self.request)
        # async with pool.acquire() as conn:
        #     await conn.execute(
        #         'UPDATE banners_to_profiles SET read_banner=True where profile_id=$1 and banner_id=$2 ;',
        #         self.request.get("profile_id"), int(self.request.query.get('banner_id'))
        #     )

        raise ApiResponse(0, dict_banners_)


@routes.view(ROUTE_BANNERS)
class GetBanners(web.View):
    class InputGetData(BaseModel):
        category_id: Optional[int] = None
        airport_id: Optional[int] = None
        limit_offset: Optional[int] = 20
        offset: Optional[int] = 0

        class Config:
            extra = 'forbid'

    """
       @api {get} https://developer.mileonair.com/api/v1/banners Список баннеров/акций
       @apiName get_banners
       @apiGroup Лента
       @apiVersion 1.0.0
        @apiParam {int} [airport_id] ID аэропорта
        @apiParam {int} [category_id] категория баннера 
        @apiParam {int} [limit_offset=20] количество баннеров
        @apiParam {int} [offset=0] от какого баннера
       @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
       @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
       @apiExample Request-Example:
            https://developer.mileonair.com/api/v1/banners?category_id=3&airport_id=1&limit_offset=1&offset=1
       @apiSuccessExample {json} Success-Response:
           HTTP/1.1 200 OK
     {
    "responseCode": 0,
    "responseMessage": "Запрос обработан успешно",
    "data": {
        "data_banners": [
            {
                "id": 2,
                "title": "баннер 2",                
                "short_description": null,
                "photo_path": "https://developer.mileonair.com/resources/Banner/3_photo_path.png",
                "image_url": "https://developer.mileonair.com/resources/Banner/3_photo_path.png",
                "preview_rectangle_image_url": "https://developer.mileonair.com/resources/",
                "preview_square_image_url": "https://developer.mileonair.com/resources/",
                "logo_path": "https://developer.mileonair.com/resources/Promotion/1_photo_path.jpg",
                "single_preview_square_image_url": "https://developer.mileonair.com/resources/Banner/photo.png"
            }
        ],
        "total_count": 1
    }
}

       @apiDescription Возвращается выборка баннеров в зависимости от query params в зависимости от них будет 
       производится фильтрация, к примеру нужен все баннеры в аэропорту:
       https://developer.mileonair.com/api/v1/banners?airport_id=1&limit_offset=1&offset=1
       соответственно только одну категорию во всех аэрпортах:
       https://developer.mileonair.com/api/v1/banners?category_id=1&limit_offset=1&offset=1
       показать все баннеры:
       https://developer.mileonair.com/api/v1/banners?limit_offset=1&offset=1
       и так дале по аналогии.
       
       

       """

    async def get(self):

        params = utils.validate_data(self.request.query, self.InputGetData)
        language_code = self.request.get('locale', 'ru')

        if params.category_id is None and params.airport_id is None:  # 00 category = none airport = none
            banners = await tools.get_all_banners(self.request, language_code,
                                                  params.limit_offset, params.offset)

        elif params.category_id is not None and params.airport_id is None:  # 01 category = notNone airport = none
            banners = await tools.get_banner_category(self.request, params.category_id, language_code,
                                                      params.limit_offset, params.offset)

        elif params.category_id is None and params.airport_id is not None:  # 10 category = none airport = notNone
            banners = await tools.get_banners_airport(self.request, params.airport_id, language_code,
                                                      params.limit_offset, params.offset)

        elif params.category_id is not None and params.airport_id is not None:  # 11 category = notNone airport = notNone
            banners = await tools.get_banners_category_airport(self.request, params.airport_id, language_code,
                                                               params.category_id, params.limit_offset, params.offset)

        else:
            banners = None

        list_banners = []
        # await tools.update_banner_count_to_profile(self.request)
        await tools.update_status_banner_to_profile(self.request)
        if not banners:
            total_count = 0
            raise ApiResponse(0, {'banners': list_banners, 'total_count': total_count})

        for banner in banners:
            dict_banner = dict(banner)
            del dict_banner['total_count']
            list_banners.append(dict_banner)
        logger.info(f'Запрос выполнен для получения баннеров выполнен')

        if banners is not None:
            total_count = banners[0]['total_count']
        else:
            total_count = 0

        if len(list_banners):
            image_url = await tools.get_single_square_image_url(self.request, list_banners[0]['id'])
            list_banners[0]['single_preview_square_image_url'] = image_url

        raise ApiResponse(0, {'banners': list_banners, 'total_count': total_count})


@routes.view(ROUTE_BANNERS_CATEGORIES)
class GetBannersCategories(web.View):
    """
       @api {get} https://developer.mileonair.com/api/v1/banner_categories Список категорий баннеров
       @apiName get_categories
       @apiGroup Лента
       @apiVersion 1.0.0
       @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
       @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
       @apiExample Request-Example:
            https://developer.mileonair.com/api/v1/banner_categories
       @apiSuccessExample {json} Success-Response:

     {
    "responseCode": 0,
    "responseMessage": "Запрос обработан успешно",
    "data": [
            {
                "id": 1,
               "name":"Новости"
            },
            {
                "id": 2,
                "name": "Персональные предложения"
            }
            ..........
        ]
}

       @apiDescription Возвращается словарь с категортями


       """

    async def get(self):
        language_code = self.request.get('locale', 'ru')
        banners = await tools.get_categories(self.request, language_code)
        data = utils.convert_data(banners)
        raise ApiResponse(0, data)


@routes.view(ROUTE_PARTICIPANT_PROMO)
class ParticipatePromo(web.View):
    """
       @api {post} https://developer.mileonair.com/api/v1/participateInPromotion Принятие участия в акции
       @apiName post_participate
       @apiGroup Лента
       @apiParam {int} id ID промо
        @apiParamExample {json} Request-Example:
    {
        "id":1
    }
       @apiVersion 1.0.0
       @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
       @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
       @apiExample Request-Example:
            https://developer.mileonair.com/api/v1/participateInPromotion
       @apiSuccessExample {json} Success-Response:

{
    "responseCode": 0,
    "responseMessage": "Запрос обработан успешно",
    "data": {
        "status": "OK"
    }
}

       @apiDescription Принятие участие в акции


       """

    async def post(self):
        body = await tools.get_data_from_request(self.request)
        try:
            await tools.insert_promotion_to_profiles(self.request, body['id'])
        except KeyError:
            raise ApiResponse(13)
        raise ApiResponse(0)


@routes.view(POPUP_BANNER)
class PopupBanner(web.View):
    """
         @api {get} https://developer.mileonair.com/api/v1/popup_banners Информация о popup банере
         @apiName get_popup_banner
         @apiGroup Лента
         @apiVersion 1.0.0

         @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
         @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
         @apiExample Request-Example:
              https://developer.mileonair.com/api/v1/popup_banners
         @apiSuccessExample {json} Success-Response:


    {
    "responseCode": 0,
    "responseMessage": "Запрос обработан успешно",
    "data": [
        {
            "title": "Оформите цифровую карту Alfa Travel и получите кэшбэк до 500 ₽ за первую покупку",
            "description": "• 2 бесплатных* упаковки багажа по карте Visa Signature сразу после привязки карты в разделе «Привилегии»\\n• Оформление – не более минуты\\n• Бесплатное обслуживание",
            "redirect": {
                "form_url": "http://localhost",
                "redirect_url": "http://localhost"
            },
            "banner_id": 22,
            "popup_banner_id": 1,
            "action": {
                "click_action": "privileges"
            },
            "image_url": "https://developer.mileonair.com/resources/BannerPopup/1_image_path.png",
            "logo_url": "https://developer.mileonair.com/resources/BannerPopup/1_logo_path.png",
            "promotion": {
                "id": 9,
                "conditions": "<p>Дебетовая картаAlfa Travel</p>\r\n\r\n<p>Лучшая карта для любителей путешествий</p>",
                "route": "/participateInPromotion"
            },
            "button": {
                "is_enabled": true,
                "text": "Понятно"
            }
        },
        .........
    ]
}



  Если popup не надо показывать

   {
      "responseCode": 0,
      "responseMessage": "Запрос обработан успешно",
      "data": [ ]

   }


         @apiDescription Получение popup баннера

         """

    async def get(self):

        language_code = self.request.get('locale', 'ru')
        popup_banners = await tools.get_popup_banner(self.request, language_code)
        list_popup_banners = []
        if popup_banners:
            for banner in popup_banners:
                dict_banner = dict(banner)
                dict_banner_ = await tools.check_promotion(self.request, dict_banner['banner_id'], dict_banner)
                if await tools.check_show_popup(self.request, dict_banner_):
                    if "redirect" in dict_banner_:
                        dict_banner_ = tools.change_title_for_redirect_banner(dict_banner_, language_code)
                    list_popup_banners.append(dict_banner_)

                logger.info(f'Отобраны попап баннеры')

        max_count_popup_show = await tools.max_count(self.request)

        raise ApiResponse(0, list_popup_banners[0:int(max_count_popup_show)])



@routes.view(REDIRECT_TEST_BANNER)
class RedirectBannerTest(web.View):

    @aiohttp_jinja2.template('test_redirect_banner.html')
    async def get(self):

            context = {}

            return context


