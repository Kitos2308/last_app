import pickle

import requests

from utils import generate_number
from Test.test_settings import *


def setup(s: requests.session()):
    try:
        with open('cookeeeee', 'rb') as f:
            s.cookies.update(pickle.load(f))
    except:
        s = register(s)
        confirm(s)
    try:
        with open('token.txt', 'r', encoding='utf-8') as f:
            token = f.readline().strip()
    except:
        s = register(s)
        s = confirm(s)
    try:
        get_profile_data(s)
    except:
        s = login(s, token)

    return s


def login(s: requests.session(), token):
    print({'token': token})
    url = URL + 'login'
    response_message = s.post(url,
                              json={'token': token,
                                    "deviceInfo": {},
                                    "locale": "ru"}
                              )
    print(url, response_message.json())
    return s


def register(s: requests.session(), phone):
    url = URL + 'register'
    request_body = {
        "phone": phone,
        "deviceInfo": {}
    }
    # assert self.s.get(url=url, json=request_body) == 200
    with s.post(url, json=request_body) as resp:
        assert resp.status_code == 200
        bank_response = resp.json()
        assert bank_response.get('responseCode', None) == 0
    return s


def confirm(s: requests.session()):
    url = URL + 'confirm'
    request_body = {
        "code": "22222"
    }
    # assert self.s.get(url=url, json=request_body) == 200
    with s.post(url, json=request_body) as resp:
        assert resp.status_code == 200
        bank_response = resp.json()
        response_message = bank_response.get('responseMessage', None)
        print(url, response_message)
        assert bank_response.get('responseCode', None) == 0
        data = bank_response.get('data', None)
        token = data.get('token')
        with open('token.txt', 'w', encoding='utf-8') as f:
            print(token, file=f)
    return s


def get_profile_data(s: requests.session()):
    url = URL + 'profile'
    with s.get(url) as resp:
        assert resp.status_code == 200
        jresp = resp.json()
        assert jresp.get('responseCode', None) == 0
    return jresp.get('data')


def compare_data_keys(d, example, opt_fields=()):
    if isinstance(d, list):
        for q in d:
            compare_data_keys(q, example[0], opt_fields)

    else:
        if d.keys() != example.keys():
            for dif in set(example.keys() - d.keys()):
                assert dif in opt_fields, (f'{dif}')
        for key in d.keys():
            if isinstance(d[key], (list)):
                for i in d[key]:
                    compare_data_keys(i, example[key][0], opt_fields)
            if isinstance(d[key], (dict)):
                compare_data_keys(d[key], example[key], opt_fields)
