# pip install PyJWT
#%%
# libraries
import jwt as pyjwt
import hashlib
import os
import requests
import uuid
from urllib.parse import urlencode, unquote
#%%
# api keys
access_key = os.environ['UPBIT_OPEN_API_ACCESS_KEY']
secret_key = os.environ['UPBIT_OPEN_API_SECRET_KEY']
# server_url = os.environ['UPBIT_OPEN_API_SERVER_URL']
#%%
# authorization
payload = {
    'access_key': access_key,
    'nonce': str(uuid.uuid4()),
}

jwt_token = pyjwt.encode(payload, secret_key)
authorization = 'Bearer {}'.format(jwt_token)
#%%
# url, params, and headers
url = "https://api.upbit.com/v1/candles/days"
params = {"market": "KRW-BTC", "count": 200}

headers = {
  'Authorization': authorization,
  "Accept": "application/json"
}
#%%
# fetch data
res = requests.get(url, headers=headers, params=params).json()
print(res)