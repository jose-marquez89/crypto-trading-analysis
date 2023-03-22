import requests
import json
import pandas as pd

res = requests.get(f'https://api.coingecko.com/api/v3/exchanges/gdax/tickers')
res.raise_for_status()

data = res.json()['tickers']
data = json.dumps(data)
df = pd.read_json(data)
df = df[df['target'] == 'USD']
df['usd_vol'] = df['converted_volume'].apply(lambda x: x['usd'])
df = df.sort_values(by='usd_vol', ascending=False)
target_coins = df.reset_index(drop=True)[['base', 'target', 'coin_id']].iloc[:21]

target_coins.to_csv('target_cb_coins.csv', index=False)