#!/usr/bin/env python
# -*- coding:utf-8 -*-

import logging
import json
import time
import hashlib
import hmac
import urllib
import socket
import multiprocessing
import threading

import websocket
import requests


REST_URL = 'https://api.spiral.exchange/api/v1'
WS_URL = 'wss://ws.spiral.exchange'
PING_INTERVAL = 30
QUEUE_MAX_SIZE = 1024


class Rest(object):
    """docstring for Rest."""

    def __init__(self, key, secret, expires):
        super(Rest, self).__init__()
        self.url = REST_URL
        self.key = key
        self.secret = secret
        self.expires = expires

    def start(self):
        self.session = requests.Session()

    def stop(self):
        self.session.close()

    def _auth_headers(self, method, path, data):
        expires = str(int(time.time() + self.expires))

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

    def _http(self, method, endpoint, params, data):
        url = self.url + endpoint
        req = requests.Request('GET', url, params=params)
        prepped = req.prepare()
        resp = self.session.send(prepped)
        logging.debug(resp.status_code)
        logging.debug(resp.json())
        return resp.status_code, resp.json()

    def _http_auth(self, method, endpoint, params, data):
        url = self.url + endpoint
        req = requests.Request(method, url, params=params)
        prepped = req.prepare()
        prepped.headers = self._auth_headers(method, prepped.path_url, data)
        resp = self.session.send(prepped)
        logging.debug(resp.status_code)
        logging.debug(resp.json())
        return resp.status_code, resp.json()

    def get_currencies(self, **kwargs):
        return self._http('GET', '/currencies', kwargs, '')

    def get_products(self, **kwargs):
        return self._http('GET', '/products', kwargs, '')

    def get_klines(self, **kwargs):
        return self._http('GET', '/klines', kwargs, '')

    def get_orderbook(self, **kwargs):
        return self._http('GET', '/orderbook', kwargs, '')

    def get_trades(self, **kwargs):
        return self._http('GET', '/trades', kwargs, '')

    def get_wallet_balances(self, **kwargs):
        return self._http_auth('GET', '/wallet/balances', kwargs, '')

    def get_myTrades(self, **kwargs):
        return self._http_auth('GET', '/myTrades', kwargs, '')

    def get_order(self, **kwargs):
        return self._http_auth('GET', '/order', kwargs, '')

    def post_order(self, **kwargs):
        return self._http_auth('POST', '/order', '', json.dumps(kwargs))

    def delete_order(self, **kwargs):
        return self._http_auth('DELETE', '/order', '', json.dumps(kwargs))

    def delete_order_all(self, **kwargs):
        return self._http_auth('DELETE', '/order/all', '', json.dumps(kwargs))


class Websocket(object):
    """docstring for Websocket."""

    def __init__(self, key, secret, expires):
        super(Websocket, self).__init__()
        self.ping_timer = None
        self.key = key
        self.secret = secret
        self.expires = expires
        self.url = WS_URL
        self.queue = multiprocessing.Queue(QUEUE_MAX_SIZE)

    def start(self):
        self.socket = websocket.WebSocketApp(self.url,
                                             on_open=self._on_open,
                                             on_message=self._on_message,
                                             on_error=self._on_error,
                                             on_close=self._on_close)

        kwargs = {'sockopt': ((socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),)}
        self.thread = threading.Thread(
            target=self.socket.run_forever, kwargs=kwargs)
        self.thread.start()

    def stop(self):
        self.socket.close()
        self.thread.join()
        self._stop_timer()

    def _on_open(self, *args):
        logging.info('websocket connected')
        self._start_timer()

    def _on_message(self, message):
        logging.debug(message)

        data = json.loads(message)
        if data['event'] == 'connected':
            self._auth()
        elif data['event'] == 'pong':
            self._start_timer()
            return

        self._enqueue_data(data)

    def _on_close(self, *args):
        logging.info('websocket closed')
        self._stop_timer()

    def _on_error(self, error):
        logging.error(error)
        self._stop_timer()

    def _start_timer(self):
        self.ping_timer = threading.Timer(
            PING_INTERVAL, self._heartbeat)
        self.ping_timer.start()

    def _stop_timer(self):
        if self.ping_timer:
            self.ping_timer.cancel()

    def _send_data(self, event, data):
        self.socket.send(json.dumps({
            'event': event,
            'data': data
        }))

    def _heartbeat(self):
        self._send_data('ping', int(time.time()))

    def _auth(self):
        expires = int(time.time() + self.expires)
        signature_data = 'GET/realtime' + str(expires)
        signature = hmac.new(self.secret, msg=signature_data,
                             digestmod=hashlib.sha256).hexdigest()
        data = {
            'api_key': self.key,
            'expires': expires,
            'signature': signature
        }
        self._send_data('authenticate', data)

    def _enqueue_data(self, data):
        self.queue.put(data)

    def _dequeue_data(self):
        return self.queue.get()

    def get_data(self):
        return self._dequeue_data()

    def _subscribe(self, topic, kwargs):
        data = dict({'topic': topic}.items() + kwargs.items())
        self._send_data('subscribe', data)

    def subscribe_ticker(self, **kwargs):
        self._subscribe('ticker', kwargs)

    def subscribe_orderbook(self, **kwargs):
        self._subscribe('orderbook', kwargs)

    def subscribe_trade(self, **kwargs):
        self._subscribe('trade', kwargs)

    def subscribe_kline(self, **kwargs):
        self._subscribe('kline', kwargs)

    def subscribe_order(self, **kwargs):
        self._subscribe('order', kwargs)

    def subscribe_account(self, **kwargs):
        self._subscribe('account', kwargs)


class Sprial(object):
    """docstring for Sprial."""

    def __init__(self, key, secret, expires):
        super(Sprial, self).__init__()
        self.rest = Rest(key, secret, expires)
        self.ws = Websocket(key, secret, expires)

    def start(self):
        self.rest.start()
        self.ws.start()

    def stop(self):
        self.ws.stop()
        self.rest.stop()


def spiral_test_get_data(spiral):
    while True:
        data = spiral.ws.get_data()
        if data:
            logging.info('got data:')
            logging.info(data)
            if data['event'] == 'connected':
                # subscribe public
                spiral.ws.subscribe_ticker(symbols=["BTCUSDT", "ETHBTC"])
                spiral.ws.subscribe_orderbook(symbols=["BTCUSDT"])
                spiral.ws.subscribe_trade(symbols=["BTCUSDT"])
                spiral.ws.subscribe_kline(symbols=["ETHBTC"], period_minutes=5)
            elif data['event'] == 'authenticated':
                # subscribe private
                spiral.ws.subscribe_order(symbols=["BTCUSDT"])
                spiral.ws.subscribe_account()


def spiral_test():
    apiKey = 'LAqUlngMIQkIUjXMUreyu3qn'
    apiSecret = 'chNOOS4KvNXR_Xq4k4c9qsfoKWvnDecLATCRlcBwyKDYnWgO'

    spiral = Sprial(apiKey, apiSecret, 60)

    spiral.start()

    # spiral.rest.get_currencies()
    # spiral.rest.get_products()
    # spiral.rest.get_klines(symbol='BTCUSDT', limit=5)
    # spiral.rest.get_orderbook(symbol='BTCUSDT', limit=5)
    # spiral.rest.get_trades(count=5)
    #
    # spiral.rest.get_wallet_balances(currency='USDT')
    # spiral.rest.get_myTrades(count=5)
    # spiral.rest.get_order(count=5, symbol='BTCUSDT', side='ask')
    # spiral.rest.post_order(symbol='BTCUSDT', side='bid',
    #                        type='limit', quantity='0.01', price='1000')
    # spiral.rest.delete_order(order_id=131513)
    # spiral.rest.delete_order_all()

    try:
        spiral_test_get_data(spiral)
    except KeyboardInterrupt:
        pass

    spiral.stop()


def main():
    format = '%(asctime)s %(filename)s [%(lineno)d][%(levelname)s] %(message)s'
    logging.basicConfig(level=logging.DEBUG, format=format)

    spiral_test()


if __name__ == '__main__':
    main()
