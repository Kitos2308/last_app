import psycopg2
import pytest

from Test.tools_for_test import *
from utils import generate_number
from auth_model import config

@pytest.fixture(scope='session', autouse=True)
def session():
    s = requests.session()
    phone = '+7' + generate_number(10)
    s = register(s, phone)
    confirm(s)
    with open('token.txt', 'r', encoding='utf-8') as f:
        token = f.readline().strip()
    s = login(s, token)
    with open('cookeeeee', 'wb') as f:
        pickle.dump(s.cookies, f)
    yield s
    conn = psycopg2.connect(dbname=config.database.db_name, user=config.database.db_user,
                            password=config.database.db_pass, host='localhost')
    cursor = conn.cursor()
    cursor.execute(f"DELETE from profiles where phone_number = '{phone}';")
    conn.commit()
    cursor.close()
    conn.close()


@pytest.fixture(scope='function')
def set_balance_50(get_card):
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USR,
                            password=DB_PASSWORD, host='localhost')
    cursor = conn.cursor()
    cursor.execute(f"UPDATE cards SET money_balance = 50 WHERE number = '{get_card}';")
    conn.commit()
    cursor.close()
    conn.close()
    yield


@pytest.fixture(scope='function')
def set_miles_50(get_card):
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USR,
                            password=DB_PASSWORD, host='localhost')
    cursor = conn.cursor()
    cursor.execute(f"UPDATE profiles SET mile_count = 50 WHERE id = "
                   f"(select profile_id from cards where number = '{get_card}' limit 1);")
    conn.commit()
    cursor.close()
    conn.close()
    yield


@pytest.fixture(scope='class')
def get_card(session):
    url = URL + 'cards'
    number = None
    with session.get(url) as resp:

        response = resp.json()

        cards = response.get('data').get('cards')
        for card in cards:
            if card['number'] is not None:
                number = card['number']
                break
    yield number


@pytest.fixture(scope='function')
def profile(session):
    url = URL + 'profile'
    with session.get(url) as resp:
        response = resp.json()

        phone = response.get('data').get('phone_number')
        conn = psycopg2.connect(dbname=DB_NAME, user=DB_USR,
                                password=DB_PASSWORD, host='localhost')
        cursor = conn.cursor()
        cursor.execute(f"select id from profiles where phone_number = '{phone}';")
        profile_id = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        yield profile_id


@pytest.fixture(scope='function')
def add_order(session, profile):
    url = URL + 'order'

    json = {"partner_id": 56,
            "airport_id": 1,
            "cart_id": 2
            }
    with session.post(url, json=json) as resp:
        assert resp.status_code == 200
        response = resp.json()

        assert response.get('responseCode', None) == 0
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USR,
                            password=DB_PASSWORD, host='localhost')
    cursor = conn.cursor()
    cursor.execute(f"UPDATE orders SET paid = true WHERE profile_id = {profile};")
    conn.commit()
    cursor.close()
    conn.close()
    yield
