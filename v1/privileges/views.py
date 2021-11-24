from asyncio import sleep
from datetime import datetime
from typing import Optional

from aiohttp import web
from api_utils import ApiResponse, ApiPool
from asyncpg import Connection
from loguru import logger
from pydantic import BaseModel

import alfa_bank
import pss
from alfa_bank.models import OrderBundle
from auth_model import config
from settings import IS_DEV_PREFIX, BIND_CARD_PREFIX
from tools import get_data_from_request
from utils import validate_data, mask_pans, save_email_for_receipts
from v1.privileges.models import CardsModel, CardModel


class BindCardView(web.View):
    async def post(self):
        """

        @api {post} https://developer.mileonair.com/api/v1/privileges/bindCard Привязать карту

        @apiName BindCard
        @apiGroup Привелегии
        @apiVersion 1.0.0

        @apiDescription попробовать привязать карту

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {string}      data.form_url Сылка на страницу оплаты
        @apiSuccess (200) {string}      data.redirect_url Ожидаемый редирект при успешной оплате
        При фактическом редиректе в параметрах запроса будут указаны
        status: [success/failed]
        errorCode: 0 - успешно
        errorCode: 13 - карта не премиальная
        errorCode: 21 - карта уже привязана
        errorCode: 30 - ну удалось провести оплату


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

        # создать запись в premium cards
        conn: Connection
        async with ApiPool.get_pool().acquire() as conn:
            cards_exist = await conn.fetchval('select count(*)>0 from premium_cards where profile_id=$1 and active',
                                              self.request.get('profile_id')
                                              )
            if cards_exist:
                logger.warning('карта уже привязана')
                return ApiResponse(21)
            card_id = await conn.fetchval('insert into premium_cards (profile_id, active) values ($1, $2) returning id',
                                          self.request.get('profile_id'),
                                          False
                                          )
            # создать заказ в альфе
            path = self.request.app.router['privileges_loader'].url_for(filename='index.html')
            url = str(self.request.url.origin().join(path).with_scheme('https'))
            logger.debug(url)
            bank_response = await self.create_preauth_order(card_id, url)
            # Обновить запись в premium cards
            await conn.execute('update premium_cards set bank_order_id =$1 where id=$2',
                               bank_response.order_id,
                               card_id)

        # вернуть урл
        redirect_url = self.request.url.origin().join(self.request.app.router['payment_status'].url_for())
        redirect_url = redirect_url.with_scheme('https')
        return ApiResponse(0, {'form_url': bank_response.formUrl, 'redirect_url': str(redirect_url)})
        # return ApiResponse(0, bank_response)

    async def create_preauth_order(self, card_id: int, return_url: str, amount: int = 100):
        language = self.request.get('locale').upper()
        alfa_language = language if language == 'RU' else 'EN'

        order_bundle = OrderBundle()
        order_bundle.add_item('card binding', 100, 'binding')

        request_params = alfa_bank.RegisterPreAuth.input_post_model(
            clientId=IS_DEV_PREFIX + str(self.request.get('profile_id')),
            orderNumber=IS_DEV_PREFIX + BIND_CARD_PREFIX + str(card_id),
            amount=amount,
            returnUrl=return_url,
            language=alfa_language,
            orderBundle=order_bundle
        )
        logger.debug(f'сформированы параметры запроса: {request_params}')
        response: alfa_bank.RegisterPreAuth.payment_response = await alfa_bank.RegisterPreAuth.post(
            request_params
        )
        return response


class ConfirmBindingView(web.View):
    class GetInputData(BaseModel):
        orderId: str

    async def get(self):
        conn: Connection
        async with ApiPool.get_pool().acquire() as conn:
            redirect_url = self.request.url.origin().join(self.request.app.router['payment_status'].url_for())

            try:

                params = validate_data(self.request.query, self.GetInputData)
                logger.debug(params)
                attempts = 0
                # получить инфу о заказе

                while True:
                    attempts += 1
                    confirmation_data: alfa_bank.GetOrderStatusExtended.payment_response = await alfa_bank.GetOrderStatusExtended.post(
                        alfa_bank.GetOrderStatusExtended.input_post_model(orderId=params.orderId), raise_api_response=False)
                    order_status = confirmation_data.order_status
                    await sleep(1)
                    if order_status != 0 or attempts > 5:
                        break
                    attempts += 1
                logger.debug(f'order = {mask_pans(confirmation_data)}')
                hold = order_status == 1
                confirmed = order_status != 0
                profile_id = await conn.fetchval(
                    'select profile_id from premium_cards where bank_order_id=$1',
                    params.orderId
                )

                await save_email_for_receipts(confirmation_data, profile_id)
                # сохранить в бд инфу о карте и заказе
                redirect_url = redirect_url.with_scheme('https')

                # if confirmed and hold:
                if confirmed:
                    await conn.execute(
                        'update premium_cards set order_confirmed = $1 where bank_order_id = $2',
                        confirmed,
                        params.orderId
                    )
                if confirmed and hold:
                    logger.debug("средсва заморожены")
                    profile_id = await conn.fetchval(
                        'update premium_cards set (masked_bin, order_paid, order_confirmed, binding_id) = '
                        '($1, $2, $3, $4) where bank_order_id = $5 returning profile_id',
                        confirmation_data.cardAuthInfo.maskedPan,
                        hold,
                        confirmed,
                        confirmation_data.bindingInfo.bindingId,
                        params.orderId
                    )

                    customer_id = await conn.fetchval('select uid from profiles where id = $1', profile_id)
                    expire_date = datetime.strptime(confirmation_data.cardAuthInfo.expiration, '%Y%m')
                    if config.is_dev:
                        await self._trash(confirmation_data.cardAuthInfo.cardholderName, redirect_url)
                    # отпраить запрос на привязку карты в псс
                    logger.debug(f'customer_id={customer_id}, maskedPan={confirmation_data.cardAuthInfo.maskedPan},'
                                 f'expire_date={expire_date}, bindingId={confirmation_data.bindingInfo.bindingId}'
                                 f'cardholderName={confirmation_data.cardAuthInfo.cardholderName}')
                    pss_j_model = pss.BindCard.input_post_model(
                        customer_id=customer_id,
                        masked_bin=confirmation_data.cardAuthInfo.maskedPan,
                        expire_date=expire_date,
                        holder_name=confirmation_data.cardAuthInfo.cardholderName,
                        binding_id=confirmation_data.bindingInfo.bindingId
                    )
                    logger.debug(pss_j_model)
                    binding_response = await pss.BindCard.pss_post(pss_j_model)
                    logger.debug(binding_response)

                    if binding_response.code != 0:
                        logger.debug(binding_response)
                        if binding_response.code == 21:
                            logger.warning('у пользователя уже есть привязаные карты')
                            return_url = str(redirect_url.update_query(dict(status='failed', errorCode=21)))

                        elif binding_response.code == 13:
                            logger.warning('карта не премиальная')
                            return_url = str(redirect_url.update_query(dict(status='failed', errorCode=13)))

                        else:
                            logger.error(f'ответ от партнёрского сервиса не 0, а {binding_response.code}')
                            return_url = str(redirect_url.update_query(dict(status='failed', errorCode=30)))
                            return ApiResponse(30, {"return_url": return_url})
                    else:
                        # обновить хеш и тип карты
                        await conn.execute('update premium_cards set type = $1, hash_value = $2 where bank_order_id = $3',
                                           binding_response.data.get('card_type'),
                                           binding_response.data.get('hash_value'),
                                           params.orderId)
                        return_url = str(redirect_url.update_query(dict(status='success', errorCode=0)))
                        await conn.execute('update premium_cards set active = true where bank_order_id = $1',
                                           params.orderId)
                else:
                    return_url = str(redirect_url.update_query(dict(status='failed', errorCode=30)))
                logger.debug(return_url)
            except Exception as exc:
                logger.error(exc)
                return_url = str(redirect_url.update_query(dict(status='failed', errorCode=30)))
                return ApiResponse(0, {"redirect_url": return_url})

            finally:
                # вернуть деньги
                alfa_response: alfa_bank.Reverse.payment_response = await alfa_bank.Reverse.post(
                    alfa_bank.Reverse.input_post_model(
                        orderId=params.orderId)
                )
                if alfa_response.errorCode == 0:
                    await conn.execute('update premium_cards set order_refunded = true where bank_order_id = $1',
                                       params.orderId)
                logger.debug(mask_pans(alfa_response))
        return ApiResponse(0, {"redirect_url": return_url})

    async def _trash(self, name, redirect_url):
        name = name.upper()
        logger.warning("обработка заглушек")
        if config.is_dev:
            names = dict(
                DIMA=0,
                PIRAT=13,
                LUCKY=21,
                OLD=30
            )
            logger.warning(f"{name}:{names.get(name)}")
            if name in names.keys():
                if names.get(name) == 0:
                    return
                elif names.get(name) == 13:
                    return_url = str(redirect_url.update_query(dict(status='failed', errorCode=13)))
                    raise ApiResponse(0, {"redirect_url": return_url})
                elif names.get(name) == 21:
                    return_url = str(redirect_url.update_query(dict(status='failed', errorCode=21)))
                    raise ApiResponse(0, {"redirect_url": return_url})
                elif names.get(name) == 30:
                    return_url = str(redirect_url.update_query(dict(status='failed', errorCode=30)))
                    raise ApiResponse(0, {"redirect_url": return_url})


class UnBindCardView(web.View):
    async def post(self):
        """
        @api {post} https://developer.mileonair.com/api/v1/privileges/unbindCard Отвязать карту

        @apiName UnBindCard
        @apiGroup Привелегии
        @apiVersion 1.0.0

        @apiDescription Отвязать карту

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа


        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
                {
                    "responseCode": 0,
                    "responseMessage": "Запрос обработан успешно"
                }
        """
        conn: Connection
        async with ApiPool.get_pool().acquire() as conn:
            cards_exist = await conn.fetchval('select count(*)>0 from premium_cards where profile_id=$1 and active',
                                              self.request.get('profile_id')
                                              )

            if cards_exist:
                card_row = await conn.fetchrow('select * from premium_cards where active and profile_id = $1',
                                               self.request.get('profile_id')
                                               )

                card = CardModel(**card_row)



                logger.debug(card)
                pss_j_model = pss.UnBindCard.input_post_model(hash_value=card.hash_value)

                request_params = alfa_bank.Unbind.input_post_model(
                    bindingId=card.binding_id
                )
                logger.debug(f'сформированы параметры запроса: {request_params}')
                response: alfa_bank.Unbind.payment_response = await alfa_bank.Unbind.post(
                    request_params
                )
                assert response.errorCode == 0 or response.errorCode == 2
                if response.errorCode == 2:
                    logger.info(f'связка {card.binding_id} уже неактивна')
                unbinding_response = await pss.UnBindCard.pss_post(pss_j_model)
                await conn.execute('update premium_cards set active = false where id = $1',
                                   card.id)
                logger.debug(unbinding_response)

        return ApiResponse(0)


class CardsView(web.View):
    async def get(self):
        """
        @api {get} https://developer.mileonair.com/api/v1/privileges/cards Получить список привязанных карт

        @apiName Cards
        @apiGroup Привелегии
        @apiVersion 1.0.0

        @apiDescription Получить список привязанных карт

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {list}   data.cards   Список параметров
        @apiSuccess (200) {int}   data.cards.id ID карты
        @apiSuccess (200) {string}   data.cards.masked_bin Маскированый бин
        @apiSuccess (200) {string}   data.cards.card_type Тип премиальности


        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
                {
                    "responseCode": 0,
                    "responseMessage": "Запрос обработан успешно"
                    data:{
                        "cards": [
                            {
                                "id": 1,
                                "masked_bin": '9876',
                                "type": "Platinum"
                            }
                        ]
                    }
                }
        """

        conn: Connection
        async with ApiPool.get_pool().acquire() as conn:
            cards_rows = await conn.fetch('select * from premium_cards where active and profile_id = $1',
                                          self.request.get('profile_id')
                                          )

        cards = CardsModel(cards=cards_rows)
        return ApiResponse(0, cards)


class CardPacketsView(web.View):
    async def get(self):
        """
        @api {get} https://developer.mileonair.com/api/v1/privileges/packets Получить список пакетов

        @apiName Packets
        @apiGroup Привелегии
        @apiVersion 1.0.0

        @apiDescription Получить список пакетов

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {list}   data.packets   Список пакетов привелегий
        @apiSuccess (200) {int}   data.packets.id ID пакета
        @apiSuccess (200) {int}   data.packets.count количество пакетов привелегий
        @apiSuccess (200) {int}   data.packets.remainder количество доступных пакетов привелегий
        @apiSuccess (200) {bool}   data.packets.paymentable необходимость оплатить предложение в пакете
        @apiSuccess (200) {dict}   data.packets.stock предложение
        @apiSuccess (200) {int}   data.packets.stock.id ID предложения
        @apiSuccess (200) {int}   data.packets.stock.amount Стоимость
        @apiSuccess (200) {string}   data.packets.stock.name Название
        @apiSuccess (200) {string}   data.packets.stock.image Картинка
        @apiSuccess (200) {string}   data.packets.stock.logo Логотип
        @apiSuccess (200) {string}   data.packets.stock.description Описание
        @apiSuccess (200) {string}   data.packets.stock.conditions_details Подробные условия
        @apiSuccess (200) {string}   data.packets.stock.conditions условия использования
        @apiSuccess (200) {string}   data.packets.stock.short_description Короткое описание
        @apiSuccess (200) {list}   data.packets.available_airports Доступные аэропорты



        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
                {
                    "responseCode": 0,
                    "responseMessage": "Запрос обработан успешно"
                    data:{
                    "packets": [
                        {
                            "id": 1,
                            "count": 4,
                            "remainder": 2,
                            "paymentable": True,
                            "stock": {
                                "id": 1,
                                "amount": 100,
                                "name": "Бесплатная упаковка багажа от PACK&FLY",
                                "image": "https://avatanplus.ru/files/resources/original/5c5472c912edc168a9e06176.png",
                                "logo": "https://icdn.lenta.ru/images/2016/09/28/13/20160928132250525/pic_a2090870bf42a3831d45297184f08d63.jpg",
                                "description": "4 бесплатные упаковки в год",
                                "conditions_details": "",
                                "conditions": "Чтобы получить привилегию – воспользуйтесь премиальной картой Visa. Стоимость покупки будет всего лишь 1 рубль. Акция действует до 30.09.21",
                            },
                            "available_airports": [
                                1,
                                14,
                                15
                            ]
                        }
                    ]
                }
        """
        conn: Connection
        async with ApiPool.get_pool().acquire() as conn:
            hash_value = await conn.fetchval(
                'select hash_value from premium_cards where profile_id = $1 and active',
                self.request.get('profile_id')
            )
            if hash_value is None:
                logger.warning("карта не найдена")
                return ApiResponse(21)
            logger.debug(f'получаем пакеты для {self.request.get("profile_id")}')
            pss_j_model = pss.CardPackets.input_post_model(
                hash_value=hash_value,
                language_code=self.request.get('locale')
            )
            response = await pss.CardPackets.pss_get(pss_j_model)
            logger.debug(f'получены пакеты {response.code}')
        if response.code != 0:
            logger.error(f'ответ от псс {response}')
            return ApiResponse(30)
        return ApiResponse(0, response.data)


class OrderView(web.View):
    async def post(self):
        """
        @api {post} https://developer.mileonair.com/api/v1/privileges/order Оформить заказ

        @apiName PostPOrder
        @apiGroup Привелегии
        @apiVersion 1.0.0

        @apiDescription Оформить заказ

        @apiParam {int} stock_id ID стока
        @apiParam {int} count количество
        @apiParam {int} packet_id ID пакета

        @apiParamExample {json} Request-Example:
            {
                "stock_id": 1,
                "count": 1,
                "packet_id": 1
            }

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными
        @apiSuccess (200) {list} data.orders  Словарь с данными

        @apiSuccess (200) {int} data.orders.id  Словарь с данными
        @apiSuccess (200) {bool} data.orders.active Заказ действительный
        @apiSuccess (200) {string} data.orders.name  название
        @apiSuccess (200) {string} data.orders.logo  Картинка
        @apiSuccess (200) {string} data.orders.description  Описание
        @apiSuccess (200) {string} data.orders.user_guide инструкция по использованию
        @apiSuccess (200) {string} data.orders.card_type  Тип карты
        @apiSuccess (200) {string} data.orders.qr  QR код
        @apiSuccess (200) {string} data.orders.expiration_date  срок истечения
        @apiSuccess (200) {string} data.orders.used_date  время использования
        @apiSuccess (200) {string} [data.orders.date]  !!! будет удалена



        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
                {
                    "responseCode": 0,
                    "responseMessage": "Запрос обработан успешно"
                    data: {
                        "orders": [
                            {
                                "id": 1,
                                "stock_id": 1,
                                "active": True,
                                "name": "Бесплатная упаковка багажа",
                                "logo": "url",
                                "description": "Чтобы получить бесплатную упаковку – покажите QR-код на кассе PACK&FLY",
                                "card_type": "Platinum|Signature|Infinite",
                                "qr": "1xef445th6556",
                                "expiration_date": "2021-09-30 23:59:59",
                                "used_date": null,
                                "date": "2021-09-30 23:59:59",
                                "user_guide": "Чтобы получить бесплатную упаковку - покажите QR-код сотруднику сервиса по упаковке багажа"
                            }
                        ]
                    }
                }
        """

        class InputModel(BaseModel):
            stock_id: int
            count: int
            packet_id: int

        data = await get_data_from_request(self.request)
        params: InputModel = validate_data(data, InputModel)
        logger.debug(params)
        pss_params = pss.PremOrder.input_post_model(
            stock_id=params.stock_id,
            language_code=self.request.get('locale'),
            customer_id=self.request.get('uid'),
            count=params.count,
            profile_phone=self.request.get('phone_number'),
            profile_fn=self.request.get('first_name'),
            profile_ln=self.request.get('last_name'))
        response = await pss.PremOrder.pss_post(pss_params)
        if response.code != 0:
            logger.error(response)
            return ApiResponse(30)
        return ApiResponse(0, response.data)


class OrdersView(web.View):
    async def get(self):
        """
        @api {get} https://developer.mileonair.com/api/v1/privileges/orders Список заказ

        @apiName Заказы
        @apiGroup Привелегии
        @apiVersion 1.0.0

        @apiDescription Получить список заказов

        @apiParam {bool} [active] только дейсвующие заказы игнорировать для отображения всех всех

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа
        @apiSuccess (200) {dict} data  Словарь с данными

        @apiSuccess (200) {int} data.orders.id  Словарь с данными
        @apiSuccess (200) {bool} data.orders.active Заказ действительный
        @apiSuccess (200) {string} data.orders.name  название
        @apiSuccess (200) {string} data.orders.logo  Картинка
        @apiSuccess (200) {string} data.orders.description  Описание
        @apiSuccess (200) {string} data.orders.user_guide инструкция по использованию
        @apiSuccess (200) {string} data.orders.card_type  Тип карты
        @apiSuccess (200) {string} data.orders.qr  QR код
        @apiSuccess (200) {string} data.orders.expiration_date  срок истечения
        @apiSuccess (200) {string} data.orders.used_date  время использования
        @apiSuccess (200) {string} [data.orders.date]  !!! будет удалена



        @apiSuccessExample Success-Response:
            HTTP/1.1 200 OK
                {
                    "responseCode": 0,
                    "responseMessage": "Запрос обработан успешно"
                    data:{
                        "orders": [
                            {
                                "id": 1,
                                "active": True,
                                "name": "Бесплатная упаковка багажа",
                                "logo": "url",
                                "description": "Чтобы получить бесплатную упаковку – покажите QR-код на кассе PACK&FLY",
                                "card_type": "Platinum|Signature|Infinite",
                                "qr": "1xef445th6556",
                                "expiration_date": "2021-09-30 23:59:59",
                                "used_date": null,
                                "date": "2021-09-30 23:59:59",
                                "user_guide": "Чтобы получить бесплатную упаковку - покажите QR-код сотруднику сервиса по упаковке багажа"
                            }
                        ]
                    }
        """

        class InputModel(BaseModel):
            active: Optional[bool]

        params = validate_data(self.request.query, InputModel)

        pss_params = pss.PremOrders.input_post_model(
            language_code=self.request.get('locale'),
            customer_id=self.request.get('uid'),
            active=params.active
        )
        response = await pss.PremOrders.pss_get(pss_params)
        if response.code != 0:
            logger.error(response)
            return ApiResponse(30)
        return ApiResponse(0, response.data)
