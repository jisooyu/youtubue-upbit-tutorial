import jwt
import hashlib
import os
import requests
import uuid
from urllib.parse import urlencode, unquote
from dotenv import load_dotenv

# ✅ Load .env file explicitly
load_dotenv()  

# api keys
ACCESS_KEY = os.environ['UPBIT_OPEN_API_ACCESS_KEY']
SECRET_KEY = os.environ['UPBIT_OPEN_API_SECRET_KEY']

# url, params, and headers
# 나의 잔고, 최저 주문량, 거래통화, 거래수수료 등의 정보
url = "https://api.upbit.com/v1/orders/chance"
params = {"market": "KRW-ETH"}

# authorization
query_string = unquote(urlencode(params, doseq=True)).encode("utf-8")
m = hashlib.sha512()
m.update(query_string)
query_hash = m.hexdigest()

payload = {
    'access_key': ACCESS_KEY,
    'nonce': str(uuid.uuid4()),
    'query_hash': query_hash,
    'query_hash_alg': 'SHA512',# 업비트에게 검색 payload 암호화 알고리즘을 알려줌. 이를 알아야 업비트가 payload query_hash 다시 계산하여 사용자가 보낸 검색내용과 일치하는 지를 확인할 수 있음. 요청의 파라미터(GET, POST, 종목, 매수/매도, 수량, 가격)를 변환시키지 못하게 하는 기능. 
}

# headers
jwt_token = jwt.encode(payload, SECRET_KEY) # HS256은 SHA256 알고리즘. SECTRET_KEY를 디지털 싸인으로 변환시켜 사용자가 보낸 요청인지 여부를 확인하는 데 사용하도록 함. SECRETE_KEY의 진위를 확인 즉, 사용자가 본인인지를 확인 할 수 있는 기능
authorization = 'Bearer {}'.format(jwt_token)
headers = {
  'Authorization': authorization,
}

# placing an order
res = requests.get(url, params=params, headers=headers)
result = res.json()
print(result)