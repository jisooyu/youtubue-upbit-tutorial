import requests
import pandas as pd
import jwt
import uuid
import hashlib
import os
import time
from urllib.parse import urlencode
from dotenv import load_dotenv
from collections import defaultdict, deque

# ✅ Load .env file explicitly
load_dotenv()  

def get_authorization_token(query={}):
    # 업비트 API 키 입력
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
        payload['query_hash_alg'] = 'SHA512'# 업비트에게 검색 payload 암호화 알고리즘을 알려줌. 이를 알아야 업비트가 payload query_hash 다시 계산하여 사용자가 보낸 검색내용과 일치하는 지를 확인할 수 있음. 요청의 파라미터(GET, POST, 종목, 매수/매도, 수량, 가격)를 변환시키지 못하게 하는 기능. 

    jwt_token = jwt.encode(payload, SECRET_KEY, algorithm='HS256') # HS256은 SHA256 알고리즘. SECTRET_KEY를 디지털 싸인으로 변환시켜 사용자가 보낸 요청인지 여부를 확인하는 데 사용하도록 함. SECRETE_KEY의 진위를 확인 즉, 사용자가 본인인지를 확인 할 수 있는 기능
    authorization_token = f'Bearer {jwt_token}'
    return authorization_token

def get_order_list(market, page=1):
    url = "https://api.upbit.com/v1/orders"
    query = {
        'market': market,# 종목: ETH/KRW, BTC/KRW
        'state': 'done',
        'page': page,
        'order_by': 'desc',# 매수, 매각
        'limit': 100,# 최대 주문량
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
        month_str = created_at.strftime('%Y-%m') # datetime object를 string로 변환. 나중에 groupby를 사용하기 편하게 하기 위해서 변환.

        executed_volume = float(order['executed_volume']) # volume을 float로 변환하여 executed_volume에 저장
        price = float(order['price']) # price를 float로 변환
        paid_fee = float(order['paid_fee']) # paid_fee를 float로 변환

        """
        executed_volume: 거래하려던 거래량
        remainin_voluem: 거래가 실행되기 전에는 거래하려던 거래량, 거래가 실행된 후에는 거래가 실행 되고 남은 거래량
        buy_volume: inventory에 있던 buy 재고량 
        matched_volume: 실제로 실행된 거래량. remaining_volume과 inventory에 있는 buy_volume 중 최저치
        """

        if order['side'] == 'bid':
            # 매수: 보유 목록에 추가
            inventory.append((price, executed_volume))
        elif order['side'] == 'ask':
            remaining_volume = executed_volume
            total_profit = 0.0

            # remaining_voluem이 0보다 크고 inventory가 있으면 ...
            while remaining_volume > 0 and inventory:
                
                buy_price, buy_volume = inventory.popleft() # inventory에서 FIFO순으로 buy_price와 buy_volume을 추출
                matched_volume = min(remaining_volume, buy_volume) # remainng_volume와 buy_volume 중 적을 것을 matched_volume에 저장
                profit = (price - buy_price) * matched_volume # 이익을 계산
                total_profit += profit # 누적이익을 계산

                # 만약 inventory에 있던 buy_volume이 matched volume보다 크면
                if buy_volume > matched_volume:
                    inventory.appendleft((buy_price, buy_volume - matched_volume)) # buy_volume 중에 남은 부분은 inventory의 맨 처음( 맨 밑)에 append

                remaining_volume -= matched_volume # remaining_volume에서 실제로 거래가 실행된 부분을 삭감. 

            pnl_by_month[month_str] += total_profit - paid_fee # 이전에 datetime을 string으로 변환했기 때문에 여기서 사용하기 편함. 

    return pnl_by_month

if __name__ == "__main__":
    market = "KRW-ETH"  # 원하는 마켓 설정
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

