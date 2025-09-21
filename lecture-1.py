# pip install PyJWT
#%%
# libraries
import jwt as pyjwt
import os
import requests
import uuid
from dotenv import load_dotenv
#%%
# ✅ Load .env file explicitly
load_dotenv()  
#%%
# api keys
ACCESS_KEY = os.environ['UPBIT_OPEN_API_ACCESS_KEY']
SECRET_KEY = os.environ['UPBIT_OPEN_API_SECRET_KEY']
# server_url = os.environ['UPBIT_OPEN_API_SERVER_URL']
#%%
# authorization
payload = {
    'access_key': ACCESS_KEY,
    'nonce': str(uuid.uuid4()), # 업비트 API에 보낸 요청을 누가 불법으로 가로채도 요청을 다시 사용하지 못하게 함. 
}

jwt_token = pyjwt.encode(payload, SECRET_KEY)
authorization = 'Bearer {}'.format(jwt_token)
#%%
# url, params, and headers
url = "https://api.upbit.com/v1/candles/days"
params = {"market": "KRW-ETH", "count": 200}

headers = {
  'Authorization': authorization,
  "Accept": "application/json"
}
#%%
# fetch data
res = requests.get(url, headers=headers, params=params).json()
print(res)