import codecs
import itertools
import operator
import os
import re
import secrets
from datetime import datetime, date
from random import choice
from typing import Union, Tuple, List

import jsonschema
from api_utils import ApiResponse, ApiPool
from asyncpg import Connection
from loguru import logger
from pydantic import BaseModel, ValidationError, MissingError, ExtraError

import tools
from alfa_bank.models import GetOrderStatusExtendedDataResponse
from tools import get_pool_from_request


def get_bool_param(request, name, required=True, default=False):
    param = request.query.get(name)
    if param is None:
        if required:
            raise ApiResponse(12)
        else:
            return default
    if param.lower() not in ['false', 'true', '0', '1']:
        raise ApiResponse(13)
    return param.lower() in ['true', '1']


def get_param(request, name, required=True, default=None):
    param = request.query.get(name, default)
    if param is None and required:
        raise ApiResponse(12)
    return param


async def get_language_id(request):
    pool = get_pool_from_request(request)
    async with pool.acquire() as conn:
        language_id = await conn.fetchval(f'select id from languages where code = $1;', request.get('locale'))
    return language_id


def get_page(request):
    limit = int(request.query.get('limit', '20'))
    offset = int(request.query.get('offset', '0'))
    if limit <= 0 or offset < 0:
        raise ApiResponse(13)
    return limit, offset


def group_data(data: list, group_keys, group_name: str):
    result = []
    by_value = operator.itemgetter(*group_keys)
    for key, group in itertools.groupby(sorted(data, key=by_value), by_value):
        if len(group_keys) > 1:
            result_item = dict(zip((*group_keys, group_name), (*key, [])))
        else:
            result_item = {group_keys[0]: key, group_name: []}
        for thing in group:
            for k in group_keys:
                thing.pop(k, None)
            result_item[group_name].append(thing)
        result.append(result_item)

    return result


def embed(data, keys, group_name):
    if data.get(group_name) is None:
        data[group_name] = {}
    for key in keys:
        data[group_name].update({key: data.pop(key)})
    return data


def convert_data(result, formatting_datetime=None, formatting_float=None):
    """
    Функция преобразования row или [row] в dict или [dict]
    Опционально форматирует типы данных такие как datetime или float
    Для форматирования дат и времени в текст в formatting_datetime передаётся формат
    Для форматирования чисел с плавающей запятой в formatting_float передаётся
        количество цифр поле запятой для форматирования всех чисел,
        словарь с кочличеством цифр после запятой по ключу "n" и списком ключей подлежащих форматированию
            по ключу "keys" для форматирования только конкретных полей
        словарь со словарём по ключу "keys" содержащим название поля и количество цыфр после запятой для этого поля

    """
    if result is None:
        return None
    elif isinstance(result, list):
        for i in range(len(result)):
            result[i] = convert_data(result[i], formatting_datetime, formatting_float)
    else:
        result = dict(result)
        if formatting_datetime or formatting_float:
            if isinstance(formatting_float, dict):
                if isinstance(formatting_float['keys'], dict):
                    for key in formatting_float['keys'].keys():
                        result[key] = to_fixed(result[key], formatting_float['keys'][key])
                elif isinstance(formatting_float['keys'], (set, tuple, list)):
                    for key in formatting_float['keys']:
                        result[key] = to_fixed(result[key], formatting_float['n'])
            for key in result.keys():
                if isinstance(formatting_float, int):
                    if formatting_float and isinstance(result[key], float):
                        result[key] = to_fixed(result[key], formatting_float)
                if formatting_datetime and (isinstance(result[key], (datetime, date))):
                    result[key] = datetime.strftime(result[key], formatting_datetime)

    return result


def to_fixed(obj, digits=2):
    return round(obj, digits)


def validate_data(data, schema):
    if data is None:
        return None
    try:
        if isinstance(schema, dict) or isinstance(schema, list):
            jsonschema.validate(data, schema,
                                format_checker=jsonschema.FormatChecker(
                                    formats=['date', 'date-time', 'phone', 'email', 'digitstr', 'str_bool']))
        elif issubclass(schema, BaseModel):
            return schema(**data)
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


async def validate_data_with_block(request, data, schema):
    try:
        jsonschema.validate(data, schema,
                            format_checker=jsonschema.FormatChecker(
                                formats=['date', 'date-time', 'phone', 'email', 'digitstr']))

    except jsonschema.exceptions.ValidationError as exc:
        logger.warning(f'validate_data_with_block: Сессия заблокирована, data={data} не соответствует схеме')
        await tools.set_blocked_session(request, True)
        raise ApiResponse(22)


def validate_data_pydantic(data, class_pydantic):
    try:
        result = class_pydantic(**data)
        return result
    except ValidationError as e:
        for error in e.errors():
            if error['msg'] == 'field required':
                raise ApiResponse(12)
            else:
                raise ApiResponse(13)


def generate_number(n: int = 16):
    chars = '1234567890'
    card_number = ''
    for i in range(n):
        card_number += choice(chars)
    return card_number


def to_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        raise ApiResponse(13)


def rename_field(row: dict, names: Union[Tuple[str, str], List[Tuple[str, str]]]):
    if isinstance(names, list):
        for name in names:
            row[name[1]] = row.pop(name[0])
    else:
        row[names[1]] = row.pop(names[0])
    return row


class RequestFileSaver:

    def __init__(self, form_name, upload_folder):
        self._form_name = form_name
        self._upload_folder = upload_folder

    async def save_files(self, request):
        post = await request.post()

        images = post.getall(self._form_name, [''])
        filenames = []
        if images != ['']:
            for image in images:
                if isinstance(image, bytearray):
                    filename = secrets.token_urlsafe(64) + '.jpg'
                    with open(os.path.join(self._upload_folder, filename)) as f:
                        f.write(image)
                else:
                    filename = secrets.token_urlsafe(64) + '.' + image.filename.split('.')[-1]
                    with open(os.path.join(self._upload_folder, filename), 'wb') as f:
                        f.write(image.file.read())
                    filenames.append(os.path.join(self._upload_folder, filename))
        return filenames


class DecodingStreamReader:
    def __init__(self, stream, encoding='utf-8', errors='strict'):
        self.stream = stream
        self.decoder = codecs.getincrementaldecoder(encoding)(errors=errors)

    async def read(self, n=-1):
        data = await self.stream.read(n)
        if isinstance(data, (bytes, bytearray)):
            data = self.decoder.decode(data)
        return data

    def at_eof(self):
        return self.stream.at_eof()


def get_redirect_url(request, is_success: bool, cashback=0):
    status = {
        True: 'success',
        False: 'failed'
    }
    path = request.app.router['payment_status'].url_for().with_query(dict(
        status=status[is_success],
        cashback=cashback
    ))
    url = str(request.url.origin().join(path)).replace('http://', 'https://')
    return url


def mask_pans(raw):
    if raw is None:
        return None
    return re.sub('[0-9]{6}\*\*[0-9]{4}', '######**####', str(raw))


async def save_email_for_receipts(confirmation_data: GetOrderStatusExtendedDataResponse, profile_id):
    conn: Connection
    try:
        email = confirmation_data.orderBundle.customerDetails.email
    except Exception as exc:
        logger.warning(f'{type(exc)}, {exc}')
        email = None
    if email is not None:
        async with ApiPool.get_pool().acquire() as conn:
            email_for_receipts = await conn.fetchval(
                'select email_for_receipts from profiles '
                'where profiles.id = $1',
                profile_id
            )
            if email_for_receipts is None or email_for_receipts == '':
                await conn.execute(
                    'update profiles set email_for_receipts = $1 where '
                    'id = $2',
                    email,
                    profile_id
                )