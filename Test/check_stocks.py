import argparse
import asyncio
import os

import toml
from tortoise import Tortoise
from tortoise.query_utils import Q
from tortoise.timezone import now

from models import *


def load_config():
    config_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__))) + '/config/config.toml'
    with open(config_path) as f:
        conf = toml.load(f)
    return conf


async def main(phone, stock_id, airport_id):
    await Tortoise.init(
        db_url=f"postgres://{config['database'].get('DB_USER')}:{config['database'].get('DB_PASS')}@{config['database'].get('DB_HOST')}/{config['database'].get('DB_NAME')}",
        modules={'models': ['models']}
    )
    try:
        print('find profile')
        profile = await Profiles.get(phone_number=phone)
        print('find stock')
        stock = await Stocks.get(id=stock_id, active=True, custom=True)
        print('check stock start date')
        assert stock.start_date is None or stock.start_date < now()
        print('check stock end date')
        assert stock.end_date is None or stock.end_date > now()
        print('find stock to profile ')
        stp = await StockToProfile.get(profile=profile, stock=stock)
        print('find cart ')
        cart = await Carts.get(stock=stock)
        print('find products list ')
        products_list = [ptc.product for ptc in await ProductToCart.filter(cart=cart).prefetch_related('product')]
        print('find airports ')
        airports = await Airports.filter(Q(id=airport_id) | Q(parent=airport_id), active=True)
        print('find points ')
        points = await Points.filter(active=True, airport_id__in=(x.id for x in airports))
        for point in points:
            try:
                print(f'----point: {point.id}')
                print('|---find partner ')
                partner = await Partners.get(points=point.id, active=True)
                print('|---begin check products')
                for product in products_list:
                    print(f'|---product id:{product.id}')
                    print('|-|-check product active ')
                    assert product.active
                    print('|-|-check product to point ')
                    ptp = await ProductToPoint.get(point=point, product=product)
                    print('|-|-check product unit ')
                    pu = await ProductUnits.get(partner=partner, active=True, products=product.id)
                    print('|-|-find check product unit owner ')
                    assert partner == await pu.partner

                print('|---find brand ')

                brand = await Brands.get(points=point.id, active=True)
                print('|---find brand relation ')
                airport = await point.airport
                br = await BrandRelations.get(Q(airport=airport) | Q(airport=await airport.parent), brand=brand)
                print('!!!!!!!!!!!!success!!!!!!!!!!!!!')
            except Exception as e:
                print(f'failed for point {point.id}')
                print(e)
    except Exception as e:
        print('Failed')
        print(e)
    await Tortoise.close_connections()
    return True


if __name__ == '__main__':
    config = load_config()
    database = dict(dbname=config['database'].get('DB_NAME'),
                    user=config['database'].get('DB_USER'),
                    password=config['database'].get('DB_PASS'),
                    host=config['database'].get('DB_HOST'),
                    port=config['database'].get('DB_PORT'))

    parser = argparse.ArgumentParser(description='поиск отсутсвующих зависимостей в персональных предложениях\n')
    parser.add_argument('-p', '--phone', required=True,help='телефон')
    parser.add_argument('-s', '--stock_id', required=True,help='')
    parser.add_argument('-a', '--airport_id',required=True, help='')
    args = parser.parse_args()
    # Python 3.7+
    # for arg in (args.phone, args.stock_id, args.airport_id):
    #     assert arg is not None
    asyncio.run(main(args.phone, args.stock_id, args.airport_id))
