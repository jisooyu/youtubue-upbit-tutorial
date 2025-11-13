import os
import time
import uuid
import hashlib
import requests
import pandas as pd
from urllib.parse import urlencode
from collections import defaultdict, deque
from dotenv import load_dotenv
import jwt

# Load .env if available
load_dotenv()


class UpbitAPI:
    BASE_URL = "https://api.upbit.com"

    def __init__(self, access_key=None, secret_key=None):
        self.access_key = access_key or os.getenv("UPBIT_OPEN_API_ACCESS_KEY")
        self.secret_key = secret_key or os.getenv("UPBIT_OPEN_API_SECRET_KEY")
        if not (self.access_key and self.secret_key):
            raise ValueError("Access/Secret keys must be provided or set in env variables.")

    # ----------------------------------------------------------
    # Authorization Token
    # ----------------------------------------------------------
    def _get_authorization_token(self, query=None):
        query = query or {}
        payload = {
            'access_key': self.access_key,
            'nonce': str(uuid.uuid4()),
        }

        # If the request has query params, hash them for Upbit verification
        if query:
            query_string = urlencode(query).encode()
            h = hashlib.sha512()
            h.update(query_string)

            payload['query_hash'] = h.hexdigest()
            payload['query_hash_alg'] = 'SHA512'

        jwt_token = jwt.encode(payload, self.secret_key, algorithm='HS256')
        if isinstance(jwt_token, bytes):
            jwt_token = jwt_token.decode()
        return f'Bearer {jwt_token}'

    # ----------------------------------------------------------
    # Order Fetching
    # ----------------------------------------------------------
    def get_order_list(self, market, page=1):
        url = f"{self.BASE_URL}/v1/orders"
        query = {
            'market': market,
            'state': 'done',
            'page': page,
            'order_by': 'desc',
            'limit': 100,
        }
        headers = {'Authorization': self._get_authorization_token(query)}
        r = requests.get(url, headers=headers, params=query)

        if r.status_code == 200:
            return r.json()
        else:
            print("❌ API Error:", r.json())
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

    # ----------------------------------------------------------
    # FIFO Realized PnL Calculator
    # ----------------------------------------------------------
    def calculate_real_pnl(self, orders):
        """
        Calculate realized PnL using FIFO matching of buy → sell.
        Returns: dict { 'YYYY-MM-DD': pnl_value }
        """
        inventory = deque()
        pnl_by_date = defaultdict(float)

        for order in sorted(orders, key=lambda x: x["created_at"]):
            created_at = pd.to_datetime(order["created_at"])
            date_str = created_at.strftime("%Y-%m-%d")

            executed_volume = float(order["executed_volume"])
            price = float(order["price"])
            fee = float(order["paid_fee"])

            if order["side"] == "bid":   # Buy
                inventory.append((price, executed_volume))

            elif order["side"] == "ask":  # Sell
                remaining = executed_volume
                realized = 0.0

                # FIFO match against inventory
                while remaining > 0 and inventory:
                    buy_price, buy_volume = inventory.popleft()
                    matched = min(remaining, buy_volume)
                    realized += (price - buy_price) * matched

                    if buy_volume > matched:
                        inventory.appendleft((buy_price, buy_volume - matched))

                    remaining -= matched

                pnl_by_date[date_str] += realized - fee

        return pnl_by_date

    # ----------------------------------------------------------
    # NEW: Full PNL DataFrame Builder
    # ----------------------------------------------------------
    def compute_pnl_dataframe(self, markets):
        """
        Fetches order history for all markets,
        computes realized PNL per-day per-crypto,
        and returns a tidy DataFrame.
        """
        total_pnl = defaultdict(float)

        for market in markets:
            orders = self.collect_all_orders(market)
            pnl_dict = self.calculate_real_pnl(orders)

            for date, pnl_value in pnl_dict.items():
                total_pnl[(date, market)] += pnl_value

        # Convert to DataFrame
        df = pd.DataFrame(
            [(date, market, pnl) for (date, market), pnl in total_pnl.items()],
            columns=["Date", "Crypto", "P/N"]
        )

        df["Date"] = pd.to_datetime(df["Date"])
        df["Year"] = df["Date"].dt.year
        df.sort_values(by=["Date", "Crypto"], inplace=True)

        return df


# ==========================================================
# Main
# ==========================================================
if __name__ == "__main__":
    upbit = UpbitAPI()
    markets = ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP"]

    df = upbit.compute_pnl_dataframe(markets)

    pd.set_option('display.float_format', '{:,.0f}'.format)
    print(df)

    # Yearly profit summary
    yearly_profit = df.groupby("Year")["P/N"].sum()
    for year, profit in yearly_profit.items():
        print(f"{year}년 총 손익: ₩{profit:,.0f}")

    total_profit = df["P/N"].sum()
    print(f"2024-2025 총 손익: ₩{total_profit:,.0f}")
