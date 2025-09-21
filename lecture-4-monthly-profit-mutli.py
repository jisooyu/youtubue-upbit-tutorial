import requests
import pandas as pd
import jwt
import uuid
import hashlib
import time
import os
from urllib.parse import urlencode
from collections import defaultdict, deque

def get_authorization_token(query={}):
    ACCESS_KEY = os.environ['UPBIT_OPEN_API_ACCESS_KEY']
    SECRET_KEY = os.environ['UPBIT_OPEN_API_SECRET_KEY']
    payload = {
        'access_key': ACCESS_KEY,
        'nonce': str(uuid.uuid4()),
    }
    if query:
        m = hashlib.sha512()
        query_string = urlencode(query).encode()
        m.update(query_string)
        payload['query_hash'] = m.hexdigest()
        payload['query_hash_alg'] = 'SHA512'

    jwt_token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    return f'Bearer {jwt_token}'

def get_order_list(market, page=1):
    url = "https://api.upbit.com/v1/orders"
    query = {
        'market': market,
        'state': 'done',
        'page': page,
        'order_by': 'desc',
        'limit': 100,
    }
    headers = {
        'Authorization': get_authorization_token(query)
    }
    response = requests.get(url, headers=headers, params=query)
    if response.status_code == 200:
        return response.json()
    else:
        print(response.json())
        return []

def collect_all_orders(market):
    all_orders = []
    page = 1
    while True:
        orders = get_order_list(market, page)
        if not orders:
            break
        all_orders.extend(orders)
        if len(orders) < 100:
            break
        page += 1
        time.sleep(0.2)
    return all_orders

def calculate_real_pnl(orders):
    inventory = deque()
    pnl_by_month = defaultdict(float)

    for order in sorted(orders, key=lambda x: x['created_at']):
        created_at = pd.to_datetime(order['created_at'])
        month_str = created_at.strftime('%Y-%m')

        executed_volume = float(order['executed_volume'])
        price = float(order['price'])
        paid_fee = float(order['paid_fee'])

        if order['side'] == 'bid':
            inventory.append((price, executed_volume))
        elif order['side'] == 'ask':
            remaining_volume = executed_volume
            total_profit = 0.0

            while remaining_volume > 0 and inventory:
                buy_price, buy_volume = inventory.popleft()
                matched_volume = min(remaining_volume, buy_volume)
                profit = (price - buy_price) * matched_volume
                total_profit += profit

                if buy_volume > matched_volume:
                    inventory.appendleft((buy_price, buy_volume - matched_volume))
                remaining_volume -= matched_volume

            pnl_by_month[month_str] += total_profit - paid_fee

    return pnl_by_month

if __name__ == "__main__":
    markets = ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP"]
    total_pnl = defaultdict(float)

    for market in markets:
        orders = collect_all_orders(market)
        pnl = calculate_real_pnl(orders)
        for month, value in pnl.items():
            total_pnl[(market, month)] += value

    df = pd.DataFrame([(m[0], m[1], v) for m, v in total_pnl.items()], columns=["Crypto", "Date", "P/L"])
    df.sort_values(by=["Date", "Crypto"], inplace=True)
    pd.set_option('display.float_format', '{:,.0f}'.format) # 일반숫자 형태로 표시
    print(df)
    total_profit = df['P/L'].sum()
    print(f"전체 기간 총 손익: \u20A9{total_profit:,.0f}")
