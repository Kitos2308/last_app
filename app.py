import argparse
import asyncio
import base64
import os
import traceback

import aiohttp_jinja2
import aiohttp_session
import aioredis
import jinja2
from aiohttp import web
from aiohttp_session import session_middleware
from aiohttp_session import setup
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from aiohttp_session.redis_storage import RedisStorage
from api_utils import ApiPool, Mail
from cryptography import fernet
from loguru import logger, _file_sink

import settings as s
import tools
from auth_model import DatabaseConfig, config
from confirm_email import create_views as create_confirm_email_views
from middlewares import auth_middleware, errors_middleware, context_middleware
from v1.privileges import create_views as create_privileges_views
from v1.superuser import create_views as create_superuser_views
from views import routes as view_routes
from views_ext import routes as view_ext_routes


def new_generate_rename_path(root, ext, _):
    dirpath, filename = os.path.split(root)
    files = os.listdir(dirpath)
    files = list(filter(lambda x: x.startswith(f'{filename}{ext}.') and x.split('.')[-1].isdigit(), files))

    files.sort(key=lambda x: -int(x.split('.')[-1]))
    for file in files:
        os.rename(os.path.join(dirpath, file),
                  os.path.join(dirpath, '.'.join([*file.split('.')[:-1], str(int(file.split('.')[-1]) + 1)]))
                  )
    renamed_path = "{}{}.{}".format(root, ext, 1)

    return renamed_path


_file_sink.generate_rename_path = new_generate_rename_path
pool = ApiPool

pool_settings = dict(
    host=s.DB_HOST,
    port=s.DB_PORT,
    user=s.DB_USER,
    password=s.DB_PASSWORD,
    database=s.DB_DATABASE,
    command_timeout=30,
    min_size=10,
    max_size=100,
    max_queries=20000,
    max_inactive_connection_lifetime=60
)


async def make_redis_pool():
    redis_address = s.REDIS_ADRESS
    return await aioredis.create_redis_pool(redis_address, timeout=1)


def construct_db_url(config: DatabaseConfig):
    DSN = "postgresql://{user}:{password}@{host}:{port}/{database}"
    return DSN.format(
        user=config.db_user,
        password=config.db_pass,
        database=config.db_name,
        host=config.db_host,
        port=config.db_port,
    )


async def close_pool(pool):
    try:
        if pool is not None:
            await pool.close()
    except Exception as exc:
        logger.error(f'Исключение при отключении от БД: {exc}')


def make_app():
    try:
        loop = asyncio.get_event_loop()

        app = web.Application(middlewares=[context_middleware, errors_middleware, auth_middleware],
                              client_max_size=50 * 10485760)

        res = tools.read_sys_params(app)

        redis_pool = loop.run_until_complete(make_redis_pool())
        storage = None
        if s.TYPE_SESSION_STORAGE == 0:
            storage = aiohttp_session.SimpleCookieStorage(cookie_name=s.REDIS_COOKIE_NAME, max_age=app[
                s.LIFE_TIME_SESSION])
        elif s.TYPE_SESSION_STORAGE == 1:
            # шифр.куки
            fernet_key = fernet.Fernet.generate_key()
            secret_key = base64.urlsafe_b64decode(fernet_key)
            storage = EncryptedCookieStorage(secret_key, cookie_name=s.REDIS_COOKIE_NAME,
                                             max_age=app[s.LIFE_TIME_SESSION])
        elif s.TYPE_SESSION_STORAGE == 2:
            storage = RedisStorage(redis_pool, cookie_name=s.REDIS_COOKIE_NAME, max_age=app[s.LIFE_TIME_SESSION])
        if storage is not None:
            app.middlewares.insert(0, session_middleware(storage))

        async def dispose_redis_pool(app):
            redis_pool.close()
            await redis_pool.wait_closed()

        # setup(app, storage)
        app.on_cleanup.append(dispose_redis_pool)

        setup(app, storage)
        app['storage'] = storage

        app.on_startup.append(on_start)
        app.on_shutdown.append(on_shutdown)

        # инициализация системных переменных
        # app[s.SP_SMS_STATUS] = s.SMS_ENABLE
        order_loader_path = os.path.join(os.path.join(os.path.dirname(__file__), 'static'), 'order')
        privileges_loader_path = os.path.join(os.path.join(os.path.dirname(__file__), 'static'), 'privileges')

        app.router.add_static(s.static_prefix + '/order', order_loader_path, name='order_status_loader')
        app.router.add_static(s.static_prefix + s.PRIVILEGES_ROUTE_PREF, privileges_loader_path,
                              name='privileges_loader')
        # logger.info(res)
        path_ = os.path.join(os.path.dirname(__file__), 'test_banner')
        app.router.add_static('/pre', path_, name='test_banner')
        # ===========================================================

        app.add_routes([*view_routes, *view_ext_routes])
        app.add_routes(create_privileges_views(s.PRIVILEGES_ROUTE_PREF))
        app.add_routes(create_superuser_views(s.ROUTE_PREF + '/admin_api'))
        app.add_routes(create_confirm_email_views(s.CONFIRM_EMAIL_ROUTE_PREF))

        for name, resource in app.router.named_resources().items():
            print(f'{name}, {resource}')
        return app
    except Exception as ex:
        print(f'Исключение в make_app: {ex}')
        logger.error(f'Исключение в make_app: {ex}')
        raise


async def on_start(app):
    await pool.create(s.POOL, **pool_settings)
    Mail.configure(True, config.mail.host, config.mail.password, config.mail.user, 587)
    # await init_db(app)
    # app[s.POOL] = await create_pool(s.POOL)
    # app[s.LOG_POOL] = await create_pool(s.LOG_POOL)


async def on_shutdown(app):
    await pool.close(s.POOL)
    # await close_pool(app[s.POOL])


def main():
    app = make_app()
    templates_path = os.path.join(s.BASE_DIR, "templates")

    aiohttp_jinja2.setup(
        app, loader=jinja2.FileSystemLoader(templates_path)
    )
    web.run_app(app, host=args.host, port=args.port)


def err_log_filter(message):
    if message.levelname == 'CRITICAL':
        return True
    else:
        return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='API Server. API server MileOnAir Loyalty Programs\n')
    parser.add_argument('host', nargs='?', default='127.0.0.1', help='IP adress of api server')
    parser.add_argument('-p', '--port', nargs='?', default='8080', help='listening port')
    args = parser.parse_args()


    def formatter(record):
        format_ = s.LOGURU_FORMAT
        if record["exception"] is not None:
            record["extra"]["stack"] = traceback.format_exc().replace('\n', ' & ')
            format_ += "TRACEBACK:  {extra[stack]}"
        return format_ + "\n"


    logger.add(
        s.LOG_FILE_NAME,
        format=formatter,
        level='DEBUG',
        rotation='30 MB',

        backtrace=False,
        catch=False,
        diagnose=False,
    )
    logger.opt(exception=False)
    logger.add(
        s.FULL_LOG_FILE_NAME,
        format=s.LOGURU_FORMAT,
        level='DEBUG',
        rotation='30 MB',
        backtrace=False,
    )

    with logger.contextualize(ip=None, moa_sid=None, method=None, path=None, phone=None):
        main()
