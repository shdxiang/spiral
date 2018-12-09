#!/usr/bin/env python
# -*- coding:utf-8 -*-

import logging

import spiral

API_KEY = 'LAqUlngMIQkIUjXMUreyu3qn'
API_SECRET = 'chNOOS4KvNXR_Xq4k4c9qsfoKWvnDecLATCRlcBwyKDYnWgO'
API_EXPIRES = 24 * 3600


def loop_handle_data(api):
    while True:
        data = api.ws.get_data()
        if not data:
            return

        logging.info('got data:')
        logging.info(data)

        if data['event'] == 'connected':
            # subscribe public
            api.ws.subscribe_orderbook(symbols=["ETHUSDT"])
        elif data['event'] == 'authenticated':
            # subscribe private
            api.ws.subscribe_order(symbols=["ETHUSDT"])
        elif data['event'] == 'orderbook':
            if data['data']['symbol'] != 'ETHUSDT':
                continue

            if 'data' not in data['data']:
                continue

            orders = data['data']['data']

            if orders[0][2] != 'bid':
                continue

            price = orders[0][0]
            quantity = orders[0][1]

            if price > 100.0:
                logging.info('post_order')
                errcode, resp = api.rest.post_order(
                    symbol='ETHUSDT', side='ask', type='limit', quantity=quantity, price=price)
                logging.info('errcode:')
                logging.info(errcode)
                logging.info('resp:')
                logging.info(resp)


def trade():

    api = spiral.Sprial(API_KEY, API_SECRET, API_EXPIRES)

    api.start()

    currencies = api.rest.get_currencies()
    logging.info('currencies:')
    logging.info(currencies)

    try:
        loop_handle_data(api)
    except KeyboardInterrupt:
        pass

    api.stop()


def main():
    format = '%(asctime)s %(filename)s [%(lineno)d][%(levelname)s] %(message)s'
    logging.basicConfig(level=logging.INFO, format=format)

    trade()


if __name__ == '__main__':
    main()
