from datetime import datetime, timedelta
import ast
import jwt
from aiohttp import web
from api_utils import ApiResponse, Mail, ApiPool
from asyncpg import Connection
from loguru import logger
from yarl._url import URL
import os
from user.models import User, Profile
from email.utils import formatdate
from datetime import datetime
class ConfirmEmail(web.View):

    async def get(self):
        try:
            conn: Connection
            encoded_jwt = self.request.query.get('data')
            payload = jwt.decode(encoded_jwt, "@m36@5Pn4h?5GA0k8zNfJMHmV9Acoqa1YJX9#Dj4", algorithms=["HS256"])
            user = await Profile.find(payload.get('profile_info')[0])
            if payload.get('profile_info')[2] == 'ru':
                with open(os.path.dirname(os.path.realpath(__file__)).replace('confirm_email',
                                                                              'templates/template_wide.html'),
                          'r') as report_file:
                    html = report_file.read()
            elif payload.get('profile_info')[2] == 'en':
                with open(os.path.dirname(os.path.realpath(__file__)).replace('confirm_email',
                                                                              'templates/template_wide_en.html'),
                          'r') as report_file:
                    html = report_file.read()
            if payload.get('profile_info')[1] == user.email and datetime.utcnow().timestamp() < payload.get(
                    'expire') and \
                    payload.get('resend_confirmation_email_date') == (user.resend_confirmation_email_date).timestamp():
                async with ApiPool.get_pool().acquire() as conn:
                    await conn.execute('update profiles set email_confirmed=True where id = $1', user.id)
            else:

                if payload.get('profile_info')[2] == 'ru':
                    with open(os.path.dirname(os.path.realpath(__file__)).replace('confirm_email',
                                                                                  'templates/template_expired_email_ru.html'),
                              'r') as report_file:
                        html_expired = report_file.read()
                elif payload.get('profile_info')[2] == 'en':
                    with open(os.path.dirname(os.path.realpath(__file__)).replace('confirm_email',
                                                                                  'templates/template_expired_email_en.html'),
                              'r') as report_file:
                        html_expired = report_file.read()

                return web.Response(
                    body=html_expired,
                    content_type='text/html',
                    charset='utf-8'
                )
            return web.Response(
                body=html,  # "<h1>Email успешно подтверждён</h1>",
                content_type='text/html',
                charset='utf-8'
            )
        except Exception as exc:
            logger.exception(exc)
            return web.Response(
                body="<h1>Не удалось подтвердить Email</h1>",
                content_type='text/html',
                charset='utf-8'
            )


class SendEmail(web.View):

    async def post(self):
        """

        @api {post} https://developer.mileonair.com/api/v1/email/send Отправить email подтверждения

        @apiName send_email
        @apiGroup mail
        @apiVersion 1.0.0

        @apiDescription отпраить письмо подтверждением для подтверждения адреса электронной почты

        @apiSuccess (200) {int} responseCode Код ошибки (0 - нет ошибки)
        @apiSuccess (200) {string} responseMessage  Описание ошибки, ответа


        @apiSuccessExample {json} Success-Response:
            {
                "responseCode": 0,
                "responseMessage": "Запрос обработан успешно",
            }
        """
        user = User.get()
        path = self.request.app.router['ConfirmEmail'].url_for()
        url = self.request.url.origin().join(path)
        await self.send_confirmation_email(url, user)
        # url= url.with_scheme('https')
        return ApiResponse(0)

    @staticmethod
    async def send_confirmation_email(url: URL, user: Profile, language_code, language_code_registration):
        if language_code is None:
            language_code = language_code_registration
        payload = dict(
            profile_info=(user.id, user.email, language_code),
            expire=(datetime.utcnow() + timedelta(hours=24)).timestamp(),
            resend_confirmation_email_date=(user.resend_confirmation_email_date).timestamp()
        )
        encoded_jwt = jwt.encode(payload, "@m36@5Pn4h?5GA0k8zNfJMHmV9Acoqa1YJX9#Dj4", algorithm="HS256")
        if language_code == 'ru':
            with open(os.path.dirname(os.path.realpath(__file__)).replace('confirm_email',
                                                                          'templates/template_confirmed_email_ru.html'),
                      'r') as report_file:
                html = report_file.read()
                head = 'Подтверждение электронной почты MILEONAIR'
        elif language_code == 'en':
            with open(os.path.dirname(os.path.realpath(__file__)).replace('confirm_email',
                                                                          'templates/template_confirmed_email_en.html'),
                      'r') as report_file:
                html = report_file.read()
                head = 'MILEONAIR e-mail confirmation'
        html_ = html.replace('Константин', str(user.first_name)).replace('url_confirm',
                                                                         str(url.with_query(dict(data=encoded_jwt))))
        await Mail.send_mail_async(
            'noreply@mileonair.com',
            user.email,
            head,
            html_,
            text_type='html'
        )

        return encoded_jwt
