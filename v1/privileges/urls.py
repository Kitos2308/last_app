from aiohttp import web

from settings import CONFIRM_BINDING_URL
from .views import CardsView, BindCardView, UnBindCardView, CardPacketsView, OrderView, OrdersView, ConfirmBindingView

BIND_CARD_URL = '/bindCard'
UNBIND_CARD_URL = '/unbindCard'
CARDS_URL = '/cards'
PACKETS_URL = '/packets'
ORDER_URL = '/order'
ORDERS_URL = '/orders'


def create_views(prefix):
    urls = [
        web.view(prefix + BIND_CARD_URL, BindCardView, name='privileges_bind_card'),
        web.view(prefix + CONFIRM_BINDING_URL, ConfirmBindingView, name='privileges_confirm_binding_card'),
        web.view(prefix + UNBIND_CARD_URL, UnBindCardView, name='privileges_unbind_card'),
        web.view(prefix + CARDS_URL, CardsView, name='privileges_cards'),
        web.view(prefix + PACKETS_URL, CardPacketsView, name='privileges_packets'),
        web.view(prefix + ORDER_URL, OrderView, name='privileges_order'),
        web.view(prefix + ORDERS_URL, OrdersView, name='privileges_orders'),
    ]
    return urls
