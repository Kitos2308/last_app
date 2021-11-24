import os
import os.path

import pytoml as toml
from auth_model import config
from confirm_email.urls import CONFIRM_EMAIL

BASE_DIR = os.path.dirname(__file__)
PACKAGE_NAME = 'bs_api'


def load_config(path):
    with open(os.path.join(BASE_DIR, path)) as f:
        conf = toml.load(f)
    return conf


# ===============
SMS_ENABLE = False  # помимо отключения отправки смс отключена генерация рандомного кода, всегда = 22222
SMS_SENDER = 'MILEONAIR'
SMS_DOMEN = config.sms_service.url

# ============ ROUTES
ROUTE_PREF = '/api/v1'
PRIVILEGES_ROUTE_PREF = ROUTE_PREF +'/privileges'
CONFIRM_EMAIL_ROUTE_PREF = ROUTE_PREF +'/email'
# ------- GET+POST routes
ROUTE_PROFILE = f'{ROUTE_PREF}/profile'

# ------- GET routes
ROUTE_ROOT = f'{ROUTE_PREF}/'
ROUTE_UPDATE_CARDS_INFO = f'{ROUTE_PREF}/updateCardsInfo'
ROUTE_BALANCE = f'{ROUTE_PREF}/balance'
ROUTE_TRANSACTIONS = f'{ROUTE_PREF}/transactions'
ROUTE_CARDS = f'{ROUTE_PREF}/cards'
ROUTE_NOTIFICATIONS = f'{ROUTE_PREF}/notifications'
ROUTE_FAQ = f'{ROUTE_PREF}/faq'
ROUTE_AIRPORTS = f'{ROUTE_PREF}/airports'
ROUTE_PARTNER_CATEGORIES = f'{ROUTE_PREF}/partnerCategories'
ROUTE_PARTNERS_AIRPORTS = f'{ROUTE_PREF}/partnersInAirport'
ROUTE_PARTNERS_CITIES = f'{ROUTE_PREF}/partnersInCity'
ROUTE_PARAMETERS = f'{ROUTE_PREF}/parameters'
ROUTE_HASHES = f'{ROUTE_PREF}/hashes'
ROUTE_LANGUAGES = f'{ROUTE_PREF}/languages'
ROUTE_PARTNERS_RELEVANT = f'{ROUTE_PREF}/partnersRelevant'
ROUTE_CITIES = f'{ROUTE_PREF}/cities'
ROUTE_INFO = f'{ROUTE_PREF}/info'
ROUTE_LOGGER = f'{ROUTE_PREF}/logs_f6D23iw'
ROUTE_RELOAD_PARAMS = f'{ROUTE_PREF}/reloadParams'
ROUTE_STOCKS = f'{ROUTE_PREF}/stocks'
ROUTE_ORDERS = f'{ROUTE_PREF}/orders'
ROUTE_CUSTOM_STOCKS = f'{ROUTE_PREF}/customStocks'
ROUTE_STOCK = f'{ROUTE_PREF}/stock'
ROUTE_CUSTOM_STOCK = f'{ROUTE_PREF}/customStock'
ROUTE_ONPASS = f'{ROUTE_PREF}/onpass/types'
ROUTE_ONPASS_ORDER = f'{ROUTE_PREF}/onpass/order'
ROUTE_ONPASS_POINT = f'{ROUTE_PREF}/onpass/point'
ROUTE_ONPASS_POINTS = f'{ROUTE_PREF}/onpass/points'
ROUTE_ONPASS_POINTS_IN_AIRPORT = f'{ROUTE_PREF}/onpass/pointsInAirport'
ROUTE_ONPASS_STOCKS = f'{ROUTE_PREF}/onpass/stocks'
ROUTE_PRODUCTS = f'{ROUTE_PREF}/products'
ROUTE_PRODUCT = f'{ROUTE_PREF}/product'
# = f'{ROUTE_PREF}/onpass/products'
ROUTROUTE_ONPASS_ORDERS = f'{ROUTE_PREF}/onpass/orders'

ROUTE_CONFIG = f'{ROUTE_PREF}/config'
ROUTE_SUP_LANGUAGES = f'{ROUTE_PREF}/supportedLanguages'
ROUTE_COUNTRIES = f'{ROUTE_PREF}/countries'
ROUTE_TEST_ = f'{ROUTE_PREF}/test_'
ROUTE_BANNER = f'{ROUTE_PREF}/banner'
ROUTE_BANNERS = f'{ROUTE_PREF}/banners'
ROUTE_BANNERS_CATEGORIES = f'{ROUTE_PREF}/banner_categories'
ROUTE_PARTICIPANT_PROMO = f'{ROUTE_PREF}/participateInPromotion'


# ------- POST routes
ROUTE_REGISTER = f'{ROUTE_PREF}/register'
ROUTE_CONFIRM = f'{ROUTE_PREF}/confirm'
ROUTE_LOGIN = f'{ROUTE_PREF}/login'
ROUTE_LOGOUT = f'{ROUTE_PREF}/logout'
ROUTE_CARD_ISSUE = f'{ROUTE_PREF}/cardIssue'
ROUTE_CONVERSION = f'{ROUTE_PREF}/conversion'
ROUTE_SETTINGS = f'{ROUTE_PREF}/settings'
ROUTE_FEEDBACK = f'{ROUTE_PREF}/feedback'
ROUTE_REMOVE_PROFILE = f'{ROUTE_PREF}/removeProfile'
ROUTE_QR = f'{ROUTE_PREF}/qr'
ROUTE_PROMOTIONS = f'{ROUTE_PREF}/promotions'
ROUTE_GEO = f'{ROUTE_PREF}/geo'
ROUTE_ORDER = f'{ROUTE_PREF}/order'
ROUTE_CUSTOM_ORDER = f'{ROUTE_PREF}/customOrder'
WALLET_CARD = f'{ROUTE_PREF}/walletCard'
POPUP_BANNER = f'{ROUTE_PREF}/popup_banners'
# test = f'{ROUTE_PREF}/test'

CONFIRM_BINDING_URL = '/confirmBinding'

PAY_WEB = f'{ROUTE_PREF}/payWeb'
PAY_APPLE = f'{ROUTE_PREF}/payApple'
PAY_GOOGLE = f'{ROUTE_PREF}/payGoogle'
PAY_SAMSUNG = f'{ROUTE_PREF}/paySamsung'

CONFIRM_PAY = f'{ROUTE_PREF}/confirmPay'

REDIRECT_ENDPOINT = '/paymentResult'
QR_VALIDATOR = f'{ROUTE_PREF}/QRValidator'
static_prefix = '/static'

REDIRECT_TEST_BANNER = f'{ROUTE_PREF}/test_redirect_banner'
# ----------
ROUTES_SHARE = [ROUTE_AIRPORTS, ROUTE_PARTNER_CATEGORIES, ROUTE_LANGUAGES, ROUTE_CITIES, ROUTE_ROOT, ROUTE_LOGGER,
                ROUTE_PARAMETERS, ROUTE_GEO, ROUTE_RELOAD_PARAMS, ROUTE_INFO, ROUTE_CONFIG,
                ROUTE_SUP_LANGUAGES, ROUTE_HASHES, ROUTE_COUNTRIES, '/static/onpass_logo.svg', CONFIRM_PAY,
                REDIRECT_ENDPOINT,
                PRIVILEGES_ROUTE_PREF+CONFIRM_BINDING_URL,
                CONFIRM_EMAIL_ROUTE_PREF+CONFIRM_EMAIL,
                REDIRECT_TEST_BANNER
                 ]
ROUTES_STATIC = [static_prefix]

# =====================
# deviceInfo пишущиеся ключи

DEVICE_INFO_LIST = ['instance_id', 'ip_address', 'os', 'os_version', 'device_model', 'locale', 'fcm_token',
                    'geo_permission', 'push_permission']
DEVICE_INFO_NOT_USING = ['locale', ]

# ==========LOG TYPES

TYPE_OF_LOGGING = 1  # 0 - логирование отключено, 1 - на диск, 2 - в БД, 3 - на диск и в БД
LOGGING_TYPE = 'logging_type'

LOG_MAX_BYTES = 30000000  # количество байт логов на один файл
LOG_BACKUP_COUNT = 50  # количество файлов ротационных логов

LOG_FILE_NAME = os.path.dirname(os.path.realpath(__file__)) + '/log/bs_api.log'
FULL_LOG_FILE_NAME = os.path.dirname(os.path.realpath(__file__)) + '/log/full_bs_api.log'
LOG_FORMAT = '%(asctime)s,%(msecs)d: %(levelname)s: %(message)s'
LOGURU_FORMAT = '{time:YYYY-MM-DD HH:mm:ss.SSS}: {level}: {extra[ip]}: {extra[moa_sid]}: {extra[method]}: ' \
                '{extra[path]}: {extra[phone]}: {message}'

VERBOSE = 3

# ================ coockie managed
REDIS_ADRESS = config.redis.url
REDIS_DB_CODES = 1
REDIS_DB_GSID = 2
REDIS_DB_TSID = 3

REDIS_COOKIE_NAME = 'session_id'
TYPE_SESSION_STORAGE = 2  # 0 - simple_coockie, 1 - encrypted_cookie, 2 - redis
# ====== RESPONSES===
SESSION_TOKEN = 'token'

# ======  system_parameters======
CONFIRMATION_CODE_LIFETIME = 'confirmation_code_lifetime'
LIFE_TIME_LONG_TOKEN = 'long_token_lifetime'
LIFE_TIME_SESSION = 'session_lifetime'
TYPE_OF_LOGGING_SYS = 'type_of_logging'
SP_SMS_STATUS = 'sms_enable'

RESOURCE_URL = 'resource_server_url'

# если в базе отсутствую константы, учитываются следующие:
LOC_CONFIRMATION_CODE_LIFETIME = 60
LOC_LIFE_TIME_LONG_TOKEN = 720
LOC_LIFE_TIME_SESSION = 900

# ==========================
IS_DEV_PREFIX = 'dev.' if config.is_dev else ''
ORGANISATION_NAME = 'Organization' if config.is_dev else config.organization_name
POINT_NAME = 'Point' if config.is_dev else config.point_name
KASSA_CONFIRM_CODE = 2222 if config.is_dev else config.kassa_service.confirm_code
MOA_ORDER_PREFIX = 'MOA.'

POOL = 'root'
LOG_POOL = 'log_pool'
# CURRENT_TIMEZONE = 'Europe/Moscow'

FORMAT_DATE = '%Y-%m-%d'
FORMAT_DATE_TIME = '%Y-%m-%d %H:%M:%S'

DB_HOST = config.database.db_host  # 'hulk.mileonair.com'
DB_PORT = config.database.db_port
DB_DATABASE = config.database.db_name
DB_USER = config.database.db_user
DB_PASSWORD = config.database.db_pass

DATABASE_LOCAL = {
    'dbname': config.database.db_name,
    'user': config.database.db_user,
    'password': config.database.db_pass,
    'host': config.database.db_host,
    'port': config.database.db_port,
}

DATABASE_LOG = {
    'dbname': config.log_database.db_name,
    'user': config.log_database.db_user,
    'password': config.log_database.db_pass,
    'host': config.log_database.db_host,
    'port': config.log_database.db_port,
}

RESPONSE_CODE = 'responseCode'
RESPONSE_MESSAGE = 'responseMessage'
RESPONSE_DATA = 'data'
RESPONSE_STATUS = 200
RESPONSE_NOT_FOUND = 404

# Стас
# Настройки для стороннего банка
MAX_CARDS_COUNT = 3

MAIL_PARAMS = {'TLS': True,
               'host': config.mail.host,
               'password': config.mail.password,
               'user': config.mail.user,
               'port': 587}

MAIL_RECEIVER = config.mail.receiver

FEEDBACK_IMAGES_FOLDER = config.feedback_images_folder

LOG_NAME = "Event log of bs_api module"

ONPASS_CATEGORY_ID = 4
ONPASS_BRAND_ID = 2
ONPASS_BRAND_TAG = 'onpass'

EXP_ORDER_DAYS = 365


BIND_CARD_PREFIX = 'TEMP_BINDING_ORDER.'
