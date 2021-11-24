from aiohttp import web

from .urls import create_views


def make_app():
    app = web.Application()
    app.add_routes(create_views(''))
    return app
