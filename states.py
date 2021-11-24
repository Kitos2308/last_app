from __future__ import annotations

from abc import ABC, abstractmethod

from api_utils import ApiResponse
from settings import ROUTE_REGISTER, ROUTE_LOGIN, ROUTE_CONFIRM, ROUTE_LOGOUT, ROUTE_PROFILE


def authorize():
    return True


class Context(ABC):
    """
    Контекст определяет интерфейс, представляющий интерес для клиентов. Он также
    хранит ссылку на экземпляр подкласса Состояния, который отображает текущее
    состояние Контекста.
    """

    _state = None
    """
    Ссылка на текущее состояние Контекста.
    """

    def __init__(self, state: State):
        self._state = state
        self._state.context = self

    def get_permission_checker(self, request):
        handler_switch = {
            ROUTE_REGISTER: self._state.registration,
            ROUTE_LOGIN: self._state.login,
            ROUTE_CONFIRM: self._state.confirm,
            ROUTE_LOGOUT: self._state.logout,
            ROUTE_PROFILE: self._state.profile,
        }
        try:
            return handler_switch[request.path]
        except KeyError:
            return self._state.handle


class State(ABC):
    """
    Базовый класс Состояния объявляет методы, которые должны реализовать все
    Конкретные Состояния, а также предоставляет обратную ссылку на объект
    Контекст, связанный с Состоянием. Эта обратная ссылка может использоваться
    Состояниями для передачи Контекста другому Состоянию.
    """

    @abstractmethod
    def registration(self, request):
        pass

    @abstractmethod
    def login(self, request):
        pass

    @abstractmethod
    def confirm(self, request):
        pass

    @abstractmethod
    def logout(self, request):
        pass

    @abstractmethod
    def profile(self, request):
        pass

    @abstractmethod
    def handle(self, request):
        pass


"""
Конкретные Состояния реализуют различные модели поведения, связанные с
состоянием Контекста.
"""


class Unauthorized(State):

    def registration(self, request):
        pass

    def login(self, request):
        pass

    def confirm(self, request):
        raise ApiResponse(21)

    def logout(self, request):
        raise ApiResponse(21)

    def profile(self, request):
        raise ApiResponse(22)

    def handle(self, request):
        raise ApiResponse(22)


class Authorized(State):
    def registration(self, request):
        raise ApiResponse(22)

    def login(self, request):
        pass

    def confirm(self, request):
        raise ApiResponse(21)

    def logout(self, request):
        pass

    def profile(self, request):
        pass

    def handle(self, request):
        pass


class Unconfirmed(Unauthorized):

    def confirm(self, request):
        pass


class Confirmed(Unconfirmed):
    def profile(self, request):
        if request.method == 'POST':
            pass
        else:
            raise ApiResponse(22)
