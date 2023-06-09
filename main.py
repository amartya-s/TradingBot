import calendar
import datetime
import re
import threading
import time

import pytz
import requests
import telegram
from telethon import TelegramClient, events


# pip install python-telegram-bot
class TransactionType:
    Buy = 'Buy'
    Sell = 'Sell'


class OrderType:
    Limit = 'Limit'
    Market = 'Market'


class Logger:
    token = '2138126360:AAHr6WLgfu7t3UBxbRZODod1W8w145tqE84'
    bot = telegram.Bot(token=token)
    chat_id = -1001606384444

    # chat_id = 1015764287

    @staticmethod
    def log(msg):
        ts = datetime.datetime.strftime(datetime.datetime.now().astimezone(tz=pytz.timezone('Asia/Kolkata')),
                                        '%H:%M:%S')
        print(ts + " " + msg)
        res = requests.get(
            "https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={chat_id}&text={msg}".format(
                BOT_TOKEN=Logger.token, chat_id=Logger.chat_id, msg=msg))

        if res.status_code != 200:
            print("Failed sending msg", res.status_code, res.json())

class KiteHelper:

    @staticmethod
    def place_order(option, lots, price=None, target=None, stoploss=None, order_type=OrderType.Market,
                    transaction_type=TransactionType.Buy):
        """ place order at given price"""

        price = price if order_type == OrderType.Limit else option.get_live_price()

        if transaction_type == TransactionType.Sell:
            # verify if we have an active position
            pass

        Logger.log("Order placed [{transaction_type}] for {option} {lots} lots @{price}".format(
            transaction_type=transaction_type, option=str(option), price=price, lots=lots))

        orders = [price for lot in range(lots)]

        return orders


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
            # utc_now = datetime.datetime(2023,6,8,10)
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
        except:
            raise Exception("Failed fetching live price for {}".format(self))

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

    def trail(self, target_by, stoploss_by):
        self.target += target_by
        self.stoploss -= stoploss_by

    def square_off(self):
        price = KiteHelper.place_order(self.option, 1, transaction_type=TransactionType.Sell)
        self.sell_price = price[0]
        self.is_live = False

    def dump(self):
        Logger.log('Lot {lot_no} {option} | target = {target} | stoploss = {stoploss}'.format(lot_no=self.lot_no,
                                                                                              option=self.option,
                                                                                              target=self.target,
                                                                                              stoploss=self.stoploss))


class OrderProcessor:
    TARGET = 30
    STOPLOSS = 20

    def __init__(self, idx, option, lots):
        self.index = idx
        self.option = option
        self.lots = lots
        self.orders = None
        self.p_and_l = 0

    def start(self):
        price_list = KiteHelper.place_order(self.option, lots=self.lots, order_type=OrderType.Market)
        orders = [Order(idx + 1, self.option, price) for idx, price in enumerate(price_list)]
        for order in orders:
            order.set_target(order.buy_price + OrderProcessor.TARGET)
            order.set_stoploss(order.buy_price - OrderProcessor.STOPLOSS)
            order.dump()

        self.orders = orders

        t = threading.Thread(target=self.monitor)
        t.start()

    def dump(self):
        market_price = self.option.get_live_price()
        active_count = len([order for order in self.orders if order.is_live])

        Logger.log(
            "DUMP [{idx}] {option}| live price={price} | lots={lots} | active={active_count} | Net P_L={p_and_l}".format(
                idx=self.index, option=self.option, lots=self.lots, active_count=active_count,
                price=market_price, p_and_l=round(self.p_and_l, 2)))

    def monitor(self):
        ctr = 0
        while True:
            try:
                active_count = len([order for order in self.orders if order.is_live])
                if active_count == 0:
                    Logger.log(
                        "Stopped monitoring [{idx}] {lots} lots for {option} | P_L={p_and_l}".format(idx=self.index,
                                                                                                     lots=self.lots,
                                                                                                     option=self.option,
                                                                                                     p_and_l=round(
                                                                                                         self.p_and_l,
                                                                                                         2)))
                    return

                time.sleep(5)
                market_price = self.option.get_live_price()

                target_hit = sl_hit = False
                for idx, order in enumerate(self.orders, 1):
                    if order.is_live:
                        if market_price >= order.target:
                            Logger.log("Target hit for lot {index}".format(index=idx))
                            order.square_off()
                            p_and_l = (order.sell_price - order.buy_price) * self.option.lot_size
                            Logger.log("Lot {lot_no} sold @{price}. P_L={p_and_l}".format(lot_no=order.lot_no,
                                                                                          price=order.sell_price,
                                                                                          p_and_l=p_and_l))
                            self.p_and_l += p_and_l
                            target_hit = True
                            break
                        if market_price <= order.stoploss:
                            Logger.log("Stoploss hit for lot {index}".format(index=idx))
                            order.square_off()
                            p_and_l = (order.sell_price - order.buy_price) * self.option.lot_size
                            Logger.log("Lot {lot_no} sold @{price}. P_L={p_and_l}".format(lot_no=order.lot_no,
                                                                                          price=order.sell_price,
                                                                                          p_and_l=p_and_l))
                            self.p_and_l += p_and_l
                            sl_hit = True

                if target_hit:
                    # increase target by 30 and stoploss by 20 for each live orders
                    for order in self.orders:
                        if order.is_live:
                            Logger.log('Trailing lot {lot_no}'.format(lot_no=order.lot_no))
                            order.trail(target_by=OrderProcessor.TARGET, stoploss_by=OrderProcessor.STOPLOSS)
                            order.dump()
                ctr += 1
                if ctr % 50 == 0:
                    Logger.log(
                        "Monitoring [{idx}] {option}| live price={price} | lots={lots} | active={active_count} | Net P_L={p_and_l}".format(
                            idx=self.index, option=self.option, lots=self.lots, active_count=active_count,
                            price=market_price, p_and_l=round(self.p_and_l, 2)))
            except Exception as e:
                Logger.log('Something failed in thread {}'.format(str(e)))


class TeleBot:
    API_ID = 18476711
    API_HASH = '6842c461dfe76b7586f4a7f2a30b4c45'
    PATTERN = r"(\d+)\s*(CE|PE|Ce|Pe|ce|pe|cE|pE)"

    def __init__(self):
        self.client = TelegramClient('session_name', TeleBot.API_ID, TeleBot.API_HASH)
        self.client.start()
        Logger.log("telegram client started")

    @staticmethod
    def next_thursday(date):
        days_ahead = 3 - date.weekday()  # 3 = Thursday
        if days_ahead < 0:  # Target day already happened this week
            days_ahead += 7
        return date + datetime.timedelta(days_ahead)

    def start_listener(self, channel, regex=None):

        all_orders = []

        @self.client.on(events.NewMessage(chats=channel))
        async def new_message_listener(event):
            try:
                message_from_event = event.message.message
                Logger.log("Received event with message:\n" + message_from_event[:100])
                match = re.search(TeleBot.PATTERN, message_from_event)
                if match:
                    if not 'Sl  only to paid premium member'.lower() in message_from_event.lower():
                        Logger.log('Regex match but SL missing. Ignoring message')
                        if not all_orders:
                            Logger.log('No orders placed yet')
                            return
                        for order in all_orders:
                            order.dump()
                        return
                    strike_price = match.group(1)
                    option_type = match.group(2)
                    expiry_date = TeleBot.next_thursday(datetime.datetime.today().date())  # next thursday
                    Logger.log("Expiry: {}".format(expiry_date))
                    option_type = 'CALL' if option_type.upper() == 'CE' else 'PUT'
                    option = Option(expiry_date, option_type, int(strike_price))
                    processor = OrderProcessor(len(all_orders) + 1, option, lots=3)
                    processor.start()
                    all_orders.append(processor)
                else:
                    Logger.log('Regex did not match')
                    if not all_orders:
                        Logger.log('No orders placed yet')
                        return
                    for order in all_orders:
                        order.dump()

            except Exception as e:
                Logger.log("Something failed in main handler {}".format(str(e)))

        with self.client:
            Logger.log("Listening for messages on channel {channel}".format(channel=channel))
            self.client.run_until_disconnected()


# user_input_channel = 'https://t.me/optiontelebot'
# user_input_channel = 'https://t.me/wolf_Calls_Official_bank_nifty'
user_input_channel = 'https://t.me/wolf_Calls_Official_bank_nifty'
bot = TeleBot()
bot.start_listener(user_input_channel)
