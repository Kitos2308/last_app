import asyncio
import sys
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from loguru import logger
import aiosmtplib

from settings import MAIL_PARAMS

if sys.platform == 'win32':
    loop = asyncio.get_event_loop()
    if not loop.is_running() and not isinstance(loop, asyncio.ProactorEventLoop):
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)


async def send_mail_async(sender, to, subject, text, textType='plain', **params):
    cc = params.get("cc", [])
    bcc = params.get("bcc", [])
    db_pool = params.get("db_pool")
    feedback_id = params.get("feedback_id")
    mail_params = params.get("mail_params", MAIL_PARAMS)
    photo = params.get('photo', False)

    # Prepare Message
    msg = MIMEMultipart()
    msg.preamble = str(subject.encode('cp1251'))
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(to)
    if len(cc): msg['Cc'] = ', '.join(cc)
    if len(bcc): msg['Bcc'] = ', '.join(bcc)

    msg.attach(MIMEText(text, textType, 'utf-8'))

    if photo:
        n = 1
        for file in photo:
            fp = open(file, 'rb')
            msgImage = MIMEImage(fp.read())
            fp.close()

        # Define the image's ID as referenced above
            msgImage.add_header('Content-ID', f'<image{n}>')
            msg.attach(msgImage)
            n += 1

    # Contact SMTP server and send Message
    host = mail_params.get('host', 'localhost')
    isSSL = mail_params.get('SSL', False)
    isTLS = mail_params.get('TLS', False)
    port = mail_params.get('port', 465 if isSSL else 25)
    smtp = aiosmtplib.SMTP(hostname=host, port=port, use_tls=isSSL)
    try:
        await smtp.connect()
        if isTLS:
            await smtp.starttls()
        if 'user' in mail_params:
            await smtp.login(mail_params['user'], mail_params['password'])
        resp = await smtp.send_message(msg)
        await smtp.quit()
        if db_pool is not None and resp[1].startswith('OK') and feedback_id is not None:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    f'UPDATE feedback SET processed=TRUE where id = $1',
                    feedback_id)
    except Exception as ex:
        logger.error(f'feedback id:{feedback_id} not sent: {ex}')
    else:
        logger.info(f'feedback id:{feedback_id} successfully sent')




# if __name__ == "__main__":
#     email = "ffirecent@gmail.com"
#     co1 = send_mail_async(email,
#                           [email],
#                           "Test 1",
#                           'Test 1 Message',
#                           textType="plain", SSL=True, TLS=True)
#     co2 = send_mail_async(email,
#                           [email],
#                           "Test 2",
#                           'Test 2 Message',
#                           textType="plain", SSL=True, TLS=True)
#     loop = asyncio.get_event_loop()
#     loop.run_until_complete(asyncio.gather(co1, co2))
#     loop.close()
