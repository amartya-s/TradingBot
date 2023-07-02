import calendar
import datetime

import requests

from TradingBot.enums import TransactionType
from TradingBot.kitehelper import KiteHelper


# pip install python-telegram-bot


class Option:
    LIVE_PRICE_URL = 'https://groww.in/v1/api/stocks_fo_data/v1/charting_service/chart/exchange/NSE/segment/FNO/BANKNIFTY23{expiry}{strike}{type}?endTimeInMillis={to}&intervalInMinutes=1&startTimeInMillis={frm}'

    def __init__(self, expiry, option_type, strike_price):
        self.expiry = expiry
        self.type = option_type
        self.strike_price = strike_price
        self.lot_size = 25

    def __str__(self):
        return self.expiry.strftime('%d%b') + ' ' + str(self.strike_price) + self.type

    def get_live_price(self):
        """ return market price of for this option """

        try:
            option_type = 'CE' if self.type == 'CALL' else 'PE'

            # get last 5 minutes candlestick
            utc_now = datetime.datetime.now()
            utc_now = datetime.datetime(2023, 6, 30, 10)
            utc_5_mins_back = utc_now - datetime.timedelta(minutes=5)
            milliseconds_from, milliseconds_to = int(utc_5_mins_back.timestamp()) * 1000, int(
                utc_now.timestamp()) * 1000

            # format expiry for url
            is_monthly_expiry = calendar.monthrange(self.expiry.year, self.expiry.month)[-1] - self.expiry.day < 7
            expiry = self.expiry.strftime('%b').upper() if is_monthly_expiry else datetime.datetime.strftime(
                self.expiry,
                '%m%d')
            expiry = expiry[1:] if expiry.startswith('0') else expiry

            url = Option.LIVE_PRICE_URL.format(
                expiry=expiry, strike=self.strike_price, type=option_type, frm=milliseconds_from, to=milliseconds_to)

            response = requests.get(url)
            option_data = response.json()
            latest_price = option_data['candles'][-1][-2]

        except Exception as e:
            raise Exception("Failed fetching live price for {} - {}".format(self, e))

        return latest_price


class Order:
    def __init__(self, lot_no, option, buy_price):
        self.lot_no = lot_no
        self.option = option
        self.buy_price = buy_price
        self.target = None
        self.stoploss = None
        self.is_live = True
        self.sell_price = None

    def set_target(self, target):
        self.target = target

    def set_stoploss(self, stoploss):
        self.stoploss = stoploss

    def trail(self, target_by=0, stoploss_by=0):
        self.target += target_by
        self.stoploss += stoploss_by

    def square_off(self):
        price = KiteHelper.place_order(self.option, 1, transaction_type=TransactionType.Sell)
        self.sell_price = price[0]
        self.is_live = False

    def __str__(self):
        return 'Lot {lot_no} @{price} | tgt={target} | sl= {stoploss} | p_l = {p_l}'.format(
            lot_no=self.lot_no,
            price=self.buy_price,
            target=self.target,
            stoploss=self.stoploss,
            p_l='N/A' if self.is_live else (self.sell_price - self.buy_price) * self.option.lot_size)
