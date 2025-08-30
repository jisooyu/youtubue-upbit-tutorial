import requests
import pandas as pd
import jwt
import uuid
import hashlib
import os
import time
from urllib.parse import urlencode
from collections import defaultdict, deque

# 업비트 API 키 입력
ACCESS_KEY = os.environ['UPBIT_OPEN_API_ACCESS_KEY']
SECRET_KEY = os.environ['UPBIT_OPEN_API_SECRET_KEY']

def get_authorization_token(query={}):
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
    authorization_token = f'Bearer {jwt_token}'
    return authorization_token

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
    return response.json()

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
        time.sleep(0.1)  # API rate limit 고려
    return all_orders

def calculate_real_pnl(orders):
    inventory = deque()  # (단가, 수량) 순서대로 보유
    pnl_by_month = defaultdict(float)

    for order in sorted(orders, key=lambda x: x['created_at']):  # 시간 순 정렬
        created_at = pd.to_datetime(order['created_at'])
        month_str = created_at.strftime('%Y-%m')

        executed_volume = float(order['executed_volume'])
        price = float(order['price'])
        paid_fee = float(order['paid_fee'])

        if order['side'] == 'bid':
            # 매수: 보유 목록에 추가
            inventory.append((price, executed_volume))
        elif order['side'] == 'ask':
            remaining_volume = executed_volume
            total_profit = 0.0

            while remaining_volume > 0 and inventory:
                buy_price, buy_volume = inventory.popleft()
                matched_volume = min(remaining_volume, buy_volume)
                profit = (price - buy_price) * matched_volume
                total_profit += profit

                # 남은 수량 다시 넣기
                if buy_volume > matched_volume:
                    inventory.appendleft((buy_price, buy_volume - matched_volume))

                remaining_volume -= matched_volume

            pnl_by_month[month_str] += total_profit - paid_fee

    return pnl_by_month

if __name__ == "__main__":
    market = "KRW-XRP"  # 원하는 마켓 설정
    orders = collect_all_orders(market)
    pnl_by_month = calculate_real_pnl(orders)
    print(pnl_by_month)

    # DataFrame으로 보기 좋게 출력
    df = pd.DataFrame(list(pnl_by_month.items()), columns=['월', '손익(KRW)'])
    pd.set_option('display.float_format', '{:,.0f}'.format)
    df.sort_values(by='월', inplace=True)
    total_amount = df['손익(KRW)'].sum() 
    print(df)
    print(f"Total profit/loss is {total_amount:,.0f} KRW")

