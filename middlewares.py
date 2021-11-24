from asyncio import CancelledError

from aiohttp import web
from aiohttp_session import get_session, new_session
from api_utils import ApiResponse
from loguru import logger

import tools
from settings import *
from states import Context, Unauthorized, Authorized, Unconfirmed, Confirmed

# from utils import prepare_json
from user.models import User

log_types = {
    0: logger.info,
    10: logger.debug,
    11: logger.debug,
    12: logger.warning,
    13: logger.debug,
    14: logger.debug,
    20: logger.debug,
    21: logger.warning,
    22: logger.warning,
    30: logger.error,
    31: logger.error,
    90: logger.error,
}


async def auth_middleware(app, handler):  # NOQA
    async def middleware(request):
        if request.path in ROUTES_SHARE or any(map(request.path.startswith, ROUTES_STATIC)):
            return await handler(request)

        # получаем сессию
        session = await get_session(request)
        state = Unauthorized()
        # если сессия есть и неактивна - создаём новую с новым моа сид
        session_is_active = await tools.session_is_active(request)
        if session_is_active is None:
            logger.error(f'middleware: сессии в БД нет с таким моа сид')
            await tools.renew_moa_in_coockie(request)
        if not session_is_active:
            logger.debug(f'middleware: сессия есть и неактивна')
            session.clear()
            raise ApiResponse(20)
        await tools.update_lifetime_session(request)
        # получаем данные профиля
        await tools.get_dev_prof(request)
        user = User.get()
        phone = request.get('phone_number', None)
        with logger.contextualize(phone=phone):
            # проверяем наличие устройств
            have_devices = await tools.have_devices(request)
            # проверяем наличие профилей
            have_profile = await tools.have_profile(request)
            need_to_fill_profile = None
            if have_profile:
                if not have_devices:
                    need_to_fill_profile = await tools.check_need_to_fill_profile(request, None)
                    if user.active and need_to_fill_profile:
                        state = Confirmed()
                    else:
                        state = Unconfirmed()
                else:
                    if user.active:
                        state = Authorized()
            context = Context(state)
            logger.debug(f'middleware: have_profile={have_profile}, профиль profile_active={user.active}, '
                         f'have_devices={have_devices}, need_to_fill_profile={need_to_fill_profile}, status: {state}')
            check_permission = context.get_permission_checker(request)
            check_permission(request)
            return await handler(request)

    return middleware


async def context_middleware(_, handler):
    async def middleware(request):
        ip_client = tools.get_ip_from_request(request)
        with logger.contextualize(method=request.method, ip=ip_client, path=request.path):
            await tools.have_any_problem(request, ip_client)
            session = await get_session(request)
            if not session.new:
                # если сессия не новая
                # обновляем срок жизни сессии в хранилище
                moa_sid = session['moa_sid'] if 'moa_sid' in session else None
                identity = session.identity
                del session
                session = await new_session(request)
                session.set_new_identity(identity)
                await tools.set_moa_sid_in_coockie(request, moa_sid)
                request['moa_sid'] = moa_sid
            else:
                # если сессия новая - создаём её
                logger.debug(f'middleware: сессия новая')
                await tools.renew_moa_in_coockie(request)
                moa_sid = session['moa_sid'] if 'moa_sid' in session else None
            with logger.contextualize(moa_sid=moa_sid):

                return await handler(request)

    return middleware


async def errors_middleware(app, handler):  # NOQA

    async def middleware(request):
        # return await handler(request)
        resolve = await app.router.resolve(request)
        if resolve.http_exception:
            raise resolve.http_exception
        overrides = {
            # 200: get_err_handler(0),
            # 404: 10,
            405: 10,
            500: 90
        }

        try:
            response = await handler(request)

            override = overrides.get(response.status)
            if override:
                raise ApiResponse(override)
            return response
        except ApiResponse as exc:
            handle_api_response(request, exc)
            # log_message = str(exc.log_message).replace('\n', ' & ')
            # if isinstance(exc, CancelledError):
            #     raise exc
            # exception = str(exc.exc).replace('\n', ' & ')
            # tr = None
            # if exc.code != 0 and exc.exc is not None:
            #     tr = traceback.format_exc().replace('\n', ' & ')
            # tools.do_write_log(f'код ответа: {exc.code}, message: {log_message} exc:{exception} tb:{tr}',
            #                    log_types[exc.code], request)
            # raise
        except web.HTTPFound:
            raise
        except web.HTTPException as exc:
            override = overrides.get(exc.status)
            if override:
                raise ApiResponse(override, exc=exc)
            raise
        except Exception as exc:
            handle_api_response(request, exc)

    return middleware


def handle_api_response(request, exc):
    if isinstance(exc, CancelledError):
        raise exc
    if isinstance(exc, ApiResponse):
        log_message = str(exc.log_message).replace('\n', ' & ')
        if exc.code == 0:
            log_types[exc.code](f'message: {log_message}, код ответа: {exc.code}')
            raise exc
        if exc.code != 0 and isinstance(exc.exc, ApiResponse):
            log_types[exc.code](f'код ответа: {exc.code} and exc.exc={exc.exc} ->recurs-> handle_api_response(), '
                               f'message: {exc.log_message}')
            handle_api_response(request, exc.exc)

        log_types[exc.code](f'код ответа: {exc.code}, message_: {log_message}')
        raise exc
    logger.exception(exc)
    raise ApiResponse(90)
