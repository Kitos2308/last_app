from aiohttp import web

from .views import ConfirmEmail, SendEmail

RESEND_CONFIRMATION_MAIL = '/send'
CONFIRM_EMAIL = '/confirm'


def create_views(prefix):
    urls = [
        web.view(prefix + RESEND_CONFIRMATION_MAIL, SendEmail, name='SendEmail'),
        web.view(prefix + CONFIRM_EMAIL, ConfirmEmail, name='ConfirmEmail'),
    ]
    return urls
