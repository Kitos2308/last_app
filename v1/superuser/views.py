from asyncio import sleep
from datetime import datetime

from aiohttp import web
from api_utils import ApiResponse, ApiPool
from asyncpg import Connection
from loguru import logger
from pydantic import BaseModel

import alfa_bank
import pss
from tools import get_data_from_request
from user.models import User
from utils import validate_data


class BindCardView(web.View):
    class PostInputData(BaseModel):
        card_id: int

    @User.superuser_only
    async def post(self):
        conn: Connection

        data = await get_data_from_request(self.request)
        params = validate_data(data, self.PostInputData)
        async with ApiPool.get_pool().acquire() as conn:

            card_row = await conn.fetchrow('select * from premium_cards where id = $1', params.card_id)
            attempts = 0
            while True:
                attempts += 1
                confirmation_data = await alfa_bank.GetOrderStatusExtended.post(
                    alfa_bank.GetOrderStatusExtended.input_post_model(orderId=card_row.get('bank_order_id')),
                    raise_api_response=False)
                order_status = confirmation_data.order_status
                if order_status != 0 or attempts > 5:
                    break
                await sleep(1)
                attempts += 1

            customer_id = await conn.fetchval('select uid from profiles where id = $1', card_row.get('profile_id'))
            expire_date = datetime.strptime(confirmation_data.cardAuthInfo.expiration, '%Y%m')
            pss_j_model = pss.BindCard.input_post_model(
                customer_id=customer_id,
                masked_bin=confirmation_data.cardAuthInfo.maskedPan,
                expire_date=expire_date,
                holder_name=confirmation_data.cardAuthInfo.cardholderName,
                binding_id=confirmation_data.bindingInfo.bindingId,
                allow_duplicates=True
            )
            binding_response = await pss.BindCard.pss_post(pss_j_model)
            logger.debug(f'ответ от псс {binding_response}')

            if binding_response.code != 0:
                logger.debug(binding_response)
                if binding_response.code == 21:
                    logger.warning('у пользователя уже есть привязаные карты')
                    reason = 'у пользователя уже есть привязаные карты'
                elif binding_response.code == 13:
                    logger.warning('карта не премиальная')
                    reason = 'карта не премиальная'

                else:
                    logger.error(f'ответ от партнёрского сервиса не 0, а {binding_response.code}')
                    reason = f'Ошибка псс, код: {binding_response.code}'

                return ApiResponse(30, dict(reason=reason))
            else:
                # обновить хеш и тип карты
                await conn.execute('update premium_cards set type = $1, hash_value = $2 where id = $3',
                                   binding_response.data.get('card_type'),
                                   binding_response.data.get('hash_value'),
                                   params.card_id)

                await conn.execute('update premium_cards set active = true where id = $1',
                                   params.card_id)

        return ApiResponse(0, dict(status='success'))
