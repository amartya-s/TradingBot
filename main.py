
import datetime
import re

from telethon import TelegramClient, events

from TradingBot.common import Option
from TradingBot.logger import Logger
from TradingBot.strategy.s1 import OrderProcessor as Strategy1


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

        all_orders = dict()

        @self.client.on(events.NewMessage(chats=channel))
        async def new_message_listener(event):
            try:
                expiry_date = TeleBot.next_thursday(datetime.datetime.today().date())  # next thursday
                all_orders.setdefault(expiry_date, [])

                message_from_event = event.message.message
                #Logger.log("Received event with message:\n" + message_from_event[:100])
                match = re.search(TeleBot.PATTERN, message_from_event)
                if match:
                    if 'sl' not in message_from_event.lower() and 'only' not in message_from_event.lower():
                        Logger.log('Regex match but SL/Only missing. Ignoring message')
                        if not all_orders[expiry_date]:
                            Logger.log('No orders placed yet')
                            return
                        for order in all_orders[expiry_date]:
                            order.dump()
                        return
                    Logger.log("Received event with message:\n" + message_from_event)
                    strike_price = int(match.group(1))
                    option_type = match.group(2)
                    Logger.log("Expiry: {}".format(expiry_date))
                    option_type = 'CALL' if option_type.upper() == 'CE' else 'PUT'
                    # check for any open opposite trades. It does not makes sense to have 2 opposite open positions.
                    for order in all_orders[expiry_date]:
                        if order.is_live:
                            prev_option = order.option
                            if prev_option.type != option_type:
                                Logger.log("OPPOSITE LIVE POSITION FOUND IN ORDER [{}]".format(order.index))
                                order.sqaure_off_live_positions()
                            if prev_option.type == option_type and prev_option.strike_price == strike_price:
                                Logger.log("DUPLICATE ORDER RECEIVED. Ignoring")
                                return

                    option = Option(expiry_date, option_type, strike_price)
                    processor = Strategy1(len(all_orders[expiry_date]) + 1, option, lots=10)
                    processor.start()
                    all_orders[expiry_date].append(processor)
                else:
                    Logger.log('Regex did not match')
                    if not all_orders[expiry_date]:
                        Logger.log('No orders placed yet')
                        return
                    for order in all_orders[expiry_date]:
                        order.dump()

            except Exception as e:
                Logger.log("Something failed in main handler {}".format(str(e)))

        with self.client:
            Logger.log("Listening for messages on channel {channel}".format(channel=channel))
            self.client.run_until_disconnected()


user_input_channel = 'https://t.me/optiontelebot'
# user_input_channel = 'https://t.me/wolf_Calls_Official_bank_nifty'
# user_input_channel = 'https://t.me/BANK_Nifty_WOLF_CALLS_OFFICIALq'
bot = TeleBot()
bot.start_listener(user_input_channel)
