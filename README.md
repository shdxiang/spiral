# spiral

Python API for https://www.spiral.exchange/

## Usage

Install requirements:

```
pip install -r requirements.txt
```

Example:

[example.py](example.py)

```
python example.py
```

## Examples for all API

### Reference

https://docs.spiral.exchange/en/latest/api_introduction.html

### spiral

```
api = Sprial(api_key, api_secret, api_expires)
api.start()
api.stop()
```

### spiral REST

#### Public

```
api.rest.get_currencies()
api.rest.get_products()
api.rest.get_klines(symbol='BTCUSDT', limit=5)
api.rest.get_orderbook(symbol='BTCUSDT', limit=5)
api.rest.get_trades(count=5)
```

#### Private

```
api.rest.get_wallet_balances(currency='USDT')
api.rest.get_myTrades(count=5)
api.rest.get_order(count=5, symbol='BTCUSDT', side='ask')
api.rest.post_order(symbol='BTCUSDT', side='bid', type='limit', quantity='0.01', price='1000')
api.rest.delete_order(order_id=131513)
api.rest.delete_order_all()
```

### spiral Websocket

#### Public

```
api.ws.subscribe_ticker(symbols=["BTCUSDT", "ETHBTC"])
api.ws.subscribe_orderbook(symbols=["BTCUSDT"])
api.ws.subscribe_trade(symbols=["BTCUSDT"])
api.ws.subscribe_kline(symbols=["ETHBTC"], period_minutes=5)
```

#### Private

```
api.ws.subscribe_order(symbols=["BTCUSDT"])
api.ws.subscribe_account()
```
