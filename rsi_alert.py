import requests
import pandas as pd
import numpy as np
import time
import datetime
import smtplib
import os
import ssl
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

SERVER = os.environ['SERVER']
PORT = int(os.environ['PORT'])
TO = os.environ['TO']
FROM = os.environ['FROM']
PASSWORD = os.environ['PASSWORD']

def get_rsi_rate(coin_id, ticker):
    res = requests.get(f'https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=1')
    res.raise_for_status()

    coin_data = res.json()
    unzipped = list(zip(*coin_data['prices']))
    df = pd.DataFrame({'ms_datetime': unzipped[0], 'price': unzipped[1]})
    
    # format dataset time
    df['date_time'] = pd.to_datetime(df['ms_datetime'], unit='ms', utc=True)
    df = df[['date_time', 'price']].copy()
    df = df.sort_values(by='date_time')[['date_time', 'price']]

    # cut down to 15-minute intervals
    df['fifteen_min'] = np.tile(range(1, 4), df.shape[0]//3 + 1)[:df.shape[0]]
    df['fifteen_min'] = df['fifteen_min'] == 1
    df = df[df['fifteen_min']].reset_index(drop=True)
    df = df[['date_time', 'price']]
    
    # add rsi
    rsi_periods = 14
    df['price_change'] = df['price'].diff()
    df['pos_pc'] = df['price_change'].apply(lambda x: x if x > 0 else 0)
    df['neg_pc'] = df['price_change'].apply(lambda x: abs(x) if x < 0 else 0)

    df['avg_gain'] = df['pos_pc'].rolling(rsi_periods).mean()
    df['avg_loss'] = df['neg_pc'].rolling(rsi_periods).mean()
    df['rs'] = df['avg_gain'] / df['avg_loss']
    df['rsi'] = 100 - (100 / (1 + df['rs']))
    
    df = df.tail(14)[['date_time', 'rsi']]
    
    current_rsi = df['rsi'].iloc[-1]
    first_rsi = df['rsi'].iloc[0]
    rate = current_rsi / first_rsi - 1
    
    return (ticker, rate, current_rsi)

def send_alert():
    reference = pd.read_csv('target_cb_coins.csv')
    ids = reference[['base', 'coin_id']].values
    data = []

    for tck, cid in ids:
        if tck == 'USDT':
            continue
        time.sleep(8)
        data.append(get_rsi_rate(cid, tck))

    rates = pd.DataFrame(data, columns=['ticker', 'rsi_rate', 'current_rsi'])

    target_tickers = rates[(rates['rsi_rate'] < -0.20) & (rates['current_rsi'] <= 40)]
    target_tickers = target_tickers.sort_values(by='rsi_rate')

    # send email
    if target_tickers.shape[0] > 0:
        with open('outgoing.txt', 'w') as content:
            content.write("Current low RSI Coins:\n\n")
            content.write(target_tickers.to_string())

        with open('outgoing.txt', 'r') as email_out:
            msg = EmailMessage()
            msg.set_content(email_out.read())

        msg['Subject'] = f'Low RSI Alert'
        msg['From'] = FROM
        msg['To'] = TO

        server = smtplib.SMTP(SERVER, PORT)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(FROM, PASSWORD)
        server.send_message(msg)
        server.quit()
    else:
        return
    
if __name__ == "__main__":
    while True:
        interval = 60 * 15
        # run until stopped manually for now
        print(f"Fetching data and running at {datetime.datetime.now()}")
        try:
            send_alert()
            time.sleep(interval)
        except Exception as err:
            print("There was an error:", err)
            print("Retrying in 2 minutes")
            time.sleep(120)
            
