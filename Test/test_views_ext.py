import Test.tools_for_test as t
import utils
from Test.test_settings import *


class Test_get_profile:

    def test_get_profile_data(self, session):
        url = URL + 'profile'
        correct_data = {
            "responseCode": 0,
            "responseMessage": "Запрос обработан успешно",
            "data": {
                "customer_id": "386d81d6-e10e-4f38-b8a3-4ae3e5651747",
                "phone_number": "+79687137143",
                "first_name": "Ivan",
                "last_name": "Ivanov",
                "patronymic": "Ivanovich",
                "email": "ivaan@example.com",
                "birth_date": "1995-01-06",
                "mile_count": 0,
                "user_status": {
                    "name": "стандарт",
                    "conversion_rate": 0.3,
                    "minimum_conversion_threshold": 250.0
                },
                "settings": {
                    "language_id": 1
                },
                "onpass_data": {
                    "pass_count_1": 0,
                    "pass_count_2": 0,
                    "pass_count_3": 0
                }
            }
        }
        with session.get(url) as resp:
            assert resp.status_code == 200
            bank_response = resp.json()
            assert bank_response.get('responseCode', None) == 0
            t.compare_data_keys(bank_response, correct_data)


class Test_update_data:

    def test_update_profile(self, session):
        email = f"{utils.generate_number(15)}@sergey.com"
        testdata1 = {
            "first_name": "Sergey",
            "last_name": "Sergeev",
            "patronymic": "Sergeevich",
            "email": email,
            "birth_date": "2002-02-02"
        }

        url = URL + 'profile'
        with session.post(url, json=testdata1) as resp:
            assert resp.status_code == 200
            response = resp.json()

            assert response.get('responseCode', None) == 0

            server_data = t.get_profile_data(session)
            for key in testdata1.keys():
                assert server_data[key] == testdata1[key]

        email = f"{utils.generate_number(15)}@sergey.com"
        testdata2 = {
            "first_name": "Ivan",
            "last_name": "Ivanov",
            "patronymic": "Ivanovich",
            "email": email,
            "birth_date": "2002-02-02"
        }

        url = URL + 'profile'
        with session.post(url, json=testdata2) as resp:
            assert resp.status_code == 200
            response = resp.json()

            assert response.get('responseCode', None) == 0
            server_data = t.get_profile_data(session)
            for key in testdata2.keys():
                assert server_data[key] == testdata2[key]

    def test_update_profile_validate_date(self, session):
        email = f"{utils.generate_number(15)}@sergey.com"
        testdata1 = {
            "first_name": "Sergey",
            "last_name": "Sergeev",
            "patronymic": "Sergeevich",
            "email": email,
            "birth_date": "2002-0202"
        }

        url = URL + 'profile'
        with session.post(url, json=testdata1) as resp:
            assert resp.status_code == 200
            response = resp.json()
            assert response.get('responseCode', None) == 13

    def test_update_profile_validate_mail(self, session):
        email = f"{utils.generate_number(15)}sergey.com"
        testdata1 = {
            "first_name": "Sergey",
            "last_name": "Sergeev",
            "patronymic": "Sergeevich",
            "email": email,
            "birth_date": "2002-02-02"
        }

        url = URL + 'profile'
        with session.post(url, json=testdata1) as resp:
            assert resp.status_code == 200
            response = resp.json()
            assert response.get('responseCode', None) == 13


class Test_get_airports:
    def test_get_airports(self, session):
        url = URL + 'airports'
        example_data = {
            "airports": [
                {
                    "id": 1,
                    "city_id": 1,
                    "code_iata": "SVO",
                    "latitude": None,
                    "longitude": None,
                    "photo_path": None,
                    "available": False,
                    "partners_count": 1,
                    "terminals": [
                        {
                            "id": 15,
                            "latitude": 55.981178283691406,
                            "longitude": 37.415096282958984,
                            "photo_path": "https://developer.mileonair.com/resources/Airport/15_photo_path.jpg",
                            "available": False,
                            "partners_count": 12
                        }
                    ]
                }
            ],
            "translates": [
                {
                    "id": 1,
                    "airport_id": 1,
                    "title": "Шереметьево",
                    "language_id": 1
                }
            ]
        }
        with session.get(url) as resp:
            assert resp.status_code == 200
            response = resp.json()

            assert response.get('responseCode', None) == 0
            t.compare_data_keys(response.get('data'), example_data, {"terminals"})


class Test_get_partners_in_airport:
    def test_get_partners_in_airports(self, session):
        url = URL + 'partnersInAirport'
        example_data = {'partners_in_airport': [
            {
                "category_id": 1,
                "partners": [
                    {
                        "id": 23,
                        "name": "Му-Му",
                        "description_short": "«Му-му» — Фастфуд. Еда и напитки.",
                        "description": "«Му-му» — московская сеть ресторанов фастфуда, где большая часть блюд приготовлена по простым рецептам русской кухни и реализуется по невысоким ценам.",
                        "open_partner_schedule": "09:00",
                        "close_partner_schedule": "18:00",
                        "address_short": "Терминал B, Этаж 3\r\nОбщая зона\r\n\r\nТерминал D, Этаж 2\r\nОбщая зона",
                        "address": "Шереметьевское шоссе, вл2с1\r\nХимки, Московская область,\r\nРоссия 141425",
                        "cashback_part": 10.0,
                        "logo_path": "https://developer.mileonair.com/resources/var/www/html/resources/Partner/Му-Му.png",
                        "photo_path": "https://developer.mileonair.com/resources/var/www/html/resources/Partner/Му-Му.jpg"
                    }
                ]
            }
        ]
        }

        params = [('airport_id', "1"), ('testing', 'true')]
        with session.get(url, params=params) as resp:
            assert resp.status_code == 200
            response = resp.json()

            assert response.get('responseCode', None) == 0
            t.compare_data_keys(response.get('data'), example_data)


class Test_partners_in_city:
    def test_get_partners_in_city(self, session):
        url = URL + 'partnersInCity'
        example_data = {"partners": [
            {
                "id": 1,
                "name": "партнёр 1",
                "description_short": "краткое описание 1",
                "description": "описание 1",
                "open_partner_schedule": "11:00",
                "close_partner_schedule": "01:00",
                "address_short": "короткий адрес 1",
                "address": "полный адрес 1",
                "cashback_part": 0.10,
                "logo_path": "https://developer.mileonair.com/resources/1.jpg",
                "partner_category_id": 1
            }
        ]
        }

        params = [('city_id', "1"), ('testing', 'true')]
        with session.get(url, params=params) as resp:
            assert resp.status_code == 200
            response = resp.json()

            assert response.get('responseCode', None) == 0
            t.compare_data_keys(response.get('data'), example_data)

    def test_get_partners_in_city_err1(self, session):
        url = URL + 'partnersInCity'
        params = [('city_id', "qwe"), ('testing', 'true')]
        with session.get(url, params=params) as resp:
            assert resp.status_code == 200
            response = resp.json()

            assert response.get('responseCode', None) == 13

        with session.get(url) as resp:
            assert resp.status_code == 200
            response = resp.json()

            assert response.get('responseCode', None) == 12


class Test_parameters:
    def test_get_parameters(self, session):
        url = URL + 'parameters'
        example_data = {
            "parameters": [
                {
                    "name": "default_mile_accrual_percentage",
                    "description": None,
                    "value": "0.1"
                }
            ]
        }

        with session.get(url) as resp:
            assert resp.status_code == 200
            response = resp.json()

            assert response.get('responseCode', None) == 0
            t.compare_data_keys(response.get('data'), example_data)


class Test_Languages:
    def test_get_languages(self, session):
        url = URL + 'languages'
        example_data = {
            "languages": [
                {
                    "id": 1,
                    "name": "русский",
                    "code": "ru"
                },
                {
                    "id": 2,
                    "name": "english",
                    "code": "en"
                },
                {
                    "id": 3,
                    "name": "italiano",
                    "code": "it"
                }
            ]
        }

        with session.get(url) as resp:
            assert resp.status_code == 200
            response = resp.json()

            assert response.get('responseCode', None) == 0
            t.compare_data_keys(response.get('data'), example_data)


class Test_set_profile_settings:
    def test_set_profile_settings(self, session):
        url = URL + 'settings'
        json = {
            "language_id": 2
        }
        with session.post(url, json=json) as resp:
            assert resp.status_code == 200
            response = resp.json()

            assert response.get('responseCode', None) == 0

    def test_set_profile_settings_err1(self, session):
        url = URL + 'settings'
        json = {
            "langua1ge_id": "qwe"
        }
        with session.post(url, json=json) as resp:
            assert resp.status_code == 200
            response = resp.json()

            assert response.get('responseCode', None) == 12

    def test_set_profile_settings_err2(self, session):
        url = URL + 'settings'
        json = {
            "language_id": "qwe"
        }
        with session.post(url, json=json) as resp:
            assert resp.status_code == 200
            response = resp.json()

            assert response.get('responseCode', None) == 13


class Test_get_partner_categories:
    def test_get_partner_categories(self, session):
        url = URL + 'partnerCategories'
        example_data = {
            "partner_categories": [
                {
                    "id": 1
                }
            ],
            "translates": [
                {
                    "id": 1,
                    "partner_category_id": 1,
                    "name": "Кафе",
                    "language_id": 1
                }
            ]
        }

        with session.get(url) as resp:
            assert resp.status_code == 200
            response = resp.json()

            assert response.get('responseCode', None) == 0
            t.compare_data_keys(response.get('data'), example_data)


class Test_get_hashes:
    def test_get_hashes(self, session):
        url = URL + 'hashes'
        example_data = {
            "hashes": [
                {
                    "table_name": "airports",
                    "value": "e70029a276f7289b8854111c382069ed"
                },
                {
                    "table_name": "languages",
                    "value": "2fd668775ee664ffa32914f0f3601498"
                },
                {
                    "table_name": "partner_categories",
                    "value": "80936f7d428efe9e6cdb5644835bc777"
                }
            ]
        }

        with session.get(url) as resp:
            assert resp.status_code == 200
            response = resp.json()

            assert response.get('responseCode', None) == 0
            t.compare_data_keys(response.get('data'), example_data)


# class Test_add_feedback:
#     def test_add_feedback(self, session):
#         url = URL + 'feedback'
#         json = {
#             "message": "qwe",
#             "email": "asd@asd.asd"
#         }
#         with session.post(url, json=json) as resp:
#             assert resp.status_code == 200
#             response = resp.json()
#
#             assert response.get('responseCode', None) == 0
#
#     def test_add_feedback_err1(self, session):
#         url = URL + 'feedback'
#         json = {
#             "message": "qwe",
#             "email": "asdasd.asd"
#         }
#         with session.post(url, json=json) as resp:
#             assert resp.status_code == 200
#             response = resp.json()
#
#             assert response.get('responseCode', None) == 13
#
#     def test_add_feedback_err2(self, session):
#         url = URL + 'feedback'
#         json = {
#
#             "email": "asd@asd.asd"
#         }
#         with session.post(url, json=json) as resp:
#             assert resp.status_code == 200
#             response = resp.json()
#
#             assert response.get('responseCode', None) == 12


class Test_get_faq:
    def test_get_faq(self, session):
        url = URL + 'faq'
        example_data = {
            "faq": [
                {
                    "ord": 1,
                    "question": "где?",
                    "answer": "везде",
                    "ico_path": "https://developer.mileonair.com/resources/6.jpg",
                },
                {
                    "ord": 2,
                    "question": "когда?",
                    "answer": "всегда",
                    "ico_path": "https://developer.mileonair.com/resources/6.jpg",
                },
                {
                    "ord": 3,
                    "question": "для кого?",
                    "answer": "для всех",
                    "ico_path": "https://developer.mileonair.com/resources/6.jpg",
                }
            ]
        }

        with session.get(url) as resp:
            assert resp.status_code == 200
            response = resp.json()

            assert response.get('responseCode', None) == 0
            t.compare_data_keys(response.get('data'), example_data)


class Test_get_notifications:
    def test_get_notifications(self, session):
        url = URL + 'notifications'
        example_data = {
            "notifications": [
                {
                    "message": "а вот и третье",
                    "created_date": "2020-05-13 15:50:14"
                },
                {
                    "message": "вот ещё оповещение",
                    "created_date": "2020-05-13 15:47:55"
                },
                {
                    "message": "привет",
                    "created_date": "2020-05-13 15:47:25"
                }
            ]
        }

        with session.get(url) as resp:
            assert resp.status_code == 200
            response = resp.json()

            assert response.get('responseCode', None) == 0
            t.compare_data_keys(response.get('data'), example_data)


class Test_get_partners_relevant:
    def test_get_partners_relevant(self, session):
        url = URL + 'partnersRelevant'
        example_data = {'partners_relevant':
            [
                {
                    "category_id": 1,
                    "partners": [
                        {
                            "id": 23,
                            "name": "Му-Му",
                            "description_short": "«Му-му» — Фастфуд. Еда и напитки.",
                            "description": "«Му-му» — московская сеть ресторанов фастфуда, где большая часть блюд приготовлена по простым рецептам русской кухни и реализуется по невысоким ценам.",
                            "open_partner_schedule": "09:00",
                            "close_partner_schedule": "18:00",
                            "address_short": "Терминал B, Этаж 3\r\nОбщая зона\r\n\r\nТерминал D, Этаж 2\r\nОбщая зона",
                            "address": "Шереметьевское шоссе, вл2с1\r\nХимки, Московская область,\r\nРоссия 141425",
                            "cashback_part": 10.0,
                            "logo_path": "https://developer.mileonair.com/resources/var/www/html/resources/Partner/Му-Му.png",
                            "photo_path": "https://developer.mileonair.com/resources/var/www/html/resources/Partner/Му-Му.jpg",
                            "relevant_order": 2
                        }
                    ]
                }
            ]
        }
        params = [('testing', 'true')]
        with session.get(url, params=params) as resp:
            assert resp.status_code == 200
            response = resp.json()

            assert response.get('responseCode', None) == 0
            t.compare_data_keys(response.get('data'), example_data)


class Test_post_order:
    def test_post_order(self, session):
        url = URL + 'order'
        example_data = {
            "custom": False,
            "qr": "a18618eca164a4854f43515676691ccd1234d7eabde5e507f851e9e38e0222fe",
            "estimated_date": "2020-09-27 15:58:16",
            "used_date": "",
            "sum": 70000,
            "stock": {
                "title": "Стандартная упаковка багажа",
                "purchase_terms": "Условия покупки",
                "photo_path": "https://developer.mileonair.com/resources/Stock/2_photo_path.jpg",
                "partner": {
                    "name": "PACK&FLY",
                    "address_short": "Терминалы B, C, D, E и F",
                    "id": 56,
                    "logo_path": "https://developer.mileonair.com/resources/Partner/logo.png",
                    "open_partner_schedule": "06:00",
                    "close_partner_schedule": "23:00"
                }
            }
        }

        json = {"partner_id": 56,
                "airport_id": 1,
                "cart_id": 2
                }
        with session.post(url, json=json) as resp:
            assert resp.status_code == 200
            response = resp.json()

            assert response.get('responseCode', None) == 0
            t.compare_data_keys(response.get('data'), example_data)


class Test_get_orders:
    def test_get_order(self, session, add_order):
        url = URL + 'orders'
        params = [('active', "true")]
        example_data = {
            "orders": [
                {
                    "custom": False,
                    "qr": "aacd525e012ee4d5d365829921deb09d2176127b113f7afcbe83b16174904a6e",
                    "estimated_date": "2020-08-20",
                    "used_date": "2020-08-20",
                    "sum": 90000,
                    "stock": {
                        "title": "Стандартная упаковка + защита pack&fly",
                        "purchase_terms": "Условия покупки",
                        "photo_path": "https://developer.mileonair.com/resources/Stock/photo.jpg",
                        "partner": {
                            "name": "Pack&Fly",
                            "address_short": "Терминал F, второй этаж",
                            "logo_path": "https://developer.mileonair.com/resources/Partner/logo.png",
                            "open_partner_schedule": "06:00",
                            "close_partner_schedule": "23:00"
                        }
                    }
                }
            ]
        }

        with session.get(url, params=params) as resp:
            assert resp.status_code == 200
            response = resp.json()

            assert response.get('responseCode', None) == 0
            t.compare_data_keys(response.get('data'), example_data)
