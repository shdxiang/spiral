#!/usr/bin/env python
# -*- coding:utf-8 -*-

import logging
import json
import time
import hashlib
import hmac
import requests
import urllib
from requests import Request, Session


REST_URL = 'https://api.spiral.exchange/api/v1'
WSS_URL = 'wss://ws.spiral.exchange'


class Rest(object):
    """docstring for Rest."""

    def __init__(self, url):
        super(Rest, self).__init__()
        self.url = url
        self.session = Session()

    def auth(self, key, secret, expires):
        self.key = key
        self.secret = secret
        self.expires = expires

    def auth_headers(self, method, path, data):
        expires = str(int(round(time.time()) + self.expires))

        signature_data = method + path + expires + data
        logging.debug(signature_data)

        signature = hmac.new(self.secret, msg=signature_data,
                             digestmod=hashlib.sha256).hexdigest()

        headers = {
            'api-key': self.key,
            'api-expires': expires,
            'api-signature': signature
        }
        return headers

    def http(self, method, endpoint, params, data):
        url = self.url + endpoint
        req = Request('GET', url, params=params)
        prepped = req.prepare()
        resp = self.session.send(prepped)
        logging.debug(resp.status_code)
        logging.debug(resp.json())
        return resp.status_code, resp.json()

    def http_auth(self, method, endpoint, params, data):
        url = self.url + endpoint
        req = Request(method, url, params=params)
        prepped = req.prepare()
        prepped.headers = self.auth_headers(method, prepped.path_url, data)
        resp = self.session.send(prepped)
        logging.debug(resp.status_code)
        logging.debug(resp.json())
        return resp.status_code, resp.json()

    def get_currencies(self, **kwargs):
        return self.http('GET', '/currencies', kwargs, '')

    def get_products(self, **kwargs):
        return self.http('GET', '/products', kwargs, '')

    def get_klines(self, **kwargs):
        return self.http('GET', '/klines', kwargs, '')

    def get_orderbook(self, **kwargs):
        return self.http('GET', '/orderbook', kwargs, '')

    def get_trades(self, **kwargs):
        return self.http('GET', '/trades', kwargs, '')

    def get_wallet_balances(self, **kwargs):
        return self.http_auth('GET', '/wallet/balances', kwargs, '')

    def get_myTrades(self, **kwargs):
        return self.http_auth('GET', '/myTrades', kwargs, '')

    def get_order(self, **kwargs):
        return self.http_auth('GET', '/order', kwargs, '')

    def post_order(self, **kwargs):
        return self.http_auth('POST', '/order', '', json.dumps(kwargs))

    def delete_order(self, **kwargs):
        return self.http_auth('DELETE', '/order', '', json.dumps(kwargs))

    def delete_order_all(self, **kwargs):
        return self.http_auth('DELETE', '/order/all', '', json.dumps(kwargs))


class Websocket(object):
    """docstring for Websocket."""

    def __init__(self, url):
        super(Websocket, self).__init__()
        self.url = url


class Sprial(object):
    """docstring for Sprial."""

    def __init__(self):
        super(Sprial, self).__init__()
        self.rest = Rest(REST_URL)
        self.wss = Websocket(WSS_URL)

    def start(self):
        pass


def spiral_test():
    apiKey = 'LAqUlngMIQkIUjXMUreyu3qn'
    apiSecret = 'chNOOS4KvNXR_Xq4k4c9qsfoKWvnDecLATCRlcBwyKDYnWgO'

    spiral = Sprial()

    spiral.rest.get_currencies()
    spiral.rest.get_products()
    spiral.rest.get_klines(symbol='BTCUSDT', limit=5)
    spiral.rest.get_orderbook(symbol='BTCUSDT', limit=5)
    spiral.rest.get_trades(count=5)

    spiral.rest.auth(apiKey, apiSecret, 60)

    spiral.rest.get_wallet_balances(currency="USDT",)
    spiral.rest.get_myTrades(count=5)
    spiral.rest.get_order(count=5, symbol="BTCUSDT", side="ask")
    spiral.rest.post_order(symbol="BTCUSDT", side="bid",
                           type="limit", quantity="0.01", price="1000")
    spiral.rest.delete_order(order_id=131513)
    spiral.rest.delete_order_all()


def main():
    format = '%(asctime)s %(filename)s [%(lineno)d][%(levelname)s] %(message)s'
    logging.basicConfig(level=logging.DEBUG, format=format)

    spiral_test()


if __name__ == '__main__':
    main()
