from tortoise import fields

from tortoise.models import Model


class ProductToPoint(Model):
    id = fields.BigIntField(pk=True)
    product = fields.ForeignKeyField('models.Products', related_name='product_to_point_product')
    point = fields.ForeignKeyField('models.Points', related_name='product_to_point_points')
    created_date = fields.DatetimeField()

    class Meta:
        table = 'product_to_point'


class Points(Model):
    id = fields.BigIntField(pk=True)
    airport = fields.ForeignKeyField('models.Airports', related_name='points')
    partner = fields.ForeignKeyField('models.Partners', related_name='points')
    brand = fields.ForeignKeyField('models.Brands', related_name='points')
    created_date = fields.DatetimeField()
    active = fields.BooleanField(default=True)


class Stocks(Model):
    id = fields.BigIntField(pk=True)
    start_date = fields.DatetimeField()
    end_date = fields.DatetimeField()
    validity = fields.IntField()
    photo_path = fields.TextField()
    active = fields.BooleanField(default=True)
    created_date = fields.DatetimeField()
    ord = fields.SmallIntField()
    custom = fields.BooleanField(default=False)


class Carts(Model):
    id = fields.BigIntField(pk=True)
    stock = fields.ForeignKeyField('models.Stocks', related_name='cart')
    sum = fields.IntField()


class Profiles(Model):
    id = fields.BigIntField(pk=True)
    phone_number = fields.CharField(25)


class StockToProfile(Model):
    id = fields.BigIntField(pk=True)
    stock = fields.ForeignKeyField('models.Stocks', related_name='stock_to_profile')
    profile = fields.ForeignKeyField('models.Profiles', related_name='stock_to_profile')

    class Meta:
        table = 'stock_to_profile'


class ProductToCart(Model):
    id = fields.BigIntField(pk=True)
    product = fields.ForeignKeyField('models.Products', related_name='product_to_cart')
    cart = fields.ForeignKeyField('models.Carts', related_name='product_to_cart')
    quantity = fields.IntField(default=1)

    class Meta:
        table = 'product_to_cart'


class BrandRelations(Model):
    id = fields.BigIntField(pk=True)
    airport = fields.ForeignKeyField('models.Airports', related_name='relations')
    brand = fields.ForeignKeyField('models.Brands', related_name='relations')

    class Meta:
        table = 'brand_relations'


class Products(Model):
    id = fields.BigIntField(pk=True)
    online_price = fields.IntField()
    offline_price = fields.IntField()
    active = fields.BooleanField(default=True)
    created_date = fields.DatetimeField()
    product_unit = fields.ForeignKeyField('models.ProductUnits', related_name='products')


class Airports(Model):
    id = fields.BigIntField(pk=True)
    code_iata = fields.CharField(4)
    parent: fields.ForeignKeyNullableRelation['Airports'] = fields.ForeignKeyField(
        "models.Airports", related_name="terminals", null=True
    )
    latitude = fields.FloatField()
    longitude = fields.FloatField()
    created_date = fields.DatetimeField()
    photo_path = fields.TextField()
    active = fields.BooleanField(default=True)
    # city = fields.ForeignKeyField('models.Cities', related_name='airport')
    ord = fields.SmallIntField()

    # terminal = fields.CharField(24)

    class META:
        table = 'airports'


# class Cities(Model):
#     id = fields.BigIntField(pk=True)
#     latitude = fields.FloatField()
#     longitude = fields.FloatField()
#     created_date = fields.DatetimeField()
#
#
# class Airports(Model):
#     id = fields.BigIntField(pk=True)
#     code_iata = fields.CharField(4)
#     parent: fields.ForeignKeyNullableRelation['Airports'] = fields.ForeignKeyField(
#         "models.Airports", related_name="terminals", null=True
#     )
#     latitude = fields.FloatField()
#     longitude = fields.FloatField()
#     created_date = fields.DatetimeField()
#     photo_path = fields.TextField()
#     active = fields.BooleanField(default=True)
#     city = fields.ForeignKeyField('models.Cities', related_name='airport')
#     ord = fields.SmallIntField()
#     terminal = fields.CharField(24)
#
#     class META:
#         table = 'airports'
#
#
class Brands(Model):
    id = fields.BigIntField(pk=True)
    logo_path = fields.TextField()
    active = fields.BooleanField(default=True)
    created_date = fields.DatetimeField()
    photo_path = fields.TextField()
    relevant = fields.BooleanField(default=True)
    relevant_order = fields.IntField()
    online = fields.BooleanField()
    tag = fields.CharField(4, null=False)


#
#
class Partners(Model):
    id = fields.BigIntField(pk=True)
    unique_value = fields.CharField(32)
    logo_path = fields.TextField()
    cashback_part = fields.FloatField()
    testing = fields.BooleanField()
    active = fields.BooleanField(default=True)
    created_date = fields.DatetimeField()
    partner_category_id = fields.ForeignKeyNullableRelation
    photo_path = fields.TextField()
    # relevant = fields.BooleanField(default=True)
    # relevant_order = fields.IntField()
    online = fields.BooleanField()
    login = fields.TextField()
    password = fields.TextField()
    id_1c = fields.CharField(20)
    token = fields.TextField()


#
#
# class AirportsTranslate(Model):
#     id = fields.BigIntField(pk=True)
#     airport = fields.ForeignKeyField('models.Airports', related_name='translates')
#     title = fields.TextField()
#
#     language = fields.ForeignKeyNullableRelation
#
#     class META:
#         table = 'airports_translate'
#
#

#
#
# class Partnership(Model):
#     id = fields.BigIntField(pk=True)
#     seller = fields.ForeignKeyField('models.Partners', related_name='partnership_seller')
#     provider = fields.ForeignKeyField('models.Partners', related_name='partnership_provider')
#     expiration_date = fields.DatetimeField()
#     created_date = fields.DatetimeField()
#     currency_code = fields.ForeignKeyNullableRelation
#     value = fields.IntField()
#     partnership_type_id = fields.ForeignKeyNullableRelation
#
#
# class PointToSeller(Model):
#     id = fields.BigIntField(pk=True)
#     point = fields.ForeignKeyField('models.Points', related_name='points')
#     seller = fields.ForeignKeyField('models.Partners', related_name='seller')
#     created_date = fields.DatetimeField()
#     description = fields.TextField()
#     active = fields.BooleanField(default=True)
#
#     class Meta:
#         table = 'point_to_seller'
#
#
class ProductUnits(Model):
    id = fields.BigIntField(pk=True)
    nds = fields.FloatField()
    created_date = fields.DatetimeField()
    active = fields.BooleanField(default=True)
    payment_object = fields.TextField()
    payment_method = fields.TextField()
    partner = fields.ForeignKeyField('models.Partners', related_name='product_units')

    class Meta:
        table = 'product_units'
#
#
# class ProductUnitsToPartner(Model):
#     id = fields.BigIntField(pk=True)
#     id_1c = fields.TextField()
#     created_date = fields.DatetimeField()
#     product_unit = fields.ForeignKeyField('models.ProductUnits', related_name='partners')
#     partner = fields.ForeignKeyField('models.Partners', related_name='product_units')
#
#     class Meta:
#         table = 'product_units_to_partners'
#
#
# class Products(Model):
#     id = fields.BigIntField(pk=True)
#     online_price = fields.IntField()
#     offline_price = fields.IntField()
#     active = fields.BooleanField(default=True)
#     created_date = fields.DatetimeField()
#     product_unit = fields.ForeignKeyField('models.ProductUnits', related_name='products')
#
#

#
#
# class ProductToCart(Model):
#     id = fields.BigIntField(pk=True)
#     product = fields.ForeignKeyField('models.Products', related_name='product_to_cart_product')
#     cart = fields.ForeignKeyField('models.Carts', related_name='product_to_cart_cart')
#     quantity = fields.IntField(default=1)
#
#     class Meta:
#         table = 'product_to_cart'
#
#

#
#
# class PtpToPts(Model):
#     id = fields.BigIntField(pk=True)
#     created_date = fields.DatetimeField()
#     product_to_point = fields.ForeignKeyField('models.ProductToPoint', related_name='ptpts_pts_ptp')
#     point_to_seller = fields.ForeignKeyField('models.PointToSeller', related_name='ptpts_pts')
#
#     class Meta:
#         table = 'ptp_to_pts'
#
#
# class Orders(Model):
#     id = fields.BigIntField(pk=True)
#     # points = fields.ForeignKeyField('models.Points', related_name='point')
#     qr = fields.TextField()
#     sold_date = fields.DatetimeField()
#     sum = fields.IntField()
#
#     points: fields.ManyToManyRelation["Points"]
#
#
# class OrderToPoint(Model):
#     id = fields.BigIntField(pk=True)
#     # point = fields.ForeignKeyField('models.Points')
#     # order = fields.ForeignKeyField('models.Orders')
#     created_date = fields.DatetimeField()
#
#     class Meta:
#         table = "order_to_point"
#
#
# class Languages(Model):
#     id = fields.BigIntField(pk=True)
#     name = fields.CharField(32)
#     code = fields.CharField(4)
#     public = fields.BooleanField(default=True)
