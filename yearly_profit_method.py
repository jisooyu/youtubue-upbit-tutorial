import requests
from dotenv import load_dotenv
import pandas as pd
import jwt
import uuid
import hashlib
import time
import os
from urllib.parse import urlencode
from collections import defaultdict, deque
import csv

# ✅ Load .env file explicitly
load_dotenv()  

def get_authorization_token(query={}):
    ACCESS_KEY = os.getenv("UPBIT_OPEN_API_ACCESS_KEY")
    SECRET_KEY = os.getenv("UPBIT_OPEN_API_SECRET_KEY")

    if not ACCESS_KEY or not SECRET_KEY:
        raise ValueError("Access key and Secret key must be provided or set in environment variables.")

    payload = {
        'access_key': ACCESS_KEY,
        'nonce': str(uuid.uuid4()), # 업비트 API에 보낸 요청을 누가 intecept해도 요청을 다시 사용하지 못하게 함. 
    }

    if query:
        m = hashlib.sha512()
        query_string = urlencode(query).encode()
        m.update(query_string)
        payload['query_hash'] = m.hexdigest()
        payload['query_hash_alg'] = 'SHA512' # 업비트에게 검색 payload 암호화 알고리즘을 알려줌. 이를 알아야 업비트가 payload query_hash 다시 계산하여 사용자가 보낸 검색내용과 일치하는 지를 확인할 수 있음. 요청의 파라미터(GET, POST, 종목, 매수/매도, 수량, 가격)를 변환시키지 못하게 하는 기능. 

    jwt_token = jwt.encode(payload, SECRET_KEY, algorithm='HS256') # HS256은 SHA256 알고리즘. SECTRET_KEY를 디지털 싸인으로 변환시켜 사용자가 보낸 요청인지 여부를 확인하는 데 사용하도록 함. SECRETE_KEY의 진위를 확인 즉, 사용자가 본인인지를 확인 할 수 있는 기능
    return f'Bearer {jwt_token}'

def get_order_list(market, page=1):
    url = "https://api.upbit.com/v1/orders"
    query = {
        'market': market, # 종목: ETH/KRW, BTC/KRW
        'state': 'done',
        'page': page,
        'order_by': 'desc', # 매수, 매각
        'limit': 100, # 최대 주문량
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
        print(f"all orders: {all_orders}")
    return all_orders

def calculate_real_pnl(orders):
    inventory = deque()
    pnl_by_date = defaultdict(float)

    for order in sorted(orders, key=lambda x: x['created_at']):
        created_at = pd.to_datetime(order['created_at'])
        date_str = created_at.strftime('%Y-%m-%d') # datetime object를 string로 변환. 나중에 groupby를 사용하기 편하게 하기 위해서 변환.

        executed_volume = float(order['executed_volume']) # volume을 float로 변환하여 executed_volume에 저장
        price = float(order['price']) # price를 float로 변환
        paid_fee = float(order['paid_fee']) # paid_fee를 float로 변환

        """
        executed_volume: 거래하려던 거래량
        remainin_voluem: 거래가 실행되기 전에는 거래하려던 거래량, 거래가 실행된 후에는 거래가 실행 되고 남은 거래량
        buy_volume: inventory에 있던 buy 재고량 
        matched_volume: 실제로 실행된 거래량. remaining_volume과 inventory에 있는 buy_volume 중 최저치
        """

        if order['side'] == 'bid': # 오더가 buy이면 price, executed_volume을 inventory에 append
            inventory.append((price, executed_volume)) 
        elif order['side'] == 'ask': # 오더가 sell이면 executed_volume를 remaining_volume에 저장
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

            pnl_by_date[date_str] += total_profit - paid_fee # 이전에 datetime을 string으로 변환했기 때문에 여기서 사용하기 편함. 

    return pnl_by_date

if __name__ == "__main__":
    
    markets = ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP"]
    total_pnl = defaultdict(float)

    for market in markets:
        orders = collect_all_orders(market)
        # orders에 어떤 정보가 있는 지를 확인하기 위해 csv 파일에 오더를 저장
        with open("orders.csv", "a", newline="") as file:
            writer = csv.writer(file)
            for item in orders:
                writer.writerow([item])
        # order에 대해 손익을 계산
        pnl = calculate_real_pnl(orders)
        for date, value in pnl.items():
            total_pnl[(date, market)] += value

    df = pd.DataFrame([(m[0], m[1], v) for m, v in total_pnl.items()], columns=["Date", "crypto", "P/N"])
    df.sort_values(by=["Date", "crypto"], inplace=True)
    pd.set_option('display.float_format', '{:,.0f}'.format)
    print(df)


   # Ensure 'Date' is in datetime format
    df["Date"] = pd.to_datetime(df["Date"])

    # Extract year
    df["Year"] = df["Date"].dt.year

    # Group by year and sum profits
    yearly_profit = df.groupby("Year")["P/N"].sum()

    # Print formatted results
    for year, profit in yearly_profit.items():
        print(f"{year}년 총 손익: \u20A9{profit:,.0f}")

    total_profit = df['P/N'].sum()
    # total_profit = df["P/N"].sum()
    print(f"2024-2025 총 손익: \u20A9{total_profit:,.0f}")