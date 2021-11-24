import re
from datetime import datetime

import jsonschema

from settings import FORMAT_DATE_TIME, FORMAT_DATE

BOOL_STR = {"type": "string", "format": "str_bool"}
POST_FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "email": {"type": "string",
                  "format": "email"},
        "message": {"type": "string"}
    }
}
POST_QR_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string"}
    },
    "required": ["code"],
    "additionalProperties": False
}
POST_SETTINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "language_id": {"type": "integer"}
    }
}

POST_GEO_SCHEMA = {
    "type": "object",
    "properties": {
        "lat": {"type": "number"},
        "long": {"type": "number"},
        "token": {"type": "string"}

    },
    "required": ["lat", "long", "token"],
    "additionalProperties": False
}

GET_BALANCE_SCHEMA = {
    "type": "object",
    "properties": {
        "number": {"type": "string",
                   "format": "digitstr"}
    }
}

CONVERSION_SCHEMA = {
    "type": "object",
    "properties": {
        "count": {"type": "integer"},
        "number": {"type": "string",
                   "format": "digitstr"}
    }
}

GET_TRANSACTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "card_number": {"type": ["string", "integer"]},
        "mile_count": {"type": "integer"}
    }
}
UPDATE_PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "first_name": {"type": "string"},
        "last_name": {"type": "string"},
        "patronymic": {"type": "string"},
        "appeal_type_id": {"type": "integer"},
        "birth_date": {"type": "string",
                       "format": "date-time"},
        "phone_number": {"type": "string",
                         "format": "phone"},
        "email": {"type": "string",
                  "format": "email"},
        "user_status_id": {"type": "integer"}
    }
}

GET_ONPASS_POINT_SCHEMA = {
    "type": "object",
    "properties": {
        "point_id": {"type": "string",
                     "format": "digitstr"}
    },
    "required": ["point_id"],
    "additionalProperties": False
}

GET_ONPASS_POINTS_IN_AIRPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "airport_id": {"type": "string"},
        "testing": {"type": "string"},
        "purchased": BOOL_STR,
    },
    # "required": ["airport_id"],
    "additionalProperties": False
}
POST_ORDERS_SCHEMA = {
    "type": "object",
    "properties": {
        "partner_id": {"type": "integer", "minimum": 1},
        "airport_id": {"type": "integer", "minimum": 1},
        "cart_id": {"type": "integer", "minimum": 1},
        "products": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "minimum": 1},
                    "quantity": {"type": "integer", "minimum": 1}

                },
                "required": ["id", "quantity"],
                "additionalProperties": False
            }
        },
        "payment_service":{"type": "string"},
        "payment_token":{"type": "string"}
    },
    "required": ["partner_id", "airport_id"],
    "additionalProperties": False
}

POST_ONPASS_ORDERS_SCHEMA = {
    "type": "object",
    "properties": {
        "cart_id": {"type": "integer", "minimum": 1},
        "products": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "minimum": 1},
                    "quantity": {"type": "integer", "minimum": 1}
                },
                "required": ["id", "quantity"],
                "additionalProperties": False
            }
        },
        "payment_service":{"type": "string"},
        "payment_token":{"type": "string"}
    },
    "additionalProperties": False
}
GET_PARTNERS_IN_CITY_SCHEMA = {

    "type": "object",
    "properties": {
        "city_id": {"type": "string", "format": "digitstr"},
        "category_id": {"type": "string", "format": "digitstr"},
        "limit": {"type": "string", "format": "digitstr"},
        "offset": {"type": "string", "format": "digitstr"},
        "testing": BOOL_STR

    },
    "required": ["city_id"],
    "additionalProperties": False
}

GET_PARTNERS_IN_AIRPORT_SCHEMA = {

    "type": "object",
    "properties": {
        "airport_id": {"type": "string", "format": "digitstr"},
        "category_id": {"type": "string", "format": "digitstr"},
        "limit": {"type": "string", "format": "digitstr"},
        "offset": {"type": "string", "format": "digitstr"},
        "testing": BOOL_STR

    },
    "required": ["airport_id"],
    "additionalProperties": False
}

GET_PARTNERS_RELEVANT_SCHEMA = {

    "type": "object",
    "properties": {
        "category_id": {"type": "string", "format": "digitstr"},
        "limit": {"type": "string", "format": "digitstr"},
        "offset": {"type": "string", "format": "digitstr"},
        "testing": BOOL_STR

    },
    "additionalProperties": False
}

GET_STOCKS_SCHEMA = {

    "type": "object",
    "properties": {
        "airport_id": {"type": "string", "format": "digitstr"},
        "partner_id": {"type": "string", "format": "digitstr"},
        "limit": {"type": "string", "format": "digitstr"},
        "offset": {"type": "string", "format": "digitstr"},
        "active": BOOL_STR

    },
    "required": ["airport_id"],
    "additionalProperties": False
}

GET_ORDERS_SCHEMA = {

    "type": "object",
    "properties": {
        "limit": {"type": "string", "format": "digitstr"},
        "offset": {"type": "string", "format": "digitstr"},
        "active": BOOL_STR
    },
    "required": ["active"],
    "additionalProperties": False
}
GET_ONPASS_STOCKS_SCHEMA = {

    "type": "object",
    "properties": {
        "airport_id": {"type": "string", "format": "digitstr"},
        "limit": {"type": "string", "format": "digitstr"},
        "offset": {"type": "string", "format": "digitstr"},
        "point_id": {"type": "string", "format": "digitstr"},
        "active": BOOL_STR

    },
    # "required": ["airport_id"],

    "additionalProperties": False
}

GET_STOCK_SCHEMA = {
    "type": "object",
    "properties": {
        "airport_id": {"type": "string", "format": "digitstr"},
        "stock_id": {"type": "string", "format": "digitstr"},
        "active": BOOL_STR

    },
    "required": ["airport_id", "stock_id"],
    "additionalProperties": False

}

DEVICE_INFO_SCHEMA = {
    "type": "object",
    "properties": {
        "geoAccuracyPermission": {"type": "string"},
        "instance_id": {"type": "string"},
        "ip_address": {"type": "string"},
        "os": {"type": "string"},
        "fcm_token": {"type": "string"},
        "os_version": {"type": "string"},
        "locale": {"type": "string"},
        "device_model": {"type": "string"},
        "geo_permission": {"type": "string"},
        "push_permission": {"type": "string"},
        "app_version": {"type": "string"}
    }, #"ip_address", , "fcm_token"
    "required": ["instance_id", "os", "os_version", "device_model", "locale", "geo_permission", "push_permission"],
    "additionalProperties": False
}


@jsonschema.FormatChecker.cls_checks("digitstr")
def _validate_digitstr_format(instance):
    try:
        if not instance.isdigit():
            raise ValueError
        if int(instance) < 0:
            raise ValueError
    except (ValueError, Exception):
        return False
    else:
        return True


@jsonschema.FormatChecker.cls_checks("str_bool")
def _validate_str_bool_format(instance):
    try:
        if instance.lower() not in ['false', 'true', '1', '0']:
            raise ValueError
    except (ValueError, Exception):
        return False
    else:
        return True


@jsonschema.FormatChecker.cls_checks('date-time')
def _validate_datetime_format(instance):
    try:
        datetime.strptime(instance, FORMAT_DATE)
        return True
    except ValueError:
        try:
            datetime.strptime(instance, FORMAT_DATE_TIME)
        except ValueError:
            return False
        except Exception:
            return False
        else:
            return True


@jsonschema.FormatChecker.cls_checks('phone')
def _validate_phone_format(instance):
    try:
        if not re.match(r'^((8|\+7)[\- ]?)?(\(?\d{3}\)?[\- ]?)?[\d\- ]{7,10}$', instance):
            raise ValueError
    except ValueError:
        return False
    except Exception:
        return False
    else:
        return True


EMPTY_SCHEMA = {"type": "object"}
