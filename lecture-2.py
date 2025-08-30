import jwt
import hashlib
import os
import requests
import uuid
from urllib.parse import urlencode, unquote

#%%
# api keys
access_key = os.environ['UPBIT_OPEN_API_ACCESS_KEY']
secret_key = os.environ['UPBIT_OPEN_API_SECRET_KEY']
#%%
# url, params, and headers
url = "https://api.upbit.com/v1/orders/chance"
params = {"market": "KRW-BTC"}

#%%
# authorization
query_string = unquote(urlencode(params, doseq=True)).encode("utf-8")
m = hashlib.sha512()
m.update(query_string)
query_hash = m.hexdigest()

payload = {
    'access_key': access_key,
    'nonce': str(uuid.uuid4()),
    'query_hash': query_hash,
    'query_hash_alg': 'SHA512',
}

# headers
jwt_token = jwt.encode(payload, secret_key)
authorization = 'Bearer {}'.format(jwt_token)
headers = {
  'Authorization': authorization,
}
#%%
# placing an order
res = requests.get(url, params=params, headers=headers)
res.json()