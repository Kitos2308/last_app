import aiohttp
from api_utils import ApiResponse
from loguru import logger

from settings import *


async def send_sms(request, phone, text_sms, sms_enable=True):
    addr = SMS_DOMEN
    error = None
    try:
        if request.app[SP_SMS_STATUS] and sms_enable:
            headers = {'Authorization': f'Bearer {config.sms_service.token}'}
            request_body = dict(phone=phone, text_sms=text_sms, text_comment='MOA-Register')
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(addr, headers=headers, json=request_body) as resp:
                        if resp is not None:
                            status = resp.status == 200
                            if status:
                                jsn = await resp.json()
                                data = jsn.get('data')
                                if data is not None:
                                    if dict(data).get('status', '') == 'OK':
                                        logger.info(f'Успешно! Sms-сервис вернул: {dict(data)}')
                                        return 1
                                    else:
                                        logger.error(f'SMS-сервис вернул: {dict(data)}')
                return 0
            except Exception as exc:
                logger.error(f'send_sms: Исключение: {exc}')
        else:
            message = f'send_sms: sms_enable={sms_enable}, request.app[SP_SMS_STATUS]={request.app[SP_SMS_STATUS]}' \
                      f' для phone={phone}, не отправляется, error_code={error}'
            if config.is_dev:
                logger.info(message)
            else:
                logger.error(message)
            return 1
    except ApiResponse:
        logger.error(f'send_sms: Исключение (phone={phone}), error_code={error}')
        raise
    except Exception as exc:
        logger.error(f'send_sms: Исключение (phone={phone}), error_code={error}: {exc}')
        raise ApiResponse(90, exc=exc)
    return 0

