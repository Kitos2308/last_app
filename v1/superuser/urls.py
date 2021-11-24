from aiohttp import web

from .views import BindCardView

BIND_CARD_URL = '/bindCard'


def create_views(prefix):
    urls = [
        web.view(prefix + BIND_CARD_URL, BindCardView, name='hell_case_bind_card'),
    ]
    return urls
