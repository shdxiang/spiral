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
INITIAL_RETRY_DELAY = 0.2


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
        expires = int(time.time() + self.expires)

        if not data:
            data = ''

        signature_data = method + path + str(expires) + data
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
        req = requests.Request('GET', url, params=params, data=data)
        prepped = req.prepare()
        resp = self.session.send(prepped)
        logging.debug(resp.status_code)
        logging.debug(resp.json())
        return resp.status_code, resp.json()

    def _http_auth(self, method, endpoint, params, data):
        url = self.url + endpoint
        req = requests.Request(method, url, params=params, data=data)
        prepped = req.prepare()

        headers = self._auth_headers(method, prepped.path_url, prepped.body)

        for key, value in headers.iteritems():
            prepped.headers[key] = value
        prepped.headers['Content-Type'] = 'application/json'

        logging.debug(prepped.headers)

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


class Connection(object):
    """docstring for Connection."""

    def __init__(self, type, queue, key, secret, expires):
        super(Connection, self).__init__()
        self.type = type
        self.ping_timer = None
        self.key = key
        self.secret = secret
        self.expires = expires
        self.url = WS_URL
        self.queue = queue
        self.retry_delay = INITIAL_RETRY_DELAY

    def _ws_start(self):
        self.socket = websocket.WebSocketApp(self.url,
                                             on_open=self._on_open,
                                             on_message=self._on_message,
                                             on_error=self._on_error,
                                             on_close=self._on_close)
        kwargs = {'sockopt': ((socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),)}
        self.thread = threading.Thread(
            target=self.socket.run_forever, kwargs=kwargs)
        self.thread.start()

    def _on_open(self, *args):
        logging.info('websocket connected')
        self._start_timer()
        self.retry_delay = INITIAL_RETRY_DELAY

    def _on_message(self, message):
        logging.debug(message)

        data = json.loads(message)
        if self.type == 'private' and data['event'] == 'connected':
            self._auth()
            return
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
        self.socket.close()
        time.sleep(self.retry_delay)
        if self.retry_delay < 10:
            self.retry_delay = 2 * self.retry_delay

        self._ws_start()

    def _start_timer(self):
        self.ping_timer = threading.Timer(
            PING_INTERVAL, self._heartbeat)
        self.ping_timer.start()

    def _stop_timer(self):
        if self.ping_timer:
            self.ping_timer.cancel()

    def send_data(self, event, data):
        self.socket.send(json.dumps({
            'event': event,
            'data': data
        }))

    def _heartbeat(self):
        self.send_data('ping', int(time.time()))

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
        self.send_data('authenticate', data)

    def _enqueue_data(self, data):
        self.queue.put(data)

    def start(self):
        self._ws_start()

    def stop(self):
        self.socket.close()
        self._stop_timer()


class Websocket(object):
    """docstring for Websocket."""

    def __init__(self, key, secret, expires):
        super(Websocket, self).__init__()
        self.queue = multiprocessing.Queue(QUEUE_MAX_SIZE)
        self.public = Connection('public', self.queue, key, secret, expires)
        self.private = Connection('private', self.queue, key, secret, expires)

    def start(self):
        self.public.start()
        self.private.start()

    def stop(self):
        self.public.stop()
        self.private.stop()

    def get_data(self):
        return self.queue.get()

    def _subscribe_public(self, topic, kwargs):
        data = dict({'topic': topic}.items() + kwargs.items())
        self.public.send_data('subscribe', data)

    def _subscribe_private(self, topic, kwargs):
        data = dict({'topic': topic}.items() + kwargs.items())
        self.private.send_data('subscribe', data)

    def subscribe_ticker(self, **kwargs):
        self._subscribe_public('ticker', kwargs)

    def subscribe_orderbook(self, **kwargs):
        self._subscribe_public('orderbook', kwargs)

    def subscribe_trade(self, **kwargs):
        self._subscribe_public('trade', kwargs)

    def subscribe_kline(self, **kwargs):
        self._subscribe_public('kline', kwargs)

    def subscribe_order(self, **kwargs):
        self._subscribe_private('order', kwargs)

    def subscribe_account(self, **kwargs):
        self._subscribe_private('account', kwargs)


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


def spiral_test_handle_data(api):
    while True:
        data = api.ws.get_data()
        if data:
            logging.debug('got data:')
            logging.debug(data)
            if data['event'] == 'connected':
                # subscribe public
                api.ws.subscribe_ticker(symbols=["BTCUSDT", "ETHBTC"])
                api.ws.subscribe_orderbook(symbols=["BTCUSDT"])
                api.ws.subscribe_trade(symbols=["BTCUSDT"])
                api.ws.subscribe_kline(symbols=["ETHBTC"], period_minutes=5)
            elif data['event'] == 'authenticated':
                # subscribe private
                api.ws.subscribe_order(symbols=["BTCUSDT"])
                api.ws.subscribe_account()


def spiral_test():
    api_key = '90ee6cf7c4e949cf9c45886b88eb129a'
    api_secret = 'd027e0ec1f85482aa7b255abc08b157a'
    api_expires = 60

    api = Sprial(api_key, api_secret, api_expires)

    api.start()

    api.rest.get_currencies()
    api.rest.get_products()
    api.rest.get_klines(symbol='BTCUSDT', limit=5)
    api.rest.get_orderbook(symbol='BTCUSDT', limit=5)
    api.rest.get_trades(count=5)

    api.rest.get_wallet_balances(currency='USDT')
    api.rest.get_myTrades(count=5)
    api.rest.get_order(count=5, symbol='BTCUSDT', side='ask')
    api.rest.post_order(symbol='BTCUSDT', side='bid',
                        type='limit', quantity='0.01', price='1000')
    api.rest.delete_order(order_id=131513)
    api.rest.delete_order_all()

    try:
        spiral_test_handle_data(api)
    except KeyboardInterrupt:
        pass

    api.stop()


def main():
    format = '%(asctime)s %(filename)s [%(lineno)d][%(levelname)s] %(message)s'
    logging.basicConfig(level=logging.DEBUG, format=format)

    spiral_test()


if __name__ == '__main__':
    main()
