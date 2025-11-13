import os
import time
import uuid
import hashlib
import requests
import pandas as pd
from urllib.parse import urlencode
from collections import defaultdict, deque
from dotenv import load_dotenv # only for Mac
import jwt

# Load .env if available
load_dotenv() # only for Mac

class UpbitAPI:
    BASE_URL = "https://api.upbit.com"

    def __init__(self, access_key=None, secret_key=None):
        self.access_key = access_key or os.getenv("UPBIT_OPEN_API_ACCESS_KEY")
        self.secret_key = secret_key or os.getenv("UPBIT_OPEN_API_SECRET_KEY")
        if not self.access_key or not self.secret_key:
            raise ValueError("Access key and Secret key must be provided or set in environment variables.")

    def _get_authorization_token(self, query=None):
        query = query or {}
        payload = {
            'access_key': self.access_key,
            'nonce': str(uuid.uuid4()),
        }

        if query:
            m = hashlib.sha512()
            query_string = urlencode(query).encode()
            m.update(query_string)
            payload['query_hash'] = m.hexdigest()

            """ 업비트에게 검색 payload 암호화 알고리즘을 알려줌. 이를 알아야 업비트가 payload query_hash 다시 계산하여 사용자가 보낸 검색내용과 일치하는 지를 확인할 수 있음. 요청의 파라미터(GET, POST, 종목, 매수/매도, 수량, 가격)를 변환시키지 못하게 하는 기능. """

            payload['query_hash_alg'] = 'SHA512' 
            """ HS256은 SHA256 알고리즘. SECTRET_KEY를 디지털 싸인으로 변환시켜 사용자가 보낸 요청인지 여부를 확인하는 데 사용하도록 함. SECRETE_KEY의 진위를 확인 즉, 사용자가 본인인지를 확인 할 수 있는 기능 """
            
        jwt_token = jwt.encode(payload, self.secret_key, algorithm='HS256') 

        if isinstance(jwt_token, bytes):
            jwt_token = jwt_token.decode('utf-8')
        return f'Bearer {jwt_token}'

    def get_order_list(self, market, page=1):
        url = f"{self.BASE_URL}/v1/orders"
        query = {
            'market': market,# 종목: ETH/KRW, BTC/KRW
            'state': 'done',
            'page': page,
            'order_by': 'desc',# 매수, 매각
            'limit': 100, # 최대 주문량
        }
        headers = {'Authorization': self._get_authorization_token(query)}
        response = requests.get(url, headers=headers, params=query)
        if response.status_code == 200:
            return response.json()
        else:
            print(response.json())
            return []

    def collect_all_orders(self, market):
        all_orders = []
        page = 1
        while True:
            orders = self.get_order_list(market, page)
            if not orders:
                break
            all_orders.extend(orders)
            if len(orders) < 100:
                break
            page += 1
            time.sleep(0.2)
        return all_orders

    def calculate_real_pnl(self, orders):
        """
        executed_volume: 거래하려던 거래량
        remainin_volume: 거래가 실행되기 전에는 거래하려던 거래량, 거래가 실행된 후에는 거래가 실행 되고 남은 거래량
        buy_volume: inventory에 있던 buy 재고량 
        matched_volume: 실제로 실행된 거래량. remaining_volume과 inventory에 있는 buy_volume 중 최저치
        """
        inventory = deque() # deque를 사용하여 이전 매수 주문을 저장. 매도주문이 들어오면 이전 매수주문과 매치를 함. (FIFO 로직) 
        pnl_by_date = defaultdict(float) # 새로운 주문을 0.0으로 초기화하는 딕셔너리. 각 일자별로 pnl을 저장하는 데 사용

        for order in sorted(orders, key=lambda x: x['created_at']):
            created_at = pd.to_datetime(order['created_at']) #주문 생성시기
            date_str = created_at.strftime('%Y-%m-%d') # 주문 생성시기 -> 스트링으로 변환
            executed_volume = float(order['executed_volume']) # volume을 실수로 변환하여 executed_volume에 저장
            price = float(order['price']) # 주문 가격 -> 실수로 변환
            paid_fee = float(order['paid_fee']) # 주문 코미션 -> 실수로 변환

            if order['side'] == 'bid': # 매수의 경우
                inventory.append((price, executed_volume))  # 매수 실행볼륨과 매수가를 inventory에 추가 (sell)
            elif order['side'] == 'ask': # 매도의 경우 
                remaining_volume = executed_volume # 매도 샐행볼륨이 잔존 볼륨으로 됨
                total_profit = 0.0

                while remaining_volume > 0 and inventory: # 잔존볼륨이 재고 보다 클 경우
                    buy_price, buy_volume = inventory.popleft() # 재고에서 FIFO순으로 매수가와 매수량을 추출. 재고의 예제 [(2000, 3), (2100, 2)]
                    matched_volume = min(remaining_volume, buy_volume) # 잔존량과 매수량을 중 적을 것을 matched_volume에 저장
                    profit = (price - buy_price) * matched_volume # 이익을 계산
                    total_profit += profit # 누적이익을 계산
                    # 만약 재고에 있는 매수량이 matched volume보다 크면
                    if buy_volume > matched_volume:
                        inventory.appendleft((buy_price, buy_volume - matched_volume)) # 매수량 중 남은 부분은 재고의 매 처음( 맨 밑)에 추가
                    remaining_volume -= matched_volume 

                pnl_by_date[date_str] += total_profit - paid_fee

        return pnl_by_date

if __name__ == "__main__":
    upbit = UpbitAPI()

    markets = ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP"]
    total_pnl = defaultdict(float)

    for market in markets:
        orders = upbit.collect_all_orders(market)
        pnl = upbit.calculate_real_pnl(orders)
        for date, value in pnl.items():
            total_pnl[(date, market)] += value

    df = pd.DataFrame([(m[0], m[1], v) for m, v in total_pnl.items()],
                      columns=["Date", "Crypto", "P/N"])
    # Ensure 'Date' is in datetime format
    df["Date"] = pd.to_datetime(df["Date"])

    # Extract year
    df["Year"] = df["Date"].dt.year

    df.sort_values(by=["Date", "Crypto"], inplace=True)
    pd.set_option('display.float_format', '{:,.0f}'.format)
    print(df)

    # Group by year and sum profits
    yearly_total_profit = df.groupby("Year")["P/N"].sum()

    # Print formatted results
    for year, profit in yearly_total_profit.items():
        print(f"{year}년 총 손익: \u20A9{profit:,.0f}")

    total_profit = df['P/N'].sum()
    # total_profit = df["P/N"].sum()
    print(f"2024-2025 총 손익: \u20A9{total_profit:,.0f}")


