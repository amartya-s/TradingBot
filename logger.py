import datetime

import pytz
import requests
import telegram


class Logger:
    token = '2138126360:AAHr6WLgfu7t3UBxbRZODod1W8w145tqE84'
    bot = telegram.Bot(token=token)
    chat_id = -1001855751660

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
