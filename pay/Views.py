# from asyncpg import Connection
#
# import pss
# from models import User, OrderModel
# from pool import ApiPool
# from settings import POOL
#
#
# class Pay:
#     def __init__(self, user: User):
#         self.user = user
#
#     pool = ApiPool.get_pool(POOL)
#     _conn: Connection
#     _order: OrderModel
#     _order_query = 'select * from orders where id = $1 and profile_id = $2'
#
#     async def pay(self, order_id):
#         async with self.pool.acquire() as self._conn:
#             await self.find_moa_order(order_id)
#             # await self.get_order_info()
#             await self.make_ofd_receipt()
#             await self.register_order()
#             await self.collect_response()
#
#     async def find_moa_order(self, order_id):
#         self._order = OrderModel(**await self._conn.fetchrow(self._order_query, order_id, self.user.id))
#
#     async def get_order_info(self):
#         self._pss_order = await pss.Order.get(pss.Order.input_get_model(qr=self._order.pss_qr))
#
#     async def make_ofd_receipt(self):
#         pass
#
#     async def register_order(self):
#         pass
#
#     async def collect_response(self):
#         pass
