from functools import wraps
from json import JSONDecodeError

import jsonschema
from aiohttp import web
from loguru import logger
from pydantic import ValidationError, MissingError, ExtraError # NOQA
from pydantic.main import BaseModel

import tools
from api_utils import ApiResponse


class ApiView(web.View):

    def __init__(self, request):
        super().__init__(request)

        self.params = dict(request.query)
        self.user = request.get('user')
        self.json = None
        self.page = (20, 0)
        self.pool = tools.get_pool_from_request(request)
        self.language_code = self.request.get('locale', 'ru')
        self.session = tools.get_moa_sid_from_req(request)
        self.profile_id = self.request.get("profile_id")

    async def get_json_from_request(self):
        try:
            data = await self.request.json()
        except JSONDecodeError as exc:
            logger.error(f'Ошибка при декодировании JSON запроса: {exc}')
            raise ApiResponse(11)
        except Exception as exc:
            logger.error(f'Ошибка при обращении к JSON из запроса: {exc}')
            raise ApiResponse(14)
        if data is None:
            logger.error('Пустой JSON в запросе')
            raise ApiResponse(14)
        self.json = data
        return data

    def get_page(self):
        limit = int(self.params.get('limit', '20'))
        offset = int(self.params.get('offset', '0'))
        if limit <= 0 or offset < 0:
            raise ApiResponse(13)
        self.page = (limit, offset)


def login_required(func):
    @wraps(func)
    async def wrapper(instance):
        if instance.user is None:
            raise ApiResponse(22)
        return await func(instance)

    return wrapper


def validate(parameters, schema=None):
    if schema is None:
        schema = {"type": "object"}
    try:
        if schema is not None:
            jsonschema.validate(parameters, schema,
                                format_checker=jsonschema.FormatChecker(
                                    formats=['date', 'date-time', 'phone', 'email', 'digitstr', 'str_bool']))

    except jsonschema.exceptions.ValidationError as exc:
        if exc.validator == 'required':
            raise ApiResponse(12)
        if exc.validator == 'additionalProperties':
            raise ApiResponse(14)
        else:
            logger.debug(f'validation err: {exc}')
            raise ApiResponse(13)


def validate_apiview(parameters, schema):
    try:
        if isinstance(schema, dict) or isinstance(schema, list):
            jsonschema.validate(parameters, schema,
                                format_checker=jsonschema.FormatChecker(
                                    formats=['date', 'date-time', 'phone', 'email', 'digitstr', 'str_bool']))
        elif issubclass(schema, BaseModel):
            return schema(**parameters)
    except ValidationError as exceptions:
        for ex in exceptions.raw_errors:
            if isinstance(ex.exc, MissingError):
                raise ApiResponse(12)
        for ex in exceptions.raw_errors:
            if isinstance(ex.exc, ExtraError):
                raise ApiResponse(14)
        raise ApiResponse(13)
    except jsonschema.exceptions.ValidationError as exc:
        if exc.validator == 'required':
            raise ApiResponse(12)
        if exc.validator == 'additionalProperties':
            raise ApiResponse(14)
        else:
            raise ApiResponse(13)
