import asyncio
import datetime
import hashlib
import hmac
import inspect
from abc import abstractmethod, ABC
from asyncio import CancelledError, create_task
from typing import Optional, List

import aiohttp
import aiohttp_jinja2
from aiohttp import http_parser
from aiohttp import web
from aiohttp.web_exceptions import HTTPNotFound
from api_utils import ApiResponse, ApiPool
from asyncpg import Connection
from loguru import logger
from pydantic import validator
from pydantic.main import BaseModel

import alfa_bank
import kassa
import pss
import schemas
import tools
import tools_ext
from ApiView import validate, ApiView, validate_apiview
# from auth import MAIL_USER, IS_DEV, PSS_URL, PSS_TOKEN, CALLBACK_TOKEN
from alfa_bank import create_bundle
from models import OrderModel
from order.models import OnpassOrder
from profile import Profile as ProfileObj, EmailAddress
from queries import *
from sendmail import send_mail_async
from settings import *
from confirm_email.views import SendEmail
from user.models import User, Profile as profile_find
from utils import convert_data, validate_data, get_page, get_bool_param, \
    group_data, get_language_id, to_int, rename_field, RequestFileSaver, get_redirect_url, save_email_for_receipts, validate_data
from pydantic import ValidationError
routes = web.RouteTableDef()


# @routes.view(ROUTE_PROFILE)
# class NewProfile(ApiView):
#     async def get(self):
#         profile = await ProfileObj.get_by_session(self.session)
#         print(profile)
#         return HTTPOk(content_type='application/json',
#             body=Response(0, body=profile).json())
#
#
#     async def post(self):
#         json = await self.get_json_from_request()
#         profile = await ProfileObj.get_by_session(self.session)
#         await profile.update(json)
#         return HTTPOk(content_type='application/json',
#                       body=Response(0).json())

@routes.view(ROUTE_PROFILE, name='profile')
class Profile(ApiView):

    class InputGetData(BaseModel):
        language_code: Optional[str]

    async def get(self):
        """
        @api {get} https://developer.mileonair.com/api/v1/profile Получить

        @apiName get_profile
        @apiGroup Работа с профилем
        @apiVersion 1.0.0

        @apiDescription Получение профиля пользователя

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {string}   data.customer_id   uid  профиля
        @apiSuccess (200) {string}   data.phone_number   Номер телефона
        @apiSuccess (200) {string}   data.first_name   Имя
        @apiSuccess (200) {string}   data.last_name   Фамилия
        @apiSuccess (200) {string}   data.patronymic   Отчество
        @apiSuccess (200) {string}   data.email   Почтовый адрес
        @apiSuccess (200) {string}   data.birth_date   Дата рождения
        @apiSuccess (200) {float}   data.mile_count   Количество миль
        @apiSuccess (200) {string}   data.pqr   Персональный QR
        @apiSuccess (200) {dict}   data.user_status   Словарь с данными
        @apiSuccess (200) {string}   data.user_status.name   Название статуса
        @apiSuccess (200) {float}   data.user_status.conversion_rate   Курс конвертации
        @apiSuccess (200) {float}   data.user_status.minimum_conversion_threshold   Минимальная сумма для конвертации
        @apiSuccess (200) {dict}   data.settings   Словарь с данными
        @apiSuccess (200) {int}   data.settings.language_id   Id языка
        @apiSuccess (200) {dict}   data.onpass_data   Словарь с данными
        @apiSuccess (200) {int}   data.onpass_data.pass_count_1   Доступные проходы в бизнес залы типа "Бизнес"
        @apiSuccess (200) {int}   data.onpass_data.pass_count_2   Доступные проходы в бизнес залы типа "Премиум"
        @apiSuccess (200) {int}   data.onpass_data.pass_count_3   Доступные проходы в бизнес залы типа "VIP"


        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
            {
                "responseCode": 0,
                "responseMessage": "Запрос обработан успешно",
                "data": {
                    "customer_id": "b96219aa-4d9d-40f2-9b36-d46822683592",
                    "phone_number": "+79857759703",
                    "birth_date": "1991-08-23",
                    "first_name": "Иван",
                    "patronymic": " ",
                    "last_name": "Драго",
                    "mile_count": 5809,
                    "unread_banners_count": 0,
                    "pqr": "45d0dd60db0efc165ccb1006445fc6351b990c78c1fd29536292e174e4e01e35",
                    "email": "nikit-dolgo@yandex.ru",
                    "user_status": {
                        "name": "стандарт",
                        "conversion_rate": 0.5,
                        "minimum_conversion_threshold": 250.0
                    },
                    "settings": {
                        "language_id": 1
                    },
                    "onpass_data": {
                        "pass_count_1": 0,
                        "pass_count_2": 0,
                        "pass_count_3": 0
                    },
                    "resend_confirmation_email_date": "2021-09-07 07:15:04",
                    "is_email_confirmed": false
                }
            }

        """
        await tools.check_banners(self.request)
        profile = await ProfileObj.get_by_session(self.session)
        return ApiResponse(0, profile)

    async def post(self):
        """
        @api {post} https://developer.mileonair.com/api/v1/profile Изменить

        @apiName update_profile
        @apiGroup Работа с профилем
        @apiVersion 1.0.0

        @apiParam {string} [first_name]  Имя
        @apiParam {string} [last_name]  Фамилия
        @apiParam {string} [patronymic]  Отчество
        @apiParam {string} [email]  Электронная почта
        @apiParam {string} [birth_date] дата рождения (если дата рождения уже указана - поле игнорируется)
        @apiParam {str} [language_code=ru] Локаль при регистрации
        @apiParamExample {json} Request-Example:
            {
              "first_name": "Иван",
              "last_name": "Иванов",
              "patronymic": "Иванович",
              "email": "ivan@example.com",
              "birth_date": "1995-01-06"
            }

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа

        @apiSuccessExample {json} Success-Response:
            HTTP/1.1 200 OK
            {
              "responseCode": 0,
              "responseMessage": "Запрос обработан успешно"
            }
        """
        params = validate_data(self.request.query, self.InputGetData)
        json = await self.get_json_from_request()
        profile = await ProfileObj.get_by_session(self.session)
        if 'email' in json:
            try:
                EmailAddress(email=json['email'])
            except ValidationError:
                logger.info(f'не валидный email {json["email"]}')
                raise ApiResponse(13)
            json['resend_confirmation_email_date'] = datetime.datetime.utcnow()
            json['is_email_confirmed'] = False
            await profile.update(json)
            path = self.request.app.router['ConfirmEmail'].url_for()
            url = self.request.url.origin().join(path)
            profile_email = await profile_find.find(self.request.get('profile_id'))
            profile_email.email = json['email']
            create_task(SendEmail(self.request).send_confirmation_email(url.with_scheme('https'), profile_email, self.request.get('locale', 'ru'), params.language_code))
        else:
            #await profile.update(json)
            raise ApiResponse(13)
        raise ApiResponse(0)


@routes.view(ROUTE_AIRPORTS)
class Airports(web.View):

    async def get(self):
        """

        @api {get} https://developer.mileonair.com/api/v1/airports Аэропорты

        @apiName get_airports
        @apiGroup Справочники
        @apiVersion 1.0.0

        @apiParam {int} [limit=20] Ограничение количества выводимых значений
        @apiParam {int} [offset=0] Отступ пагинации

        @apiDescription Получить список аэропортов и их терминалов при наличии.

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {list}   data.airports   Список аэропортов
        @apiSuccess (200) {int}   data.airports.id ID аэропорта
        @apiSuccess (200) {int}   data.airports.city_id ID города
        @apiSuccess (200) {string}   data.airports.code_iata ИАТА Код аэропорта
        @apiSuccess (200) {float}   data.airports.latitude Координаты аэропорта: широта
        @apiSuccess (200) {float}   data.airports.longitude Координаты аэропорта: долгота
        @apiSuccess (200) {string}   data.airports.photo_path Путь к фото аэропорта
        @apiSuccess (200) {bool}   data.airports.available Статус подключения аэропорта к системе
        @apiSuccess (200) {int}   data.airports.partners_count Количество партнёров в аэропорту
        @apiSuccess (200) {list}   [data.airports.terminals] список терминалов
        @apiSuccess (200) {int}   data.airports.terminals.id ID терминала
        @apiSuccess (200) {float}   data.airports.terminals.latitude Координаты терминала: широта
        @apiSuccess (200) {float}   data.airports.terminals.longitude Координаты терминала: долгота
        @apiSuccess (200) {string}   data.airports.terminals.photo_path Путь к фото терминала
        @apiSuccess (200) {bool}   data.airports.terminals.available Статус подключения терминала к системе
        @apiSuccess (200) {int}   data.airports.terminals.partners_count Количество партнёров в терминале
        @apiSuccess (200) {list}   data.translates   Список переводов
        @apiSuccess (200) {int}   data.translates.id ID перевода
        @apiSuccess (200) {int}   data.translates.airports_id ID аэропорта
        @apiSuccess (200) {string}   data.translates.title Название аэропорта или терминала
        @apiSuccess (200) {int}   data.translates.language_id ID языка





        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
                {
                    "responseCode": 0,
                    "responseMessage": "Запрос обработан успешно",
                    "data": {
                        "airports": [
                            {
                                "id": 1,
                                "city_id": 1,
                                "code_iata": "SVO",
                                "latitude": null,
                                "longitude": null,
                                "photo_path": null,
                                "available": false,
                                "partners_count": 1,
                                "terminals": [
                                    {
                                        "id": 15,
                                        "latitude": 55.981178283691406,
                                        "longitude": 37.415096282958984,
                                        "photo_path":
                                        "https://developer.mileonair.com/resources/Airport/15_photo_path.jpg",
                                        "available": false,
                                        "partners_count": 12
                                    }
                                ]
                            }
                        ],
                        "translates": [
                            {
                                "id": 1,
                                "airport_id": 1,
                                "title": "Шереметьево",
                                "language_id": 1
                            },
                            {
                                "id": 4,
                                "airport_id": 1,
                                "title": "Sheremetyevo",
                                "language_id": 2
                            },
                            {
                                "id": 29,
                                "airport_id": 15,
                                "title": "Terminal B",
                                "language_id": 2
                            },
                            {
                                "id": 31,
                                "airport_id": 15,
                                "title": "Терминал B",
                                "language_id": 1
                            }
                        ]
                    }
                }
        """

        pool = tools.get_pool_from_request(self.request)
        async with pool.acquire() as conn:
            async with conn.transaction():

                airports = await conn.fetch(GET_AIRPORTS)
                convert_data(airports)
                airports_id_list = [row['id'] for row in airports]
                terminals_prepared = await conn.prepare(GET_TERMINALS)
                for airport in airports:
                    terminals = convert_data(await terminals_prepared.fetch(airport.get('id')))
                    if terminals:
                        airport['terminals'] = terminals
                translates = await conn.fetch(GET_AIRPORTS_TRANSLATE, airports_id_list)
                convert_data(translates, formatting_datetime=FORMAT_DATE_TIME)
        data = {'airports': airports, 'translates': translates}
        raise ApiResponse(0, data)


@routes.view(ROUTE_PARAMETERS)
class Parameters(web.View):

    async def get(self):
        """
        @api {get} https://developer.mileonair.com/api/v1/parameters Системные параметры

        @apiDescription Получить список системных параметров бонусной системы и их значения

        @apiName get_parameters
        @apiGroup Справочники
        @apiVersion 1.0.0

        @apiDescription Возвращает системные пврвметры бонусной сиситемы

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
                    "name": "default_mile_accrual_percentage",
                    "description": null,
                    "value": "0.1"
                  }
                ]
              }
            }

        """
        pool = tools.get_pool_from_request(self.request)
        async with pool.acquire() as conn:
            data = await conn.fetch(SYSTEM_PARAMETERS_QUERY)
        data = convert_data(data)
        data = {'parameters': data}
        raise ApiResponse(0, data)


@routes.view(ROUTE_LANGUAGES)
class Languages(web.View):

    async def get(self):
        """

        @api {get} https://developer.mileonair.com/api/v1/languages Языки

        @apiDescription Получить список языков
        @apiName get_languages
        @apiGroup Справочники
        @apiVersion 1.0.0

        @apiDescription Возвращает доступные языки

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {list}   data.languages   Список доступных языков
        @apiSuccess (200) {int}   data.languages.id id языка
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
                  }
                ]
              }
            }
        """
        pool = tools.get_pool_from_request(self.request)
        async with pool.acquire() as conn:
            data = await conn.fetch(LANGUAGES_QUERY)
        convert_data(data)
        data = {'languages': data}
        raise ApiResponse(0, data)


@routes.view(ROUTE_SETTINGS)
class Settings(web.View):
    async def post(self):
        """
        @api {post} https://developer.mileonair.com/api/v1/settings  Изменить настройки

        @apiDescription Сменить язык
        @apiVersion 1.0.0
        @apiName set_profile_settings
        @apiGroup Параметры

        @apiParam {Int} lang_id ID нового языка


        @apiParamExample {json} Request-Example:
            {
              "language_id": 2
            }

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа

        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
            {
              "responseCode": 0,
              "responseMessage": "Запрос обработан успешно"
            }
        """
        pool = tools.get_pool_from_request(self.request)
        logger.info(f'{inspect.stack()[0][3]} profile_id={self.request.get("profile_id")}')
        moa_sid = tools.get_moa_sid_from_req(self.request)
        params = await tools.get_data_from_request(self.request)
        validate_data(params, schemas.POST_SETTINGS_SCHEMA)
        language_id = params.get('language_id')
        if language_id is None:
            raise ApiResponse(12)
        async with pool.acquire() as conn:
            async with conn.transaction():
                lang_code = await conn.fetchval(GET_LANGUAGE_CODE, language_id)
                if lang_code is None:
                    logger.error(f'{inspect.stack()[0][3]} profile_id={self.request.get("profile_id")}: '
                                 f'несуществующий язык')
                    raise ApiResponse(13)

                await conn.execute(SET_LOCALE_IN_DEVICES_QUERY, lang_code, moa_sid)
                await conn.execute(SET_LOCALE_IN_SESSIONS_QUERY, lang_code, moa_sid)
        raise ApiResponse(0)


@routes.view(ROUTE_HASHES)
class Hashes(web.View):

    async def get(self):
        """

        @api {get} https://developer.mileonair.com/api/v1/hashes Хеши

        @apiDescription Получить хошированных таблиц
        @apiName get_hashes
        @apiGroup Справочники
        @apiVersion 1.0.0

        @apiDescription Возвращает доступные Хеши

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {list}   data.hashes   Список хешей
        @apiSuccess (200) {string}   data.hashes.table_name Название
        @apiSuccess (200) {string}   data.hashes.value Значение



        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
            {
              "responseCode": 0,
              "responseMessage": "Запрос обработан успешно",
              "data": {
                "hashes": [
                  {
                    "table_name": "airports",
                    "value": "e70029a276f7289b8854111c382069ed"
                  },
                  {
                    "table_name": "languages",
                    "value": "2fd668775ee664ffa32914f0f3601498"
                  },
                  {
                    "table_name": "partner_categories",
                    "value": "80936f7d428efe9e6cdb5644835bc777"
                  }
                ]
              }
            }



        """
        pool = tools.get_pool_from_request(self.request)
        async with pool.acquire() as conn:
            data = await conn.fetch(GET_HASHES_QUERY)
        data = convert_data(data)
        data = {'hashes': data}

        raise ApiResponse(0, data)


@routes.view(ROUTE_FEEDBACK)
class Feedback(web.View):

    async def post(self):
        """
        @api {post} https://developer.mileonair.com/api/v1/feedback  Отправить отзыв

        @apiDescription Отправить отзыв, в примере запроса только json, но там 2 формы, в форме photo может быть файл
        @apiVersion 1.0.0
        @apiName add_feedback
        @apiGroup Связь с пользователем

        @apiParam {File} photo Form-based форма с изображением/изображениями (максимум 5)
        @apiParam {String} message Текст отзыва
        @apiParam {String} email Email для обратной связи

        @apiParamExample {post} Request-Example:

              "message": "Приложение работает хорошо)",
              "email": "example@example.com"


        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа

        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
            {
              "responseCode": 0,
              "responseMessage": "Запрос обработан успешно"
            }
        """
        # params = await tools.get_data_from_request((await self.request.post()))
        params = dict(await self.request.post())

        if params == {}:
            logger.debug('формы пустые')
            params = await tools.get_data_from_request(self.request)
            logger.debug(f'params={params}')
        if params.get('photo') is not None:
            saver = RequestFileSaver('photo', FEEDBACK_IMAGES_FOLDER)
            filenames = await saver.save_files(self.request)
            params.pop('photo')
        else:
            filenames = None
        validate_data(params, schemas.POST_FEEDBACK_SCHEMA)
        phone = self.request.get('phone_number', None)
        message = params.get('message')
        email = params.get('email')
        if message is None or email is None:
            raise ApiResponse(12)
        pool = tools.get_pool_from_request(self.request)
        async with pool.acquire() as conn:
            async with conn.transaction():
                feedback_id = await conn.fetchval(CREATE_FEEDBACK_QUERY,
                                                  self.request.get("profile_id"),
                                                  message, email)
            if filenames is not None:
                for filename in filenames:
                    await conn.fetchval(CREATE_PHOTO_TO_FEEDBACK_QUERY, feedback_id, filename)
        receiver_email = MAIL_RECEIVER
        user = User.get()
        co1 = send_mail_async(
            email,
            [receiver_email],
            f'Обратная связь MILEONAIR {user.first_name} {user.last_name} (id={user.id})',
            f'Email: {email}\n'
            f'Тел: {phone}\n\n'
            f'Текст письма:\n'
            f'{message}',
            textType="plain", SSL=True, TLS=True, db_pool=pool, feedback_id=feedback_id, photo=filenames)

        asyncio.create_task(co1)
        raise ApiResponse(0)


@routes.view(ROUTE_FAQ)
class Faq(web.View):

    async def get(self):
        """

        @api {get} https://developer.mileonair.com/api/v1/faq  Часто задаваемые вопросы

        @apiDescription Список часто задаваемых вопросов и ответы на них  в соответствии с языковыми настройками
        @apiVersion 1.0.0
        @apiName get_faq
        @apiGroup Связь с пользователем


        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {list}   data.faq   Список вопросов и ответов
        @apiSuccess (200) {string}   data.faq.ord Значение сортировки
        @apiSuccess (200) {string}   data.faq.question Вопрос
        @apiSuccess (200) {string}   data.faq.answer Ответ
        @apiSuccess (200) {string}   data.faq.ico_path Путь к иконке



        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
            {
              "responseCode": 0,
              "responseMessage": "Запрос обработан успешно",
              "data": {
                "faq": [
                  {
                    "ord": 1,
                    "question": "где?",
                    "answer": "везде",
                    "ico_path": "https://developer.mileonair.com/resources/6.jpg",
                  },
                  {
                    "ord": 2,
                    "question": "когда?",
                    "answer": "всегда",
                    "ico_path": "https://developer.mileonair.com/resources/6.jpg",
                  },
                  {
                    "ord": 3,
                    "question": "для кого?",
                    "answer": "для всех",
                    "ico_path": "https://developer.mileonair.com/resources/6.jpg",
                  }
                ]
              }
            }



        """

        pool = tools.get_pool_from_request(self.request)
        language_id = await get_language_id(self.request)
        async with pool.acquire() as conn:
            data = await conn.fetch(GET_FAQ_QUERY, language_id)
        convert_data(data)
        data = {'faq': data}

        raise ApiResponse(0, data)


@routes.view(ROUTE_NOTIFICATIONS)
class Notifications(web.View):

    async def get(self):
        """

        @api {get} https://developer.mileonair.com/api/v1/notifications  Оповещения

        @apiDescription Список оповещений для данного профиля
        @apiVersion 1.0.0
        @apiName get_notifications
        @apiGroup Связь с пользователем


        @apiParam {int} [limit=20] Ограничение количества выводимых оповещений
        @apiParam {int} [offset=0] Отступ пагинации

        @apiExample Request-Example:
            https://developer.mileonair.com/api/v1/notifications?limit=5&offset=0

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {list}   data.notifications   Список оповещений
        @apiSuccess (200) {string}   data.notifications.message Текст оповещения
        @apiSuccess (200) {string}   data.notifications.created_date Время создания оповещения



        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
            {
              "responseCode": 0,
              "responseMessage": "Запрос обработан успешно",
              "data": {
                "notifications": [
                  {
                    "message": "а вот и третье",
                    "created_date": "2020-05-13 15:50:14"
                  },
                  {
                    "message": "вот ещё оповещение",
                    "created_date": "2020-05-13 15:47:55"
                  },
                  {
                    "message": "привет",
                    "created_date": "2020-05-13 15:47:25"
                  }
                ]
              }
            }



        """
        limit, offset = get_page(self.request)
        pool = tools.get_pool_from_request(self.request)
        async with pool.acquire() as conn:
            data = await conn.fetch(GET_NOTIFICATIONS_QUERY, self.request.get("profile_id"), limit, offset)

        convert_data(data, formatting_datetime=FORMAT_DATE_TIME)
        data = {'notifications': data}

        raise ApiResponse(0, data)


@routes.view(ROUTE_CITIES)
class Cities(web.View):
    async def get(self):
        """

        @api {get} https://developer.mileonair.com/api/v1/cities Города

        @apiName get_cities
        @apiGroup Справочники
        @apiVersion 1.0.0

        @apiParam {int} [limit=20] Ограничение количества выводимых значений
        @apiParam {int} [offset=0] Отступ пагинации

        @apiDescription Получить список городов.

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {list}   data.cities   Список городов
        @apiSuccess (200) {int}   data.cities.id ID города
        @apiSuccess (200) {float}   data.cities.latitude Координаты города: широта
        @apiSuccess (200) {float}   data.cities.longitude Координаты города: долгота

        @apiSuccess (200) {list}   data.translates   Список переводов
        @apiSuccess (200) {int}   data.translates.id ID перевода
        @apiSuccess (200) {int}   data.translates.cities_id ID города
        @apiSuccess (200) {string}   data.translates.title Название города
        @apiSuccess (200) {int}   data.translates.language_id ID языка





        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
            {
              "responseCode": 0,
              "responseMessage": "Запрос обработан успешно",
              "data": {
                "cities": [
                  {
                    "id": 1,
                    "latitude": 55.4160041809082,
                    "longitude": 37.89794921875
                  },
                  {
                    "id": 2,
                    "latitude": 55.4160041809082,
                    "longitude": 37.89794921875
                  }
                ],
                "translates": [
                  {
                    "id": 1,
                    "cities_id": 1,
                    "title": "Москва",
                    "language_id": 1
                  },
                  {
                    "id": 2,
                    "cities_id": 2,
                    "title": "Санкт-Петербург",
                    "language_id": 1
                  },
                  {
                    "id": 3,
                    "cities_id": 1,
                    "title": "Moscow",
                    "language_id": 2
                  },
                  {
                    "id": 4,
                    "cities_id": 2,
                    "title": "St. Petersburg",
                    "language_id": 2
                  },
                  {
                    "id": 5,
                    "cities_id": 1,
                    "title": "Mosca",
                    "language_id": 3
                  },
                  {
                    "id": 6,
                    "cities_id": 2,
                    "title": "San Pietroburgo",
                    "language_id": 3
                  }
                ]
              }
            }



        """
        logger.info(f'{inspect.stack()[0][3]} profile_id={self.request.get("profile_id")}')
        pool = tools.get_pool_from_request(self.request)
        limit, offset = get_page(self.request)
        async with pool.acquire() as conn:
            async with conn.transaction():
                cities = await conn.fetch(
                    f'SELECT id,  latitude, longitude FROM cities')
                convert_data(cities)
                cities_id_list = [dic['id'] for dic in cities]

                translates = await conn.fetch(
                    f'SELECT * FROM cities_translate '
                    f'WHERE city_id = ANY($1::int[]);', cities_id_list)
                convert_data(translates)
                data = {'cities': cities, 'translates': translates}
        raise ApiResponse(0, data)


@routes.view(ROUTE_QR)
class QRCode(web.View):
    async def post(self):
        """
        @api {post} https://developer.mileonair.com/api/v1/qr  QR код

        @apiDescription Зарегестрировать QR для начисления миль
        @apiVersion 1.0.0
        @apiName set_qr
        @apiGroup Прочее
        @apiParam {string} code QR код
        @apiParamExample {json} Request-Example:
            {
              "code": "пока тут может быть что угодно"
            }
        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
            {
              "responseCode": 0,
              "responseMessage": "Запрос обработан успешно"
            }
        """
        params = tools.get_data_from_request(self.request)
        validate_data(params, schemas.POST_QR_SCHEMA)
        pool = tools.get_pool_from_request(self.request)
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(POST_QR_QUERY, self.request.get("profile_id"))
        raise ApiResponse(21)


@routes.view(WALLET_CARD)
class WalletCard(ApiView):
    async def get(self):
        """
        @api {get} https://developer.mileonair.com/api/v1/walletCard Выпуск карты

    @apiName get_walletCard
    @apiGroup Wallet-карта
    @apiVersion 1.0.0

        @apiDescription Получить URL для скачивания электронной бонусной карты.
        @apiParam {string} [type]  Тип карты

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа


        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
            {
              "responseCode": 0,
              "responseMessage": "Запрос обработан успешно",
              "data": {
                "url": "https://developer.mileonair.com/"
              }
            }


        """
        moa_sid = tools.get_moa_sid_from_req(self.request)
        pool = tools.get_pool_from_request(self.request)
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    'select pqr, first_name, last_name, phone_number, os, os_version from profiles '
                    'inner join sessions on profiles.id = sessions.profile_id '
                    'inner join devices on sessions.device_id = devices.id where sid = $1', moa_sid)
                pqr = row.get('pqr')
                first_name = row.get('first_name')
                last_name = row.get('last_name')
                phone_number = row.get('phone_number')
                operating_system = row.get('os')
                os_version = row.get('os_version')

                async with aiohttp.ClientSession() as session:
                    request_body = {"pqr": pqr,
                                    'first_name': first_name,
                                    'last_name': last_name,
                                    'phone_number': phone_number,
                                    'os': operating_system,
                                    'os_version': os_version,
                                    'language_code': self.language_code
                                    }
                    card_type = self.request.query.get("type")
                    if card_type is not None:
                        request_body.update({"type": card_type})
                    resp = await session.post(f'https://{IS_DEV_PREFIX}cl.maocloud.ru/api/v1/walletCard',
                                              json=request_body)
                    try:
                        logger.debug(f'sending request to '
                                     f'https://{IS_DEV_PREFIX}cl.maocloud.ru/api/v1/walletCard Body json: {request_body} ')
                        response = await resp.json()
                        url = response['data']['url']
                    except Exception:
                        logger.debug(f'response from '
                                     f'https://{IS_DEV_PREFIX}cl.maocloud.ru/api/v1/walletCard: {response} ')
                        raise ApiResponse(30)
            raise ApiResponse(0, {'url': url})


# ----------------- партнёры ----------------------


@routes.view(ROUTE_PARTNER_CATEGORIES)
class PartnerCategories(web.View):

    async def get(self):
        """

        @api {get} https://developer.mileonair.com/api/v1/partnerCategories Категории партнёров

        @apiName get_partner_categories
        @apiGroup Справочники
        @apiVersion 1.0.0


        @apiDescription Получить список типов партнёров.

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {list}   data.partner_categories   Типов партнёров
        @apiSuccess (200) {int}   data.partner_categories.id ID типа партнёра
        @apiSuccess (200) {list}   data.translates   Список переводов
        @apiSuccess (200) {int}   data.translates.id ID перевода
        @apiSuccess (200) {int}   data.translates.partner_category_id ID типа партнёра
        @apiSuccess (200) {string}   data.translates.title Название
        @apiSuccess (200) {int}   data.translates.language_id ID языка

        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
            {
              "responseCode": 0,
              "responseMessage": "Запрос обработан успешно",
              "data": {
                "partner_categories": [
                  {
                    "id": 1
                  }
                ],
                "translates": [
                  {
                    "id": 1,
                    "partner_category_id": 1,
                    "name": "Кафе",
                    "language_id": 1
                  },
                  {
                    "id": 5,
                    "partner_category_id": 1,
                    "name": "A cafe",
                    "language_id": 2
                  },
                  {
                    "id": 9,
                    "partner_category_id": 1,
                    "name": "Caffè",
                    "language_id": 3
                  }
                ]
              }
            }
        """
        pool = tools.get_pool_from_request(self.request)
        async with pool.acquire() as conn:
            async with conn.transaction():
                data = await conn.fetch(PARTNER_CATEGORIES)
                data = convert_data(data)
                data = {'partner_categories': [], 'translates': data}
                id_set = set()
                i = 0
                while i < len(data.get('translates')):
                    id_set.add(data['translates'][i].get('partner_category_id'))
                    if data['translates'][i].get('id') is None:
                        del data['translates'][i]
                    else:
                        i += 1
                for category_id in id_set:
                    data['partner_categories'].append({'id': category_id})
        raise ApiResponse(0, data)


@routes.view(ROUTE_PARTNERS_AIRPORTS)
class PartnersInAirport(web.View):
    class InputGetData(BaseModel):
        airport_id: Optional[int]
        category_id: Optional[int]
        point_id: Optional[int]
        limit: int = 20
        offset: int = 0

        class Config:
            extra = 'ignore'

    async def get(self):
        """

        @api {get} https://developer.mileonair.com/api/v1/partnersInAirport Партнёры в аэропорту

        @apiName get_partners_in_airports
        @apiGroup Справочники
        @apiVersion 1.0.0
        @apiExample Request-Example:
            https://developer.mileonair.com/api/v1/partnersInAirport?airport_id=3&testing=true

        @apiParam {int} [limit=20] ограничение количества выводимых партнёров
        @apiParam {int} [offset=0] отступ пагинации
        @apiParam {int} [airport_id] id аэропорта
        @apiParam {int} [point_id] id точки
        @apiParam {int} [category_id] Фильтр по категориям партнёров

        @apiDescription Возвращает списох партнёров аэропорта. Если аэропорт разделен на терминалы -
        возвращает всех партнёров аэропорта вне зависимости от терминала. В случае если необходимо получить список
        партнеров конкретного терминала - необходимо передать id этого терминала в параметрах запроса (airport_id)

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {list} data  Словарь с данными
        @apiSuccess (200) {list} data.partners_in_airport  Список парнёров сгруппированых по категориям
        @apiSuccess (200) {int}   data.partners_in_airport.category_id ID категории
        @apiSuccess (200) {list}   data.partners_in_airport.partners Список партнёров в категории
        @apiSuccess (200) {int}   data.partners_in_airport.partners.id ID партнера
        @apiSuccess (200) {int}   data.partners_in_airport.partners.point_id ID точки продаж
        @apiSuccess (200) {string/null}   data.partners_in_airport.partners.name Название компании партнера
        @apiSuccess (200) {string/null}   data.partners_in_airport.partners.description_short Краткое описание партнера
        @apiSuccess (200) {string/null}   data.partners_in_airport.partners.description Подробное описание партнера
        @apiSuccess (200) {string/null}   data.partners_in_airport.partners.open_partner_schedule Режим работы - открытие
        @apiSuccess (200) {string/null}   data.partners_in_airport.partners.close_partner_schedule Режим работы - закрытие
        @apiSuccess (200) {string/null}   data.partners_in_airport.partners.address_short  Короткий адрес
        (в рамках аэропорта)
        @apiSuccess (200) {string/null}   data.partners_in_airport.partners.address  Полный адрес
        @apiSuccess (200) {float/null}   data.partners_in_airport.partners.cashback_part Значение кэшбэка, доля 0<=float<=1
        @apiSuccess (200) {string/null}   data.partners_in_airport.partners.logo_path Путь к иконке логотипа
        @apiSuccess (200) {string/null}   data.partners_in_airport.partners.photo_path Путь к фото партнера
        @apiSuccess (200) {bool}   data.partners_in_airport.partners.is_scannable На точке можно отсканировать qr
        @apiSuccess (200) {bool}   data.partners_in_airport.partners.is_scanning_pqr На точке продаж можно показать qr



        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
            {
                "responseCode": 0,
                "responseMessage": "Запрос обработан успешно",
                "data": {
                    "partners_in_airport": [
                        {
                            "category_id": 1,
                            "partners": [
                                {
                                    "id": 28,
                                    "point_id": 28,
                                    "name": "Кофикс",
                                    "description_short": "\"Кофикс\" - кофейня",
                                    "description": "\"Кофикс\"— международная сеть кофеен, завоевавшая популярность
                                    благодаря качественному кофе и вкусной еде по справедливой цене.
                                    Первая кофейня Cofix
                                    в России открылась в октябре 2016 года.",
                                    "open_partner_schedule": "09:00",
                                    "close_partner_schedule": "18:00",
                                    "address_short": "Терминал D, Этаж 3\r\nОбщая зона\r\n\r\nТерминал F,
                                    Этаж 2\r\nВылет межд. рейсы\r\n\r\nАэроэкспресс, Этаж 3\r\nОбщая зона",
                                    "address": "Шереметьевское шоссе, вл2с1\r\nХимки,
                                    Московская область,\r\nРоссия 141425",
                                    "cashback_part": 10.0,
                                    "logo_path": "https://developer.mileonair.com/resources/Partner/кофикс.png",
                                    "photo_path": "https://developer.mileonair.com/resources/Partner/кофикс.jpg",
                                    "photo_paths": ["https://developer.mileonair.com/resources/Partner/кофикс.jpg", ..]
                                    "is_scannable": True,
                                    "is_scanning_pqr": False
                                }
                            ]
                        }
                    ]
                }
            }



        """
        params = validate_data(self.request.query, self.InputGetData)
        language_code = self.request.get('locale', 'ru')

        brands = await tools_ext.get_brands(self.request, language_code, airport_id=params.airport_id,
                                            category_id=params.category_id, limit=params.limit, offset=params.offset,
                                            point_id=params.point_id)

        resource_url = await tools_ext.get_resource_server_url(self.request)
        try:
            for i, brand in enumerate(brands):
                brands[i]['photo_paths'] = [x['photo_paths'] for x in await tools_ext.get_photo_to_point(self.request,
                                                                                                         brand[
                                                                                                             'point_id'])]
                for j, item in enumerate(brands[i]['photo_paths']):

                    if item is not None:
                        if item.find('https') == 0:
                            pass
                        else:
                            if item != ' ':
                                brands[i]['photo_paths'][j] = str(resource_url + brands[i]['photo_paths'][j])

                brands[i]['photo_paths'] = list(filter(('').__ne__, brands[i]['photo_paths']))
                brands[i]['photo_paths'] = list(filter((None).__ne__, brands[i]['photo_paths']))
                if not brands[i]['photo_paths']:
                    brands[i]['photo_paths'] = None
                else:
                    brands[i]['photo_path'] = brands[i]['photo_paths'][0]
        except Exception as ex:
            logger.error(f'неудалось получить карусель картинок для партнера {ex}')

        data = group_data(brands, ['category_id'], 'partners')
        data.sort(key=lambda i: i.get('category_id'))
        for category in data:
            if category.get('partners') is not None:
                category['partners'].sort(key=lambda i: (i.get('id')))

        data = dict(partners_in_airport=data)

        raise ApiResponse(0, data)


@routes.view(ROUTE_PARTNERS_CITIES)
class PartnersInCity(web.View):

    async def get(self):
        """

        @api {get} https://developer.mileonair.com/api/v1/partnersInCity Партнёры в городе

        @apiName get_partners_in_city
        @apiGroup Справочники
        @apiVersion 1.0.0
        @apiExample Request-Example:
            https://developer.mileonair.com/api/v1/partnersInCity?city_id=3&testing=true

        @apiParam {int} city_id id города
        @apiParam {int} [category_id] Фильтр по категориям партнёров
        @apiParam {int} [limit=20] ограничение количества выводимых партнёров
        @apiParam {int} [offset=0] отступ пагинации
        @apiParam {bool} [testing] Показывать тестовые результаты

        @apiDescription Возвращает списох партнёров в городе.

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {list}   data.partners  Список партнёров
        @apiSuccess (200) {int}   data.partners.id ID партнера
        @apiSuccess (200) {string}   data.partners.name Название компании партнера
        @apiSuccess (200) {string}   data.partners.description_short Краткое описание партнера
        @apiSuccess (200) {string}   data.partners.description Подробное описание партнера
        @apiSuccess (200) {string}   data.partners.open_partner_schedule Режим работы - открытие
        @apiSuccess (200) {string}   data.partners.close_partner_schedule Режим работы - закрытие
        @apiSuccess (200) {string}   data.partners.address_short  Короткий адрес (в рамках аэропорта)
        @apiSuccess (200) {string}   data.partners.address  Полный адрес
        @apiSuccess (200) {string}   data.partners.logo_path Путь к иконке логотипа
        @apiSuccess (200) {string}   data.partners.photo_path Путь к фото партнера
        @apiSuccess (200) {float}   data.partners.cashback_part Значение кэшбэка, доля 0<=float<=1
        @apiSuccess (200) {int}   data.partners.category_id ID категории



        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
            {
              "responseCode": 0,
              "responseMessage": "Запрос обработан успешно",
              "data": {
                "partners": [
                  {
                    "id": 1,
                    "name": "партнёр 1",
                    "description_short": "краткое описание 1",
                    "description": "описание 1",
                    "open_partner_schedule": "11:00",
                    "close_partner_schedule": "01:00",
                    "address_short": "короткий адрес 1",
                    "address": "полный адрес 1",
                    "cashback_part": 0.10,
                    "logo_path": "https://developer.mileonair.com/resources/1.jpg",
                    "category_id": 1
                  }
                ]
              }
            }

        """
        language_code = self.request.get('locale')
        params = self.request.query
        validate(dict(params), schemas.GET_PARTNERS_IN_CITY_SCHEMA)
        limit = to_int(params.get('limit', '20'))
        offset = to_int(params.get('offset', '0'))
        city_id = to_int(params.get('city_id'))
        testing = get_bool_param(self.request, 'testing', required=False)
        category_id = to_int(params.get('category_id'))

        brands = await tools_ext.get_brands(self.request, language_code, testing=testing, category_id=category_id,
                                            city_id=city_id, limit=limit, offset=offset)
        data = convert_data(brands)
        # data = group_data(brands, ['category_id'], 'partners')
        data = dict(partners=data)
        raise ApiResponse(0, data)


@routes.view(ROUTE_PARTNERS_RELEVANT)
class PartnersRelevant(web.View):

    async def get(self):
        """

        @api {get} https://developer.mileonair.com/api/v1/partnersRelevant Значимые партнёры

        @apiName get_partners_relevant
        @apiGroup Справочники
        @apiVersion 1.0.0
        @apiExample Request-Example:
            https://developer.mileonair.com/api/v1/partnersRelevant

        @apiParam {int} [limit=20] ограничение количества выводимых партнёров
        @apiParam {int} [offset=0] отступ пагинации
        @apiParam {bool} [testing] Показывать тестовые результаты
        @apiParam {int} [category_id] Фильтр по категориям партнёров


        @apiDescription Возвращает списох значимых партнёров

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {list} data.partners_relevant  Список партнёров сгруппированных по категориям
        @apiSuccess (200) {int}   data.partners_relevant.category_id ID категории
        @apiSuccess (200) {list}   data.partners_relevant.partners Список партнёров в категории
        @apiSuccess (200) {int}   data.partners_relevant.partners.id ID партнера
        @apiSuccess (200) {string}   data.partners_relevant.partners.name Название компании партнера
        @apiSuccess (200) {string}   data.partners_relevant.partners.description_short Краткое описание партнера
        @apiSuccess (200) {string}   data.partners_relevant.partners.description Подробное описание партнера
        @apiSuccess (200) {string}   data.partners_relevant.partners.open_partner_schedule Режим работы - открытие
        @apiSuccess (200) {string}   data.partners_relevant.partners.close_partner_schedule Режим работы - закрытие
        @apiSuccess (200) {string}   data.partners_relevant.partners.address_short  Короткий адрес (в рамках аэропорта)
        @apiSuccess (200) {string}   data.partners_relevant.partners.address  Полный адрес
        @apiSuccess (200) {float}   data.partners_relevant.partners.cashback_part Значение кэшбэка, доля 0<=float<=1
        @apiSuccess (200) {string}   data.partners_relevant.partners.logo_path Путь к иконке логотипа
        @apiSuccess (200) {string}   data.partners_relevant.partners.photo_path Путь к фото партнера
        @apiSuccess (200) {int}   data.partners_relevant.partners.relevant_order Показатель значимости

        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
            {
              "responseCode": 0,
              "responseMessage": "Запрос обработан успешно",
              "data": {
                "partners_relevant": [
                  {
                    "category_id": 1,
                    "partners": [
                      {
                        "id": 23,
                        "name": "Му-Му",
                        "description_short": "«Му-му» — Фастфуд. Еда и напитки.",
                        "description": "«Му-му» — московская сеть ресторанов фастфуда, где большая часть блюд
                        приготовлена
                        по простым рецептам русской кухни и реализуется по невысоким ценам.",
                        "open_partner_schedule": "09:00",
                        "close_partner_schedule": "18:00",
                        "address_short": "Терминал B, Этаж 3\r\nОбщая зона\r\n\r\nТерминал D, Этаж 2\r\nОбщая зона",
                        "address": "Шереметьевское шоссе, вл2с1\r\nХимки, Московская область,\r\nРоссия 141425",
                        "cashback_part": 10.0,
                        "logo_path":
                        "https://developer.mileonair.com/resources/var/www/html/resources/Partner/Му-Му.png",
                        "photo_path":
                        "https://developer.mileonair.com/resources/var/www/html/resources/Partner/Му-Му.jpg",
                        "relevant_order": 2
                      }
                    ]
                  }
                ]
              }
            }



        """
        language_code = self.request.get('locale')
        params = self.request.query
        validate(dict(params), schemas.GET_PARTNERS_RELEVANT_SCHEMA)
        limit = to_int(params.get('limit', '20'))
        offset = to_int(params.get('offset', '0'))
        testing = get_bool_param(self.request, 'testing', required=False)
        category_id = to_int(params.get('category_id'))

        brands = await tools_ext.get_brands(self.request, language_code, testing=testing, category_id=category_id,
                                            limit=limit, offset=offset)
        data = group_data(brands, ['category_id'], 'partners')
        data = dict(partners_relevant=data)
        raise ApiResponse(0, data)


@routes.view(ROUTE_INFO)
class Info(web.View):
    async def get(self):
        """

        @api {get} https://developer.mileonair.com/api/v1/info Информация

        @apiDescription Получить информационные данные
        @apiName get_info
        @apiGroup Справочники
        @apiVersion 1.0.0

        @apiDescription Возвращает информационные данные в соответствии с языковыми настройками

        @apiParam {string} [name] Фильтрация выводимой информации по имени
        @apiParam {string} [language_code] Код языка

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {list}   data.info   Список информационных данных
        @apiSuccess (200) {int}   data.info.id ID
        @apiSuccess (200) {string}   data.info.name Название
        @apiSuccess (200) {string}   data.info.created_date Дата создания
        @apiSuccess (200) {string}   data.info.title Заголовок
        @apiSuccess (200) {string}   data.info.body Тело
        @apiSuccess (200) {int}   data.info.language_id ID языка



        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
            {
              "responseCode": 0,
              "responseMessage": "Запрос обработан успешно",
              "data": {
                "info": [
                  {
                    "id": 2,
                    "name": "aboutProduct",
                    "created_date": "2020-05-21 14:01:45",
                    "information_id": 2,
                    "title": "1 миля = 1 рубль по курсу MILEONAIR",
                    "body": "форматированный текст...",
                    "language_id": 1
                  },
                  {
                    "id": 3,
                    "name": "aboutCard",
                    "created_date": "2020-05-21 14:01:45",
                    "information_id": 3,
                    "title": "Карта MILEONAIR",
                    "body": "форматированный текст..",
                    "language_id": 1
                  },
                  {
                    "id": 1,
                    "name": "conditions",
                    "created_date": "2020-05-21 14:01:45",
                    "information_id": 1,
                    "title": "Условия участия",
                    "body": "<p><strong>форматированный текст</strong></p>",
                    "language_id": 1
                  }
                ]
              }
            }



        """
        name = self.request.query.get('name')
        code = self.request.query.get('language_code', self.request.get('locale'))

        pool = tools.get_pool_from_request(self.request)
        async with pool.acquire() as conn:
            async with conn.transaction():
                data = await conn.fetch(GET_INFORMATION_QUERY, code, name)
                if len(data) == 0:
                    raise ApiResponse(13)
                convert_data(data, formatting_datetime=FORMAT_DATE_TIME)
                data = {'info': data}
        raise ApiResponse(0, data)


@routes.post(ROUTE_GEO)
class Geo(web.View):

    async def post(self):
        """
        @api {post} https://developer.mileonair.com/api/v1/geo Сохранить геоточку

        @apiName post_geo
        @apiGroup Прочее
        @apiVersion 1.0.0

        @apiParam {string} token  Токен
        @apiParam {float} lat  Широта
        @apiParam {float} long  Долгота

        @apiParamExample {json} Request-Example:
            {
                "token": "60ccb0db-5ca8-4c04-97fb-13ae3ef3bce3",
                "lat": 10.999,
                "long": 999.99
            }

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа

        @apiSuccessExample {json} Success-Response:
            HTTP/1.1 200 OK
            {
              "responseCode": 0,
              "responseMessage": "Запрос обработан успешно"
            }
        """
        params = await tools.get_data_from_request(self.request)
        validate_data(params, schemas.POST_GEO_SCHEMA)
        pool = tools.get_pool_from_request(self.request)
        async with pool.acquire() as conn:
            async with conn.transaction():
                device_id = await conn.fetchval(GET_PROFILE_BY_DEVICE, params.get('token'))
                if device_id is None:
                    raise ApiResponse(13)

                await conn.execute(POST_GEO_QUERY, device_id, params.get("lat"), params.get("long"))
        asyncio.create_task(self.send_push(params))
        raise ApiResponse(0)

    async def send_push(self, params):
        json_body = {
            'guid': params.get('token'),
            'latitude': str(params.get("lat")),
            'longitude': str(params.get('long'))
        }
        headers = {'Authorization': f'Bearer {config.callback_service.token}'}
        url = f'{config.callback_service.url}pushes/geo'
        try:
            async with aiohttp.ClientSession() as session:
                await tools_ext.get_api_response_json(self.request, session, url, 'post', headers,
                                                      json=json_body)
            logger.info(f'запрос успешно доставлен на {url}, код ответа 0')
        except ApiResponse:
            pass


# ----------------- предложения ---------------------


@routes.view(ROUTE_PROMOTIONS)
class Promotions(ApiView):
    class PromotionInputParams(BaseModel):
        active: str

        @validator('active')
        def validate_active(cls, v):
            if v == '':
                raise ApiResponse(12)
            if v not in ('true', 'false'):
                raise ApiResponse(13)
            return v in ('true',)

    async def get(self):
        """
        @api {get} https://developer.mileonair.com/api/v1/promotions Промо акции

        @apiName get_promotions
        @apiGroup Справочники
        @apiVersion 1.0.0
        @apiExample Request-Example:
            https://developer.mileonair.com/api/v1/promotions?active=true

        @apiParam {bool="true", "false"} active Выбор между активными промо акциями и архивом акций.
        @apiParam {int} [limit=20] Ограничение количества выводимых значений
        @apiParam {int} [offset=0] Отступ пагинации

        @apiDescription Возвращает Промо акций

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {list}   data.promotions  Список акций
        @apiSuccess (200) {string}   data.promotions.title Название акции
        @apiSuccess (200) {string}   data.promotions.description_short Краткое описание акции
        @apiSuccess (200) {string}   data.promotions.description Подробное описание акции
        @apiSuccess (200) {string}   data.promotions.photo_path  Путь к фотографии
        @apiSuccess (200) {string}   data.promotions.start_date Дата начала акции
        @apiSuccess (200) {string}   data.promotions.end_date Дата окончания акции


        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
            {
              "responseCode": 0,
              "responseMessage": "Запрос обработан успешно",
              "data": {
                "promotions": [
                  {
                    "title": "заголовок",
                    "description_short": "Краткое описание",
                    "description": "Полное описание акции",
                    "photo_path": "https://developer.mileonair.com/resources/1.jpg",
                    "start_date": "2020-05-20 10:51:06",
                    "end_date": "2020-05-21 10:51:12"
                  }
                ]
              }
            }



        """
        self.get_page()
        limit, offset = self.page
        params = validate_apiview(self.params, self.PromotionInputParams)
        print(params)
        language_id = await get_language_id(self.request)

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                data = await conn.fetch(GET_PROMOTIONS_QUERY, params.active, language_id, limit, offset)
                convert_data(data, formatting_datetime=FORMAT_DATE_TIME)

        data = {'promotions': data}

        raise ApiResponse(0, data)


@routes.view(ROUTE_STOCKS)
class Stocks(web.View):
    async def _get_stocks(self, brand_id, url, airport_code=None, point_id=None):
        pool = tools.get_pool_from_request(self.request)
        active = get_bool_param(self.request, 'active', required=False, default=True)
        limit = int(self.request.query.get('limit', '1000'))
        offset = int(self.request.query.get('offset', '0'))
        language_code = self.request.get('locale')
        headers = {
            'Authorization': f'Bearer {config.pss_service.token}'
        }
        params = dict(language_code=language_code, limit=limit, offset=offset,
                      active=str(active))
        async with pool.acquire() as conn:
            async with conn.transaction():

                if airport_code is not None:
                    params.update(dict(airport_code=airport_code))
                if point_id is not None:
                    params.update(dict(point_id=point_id))
                if brand_id is not None:
                    brand_tag = await conn.fetchval(GET_BRAND_TAG, brand_id)
                    if brand_tag is None:
                        raise ApiResponse(13)
                    params.update(dict(brand_tag=brand_tag))

        try:
            async with aiohttp.ClientSession() as session:
                response = await session.get(url, headers=headers, params=params, timeout=2)
                response_data = await response.json()
        except CancelledError:
            raise
        except Exception as ex:
            raise ApiResponse(31, exc=ex,
                              log_message=f"не удалось выполнить запрос к партнёрскму сервису: {url} : {ex}")
        try:
            if response_data.get('responseCode') != 0:
                logger.error(f"Ответ партнёрского сервиса не 0 партнёрскму сервису: {url}, "
                             f"params = {params}, responseCode ={response_data.get('responseCode')}")
                raise ApiResponse(30)
            stocks = response_data['data'].get('stocks')
            for stock in stocks:
                stock['ord'] = 1
                # stock.pop('points')
                rename_field(stock, ('stock_id', 'id'))
                rename_field(stock['cart'], ('cart_id', 'id'))
                rename_field(stock['cart'], ('cart_amount', 'amount'))
        except CancelledError:
            raise
        except Exception as ex:
            raise ApiResponse(30, exc=ex, log_message=f"не удалось прочитать ответ партнёрского сервиса: {url} : {ex}")

        data = {"stocks": stocks}
        raise ApiResponse(0, data)

    async def get(self):
        """

        @api {get} https://developer.mileonair.com/api/v1/stocks Список предложений

        @apiName get_stocks
        @apiGroup Предложения
        @apiVersion 1.0.0
        @apiExample Request-Example:
            https://developer.mileonair.com/api/v1/stocks?active=true

        @apiParam {bool="true", "false"} active Выбор между активными предложениями и архивом.
        @apiParam {int} [limit=20] Ограничение количества выводимых значений
        @apiParam {int} [offset=0] Отступ пагинации
        @apiParam {int} airport_id ID аэропорта
        @apiParam {int} [partner_id] ID партнёра


        @apiDescription Возвращает список предложений

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {list}   data.stocks  Список предложений
        @apiSuccess (200) {int}   data.stocks.id ID предложения
        @apiSuccess (200) {int}   data.stocks.ord порядковый номер предложения
        @apiSuccess (200) {string}   data.stocks.title Название предложения
        @apiSuccess (200) {string}   data.stocks.title_short Краткое название предложения
        @apiSuccess (200) {string}   data.stocks.note Примечание/Заметкаия
        @apiSuccess (200) {string}   data.stocks.purchase_terms Условия покупки
        @apiSuccess (200) {string}   data.stocks.photo_path  Путь к фотографии
        @apiSuccess (200) {string}   data.stocks.start_date Дата начала предложения
        @apiSuccess (200) {string}   data.stocks.end_date Дата окончания предложения
        @apiSuccess (200) {dict}   data.stocks.cart Информация о корзине
        @apiSuccess (200) {int}   data.stocks.cart.id ID корзины
        @apiSuccess (200) {string}   data.stocks.cart.taxation Налогообложение
        @apiSuccess (200) {int}   data.stocks.cart.amount Стоимость при онлайн покупке
        @apiSuccess (200) {int}   data.stocks.cart.amount_offline Стоимость при оффлайн покупке
        @apiSuccess (200) {list}   data.stocks.cart.products  Список товаров/услуг входящих в акцию
        @apiSuccess (200) {string}   data.stocks.cart.products.name Название товара
        @apiSuccess (200) {int}   data.stocks.cart.products.quantity Количество товара
        @apiSuccess (200) {int}   data.stocks.cart.products.price Стоимость за одну еденицу товара
        @apiSuccess (200) {int}   data.stocks.cart.products.amount Общая стоимость
        @apiSuccess (200) {string}   data.stocks.cart.products.tax Налог
        @apiSuccess (200) {string}   data.stocks.cart.products.payment_object Признак предмета расчета
        @apiSuccess (200) {string}   data.stocks.cart.products.payment_method Признак способа расчета


        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
            {
                "responseCode": 0,
                "responseMessage": "Запрос обработан успешно",
                "data": {
                    "stocks": [
                        {
                            "id": 1,
                            "ord": 1,
                            "title": "stock title",
                            "title_short": "краткое название"
                            "note": "Заметка/Примечание",
                            "purchase_terms": "Условия покупки",
                            "photo_path": "https://developer.mileonair.com/resources/qwe.jpg",
                            "start_date": "2020-07-05 00:14:53",
                            "end_date": "1970-01-01 00:00:00",
                            "cart": {
                                "id": 4,
                                "taxation": "osn",
                                "amount": 500,
                                "amount_offline": 1000,
                                "products": [
                                    {
                                        "name": "Услуга упаковки",
                                        "quantity": 1,
                                        "price": 100,
                                        "amount": 100,
                                        "tax": "vat20",
                                        "payment_object": "service",
                                        "payment_method": "full_prepayment"
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        """
        validate(dict(self.request.query), schemas.GET_STOCKS_SCHEMA)
        brand_id = to_int(self.request.query.get('partner_id'))
        airport_id = to_int(self.request.query.get('airport_id'))
        pool = tools.get_pool_from_request(self.request)
        url = config.pss_service.url + 'seller/stocks'

        async with pool.acquire() as conn:
            async with conn.transaction():
                airport_code = await conn.fetchval(GET_AIRPORT_CODE, airport_id)
        await self._get_stocks(brand_id, url, airport_code)


@routes.view(ROUTE_STOCK)
class Stock(web.View):

    async def get(self):
        """
        @api {get} https://developer.mileonair.com/api/v1/stock Информация о предложении

        @apiName get_stock
        @apiGroup Предложения
        @apiVersion 1.0.0
        @apiExample Request-Example:
            https://developer.mileonair.com/api/v1/stock?active=true&id=3

        @apiParam {bool="true", "false"} [active] Выбор между активными предложениями и архивом.
        @apiParam {int} stock_id ID предложения
        @apiParam {int} airport_id ID Аэропорта


        @apiDescription Возвращает информацию о предложении

        @apiSuccess (200) {int}         responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string}      responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict}        data  Словарь с данными
        @apiSuccess (200) {dict}        data.stock  Предлжение
        @apiSuccess (200) {int}         data.stock.id ID предложения
        @apiSuccess (200) {string}      data.stock.title Название предложения
        @apiSuccess (200) {string}      data.stock.title_short Краткое название предложения
        @apiSuccess (200) {string}      data.stock.note Примечание/Заметкаия
        @apiSuccess (200) {string}      data.stock.purchase_terms Условия покупки
        @apiSuccess (200) {string}      data.stock.photo_path  Путь к фотографии
        @apiSuccess (200) {string}      data.stock.start_date Дата начала предложения
        @apiSuccess (200) {string}      data.stock.end_date Дата окончания предложения
        @apiSuccess (200) {dict}        data.stock.cart Информация о корзине
        @apiSuccess (200) {int}         data.stock.cart.id ID корзины
        @apiSuccess (200) {string}      data.stock.cart.taxation Налогообложение
        @apiSuccess (200) {int}         data.stock.cart.amount Стоимость при онлайн покупке
        @apiSuccess (200) {int}         data.stock.cart.amount_offline Стоимость при оффлайн покупке
        @apiSuccess (200) {list}        data.stock.cart.products  Список товаров/услуг входящих в акцию
        @apiSuccess (200) {string}      data.stock.cart.products.name Название товара
        @apiSuccess (200) {int}         data.stock.cart.products.quantity Количество товара
        @apiSuccess (200) {int}         data.stock.cart.products.price Стоимость за одну еденицу товара
        @apiSuccess (200) {int}         data.stock.cart.products.amount Общая стоимость
        @apiSuccess (200) {string}      data.stock.cart.products.tax Налог
        @apiSuccess (200) {string}      data.stock.cart.products.payment_object Признак предмета расчета
        @apiSuccess (200) {string}      data.stock.cart.products.payment_method Признак способа расчета
        @apiSuccess (200) {dict}        data.partner  Список товаров/услуг входящих в акцию
        @apiSuccess (200) {string}      data.partner.name Название партнёра
        @apiSuccess (200) {string}      data.partner.address_short Короткий адрес
        @apiSuccess (200) {string}      data.partner.logo_path Путь к иконке
        @apiSuccess (200) {string}      data.partner.open_partner_schedule Окрытие
        @apiSuccess (200) {string}      data.partner.close_partner_schedule Закрытие


        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
            {
                "responseCode": 0,
                "responseMessage": "Запрос обработан успешно",
                "data": {
                    "stock": {
                        "title": "Дезинфекция багажа + Стандартная упаковка",
                        "title_short": "Упаковка+Дезинфекция",
                        "note": null,
                        "purchase_terms": null,
                        "photo_path": "https://developer.mileonair.com/resources/Stock/7_photo_path.png",
                        "start_date": null,
                        "end_date": null,
                        "cart": {
                            "id": 6,
                            "taxation": "osn",
                            "amount": 20100,
                            "amount_offline": 95000,
                            "products": [
                                {
                                    "name": "Услуга обработки багажа",
                                    "quantity": 1,
                                    "price": 20000,
                                    "tax": "vat20",
                                    "payment_object": "service",
                                    "payment_method": "full_prepayment",
                                    "amount": 20000
                                }
                            ]
                        },
                        "id": 7
                    },
                    "partner": {
                        "address_short": "Терминалы B, C, D, E и F",
                        "logo_path": "https://developer.mileonair.com/resources/Partner/logo.png",
                        "open_partner_schedule": "06:00",
                        "close_partner_schedule": "23:00",
                        "id": 56,
                        "name": "Pack&Fly"
                    }
                }
            }

        """
        validate(dict(self.request.query), schemas.GET_STOCK_SCHEMA)
        stock_id = to_int(self.request.query.get('stock_id'))
        airport_id = to_int(self.request.query.get('airport_id'))
        language_code = self.request.get('locale')

        data = await tools_ext.get_st(self.request, stock_id, language_code, airport_id)

        raise ApiResponse(0, data)


@routes.view(ROUTE_ONPASS_STOCKS)
class OnpassStocks(Stocks):
    async def get(self):
        """
        @api {get} https://developer.mileonair.com/api/v1/onpass/stocks Список предложений onpass

        @apiName get_onpass_stocks
        @apiGroup Onpass
        @apiVersion 1.0.0
        @apiExample Request-Example:
            https://developer.mileonair.com/api/v1/onpass/stocks?airport_code=SVO

        @apiParam {int} [airport_id] ID Аэропорта
        @apiParam {int} [point_id] ID точки продаж
        @apiParam {bool="true", "false"} [active] Выбор между активными предложениями и архивом.
        @apiParam {int} [limit] Ограничение количества выводимых значений
        @apiParam {int} [offset=0] Отступ пагинации


        @apiDescription Возвращает список предложений

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {list}   data.stocks  Список предложений
        @apiSuccess (200) {int}   data.stocks.id ID предложения
        @apiSuccess (200) {int}   data.stocks.ord порядковый номер предложения
        @apiSuccess (200) {string}   data.stocks.title Название предложения
        @apiSuccess (200) {string}   data.stocks.title_short Краткое название предложения
        @apiSuccess (200) {string}   data.stocks.note Примечание/Заметкаия
        @apiSuccess (200) {string}   data.stocks.purchase_terms Условия покупки
        @apiSuccess (200) {string}   data.stocks.photo_path  Путь к фотографии
        @apiSuccess (200) {string}   data.stocks.start_date Дата начала предложения
        @apiSuccess (200) {string}   data.stocks.end_date Дата окончания предложения
        @apiSuccess (200) {dict}   data.stocks.cart Информация о корзине
        @apiSuccess (200) {int}   data.stocks.cart.id ID корзины
        @apiSuccess (200) {string}   data.stocks.cart.taxation Налогообложение
        @apiSuccess (200) {int}   data.stocks.cart.amount Стоимость при онлайн покупке
        @apiSuccess (200) {int}   data.stocks.cart.amount_offline Стоимость при оффлайн покупке
        @apiSuccess (200) {list}   data.stocks.cart.products  Список товаров/услуг входящих в акцию
        @apiSuccess (200) {string}   data.stocks.cart.products.name Название товара
        @apiSuccess (200) {int}   data.stocks.cart.products.quantity Количество товара
        @apiSuccess (200) {int}   data.stocks.cart.products.price Стоимость за одну еденицу товара
        @apiSuccess (200) {int}   data.stocks.cart.products.amount Общая стоимость
        @apiSuccess (200) {string}   data.stocks.cart.products.tax Налог
        @apiSuccess (200) {string}   data.stocks.cart.products.payment_object Признак предмета расчета
        @apiSuccess (200) {string}   data.stocks.cart.products.payment_method Признак способа расчета


        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
            {
                "responseCode": 0,
                "responseMessage": "Запрос обработан успешно",
                "data": {
                    "stocks": [
                        {
                            "purchase_terms": "",
                            "title_short": "визит BUSINESS",
                            "note": "",
                            "start_date": "2020-11-25 20:42:24",
                            "end_date": "2020-12-15 20:42:29",
                            "title": "1 визит BUSINESS",
                            "photo_path": "",
                            "cart": {
                                "taxation": "osn",
                                "id": 9,
                                "amount": 249000,
                                "amount_offline": 249000,
                                "products": [
                                    {
                                        "product_id": 19,
                                        "quantity": 1,
                                        "payment_method": "full_prepayment",
                                        "product_amount": 249000,
                                        "tax": "vat20",
                                        "payment_object": "service",
                                        "name": "Проход BUSINESS",
                                        "price": 249000
                                    }
                                ]
                            },
                            "brand_tag": "onpass",
                            "ord": 1,
                            "id": 12
                        }
                    ]
                }
            }
        """
        pool = tools.get_pool_from_request(self.request)
        validate(dict(self.request.query), schemas.GET_ONPASS_STOCKS_SCHEMA)
        airport_id = to_int(self.request.query.get('airport_id'))
        point_id = to_int(self.request.query.get('point_id'))
        url = config.pss_service.url + 'seller/stocks'
        brand_id = ONPASS_BRAND_ID
        if airport_id is not None:
            async with pool.acquire() as conn:
                airport_code = await conn.fetchval(GET_AIRPORT_CODE, airport_id)
        else:
            airport_code = None
        await self._get_stocks(brand_id, url, airport_code=airport_code, point_id=point_id)


@routes.view(ROUTE_CUSTOM_STOCKS)
class CustomStocks(ApiView):
    class CustomStocksInputParams(BaseModel):
        active: str
        airport_id: int
        partner_id: Optional[int] = None

        @validator('active')
        def validate_active(cls, v):
            if v == '':
                raise ApiResponse(12)
            if v not in ('true', 'false'):
                raise ApiResponse(13)
            return v in ('true',)

    async def get(self):
        """

            @api {get} https://developer.mileonair.com/api/v1/customStocks Список персональных предложений

            @apiName get_custom_stocks
            @apiGroup Предложения
            @apiVersion 1.0.0
            @apiExample Request-Example:
                https://developer.mileonair.com/api/v1/customStocks?active=true&airport_id=1&partner_id=56

            @apiParam {bool="true", "false"} active Выбор между активными предложениями и архивом.
            @apiParam {int} [limit=20] Ограничение количества выводимых значений
            @apiParam {int} [offset=0] Отступ пагинации
            @apiParam {int} airport_id ID аэропорта
            @apiParam {int} [partner_id] ID партнёра

            @apiDescription Возвращает список персональных предложений

            @apiSuccess (200) {int}         responseCode Код ошибки (0 - нет ошибки)
            @apiSuccess (200) {string}      responseMessage  Описание ошибки, ответа
            @apiSuccess (200) {dict}        data  Словарь с данными
            @apiSuccess (200) {dict}        data.custom_stock  Персональное предложение
            @apiSuccess (200) {list}        data.custom_stocks  Персональное предложение
            @apiSuccess (200) {int}         data.custom_stocks.custom_stock.id ID предложения
            @apiSuccess (200) {string}      data.custom_stocks.custom_stock.title Название предложения
            @apiSuccess (200) {string}      data.custom_stocks.custom_stock.title_short Краткое название предложения
            @apiSuccess (200) {string}      data.custom_stocks.custom_stock.note Примечание/Заметка
            @apiSuccess (200) {string}      data.custom_stocks.custom_stock.purchase_terms Условия покупки
            @apiSuccess (200) {string}      data.custom_stocks.custom_stock.photo_path  Путь к фотографии
            @apiSuccess (200) {string}      data.custom_stocks.custom_stock.start_date Дата начала предложения
            @apiSuccess (200) {string}      data.custom_stocks.custom_stock.end_date Дата окончания предложения
            @apiSuccess (200) {dict}        data.custom_stocks.custom_stock.cart Информация о корзине
            @apiSuccess (200) {int}         data.custom_stocks.custom_stock.cart.id ID корзины
            @apiSuccess (200) {string}      data.custom_stocks.custom_stock.cart.taxation Налогообложение
            @apiSuccess (200) {int}         data.custom_stocks.custom_stock.cart.amount Стоимость при онлайн покупке
            @apiSuccess (200) {int}         data.custom_stocks.custom_stock.cart.amount_offline Стоимость при оффлайн
            покупке
            @apiSuccess (200) {list}        data.custom_stocks.custom_stock.cart.products  Список товаров/услуг входящих
            в акцию
            @apiSuccess (200) {string}      data.custom_stocks.custom_stock.cart.products.name Название товара
            @apiSuccess (200) {int}         data.custom_stocks.custom_stock.cart.products.quantity Количество товара
            @apiSuccess (200) {int}         data.custom_stocks.custom_stock.cart.products.price
            Стоимость за одну еденицу
            товара
            @apiSuccess (200) {int}         data.custom_stocks.custom_stock.cart.products.amount Общая стоимость
            @apiSuccess (200) {string}      data.custom_stocks.custom_stock.cart.products.tax Налог
            @apiSuccess (200) {string}      data.custom_stocks.custom_stock.cart.products.payment_object
            Признак предмета
            расчета
            @apiSuccess (200) {string}      data.custom_stocks.custom_stock.cart.products.payment_method Признак способа
            расчета

            @apiSuccess (200) {dict}        data.custom_stocks.partner  Партнёр
            @apiSuccess (200) {string}      data.custom_stocks.partner.name Название партнёра
            @apiSuccess (200) {string}      data.custom_stocks.partner.address_short Короткий адрес
            @apiSuccess (200) {string}      data.custom_stocks.partner.logo_path Путь к иконке
            @apiSuccess (200) {string}      data.custom_stocks.partner.open_partner_schedule Окрытие
            @apiSuccess (200) {string}      data.custom_stocks.partner.close_partner_schedule Закрытие
            @apiSuccess (200) {string}      data.custom_stocks.partner.cashback_part Доля кэшбэка
            @apiSuccess (200) {string}      data.custom_stocks.partner.description_short Краткое описание
            @apiSuccess (200) {string}      data.custom_stocks.partner.description Описание

            @apiSuccess (200) {int}         data.custom_stocks.airport_id ID аэропорта

            @apiSuccessExample Success-Response:
                HTTP/1.1 200 OK
                {
                  "responseCode": 0,
                  "responseMessage": "Запрос обработан успешно",
                  "data": {
                    "custom_stocks": [
                      {
                        "airport_id": 1,
                        "custom_stock": {
                          "note": "",
                          "title": "Дезинфекция + Упаковка + Защита по цене Упаковки",
                          "end_date": null,
                          "title_short": "Набор услуг",
                          "start_date": null,
                          "photo_path": "https://developer.mileonair.com/resources/CustomStock/photo_Cp7Tibl.jpg",
                          "purchase_terms": "",
                          "id": 2,
                          "cart": {
                            "id": 1,
                            "amount_offline": 105000,
                            "amount": 100000,
                            "taxation": "osn",
                            "products": [
                              {
                                "payment_object": "service",
                                "product_amount": 10000,
                                "payment_method": "full_prepayment",
                                "quantity": 1,
                                "name": "Услуга Защита ПэкЭндФлай",
                                "tax": "vat20",
                                "price": 10000
                              }
                            ]
                          }
                        },
                        "partner": {
                          "address_short": "Терминалы B, C, D, E и F",
                          "logo_path": "https://developer.mileonair.com/resources/Partner/logo.png",
                          "photo_path": "https://developer.mileonair.com/resources/Partner/logo.png",
                          "cashback_part": 0.10000000149011612,
                          "open_partner_schedule": "06:00",
                          "close_partner_schedule": "23:00",
                          "partner_id": 56,
                          "description_short": "Оказание услуг пассажирам по упаковке, хранению, защите багажа и
                          реализации
                          дорожных аксессуаров.",
                          "description": "Группа компаний основана в 2011 году и является признанным лидером на рынке
                          Российской Федерации по оказанию услуг пассажирам по упаковке, хранению,
                          защите багажа и реализации дорожных аксессуаров.\r\n\r\n
                          В 2015 году Группа компаний начала активную экспансию на рынок Европы и Азии.
                          Наша компания осуществляет свою деятельность уже в 6 странах Мира: Россия, Литва,
                          Латвия, Киргизия, Эстония, Таиланд, в более, чем 24 аэропортах.\r\n\r\nНаша цель:\r\nМы
                          создаем услугу, которой приятно воспользоваться нам самим.\r\n\r\nНаша миссия:\r\nСоздание
                          комфортных условий для пассажиров во время путешествий, обеспечивая сохранность дорожных
                          сумок, чемоданов и их содержимого.\r\n\r\nКомпания  осуществляет следующие услуги:\r\n1.
                          Упаковка багажа \r\n2. Продажа защиты \r\n3. Хранение багажа (камера хранения)\r\n4. Продажа
                          дорожных аксессуаров",
                          "partner_name": "PACK&FLY"
                        }
                      }
                    ]
                  }
                }


            """
        pool = self.pool
        self.get_page()
        logger.info(f'{inspect.stack()[0][3]} profile_id={self.request.get("profile_id")}')
        params = validate_apiview(self.params, self.CustomStocksInputParams)
        limit, offset = self.page
        if limit <= 0 or offset < 0 or params.airport_id < 1:
            raise ApiResponse(13)
        language_id = await get_language_id(self.request)
        custom_stocks = list()
        async with pool.acquire() as conn:
            async with conn.transaction():
                stocks_list = await conn.fetchval(GET_CUSTOM_STOCKS_QUERY, params.airport_id,
                                                  params.partner_id, params.active, self.profile_id,
                                                  limit, offset)
                if stocks_list is None:
                    raise ApiResponse(0, data={'custom_stocks': []})
                async for custom_stock in tools_ext.stock_gen(stocks_list, conn, language_id, params.active):
                    custom_stocks.append(custom_stock)

        data = {"custom_stocks": custom_stocks}

        raise ApiResponse(0, data)


@routes.view(ROUTE_CUSTOM_STOCK)
class CustomStock(ApiView):
    class CustomStockInputParams(BaseModel):
        id: int
        active: str

        @validator('active')
        def validate_active(cls, v):
            if v == '':
                raise ApiResponse(12)
            if v not in ('true', 'false'):
                raise ApiResponse(13)
            return v in ('true',)

    async def get(self):
        """
            @api {get} https://developer.mileonair.com/api/v1/customStock Информация о персональном предложении

            @apiName get_custom_stock
            @apiDescription Возвращает информацию о персональном предложении
            @apiGroup Предложения
            @apiVersion 1.0.0
            @apiExample Request-Example:
                https://developer.mileonair.com/api/v1/customStock?active=true&id=3

            @apiParam {bool="true", "false"} active Выбор между активными предложениями и архивом.
            @apiParam {int} id ID предложения

            @apiSuccess (200) {int}         responseCode Код ошибки (0 - нет ошибки)
            @apiSuccess (200) {string}      responseMessage  Описание ошибки, ответа
            @apiSuccess (200) {dict}        data  Словарь с данными
            @apiSuccess (200) {dict}        data.custom_stock  Персональное предложение
            @apiSuccess (200) {int}         data.custom_stock.id ID предложения
            @apiSuccess (200) {string}      data.custom_stock.title Название предложения
            @apiSuccess (200) {string}      data.custom_stock.title_short Краткое название предложения
            @apiSuccess (200) {string}      data.custom_stock.note Примечание/Заметка
            @apiSuccess (200) {string}      data.custom_stock.purchase_terms Условия покупки
            @apiSuccess (200) {string}      data.custom_stock.photo_path  Путь к фотографии
            @apiSuccess (200) {string}      data.custom_stock.start_date Дата начала предложения
            @apiSuccess (200) {string}      data.custom_stock.end_date Дата окончания предложения
            @apiSuccess (200) {dict}        data.custom_stock.cart Информация о корзине
            @apiSuccess (200) {int}         data.custom_stock.cart.id ID корзины
            @apiSuccess (200) {string}      data.custom_stock.cart.taxation Налогообложение
            @apiSuccess (200) {int}         data.custom_stock.cart.amount Стоимость при онлайн покупке
            @apiSuccess (200) {int}         data.custom_stock.cart.amount_offline Стоимость при оффлайн покупке
            @apiSuccess (200) {list}        data.custom_stock.cart.products  Список товаров/услуг входящих в акцию
            @apiSuccess (200) {string}      data.custom_stock.cart.products.name Название товара
            @apiSuccess (200) {int}         data.custom_stock.cart.products.quantity Количество товара
            @apiSuccess (200) {int}         data.custom_stock.cart.products.price Стоимость за одну еденицу товара
            @apiSuccess (200) {int}         data.custom_stock.cart.products.amount Общая стоимость
            @apiSuccess (200) {string}      data.custom_stock.cart.products.tax Налог
            @apiSuccess (200) {string}      data.custom_stock.cart.products.payment_object Признак предмета расчета
            @apiSuccess (200) {string}      data.custom_stock.cart.products.payment_method Признак способа расчета

            @apiSuccess (200) {dict}        data.partner  Партнёр
            @apiSuccess (200) {string}      data.partner.name Название партнёра
            @apiSuccess (200) {string}      data.partner.address_short Короткий адрес
            @apiSuccess (200) {string}      data.partner.logo_path Путь к иконке
            @apiSuccess (200) {string}      data.partner.open_partner_schedule Окрытие
            @apiSuccess (200) {string}      data.partner.close_partner_schedule Закрытие
            @apiSuccess (200) {int}         data.airport_id ID аэропорта

            @apiSuccessExample Success-Response:
                HTTP/1.1 200 OK
                {
                    "responseCode": 0,
                    "responseMessage": "Запрос обработан успешно",
                    "data": {
                        "custom_stock": {
                            "title": "Дезинфекция+Упаковка+Защита по цене Упаковки",
                            "title_short": "Набор услуг",
                            "note": "",
                            "purchase_terms": null,
                            "photo_path": "https://developer.mileonair.com/resources/CustomStock/photo_Cp7Tibl.jpg",
                            "start_date": null,
                            "end_date": null,
                            "cart": {
                                "id": 1,
                                "taxation": "osn",
                                "amount": 70000,
                                "amount_offline": 125000,
                                "products": [
                                    {
                                        "name": "Услуга обработки багажа",
                                        "quantity": 1,
                                        "price": 10000,
                                        "tax": "vat20",
                                        "payment_object": "service",
                                        "payment_method": "full_prepayment",
                                        "amount": 10000
                                    }
                                ]
                            },
                            "id": 2
                        },
                        "partner": {
                            "address_short": "Терминалы B, C, D, E и F",
                            "logo_path": "https://developer.mileonair.com/resources/Partner/logo.png",
                            "open_partner_schedule": "06:00",
                            "close_partner_schedule": "23:00",
                            "id": 56,
                            "name": "Pack&Fly"
                        },
                        "airport_id": 1
                    }
                }

            """
        pool = self.pool
        language_id = await get_language_id(self.request)
        params = validate_apiview(self.params, self.CustomStockInputParams)

        async with pool.acquire() as conn:
            async with conn.transaction():
                if not await conn.fetchval(CHECK_CUSTOM_STOCK_OWNER_QUERY, params.id, self.profile_id):
                    raise ApiResponse(13)
                async for custom_stock in tools_ext.stock_gen([params.id], conn, language_id, params.active):
                    data = {"custom_stock": custom_stock}
        raise ApiResponse(0, data)


# -------------------------------- Orders -----------------------------

@routes.view(ROUTE_ORDERS)  # todo добавить информацию о точке продаж
class OrdersView(web.View):

    async def get(self):
        """

        @api {get} https://developer.mileonair.com/api/v1/orders Список заказов

        @apiName get_orders
        @apiGroup Прочее
        @apiVersion 1.0.0
        @apiExample Request-Example:
            https://developer.mileonair.com/api/v1/orders?active=true

        @apiParam {bool="true", "false"} active Выбор между активными заказами и архивом.
        @apiParam {int} [limit=20] Ограничение количества выводимых значений
        @apiParam {int} [offset=0] Отступ пагинации


        @apiDescription Возвращает список заказов

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {list}   data.orders  Список заказов
        @apiSuccess (200) {bool}   data.orders.custom Указатель является ли заказ персональным
        @apiSuccess (200) {string}   data.orders.qr QR код
        @apiSuccess (200) {string}   data.orders.order_id id заказа
        @apiSuccess (200) {string}   data.orders.estimated_date Дата завершения действия покупки
        @apiSuccess (200) {string}   data.orders.used_date Дата использования
        @apiSuccess (200) {int}   data.orders.sum Стоимость (в копейках)
        @apiSuccess (200) {dict}   data.orders.stock  Предложение
        @apiSuccess (200) {string}   data.orders.stocks.purchase_terms Условия покупки
        @apiSuccess (200) {string}   data.orders.stocks.title Название
        @apiSuccess (200) {string}   data.orders.stocks.photo_path Путь к фотографии
        @apiSuccess (200) {dict}   data.orders.stocks.partner Партнёр
        @apiSuccess (200) {string}   data.orders.stocks.partner.name Имя партнёра
        @apiSuccess (200) {string}   data.orders.stocks.partner.address_short Короткий адрес
        @apiSuccess (200) {string}   data.orders.stocks.partner.logo_path Путь к иконке
        @apiSuccess (200) {string}   data.orders.stocks.partner.open_partner_schedule Время открытия
        @apiSuccess (200) {string}   data.orders.stocks.partner.close_partner_schedule Время закрытия


        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
            {
                "responseCode": 0,
                "responseMessage": "Запрос обработан успешно",
                "data": {
                    "orders": [
                        {
                            "custom": false,
                            "qr": "a7acd525e012ee4d5d365829921deb09d2176127b113f7af7cbe83b16174904a6e",
                            "order_id": "109eb19286306156d1a9",
                            "estimated_date": "2020-08-20",
                            "used_date": "2020-08-20",
                            "sum": 90000,
                            "stock": {
                                "title": "Стандартная упаковка + защита pack&fly",
                                "purchase_terms": "Условия покупки",
                                "photo_path": "https://developer.mileonair.com/resources/Stock/photo.jpg",
                                "partner": {
                                    "name": "Pack&Fly",
                                    "address_short": "Терминал F, второй этаж",
                                    "logo_path": "https://developer.mileonair.com/resources/Partner/logo.png",
                                    "open_partner_schedule": "06:00",
                                    "close_partner_schedule": "23:00"
                                }
                            }
                        }
                    ]
                }
            }
        """
        validate(dict(self.request.query), schemas.GET_ORDERS_SCHEMA)
        pool = tools.get_pool_from_request(self.request)
        active = get_bool_param(self.request, 'active', required=True)
        limit, offset = get_page(self.request)
        async with pool.acquire() as conn:
            orders = await conn.fetch(GET_ORDERS_QUERY, self.request.get('profile_id'), active, limit, offset)
        tasks = list()
        for order in orders:
            order_id = order.get('order_id')
            qr = order.get('qr')
            pss_qr = order.get('pss_qr')
            prepared_order = asyncio.create_task(OrderView.get_order(self.request, order_id, qr, pss_qr))
            tasks.append(prepared_order)
        data = list()
        for order in tasks:
            try:
                data.append(await order)
            except ApiResponse:
                logger.error(f'не удалось получить информацию о заказае')
                continue
        raise ApiResponse(0, dict(orders=data))


@routes.view(ROUTE_ORDER)  # todo добавить информацию о точке продаж
class OrderView(web.View):

    async def post(self):
        """
        @api {post} https://developer.mileonair.com/api/v1/order Оформить заказ

        @apiName post_orders
        @apiGroup Прочее
        @apiVersion 1.0.0

        @apiParam {int} partner_id  id партнера
        @apiParam {int} airport_id  id аэропорта
        @apiParam {list} [products] Состав корзины (необязателен если указан stock_id или cart_id) - Приоритет 1.
        Обязательным условием является наличие всех продуктов как минимум в одной точке продаж
        @apiParam {int} products.id ID продукта
        @apiParam {int} products.quantity количество едениц продукта
        @apiParam {int} [cart_id] ID корзины (необязателен если указан stock_id или cart) Приоритет 2
        @apiParam {string='web', 'apple', 'google'} [payment_service='web'] тип оплаты
        @apiParam {string} [payment_token] Токен платёжной системы закодированный в base64

        @apiParamExample {json} Request-Example:
            {"partner_id": 11,
            "airport_id": 1,
            "cart_id": 4
            }
            *************************
            {"partner_id": 11,
            "airport_id": 1,
            "products": [
                    {
                        "id": 1,
                        "quantity": 1
                    },
                    {
                        "id": 20,
                        "quantity": 2
                    }
                ]
            }

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {bool}        data.custom Указатель является ли заказ персональным
        @apiSuccess (200) {string}      data.qr QR код
        @apiSuccess (200) {string}      data.order_id ID заказа
        @apiSuccess (200) {string}      data.estimated_date Дата завершения действия покупки
        @apiSuccess (200) {string}      data.used_date Дата использования
        @apiSuccess (200) {int}         data.sum Стоимость (в копейках)
        @apiSuccess (200) {dict}        data.stock  Предложение
        @apiSuccess (200) {string}      data.stocks.purchase_terms Условия покупки
        @apiSuccess (200) {string}      data.stocks.title Название
        @apiSuccess (200) {string}      data.stocks.photo_path Путь к фотографии
        @apiSuccess (200) {dict}        data.stocks.partner Партнёр
        @apiSuccess (200) {string}      data.stocks.partner.name Имя партнёра
        @apiSuccess (200) {string}      data.stocks.partner.address_short Короткий адрес
        @apiSuccess (200) {string}      data.stocks.partner.logo_path Путь к иконке
        @apiSuccess (200) {string}      data.stocks.partner.open_partner_schedule Время открытия
        @apiSuccess (200) {string}      data.stocks.partner.close_partner_schedule Время закрытия

        @apiSuccessExample {json} Success-Response:
            {
                "responseCode": 0,
                "responseMessage": "Запрос обработан успешно",
                "data": {
                    "custom": false,
                    "qr": "a18618eca164a4854f43515676691ccd1234d7ea7bde5e507f851e9e38e0222fe",
                    "order_id": "a18618eca164a4854f43",
                    "estimated_date": "2020-08-20",
                    "used_date": "",
                    "sum": 70000,
                    "stock": {
                        "title": "Стандартная упаковка багажа",
                        "purchase_terms": "Условия покупки",
                        "photo_path": "https://developer.mileonair.com/resources/Stock/2_photo_path.jpg",
                        "partner": {
                            "name": "PACK&FLY",
                            "address_short": "Терминалы B, C, D, E и F",
                            "id": 56,
                            "logo_path": "https://developer.mileonair.com/resources/Partner/logo.png",
                            "open_partner_schedule": "06:00",
                            "close_partner_schedule": "23:00"
                        }
                    }
                }
            }
        """
        logger.warning('не реализовано!')
        raise ApiResponse(10, exc=NotImplemented)
        # Собираем все необходимые данные для формления заказа

    async def get(self):
        """
        @api {get} https://developer.mileonair.com/api/v1/order Информация о заказе

        @apiName get_orders
        @apiGroup Заказы
        @apiGroup Заказы
        @apiVersion 1.0.0

        @apiParam {string} [qr] QR код заказа (необязателен при указании order_id, используется в приоритете)
        @apiParam {string} [order_id]  id заказа


        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {bool}        data.custom Указатель является ли заказ персональным
        @apiSuccess (200) {string}      data.qr QR код
        @apiSuccess (200) {int}         data.sum Стоимость (в копейках)
        @apiSuccess (200) {int}      data.order_id ID заказа
        @apiSuccess (200) {string}      data.pdf_url Ссылка на PDF ваучер
        @apiSuccess (200) {string}      data.estimated_date Дата завершения действия покупки
        @apiSuccess (200) {bool}        data.refunded Заказ отозван
        @apiSuccess (200) {string="PROCESSING" "SUCCESS" "FAILED"}      data.payment_status Статус Оплаты
        @apiSuccess (200) {string}      data.used_date Дата использования
        @apiSuccess (200) {list}        data.points Список точек продаж в которых доступен заказ
        @apiSuccess (200) {int}        data.points.point_id id точки продаж
        @apiSuccess (200) {string}        data.points.airport_code Код аэропорта
        @apiSuccess (200) {string}        data.points.terminal Терминал
        @apiSuccess (200) {list}        data.products                 Список товаров/услуг
        @apiSuccess (200) {int}         data.products.quantity        Количество едениц товара/услуги
        @apiSuccess (200) {int}         data.products.price           Стоимость за одну еденицу товара/услуги
        @apiSuccess (200) {string}      data.products.payment_object  Признак предмета расчета
        @apiSuccess (200) {string}      data.products.name            Название товара/услуги
        @apiSuccess (200) {string}      data.products.tax             Налог
        @apiSuccess (200) {string}      data.products.product_amount  Общая стоимость
        @apiSuccess (200) {string}      data.products.payment_method  Признак способа расчета
        @apiSuccess (200) {dict}        data.stock  Предложение !Может быть Null
        @apiSuccess (200) {string}      data.stock.purchase_terms Условия покупки
        @apiSuccess (200) {string}      data.stock.title Название
        @apiSuccess (200) {string}      data.stock.photo_path Путь к фотографии
        @apiSuccess (200) {dict}        data.stock.partner Партнёр
        @apiSuccess (200) {string}      data.stock.partner.name Имя партнёра
        @apiSuccess (200) {string}      data.stock.partner.address_short Короткий адрес
        @apiSuccess (200) {string}      data.stock.partner.logo_path Путь к иконке
        @apiSuccess (200) {string}      data.stock.partner.open_partner_schedule Время открытия
        @apiSuccess (200) {string}      data.stock.partner.close_partner_schedule Время закрытия

        @apiSuccessExample {json} Success-Response:
        {
            "responseCode": 0,
            "responseMessage": "Запрос обработан успешно",
            "data": {
                "qr": "028939b0-5797-75b9-b21a-a46f01f9059b",
                "sum": 899000,
                "order_id": 633,
                "estimated_date": null,
                "refunded": false,
                "points": [
                    {
                        "point_id": 6,
                        "airport_code": "KZN",
                        "terminal": null
                    }
                ],
                "pdf_url": "http://developer.mileonair.com/api/v1/seller/file/983bdc8bbc8b846a.pdf",
                "custom": false,
                "used_date": "",
                "products": [
                    {
                        "payment_method": "full_prepayment",
                        "product_amount": 224500,
                        "tax": "vat20",
                        "name": "BUSINESS",
                        "remainder": 1,
                        "price": 224500,
                        "quantity": 1,
                        "payment_object": "service"
                    }
                ],
                "stock": {
                    "purchase_terms": "",
                    "title": "4 визита",
                    "photo_path": "",
                    "partner": {
                        "address_short": null,
                        "open_partner_schedule": null,
                        "close_partner_schedule": null,
                        "logo_path": "Brand/2_logo_path.jpg",
                        "name": "ONPASS",
                        "id": 2
                    }
                },
                "payment_status": "SUCCESS"
            }
        }
        """

        pool = tools.get_pool_from_request(self.request)
        async with pool.acquire() as conn:
            qr = self.request.query.get('qr')
            if qr is None:
                order_id = self.request.query.get('order_id')
                if order_id is None:
                    raise ApiResponse(12)
                order_row = await conn.fetchrow(
                    'SELECT id as order_id, qr, pss_qr from orders where id = $1 and profile_id = $2',
                    int(order_id),
                    self.request.get('profile_id'))
                # qr = order_row.get('qr')
            else:
                order_row = await conn.fetchrow(
                    'SELECT id as order_id, qr, pss_qr from orders where qr = $1 and profile_id = $2',
                    qr,
                    self.request.get('profile_id'))
        if order_row is None:
            raise ApiResponse(13, log_message=f"не найден заказ {self.request.query_string}")
        order_id = order_row.get('order_id')
        qr = order_row.get('qr')
        pss_qr = order_row.get('pss_qr')

        data = await self.get_order(self.request, order_id, qr, pss_qr)
        if data.pop('paid'):
            data['payment_status'] = 'SUCCESS'
        else:
            data['payment_status'] = 'FAILED'

        raise ApiResponse(0, data)

    @staticmethod
    async def get_order(request, order_id, qr, pss_qr):
        async with aiohttp.ClientSession() as session:
            url = config.pss_service.url + 'seller/order'
            headers = {'Authorization': f'Bearer {config.pss_service.token}'}
            response = await tools_ext.get_api_response_json(request, session, url, 'get', headers,
                                                             params={'qr': pss_qr})
            response['order']['qr'] = qr
            response['order']['order_id'] = order_id

        stock_id = response['order'].pop('stock_id')
        # получаем доолнительную информацию о заказае
        if stock_id is not None:
            stock = await tools_ext.get_st(request, stock_id, request.get('locale'), None)

            # подгоняем всё под формат отдачи
            stock_info = stock.get('stock')
            partner_info = stock.get('partner')
            stock_info.pop('title_short')
            stock_info.pop('start_date')
            stock_info.pop('note')
            stock_info.pop('end_date')
            stock_info.pop('cart')
            stock_info.pop('id')
            response['order']['stock'] = stock_info
            response['order']['stock']['partner'] = partner_info
        else:
            response['order']['stock'] = None

        response['order']['custom'] = False
        response['order']['used_date'] = ''
        # response['order'].pop('paid')
        response['order'].pop('refunded_date')
        response['order'].pop('profile_ln')
        response['order'].pop('confirmed_date')
        response['order'].pop('created_date')
        response['order'].pop('sold_date')
        response['order'].pop('profile_fn')
        response['order'].pop('profile_phone')
        # response['order'].pop('products')
        # response['order'].pop('points')
        return response['order']


@routes.view(ROUTE_CUSTOM_ORDER)
class CustomOrder(web.View):

    async def post(self):
        raise ApiResponse(10)


# ------------------- onpass -------------------------------

@routes.view(ROUTE_ONPASS)
class Onpass(web.View):

    async def get_onpass_types(self):
        """
        @api {get} https://developer.mileonair.com/api/v1/onpass/types Типы бизнес залов

        @apiName get_onpass_types
        @apiDescription Возвращает информацию типах бизнес залов на всех языках
        @apiGroup Справочники
        @apiVersion 1.0.0

        @apiSuccess (200) {int}         responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string}      responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict}        data  Словарь с данными
        @apiSuccess (200) {list}        data.types  Персональное предложение
        @apiSuccess (200) {int}         data.types.id ID типа бизнес зала
        @apiSuccess (200) {list}        data.translates Название  бизнес зала
        @apiSuccess (200) {string}      data.translates.type_id ID типа бизнес зала
        @apiSuccess (200) {string}      data.translates.name Тип бизнес зала
        @apiSuccess (200) {string}      data.translates.code Код языка

        @apiSuccessExample Success-Response:
        {
            "responseCode": 0,
            "responseMessage": "Запрос обработан успешно",
            "data": {
                "types": [
                    {
                        "id": "K0000000059"
                    }
                ],
                "translates": [
                    {
                        "type_id": "K0000000059",
                        "name": "Услуга Защита ПэкЭндФлай",
                        "code": "ru"
                    },
                    {
                        "type_id": "K0000000059",
                        "name": "Protection service PACK&FLY",
                        "code": "en"
                    }
                ]
            }
        }
        """
        pool = tools.get_pool_from_request(self.request)
        async with pool.acquire() as connection:
            data = await get_onpass_products_query(connection)
        data = convert_data(data)
        data = {'types': list(map(lambda x: dict(id=x), set(row['type_id'] for row in data))), 'translates': data}
        raise ApiResponse(0, data)


@routes.view(ROUTE_ONPASS_ORDER)
class OnpassOrderView(OrderView):
    class Product(BaseModel):
        id: int
        quantity: int

    class InputGetData(BaseModel):
        class Product(BaseModel):
            id: int
            quantity: int

        cart_id: Optional[int]
        products: Optional[List[Product]]
        mile_count: int

        class Config:
            extra = 'forbid'

    async def post(self):
        """
        @api {post} https://developer.mileonair.com/api/v1/onpass/order Оформить заказ

        @apiName post_onpass_orders
        @apiGroup Onpass
        @apiVersion 1.0.0

        @apiParam {list} [products] Состав корзины (необязателен если указан stock_id или cart_id) - Приоритет 1.
        Обязательным условием является наличие всех продуктов как минимум в одной точке продаж
        @apiParam {int} products.id ID продукта
        @apiParam {int} products.quantity количество едениц продукта
        @apiParam {int} [cart_id] ID корзины (необязателен если указан stock_id или cart) Приоритет 2
        @apiParam {int} mile_count Оплата продукта бонусными милями

        @apiParamExample {json} Request-Example:
            {
            "cart_id": 4
            }
            *********
            {
                "products": [{
                    "id": 20,
                    "quantity": 1

                }
                ],
                 "mile_count":1
            }

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {string}      data.qr QR код
        @apiSuccess (200) {int}         data.sum Стоимость (в копейках)
        @apiSuccess (200) {int}         data.order_id ID заказа
        @apiSuccess (200) {string}      data.estimated_date Дата завершения действия покупки
        @apiSuccess (200) {bool}        data.refunded Заказ отозван
        @apiSuccess (200) {list}        data.points Список точек продаж в которых доступен заказ
        @apiSuccess (200) {int}         data.points.point_id id точки продаж
        @apiSuccess (200) {string}      data.points.airport_code Код аэропорта
        @apiSuccess (200) {string}      data.points.terminal Терминал
        @apiSuccess (200) {string}      data.pdf_url Ссылка на PDF ваучер
        @apiSuccess (200) {bool}        data.custom Указатель является ли заказ персональным
        @apiSuccess (200) {string}      data.used_date Дата использования

        @apiSuccess (200) {list}        data.products                 Список товаров/услуг
        @apiSuccess (200) {int}         data.products.quantity        Количество едениц товара/услуги
        @apiSuccess (200) {int}         data.products.price           Стоимость за одну еденицу товара/услуги
        @apiSuccess (200) {string}      data.products.payment_object  Признак предмета расчета
        @apiSuccess (200) {string}      data.products.name            Название товара/услуги
        @apiSuccess (200) {string}      data.products.tax             Налог
        @apiSuccess (200) {string}      data.products.product_amount  Общая стоимость
        @apiSuccess (200) {string}      data.products.payment_method  Признак способа расчета
        @apiSuccess (200) {dict}        data.stock  Предложение !Может быть Null
        @apiSuccess (200) {string}      data.stock.purchase_terms Условия покупки
        @apiSuccess (200) {string}      data.stock.title Название
        @apiSuccess (200) {string}      data.stock.photo_path Путь к фотографии
        @apiSuccess (200) {dict}        data.stock.partner Партнёр
        @apiSuccess (200) {string}      data.stock.partner.name Имя партнёра
        @apiSuccess (200) {string}      data.stock.partner.address_short Короткий адрес
        @apiSuccess (200) {string}      data.stock.partner.logo_path Путь к иконке
        @apiSuccess (200) {string}      data.stock.partner.open_partner_schedule Время открытия
        @apiSuccess (200) {string}      data.stock.partner.close_partner_schedule Время закрытия

        @apiSuccessExample {json} Success-Response:
            {
                "responseCode": 0,
                "responseMessage": "Запрос обработан успешно",
                "data": {
                    "order": {
                        "order_id": 1115,
                        "qr": null,
                        "sum": 55800,
                        "estimated_date": null,
                        "refunded": false,
                        "products": [
                            {
                                "name": "VIP",
                                "price": 13900,
                                "payment_object": "qwe",
                                "quantity": 2,
                                "remainder": 2,
                                "product_amount": 27800,
                                "id": 26
                            },
                            {
                                "name": "VIP",
                                "price": 14000,
                                "payment_object": "qwe",
                                "quantity": 2,
                                "remainder": 2,
                                "product_amount": 28000,
                                "id": 26
                            }
                        ],
                        "points": [
                            {
                                "point_id": 12,
                                "terminal": "A",
                                "airport_code": "SVO"
                            }
                        ],
                        "custom": false,
                        "used_date": null,
                        "stock": null
                    }
                }
            }
        """
        params = await tools.get_data_from_request(self.request)
        user = User.get()
        response = await OnpassOrder(user).create(params)
        raise ApiResponse(0, dict(response.dict()))


@routes.view(ROUTE_ONPASS_POINT)
class OnpassPoint(web.View):
    def __init__(self, request):
        super().__init__(request)
        self._pool = tools.get_pool_from_request(self.request)

    async def get(self):
        """
        @api {get} https://developer.mileonair.com/api/v1/onpass/point Информация о бизнес зале

        @apiName getOnpassPoint
        @apiGroup Onpass
        @apiVersion 1.0.0

        @apiParam {int} point_id ID бизнес зала


        @apiSuccess (200) {int}             responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string}          responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict}            data  Словарь с данными
        @apiSuccess (200) {dict}            data.point  Партнёр
        @apiSuccess (200) {string}          data.point.name  Название
        @apiSuccess (200) {string}          data.point.address  Адрес
        @apiSuccess (200) {bool}            data.point.active  Точка продаж активна (подключена)
        @apiSuccess (200) {string}          data.point.floor  Этаж
        @apiSuccess (200) {string}          data.point.schedule  Расписане
        @apiSuccess (200) {string}          data.point.description_short  Краткое описание
        @apiSuccess (200) {string}          data.point.additional_info  Дополнительная информация
        @apiSuccess (200) {json}            data.point.custom_info  Дополнительная информация о бизнес зале (тип)
        @apiSuccess (200) {string}          data.point.brand_tag  Тег бренда
        @apiSuccess (200) {string}          data.point.airport_code  Код Аэропорта
        @apiSuccess (200) {string}          data.point.terminal  Терминал
        @apiSuccess (200) {bool}            data.point.closed  Бизнес зал закрыт
        @apiSuccess (200) {list}            data.point.photo_paths Список путей к фото
        @apiSuccess (200) {list}            data.point.services  Список сервисов
        @apiSuccess (200) {string}          data.point.services.name  Название
        @apiSuccess (200) {string}          data.point.services.ico_path  Иконка
        @apiSuccess (200) {float}          data.point.cashback_part  доля кэшбека
        @apiSuccess (200) {float}          data.point.redeem_part  Максимально допустимый процент стоимости
        доступный для оплаты милями
        @apiSuccess (200) {int}          data.point.min_redeem_mile_count  Минимальное количество миль к
        списанию
        @apiSuccess (200) {int}          data.point.price  Стоимость одного прохода
        @apiSuccess (200) {int}          data.point.purchased_visits_count  Количество активных проходов
        @apiSuccess (200) {list}        data.point.products             Список продуктов
        @apiSuccess (200) {int}         data.point.products.id          ID продукта
        @apiSuccess (200) {price}       data.point.products.price       Стоимость продукта в копейках
        @apiSuccess (200) {list[int]}   data.point.products.points      Список ID точек продаж в которых доступен продукт
        @apiSuccess (200) {string}      data.point.products.name        Название продукта


        @apiSuccessExample Success-Response:
        {
            "responseCode": 0,
            "responseMessage": "Запрос обработан успешно",
            "data": {
                "point": {
                    "name": "Perry Yoder",
                    "address": "Perry Yoder address ru",
                    "active": true,
                    "floor": "2",
                    "schedule": "Perry Yoder open_partner_schedule ru",
                    "description_short": "",
                    "additional_info": "",
                    "custom_info": {
                        "type": "VIP"
                    },
                    "brand_tag": "onpass",
                    "airport_code": "SVO",
                    "terminal": "A",
                    "closed": false,
                    "photo_paths": [
                        "https://newsroom.mastercard.com/ru/files/2017/11/NB_Mastercard_Business_Lounge1.jpg"
                    ],
                    "services": [],
                    "price": 14000,
                    "purchased_visits_count": 0,
                    "products": [
                        {
                            "id": 26,
                            "points": [
                                12
                            ],
                            "price": 14000,
                            "name": "VIP"
                        }
                    ],
                    "cashback_part": 10.0,
                    "redeem_part": 100.0,
                    "min_redeem_mile_count": 100
                }
            }
        }
        """

        params = dict(self.request.query)
        validate_data(params, schemas.GET_ONPASS_POINT_SCHEMA)
        point_id = int(params.get('point_id'))
        logger.debug(params)
        url = config.pss_service.url + 'seller/point'
        headers = {
            'Authorization': f'Bearer {config.pss_service.token}'
        }
        params = dict(point_id=point_id, language_code=self.request.get('locale'))
        async with aiohttp.ClientSession() as session:
            try:

                response = await session.get(url, headers=headers, params=params)
                response_data = await response.json()
            except CancelledError:
                raise
            except Exception as ex:
                logger.error(f"не удалось выполнить запрос к партнёрскму сервису: {url} : {ex}")
                raise ApiResponse(31)
            try:
                if response_data.get('responseCode') != 0:
                    logger.error(f"Ответ партнёрского сервиса не 0 партнёрскму сервису: {url}, "
                                 f"params = {params}, responseCode ={response_data.get('responseCode')}")
                    raise ApiResponse(30)
                point = response_data['data'].get('point')
                if point.get('brand_tag') != 'onpass':
                    logger.warning('невозможный сценарий)')
                    return ApiResponse(13)
            except CancelledError:
                raise
            except Exception as ex:
                logger.error(f"не удалось прочитать ответ партнёрского сервиса: {url} : {ex}")
                raise ApiResponse(30)

            async with self._pool.acquire() as conn:
                prepared_qr = await conn.prepare(QR_CODES_QUERY)
                purchased_visits_count = 0
                qr_codes = await prepared_qr.fetchval(point_id, self.request.get('profile_id'))
                if qr_codes is not None:
                    for pss_qr in qr_codes:
                        url = config.pss_service.url + 'seller/order'
                        headers = {'Authorization': f'Bearer {config.pss_service.token}'}
                        try:
                            pss_order = await tools_ext.get_api_response_json(self.request, session, url, 'get',
                                                                              headers,
                                                                              params={'qr': pss_qr})
                        except ApiResponse:
                            logger.error(f'Ну удалось учесть заказ с pss_qr = {pss_qr}: ')
                            continue
                        if not pss_order['order']['refunded']:
                            for product in pss_order['order']['products']:
                                purchased_visits_count += product['remainder']
            custom_info = point.get('custom_info')
            if custom_info is not None:
                try:
                    price = custom_info.pop('price')
                except:
                    price = 0
                if price is None:
                    price = 0
                point.update(
                    dict(
                        price=price,
                        purchased_visits_count=purchased_visits_count,
                    )
                )
        products = await self.get_products(dict(point_id=point_id))
        point.update(dict(products=products))
        async with self._pool.acquire() as conn:

            cashback_data = await conn.fetchrow(
                'select cashback_part, redeem_part,min_redeem_mile_count '
                'from partners inner join points on partners.id = points.partner_id '
                'where points.id = $1;', config.onpass_acq_point_id
            )
            point.update(dict(cashback_data))
        convert_data(point, formatting_float=2)
        data = {'point': point}
        raise ApiResponse(0, data)

    async def get_products(self, params=None):
        try:
            language_code = self.request.get('locale', 'ru')
            params.update({"language_code": language_code})
            url = config.pss_service.url + 'seller/products'
            headers = {'Authorization': f'Bearer {config.pss_service.token}'}
            async with aiohttp.ClientSession() as session:
                response = await session.get(url, headers=headers, params=params)
                data = await response.json()
                return data.get('data').get('products')
        except Exception as exc:
            logger.error(f"не удалось получить список продуктов для {params}, exc:{exc}")
            return list()


@routes.view(ROUTE_ONPASS_POINTS)
@routes.view(ROUTE_ONPASS_POINTS_IN_AIRPORT)
class OnpassPointsInAirport(web.View):
    class InputGetData(BaseModel):
        airport_id: Optional[int]
        purchased: bool = False

    def __init__(self, request):
        super().__init__(request)

    async def _get_params(self):

        params = dict(self.request.query)
        validate_data(params, schemas.GET_ONPASS_POINTS_IN_AIRPORT_SCHEMA)
        self._airport_id = to_int(params.get('airport_id'))
        self._purchased = get_bool_param(self.request, 'purchased', required=False)
        self._pool = tools.get_pool_from_request(self.request)

    async def _get_airport_code(self):
        if self._airport_id is None:
            self._airport_code = None
            return
        async with self._pool.acquire() as conn:
            self._airport_code = await conn.fetchval(GET_AIRPORT_CODE, self._airport_id)
            if ONPASS_BRAND_TAG is None:
                raise ApiResponse(0, {'points': []})

    async def _get_points_from_pss(self, airport_code):
        pss_response = await pss.views.Points.pss_get(
            pss.views.Points.InputGetData(
                language_code=self.request.get('locale'),
                airport_code=airport_code
            )
        )
        if pss_response.code != 0:
            logger.error(f'ответ партнёрского сервиса не 0 а {pss_response.code}')
            raise ApiResponse(30)
        return pss.views.PointsModel(**pss_response.data)

    async def get(self):
        """
        @api {get} https://developer.mileonair.com/api/v1/onpass/points Список бизнес залов

        @apiName getOnpassPoints
        @apiGroup Onpass
        @apiVersion 1.0.0

        @apiParam {bool="true", "false"} [testing="Более не используется!!!"]
        @apiParam {int} [airport_id] ID аэропорта
        @apiParam {bool} [purchased] Отображать только точки в которые есть активные проходы

        @apiSuccess (200) {int}         responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string}      responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict}        data  Словарь с данными
        @apiSuccess (200) {list}        data.points  Бизнес залы

        @apiSuccess (200) {int}         data.points.id  ID Бизнес зала
        @apiSuccess (200) {dict}        data.points.custom_info  Партнёр не работает
        @apiSuccess (200) {string}      data.points.custom_info.type Тип бизнкс зала
        @apiSuccess (200) {string}      data.points.brand_tag  тег бренда
        @apiSuccess (200) {string}      data.points.airport_code  Код Аэропорта
        @apiSuccess (200) {string}      data.points.name  Название бизнес зала
        @apiSuccess (200) {string}      data.points.address_short  Короткий адрес
        @apiSuccess (200) {string}      data.points.terminal  Терминал
        @apiSuccess (200) {string}      data.points.photo_path Путь к фото
        @apiSuccess (200) {bool}        data.points.closed  Бизнес зал закрыт
        @apiSuccess (200) {string}      data.points.floor  Этаж/Этажи
        @apiSuccess (200) {int}         data.points.price  Цена
        @apiSuccess (200) {int}         data.points.purchased_visits_count  Количетво купленных визитов
        @apiSuccess (200) {bool}        data.points.active Бизнес зал подключён


        @apiSuccessExample Success-Response:
            {
                "responseCode": 0,
                "responseMessage": "Запрос обработан успешно",
                "data": {
                    "points": [
                        {
                            "brand_tag": "onpass",
                            "airport_code": "SVO",
                            "floor": null,
                            "address_short": "короткий адрес Терминал D, 3 этаж",
                            "name": "Скоро. Скоро. Скоро. Бизнес-зал «Москва»",
                            "active": true,
                            "id": 9,
                            "terminal": "D",
                            "photo_path": "https://dev.cl.maocloud.ru/resources/PhotoToPoint/moscow2.jpg",
                            "custom_info": {
                                "type": "BUSINESS"
                            },
                            "closed": false,
                            "price": 123456,
                            "purchased_visits_count": 11
                        }
                    ]
                }
            }
        """
        if ONPASS_BRAND_TAG is None:
            raise ApiResponse(0, {'points': []})

        params = self.InputGetData(**self.request.query)
        pool = tools.get_pool_from_request(self.request)

        async with pool.acquire() as conn:
            if params.airport_id is not None:
                airport_code = await conn.fetchval(GET_AIRPORT_CODE, params.airport_id)
            else:
                airport_code = None

        points = await self._get_points_from_pss(airport_code)
        logger.debug(f'получилт поинты {points}')
        orders = pss.views.OrdersModel()
        orders_limit = 500
        page = 0
        while True:

            pss_response = await pss.views.Orders.pss_get(
                pss.views.Orders.InputGetData(
                    brand_tag=ONPASS_BRAND_TAG,
                    airport_code=airport_code,
                    phone=self.request.get('phone_number'),
                    filter=pss.views.Orders.InputGetData.FilterEnum.actual,
                    limit=orders_limit,
                    offset=page * orders_limit
                )
            )
            if pss_response.code != 0:
                logger.error(f'ответ партнёрского сервиса не 0 а {pss_response.code}')
                raise ApiResponse(30)
            pss_orders = pss.views.OrdersModel(**pss_response.data)
            orders.orders.extend(pss_orders.orders)
            page += 1
            if len(pss_orders.orders) < orders_limit: break
        logger.debug(f'orders = {orders}')
        async with pool.acquire() as conn:
            prepared_qr = await conn.prepare(QR_CODES_QUERY)
            i = 0
            while i < len(points.points):
                point = points.points[i]
                purchased_visits_count = 0

                qr_codes = await prepared_qr.fetchval(point.id, self.request.get('profile_id'))
                logger.debug(point)
                if qr_codes is not None:
                    for pss_qr in qr_codes:
                        order = orders.find(order_qr=pss_qr)
                        if order is not None:
                            for product in orders.find(order_qr=pss_qr).products:
                                purchased_visits_count += product.remainder
                if purchased_visits_count == 0 and params.purchased:
                    points.points.pop(i)
                    continue
                i += 1
                custom_info = point.custom_info
                if custom_info is not None:
                    price = custom_info.pop('price')
                    if price is not None:
                        point.price = price
                    point.purchased_visits_count = purchased_visits_count
        points.points.sort(key=lambda x: (not x.active, x.photo_path is None, -x.price, x.id))
        # data = dict(points=result)
        raise ApiResponse(0, points.dict())


# -------------------------------------------------------------------------------------------


@routes.view(ROUTE_PRODUCTS)
class ProductsView(web.View):
    async def get(self):
        """
                @api {get} https://api.maocloud.ru/api/v1/products Список продуктов

                @apiDescription Получить информацию о продукте

                @apiName get_products
                @apiGroup Заказы
                @apiVersion 1.0.0

                @apiParam {int}     [point_id]           Фильтр по точке продаж
                @apiParam {string}     [brand_tag]           Фильтр по бренду
                @apiParam {string}     [airport_code]           Фильтр по аэропорту
                @apiParam {int}     [limit=20]              Ограничение количества выводимых значений
                @apiParam {int}     [offset=0]              Отступ пагинации


                @apiSuccess (200) {int}         responseCode             Код ошибки (0 - нет ошибки)
                @apiSuccess (200) {string}      responseMessage          Описание ошибки, ответа
                @apiSuccess (200) {dict}        data                     Словарь с данными
                @apiSuccess (200) {list}        data.products             Список продуктов
                @apiSuccess (200) {int}         data.products.id          ID продукта
                @apiSuccess (200) {price}       data.products.price       Стоимость продукта в копейках
                @apiSuccess (200) {list[int]}   data.products.points      Список ID точек продаж в которых доступен продукт
                @apiSuccess (200) {string}      data.products.name        Название продукта


                @apiSuccessExample Success-Response:
                    HTTP/1.1 200 OK
                    {
                        "responseCode": 0,
                        "responseMessage": "Запрос обработан успешно",
                        "data": {
                            "products": [
                                {
                                    "id": 17,
                                    "price": 70000,
                                    "points": [
                                        4
                                    ],
                                    "name": "Услуга упаковки"
                                }
                            ]
                        }
                    }

                """

        params = dict(self.request.query)
        language_code = self.request.get('locale', 'ru')
        params.update({"language_code": language_code})
        url = config.pss_service.url + 'seller/products'
        headers = {'Authorization': f'Bearer {config.pss_service.token}'}
        async with aiohttp.ClientSession() as session:
            response = await session.get(url, headers=headers, params=params)
            data = await response.json()
        return web.json_response(data)


@routes.view(ROUTE_PRODUCT)
class ProductView(web.View):
    async def get(self):
        """
        @api {get} https://api.maocloud.ru/api/v1/product Информация о продукте

        @apiDescription Получить информацию о продукте

        @apiName get_product
        @apiGroup Заказы
        @apiVersion 1.0.0

        @apiParam {int}     id           ID продукта

        @apiSuccess (200) {int}         responseCode               Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string}      responseMessage            Описание ошибки, ответа
        @apiSuccess (200) {dict}        data                       Словарь с данными
        @apiSuccess (200) {dict}        data.product               Информация о продукте
        @apiSuccess (200) {int}         data.product.id            ID продукта
        @apiSuccess (200) {price}       data.product.price         Стоимость продукта в копейках
        @apiSuccess (200) {list[int]}   data.product.points        Список ID точек продаж в которых доступен продукт
        @apiSuccess (200) {string}      data.product.name          Название продукта


        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
            {
                "responseCode": 0,
                "responseMessage": "Запрос обработан успешно",
                "data": {
                    "product": {
                        "id": 20,
                        "price": 224500,
                        "points": [
                            6
                        ],
                        "name": "BUSINESS"
                    }
                }
            }
        """
        params = dict(self.request.query)
        language_code = self.request.get('locale', 'ru')
        params.update({"language_code": language_code})
        url = config.pss_service.url + 'seller/product'
        headers = {'Authorization': f'Bearer {config.pss_service.token}'}
        async with aiohttp.ClientSession() as session:
            response = await session.get(url, headers=headers, params=params)
            data = await response.json()
        return web.json_response(data)


# ------------------------------- Payment --------------------------------------
class BasePayView(web.View):
    user: User
    _conn: Connection
    _order: OrderModel
    _order_query = 'select * from orders where id = $1 and profile_id = $2'
    alfa_response = NotImplemented
    InputPostData = NotImplemented
    params: InputPostData

    async def pay(self, order_id):
        pool = ApiPool.get_pool()
        async with pool.acquire() as self._conn:
            await self.find_moa_order(order_id)
            await self.make_ofd_receipt()
            await self.register_order()
            cashback = await self.update_order()
            if cashback is not None:
                return await self.collect_response(cashback)
            else:
                return await self.collect_response()

    async def find_moa_order(self, order_id):
        order_row = await self._conn.fetchrow(self._order_query, order_id, self.user.id)
        if order_row is None:
            raise ApiResponse(13)
        self._order = OrderModel(**order_row)

    async def make_ofd_receipt(self):
        pass

    @abstractmethod
    async def update_order(self):
        pass

    @abstractmethod
    async def register_order(self):
        pass

    @abstractmethod
    async def collect_response(self, cashback=None):
        pass

    async def post(self):

        self.user = User.get()
        body = await tools.get_data_from_request(self.request)
        self.params = self.InputPostData(**body)
        response = await self.pay(self.params.order_id)
        raise ApiResponse(0, response)


@routes.view(PAY_WEB)
class WebPayView(BasePayView):
    """
    @api {post} https://developer.mileonair.com/api/v1/payWeb Оплатить картой

    @apiName web_pay
    @apiGroup Оплата
    @apiVersion 1.0.0

    @apiParam {int} order_id Номер заказа


    @apiParamExample {json} Request-Example:
    {
        "order_id": 1115
    }

    @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
    @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
    @apiSuccess (200) {dict} data  Словарь с данными

    @apiSuccess (200) {string}      data.form_url Сылка на страницу оплаты
    @apiSuccess (200) {string}      data.redirect_url Ожидаемый редирект при успешной оплате
    При фактическом редиректе в параметрах запроса будут указаны
    "status: [success/failed]" и "cashback:int" (количество начисленых миль)


    @apiSuccessExample {json} Success-Response:
        {
            "responseCode": 0,
            "responseMessage": "Запрос обработан успешно",
            "data": {
                "form_url": "https://web.rbsuat.com/ab/merchants/typical/mobile_payment_ru.html?mdOrder=0320e7b
                5-3ee5-7187-9fb9-547201f9059b",
                "redirect_url": "https://mileonair.com/success",
            }
        }
    """

    class InputPostData(BaseModel):
        order_id: int

    alfa_response: alfa_bank.WebPay.payment_response

    async def register_order(self):
        # path = self.request.app.router['confirm_pay'].url_for()
        path = self.request.app.router['order_status_loader'].url_for(filename='index.html')
        pss_response = await pss.Order.pss_get(
            pss.models.OrderGetInput(
                qr=self._order.pss_qr
            )
        )
        if pss_response.code != 0:
            logger.error(f'ответ партнёрского сервиса не 0 а {pss_response.code}')
            raise ApiResponse(30)
        pss_order = pss_response.data.get('order', dict())
        products = pss_order.get('products')  # достать реальные значения
        email = self.request.get('email_for_receipts')
        order_bundle = create_bundle(products, email)
        logger.debug(order_bundle)
        url = str(self.request.url.origin().join(path)).replace('http://', 'https://')
        self.alfa_response = await alfa_bank.WebPay.post(
            alfa_bank.models.WebPaymentData(
                clientId=IS_DEV_PREFIX + str(self.request.get('profile_id')),
                orderNumber=IS_DEV_PREFIX + MOA_ORDER_PREFIX + str(self.params.order_id),
                amount=self._order.sum,
                returnUrl=url,
                orderBundle=order_bundle,
                language=self.request.get('locale').upper()
            )
        )

    async def update_order(self):
        await self._conn.execute('update orders set qr = $2 where id = $1', self._order.id,
                                 self.alfa_response.order_id)

    async def collect_response(self, cashback=None):
        return dict(
            form_url=self.alfa_response.formUrl,
            redirect_url=get_redirect_url(self.request, True).rpartition('?')[0]
        )


@routes.view(CONFIRM_PAY, name='confirm_pay')
class ConfirmPay(web.View):
    class GetInputData(BaseModel):
        qr: str

        class Config:
            fields = {
                'qr': 'orderId'
            }

    params: GetInputData
    _conn: Connection
    _order_query = 'select * from orders where qr = $1'

    async def get(self):
        self.params = validate_data(self.request.query, self.GetInputData)
        # self.params = self.GetInputData(**self.request.query)
        pool = ApiPool.get_pool()
        async with pool.acquire() as self._conn:
            await self.confirm_order()

    async def confirm_order(self):
        order = validate_data(await self._conn.fetchrow(self._order_query, self.params.qr), OrderModel)
        if order is None:
            raise ApiResponse(13, log_message=f'order with params:{self.params} not found')
        # order = OrderModel(**await self._conn.fetchrow(self._order_query, self.params.qr))
        logger.debug(f'order = {order}')
        if not order.confirmed:
            attempts = 0
            while True:
                attempts += 1
                confirmation_data = await alfa_bank.GetOrderStatusExtended.post(
                    alfa_bank.GetOrderStatusExtended.input_post_model(orderId=order.qr))
                order_status = confirmation_data.order_status
                if order_status != 0 or attempts > 5:
                    break
            logger.debug(f'order = {confirmation_data}')
            order.paid = order_status == 2
            order.confirmed = order_status != 0
            await save_email_for_receipts(confirmation_data, order.profile_id)
        await self._conn.execute(
            'update orders set paid=$2, confirmed=$3 where id = $1', order.id, order.paid, order.confirmed)
        if order.confirmed and not order.processed:
            cashback = await MilesOperations(order).process()

        else:
            cashback = None
        raise ApiResponse(0, dict(
            status=order.paid,
            cashback=cashback
        ))


class MobilePayView(BasePayView, ABC):
    class InputPostData(BaseModel):
        order_id: int
        payment_token: str

    params: InputPostData

    async def update_order(self):
        if self.alfa_response.success:
            qr = self.alfa_response.data.orderId
        else:
            qr = None
        order = OrderModel(**await self._conn.fetchrow(
            'update orders set qr = $2, confirmed=True, paid = $3  where id = $1 returning *',
            self._order.id,
            qr,
            self.alfa_response.success))
        cashback = await MilesOperations(order).process()
        return cashback

    async def collect_response(self, cashback=0):
        data = {'cashback': cashback}
        data.update(self.alfa_response.dict())
        raise ApiResponse(0, data, log_message=str(data))


@routes.view(PAY_APPLE)
class ApplePayView(MobilePayView):

    async def register_order(self):
        """
        @api {post} https://developer.mileonair.com/api/v1/payApple Оплата Apple

        @apiName apple_pay
        @apiGroup Оплата
        @apiVersion 1.0.0

        @apiParam {int} order_id Номер заказа
        @apiParam {str} payment_token платёжный токен


        @apiParamExample {json} Request-Example:
        {
            "order_id": 1115,
            "payment_token": "ew0KICB7DQoJICAidmVyc2lvbiI6ICJSU0FfdjEiLA0KCSAgInNpZ25hdHVyZSI6ICJabUZyWlNCemFXZHVZW
            FIxY21VPSIsDQoJICAiaGVhZGVyIjogew0KCQkiZXBoZW1lcmFsUHVibGljS2V5IjogIk1Ga3dFd1lIS29aSXpqMENBUVlJS29aSXpq
            MERBUWNEUWdBRW14Q2hDcGpLemY5YVh6MjZXVDZaVE4yekUzaUdYUWpjWlJZWUFkUUlURFgyUmtBTmJ0N2s5cmFoRjFoempqbWVWVHh
            jZ0NvZkg4MXprMkdOVFozZHRnPT0iICAgICAgIA0KCQkid3JhcHBlZEtleSI6ICJYejI2V1Q2WlROMnpFM2lHWFFqYz0iDQoJCSJwdW
            JsaWNLZXlIYXNoIjogIk9yV2dqUkdrcUVXamRrUmRVclhmaUxHRDBoZS96cEV1NTEyRkpXckdZRm89IiwNCgkJInRyYW5zYWN0aW9uS
            WQiOiAiYXBwbGUtMTIzNDU2Nzg5MEFCQ0RFRiINCgkgIH0sDQoJICAiZGF0YSI6ICIxZFhFMTNrdnpUVlA2bldFTjhEMnBoclBsZlFj
            R3I4VzN5ajJTSFlZai9QeWNIV1RqbnBWN3ovRXI3OGJyaT09Ig0KICB9DQp9"
        }

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными

        @apiSuccess (200) {bool}     data.success Результат оплаты
        @apiSuccess (200) {int}     data.cashback Начислено миль

        @apiSuccessExample {json} Success-Response:
            {
                "responseCode": 0,
                "responseMessage": "Запрос обработан успешно",
                "data": {
                    "success": false,
                    "cashback": 0
                }
            }
        """
        pss_response = await pss.Order.pss_get(
            pss.models.OrderGetInput(
                qr=self._order.pss_qr
            )
        )
        if pss_response.code != 0:
            logger.error(f'ответ партнёрского сервиса не 0 а {pss_response.code}')
            raise ApiResponse(30)
        pss_order = pss_response.data.get('order', dict())
        products = pss_order.get('products')
        email = self.request.get('email_for_receipts')
        order_bundle = create_bundle(products, email)
        params = alfa_bank.ApplePay.input_post_model(
            orderNumber=IS_DEV_PREFIX + MOA_ORDER_PREFIX + str(self._order.id),
            paymentToken=self.params.payment_token,
            orderBundle=order_bundle
        )
        logger.debug(order_bundle)
        self.alfa_response = await alfa_bank.ApplePay.post(params)


@routes.view(PAY_GOOGLE)
class GooglePayView(MobilePayView):

    async def register_order(self):
        """
        @api {post} https://developer.mileonair.com/api/v1/payGoogle Оплата Google

        @apiName google_pay
        @apiGroup Оплата
        @apiVersion 1.0.0

        @apiParam {int} order_id Номер заказа
        @apiParam {str} payment_token платёжный токен


        @apiParamExample {json} Request-Example:
        {
            "order_id": 1115,
            "payment_token": "ew0KICB7DQoJICAidmVyc2lvbiI6ICJSU0FfdjEiLA0KCSAgInNpZ25hdHVyZSI6ICJabUZyWlNCemFXZHVZW
            FIxY21VPSIsDQoJICAiaGVhZGVyIjogew0KCQkiZXBoZW1lcmFsUHVibGljS2V5IjogIk1Ga3dFd1lIS29aSXpqMENBUVlJS29aSXpq
            MERBUWNEUWdBRW14Q2hDcGpLemY5YVh6MjZXVDZaVE4yekUzaUdYUWpjWlJZWUFkUUlURFgyUmtBTmJ0N2s5cmFoRjFoempqbWVWVHh
            jZ0NvZkg4MXprMkdOVFozZHRnPT0iICAgICAgIA0KCQkid3JhcHBlZEtleSI6ICJYejI2V1Q2WlROMnpFM2lHWFFqYz0iDQoJCSJwdW
            JsaWNLZXlIYXNoIjogIk9yV2dqUkdrcUVXamRrUmRVclhmaUxHRDBoZS96cEV1NTEyRkpXckdZRm89IiwNCgkJInRyYW5zYWN0aW9uS
            WQiOiAiYXBwbGUtMTIzNDU2Nzg5MEFCQ0RFRiINCgkgIH0sDQoJICAiZGF0YSI6ICIxZFhFMTNrdnpUVlA2bldFTjhEMnBoclBsZlFj
            R3I4VzN5ajJTSFlZai9QeWNIV1RqbnBWN3ovRXI3OGJyaT09Ig0KICB9DQp9"
        }

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными

        @apiSuccess (200) {bool}     data.success Результат оплаты
        @apiSuccess (200) {int}     data.cashback Начислено миль

        @apiSuccessExample {json} Success-Response:
            {
                "responseCode": 0,
                "responseMessage": "Запрос обработан успешно",
                "data": {
                    "success": false,
                    "cashback": 0
                }
            }
        """
        pss_response = await pss.Order.pss_get(
            pss.models.OrderGetInput(
                qr=self._order.pss_qr
            )
        )
        if pss_response.code != 0:
            logger.error(f'ответ партнёрского сервиса не 0 а {pss_response.code}')
            raise ApiResponse(30)
        pss_order = pss_response.data.get('order', dict())
        products = pss_order.get('products')
        email = self.request.get('email_for_receipts')
        order_bundle = create_bundle(products, email)
        params = alfa_bank.GooglePay.input_post_model(
            ip=tools.get_ip_from_request(self.request),
            amount=self._order.sum,
            return_url=get_redirect_url(self.request, True),
            order_id=IS_DEV_PREFIX + MOA_ORDER_PREFIX + str(self._order.id),
            paymentToken=self.params.payment_token,
            orderBundle=order_bundle
        )
        logger.debug(order_bundle)
        self.alfa_response = await alfa_bank.GooglePay.post(params)


@routes.view(REDIRECT_ENDPOINT, name='payment_status')
class RedirectSuccessView(web.View):
    @aiohttp_jinja2.template('payment_status.html')
    async def get(self):
        status = self.request.query.get("status", "")
        if status.lower() not in ['success', 'failed']:
            raise HTTPNotFound
        context = {'status': status.upper()}

        return context


class MilesOperations:
    _conn: Connection
    products: List

    def __init__(self, order: OrderModel):
        self.order = order

    async def process(self):
        async with ApiPool.get_pool().acquire() as self._conn:
            if self.order.paid:
                frozen_miles = await self._conn.fetchval('select freezed_mile_count from uuid_relations '
                                                         'where transactions_uuid= $1', self.order.uuid_relation)
                pss_response = await pss.Order.pss_get(
                    pss.models.OrderGetInput(
                        qr=self.order.pss_qr
                    )
                )
                if pss_response.code != 0:
                    logger.error(f'ответ партнёрского сервиса не 0 а {pss_response.code}')
                    raise ApiResponse(30)
                pss_order = pss_response.data.get('order', dict())
                self.products = pss_order.get('products')

                if frozen_miles is None:
                    await self.collect()
                else:
                    await self.redeem()
                mile_bonus = await self.get_mile_bonus()
            else:
                await self.unfreeze()
                mile_bonus = 0
            await self._conn.execute('update orders set processed =true where id = $1', self.order.id)
            return mile_bonus

    def create_receipt(self):
        receipt = kassa.models.Receipt(
            fn_number='214356612',  # todo заменить на реальные данные / rq
            date=datetime.datetime.strftime(self.order.created_date, FORMAT_DATE_TIME),
            # todo уточнить сюда - время создания или время оплаты
            organization_name='unknown',  # todo где брать? / ООО MileOnAir
            organization_inn="1234567899876",  # todo где брать? иннмилионера инн милеонера
            point_name='Шереметьево D1',  # todo вытаскивать из поинта? / MileonAir APP
            kkt_number='0000123',  # todo где брать? / 0000000
            operator='Хабибулина И.А.',  # todo / MileonAir APP
            type=0,
            amount=self.order.sum,
            url='',  # todo где брать? empty
            products=[kassa.models.Product(
                id=product.get('id'),
                name=product.get('name'),
                quantity=product.get('quantity'),
                price=0 if product.get('price') is None else product.get('price'),
                amount=0 if product.get('price') is None else product.get('price') * product.get('quantity')
            ) for product in self.products]
        )
        return receipt

    async def collect(self):
        data = kassa.models.CollectPostModel(
            transaction_uuid=self.order.uuid_relation,
            receipt=self.create_receipt()
        )
        await kassa.Collect.post(data)

    async def redeem(self):
        data = kassa.models.RedeemPutModel(
            transaction_uuid=self.order.uuid_relation,
            receipt=self.create_receipt()
        )
        await kassa.Redeem.put(data)

    async def unfreeze(self):
        data = kassa.models.UnfreezePostModel(
            transaction_uuid=self.order.uuid_relation,
        )
        await kassa.Unfreeze.post(data)

    async def get_mile_bonus(self):

        param = await self._conn.fetchval(
            'select mile_packets.mile_count '
            'from uuid_relations inner join '
            'mile_transactions  on uuid_relations.mile_transaction_id = '
            'mile_transactions.id inner join mile_packets on mile_packets.id = '
            'mile_transactions.mile_packet_id where '
            'uuid_relations.transactions_uuid =$1', self.order.uuid_relation)

        return param


@routes.view(QR_VALIDATOR)
class QrValidator(web.View):
    """
    @api {get} https://developer.mileonair.com/api/v1/QRValidator Проверка подписи qr кода

    @apiName qr validator
    @apiGroup QR
    @apiVersion 1.0.0

    @apiParam {string} redirect_url ссылка в теле qr
    @apiParam {string} hash подпись

    @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
    @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
    @apiSuccess (200) {dict} data  Словарь с данными

    @apiSuccess (200) {bool}  data.is_valid Резултьат проверки ссылки на валидность
    @apiSuccess (200) {bool}  [data.return_url] сыылка для перехода (возвращается только при is_valid=true)

    @apiSuccessExample {json} Success-Response:
        {
            "responseCode": 0,
            "responseMessage": "Запрос обработан успешно",
            "data": {
                "is_valid": true,
                "return_url": "https://www.bmsvend.ru/machines/aer1?hello=world&hello1=world1&
                pqr=94fd9b783a74807017bbbacaf3aaa640875306e83d944985306f4472e5107ae1"
            }
        }
    """

    async def get(self):
        redirect_url_str = self.request.query.get('redirect_url', '')
        signature = self.request.query.get('hash', '')
        url_is_valid = Signature(redirect_url_str).is_valid(signature)
        if url_is_valid:
            redirect_url = http_parser.URL(redirect_url_str)
            return_url = str(redirect_url.update_query(dict(pqr=self.request['pqr'])))
            raise ApiResponse(0, {"is_valid": True, "return_url": return_url})
        raise ApiResponse(0, {"is_valid": False})


class Signature:
    _key = config.qr_secret_key

    def __init__(self, message):
        self._message = message

    @property
    def message(self):
        return self._message

    @property
    def signature_hex(self):
        key = bytes(self._key, 'UTF-8')
        message = bytes(self._message, 'UTF-8')
        digester = hmac.new(key, message, hashlib.sha1)
        signature = digester.hexdigest()
        return signature

    def is_valid(self, signature):
        return self.signature_hex == signature
