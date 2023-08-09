import calendar
import datetime
import sqlite3 as sl

from TradingBot.enums import TransactionType, ExitType
from TradingBot.kitehelper import KiteHelper


# pip install python-telegram-bot

class SQLiteHelper:
    TABLE_NAME = 'optiontrading'

    def __init__(self):
        self.con = sl.connect(SQLiteHelper.TABLE_NAME, check_same_thread=True)
        self.con.execute("""CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                date DATE,
                expiry DATE,
                order_no INT,
                option STRING,
                lot_no int,
                entry_type string,
                buy_price float,
                sell_price float,
                exit_type string,
                p_l float
            );""".format(table_name=SQLiteHelper.TABLE_NAME))
        print("{} initialised".format(SQLiteHelper.TABLE_NAME))

    def fetch_last_order(self, date):
        records = self.con.execute(
            """SELECT * FROM {table_name} WHERE date=?""".format(table_name=SQLiteHelper.TABLE_NAME),
            (date,)).fetchall()
        return records[-1] if records else None

    def insert_or_update_record(self, expiry, order_no, option, lot_no, buy_price=0, sell_price=0, entry_type='MARKET',
                                exit_type='', p_l=0):
        try:
            primary_key = [expiry, order_no, option, lot_no]
            other_data = [entry_type, buy_price, sell_price, exit_type, p_l]
            existing_record = self.con.execute("""SELECT * FROM {table_name} WHERE
                                        expiry=? AND order_no=? AND option=? AND lot_no=?""".format(
                table_name=SQLiteHelper.TABLE_NAME), primary_key).fetchall()
            if not existing_record:
                data = [datetime.datetime.today().date()] + primary_key + other_data
                self.con.execute("""INSERT INTO {table_name} 
                                    (date, expiry, order_no, option, lot_no, entry_type, buy_price, sell_price, exit_type, p_l) 
                                    VALUES (?,?,?,?,?,?,?,?,?,?)""".format(table_name=SQLiteHelper.TABLE_NAME), data)
                print("New record inserted")
            else:
                print(existing_record)
                existing_record = list(existing_record[0])[6:]
                if entry_type:
                    existing_record[0] = entry_type
                if buy_price:
                    existing_record[1] = buy_price
                if sell_price:
                    existing_record[2] = sell_price
                if exit_type:
                    existing_record[3] = exit_type
                if p_l:
                    existing_record[4] = p_l
                self.con.execute("""UPDATE {table_name} SET 
                                            entry_type=?, buy_price=?, sell_price=?, exit_type=?, p_l=?
                                            WHERE expiry=? AND order_no=? AND option=? AND lot_no=?""".format(
                    table_name=SQLiteHelper.TABLE_NAME), existing_record + primary_key)
                print("Record updated")
        except Exception as e:
            print("Failed inserting/updating record {}".format(e))

    def all_records(self):
        for row in self.con.execute("SELECT * FROM {table_name}".format(table_name=SQLiteHelper.TABLE_NAME)).fetchall():
            print(row)

    def delete_all(self):
        print(self.con.execute("""DELETE FROM {}""".format(SQLiteHelper.TABLE_NAME)).fetchall())
        print("Deleted all records ")


class Option:
    LIVE_PRICE_URL = 'https://groww.in/v1/api/stocks_fo_data/v1/charting_service/chart/exchange/NSE/segment/FNO/BANKNIFTY23{expiry}{strike}{type}?endTimeInMillis={to}&intervalInMinutes=1&startTimeInMillis={frm}'

    def __init__(self, expiry, option_type, strike_price):
        self.expiry = expiry
        self.type = option_type
        self.strike_price = strike_price
        self.lot_size = 15

        is_monthly_expiry = calendar.monthrange(self.expiry.year, self.expiry.month)[-1] - self.expiry.day < 7
        expiry = self.expiry.strftime('%b').upper() if is_monthly_expiry else datetime.datetime.strftime(
            self.expiry,
            '%m%d')
        expiry = expiry[1:] if expiry.startswith('0') else expiry

        self.symbol = 'BANKNIFTY23{expiry}{strike}{type}'.format(expiry=expiry, strike=self.strike_price,
                                                                 type='CE' if self.type == 'CALL' else 'PE')

    def __str__(self):
        return self.expiry.strftime('%d%b') + ' ' + str(self.strike_price) + self.type

    def get_live_price(self):
        """ return market price of for this option """

        try:
            # get last 5 minutes candlestick
            # utc_now = datetime.datetime.now()
            # utc_now = datetime.datetime(2023, 6, 30, 10)
            # utc_5_mins_back = utc_now - datetime.timedelta(minutes=5)
            # milliseconds_from, milliseconds_to = int(utc_5_mins_back.timestamp()) * 1000, int(
            #    utc_now.timestamp()) * 1000

            # format expiry for symbol

            return KiteHelper.ltp(self.symbol)

            # url = Option.LIVE_PRICE_URL.format(
            #    expiry=expiry, strike=self.strike_price, type=option_type, frm=milliseconds_from, to=milliseconds_to)

            # response = requests.get(url)
            # option_data = response.json()
            # latest_price = option_data['candles'][-1][-2]
            # return latest_price

        except Exception as e:
            raise Exception("Failed fetching live price for {} - {}".format(self, e))


class Order:
    def __init__(self, order_idx, lot_no, option):
        self.order_idx = order_idx
        self.lot_no = lot_no
        self.option = option
        self.buy_price = None
        self.target = None
        self.stoploss = None
        self.is_live = True
        self.sell_price = None
        self.exit_type = None
        self.sqlhelper = SQLiteHelper()

    def set_target(self, target):
        self.target = target

    def set_stoploss(self, stoploss):
        self.stoploss = stoploss

    def trail(self, target_by=0, stoploss_by=0):
        self.target += target_by
        self.stoploss += stoploss_by

    def buy(self, price):
        self.buy_price = price
        # self.sqlhelper.insert_or_update_record(expiry=self.option.expiry,order_no=self.order_idx,option=str(self.option),lot_no=self.lot_no,buy_price=self.buy_price)

    def square_off(self, exit_type):
        price = KiteHelper.place_order(symbol=self.option.symbol, qty=self.option.lot_size,
                                       transaction_type=TransactionType.Sell)
        self.sell_price = price
        self.exit_type = exit_type
        self.is_live = False
        p_l = (self.sell_price - self.buy_price) * self.option.lot_size
        # self.sqlhelper.insert_or_update_record(expiry=self.option.expiry,order_no=self.order_idx,option=str(self.option),lot_no=self.lot_no,sell_price=self.sell_price, exit_type=self.exit_type, p_l=p_l)

    def __str__(self):
        return '{lot_no}. tgt={target} | sl={stoploss} | p_l={p_l} | {exit_type}'.format(
            lot_no=self.lot_no,
            target=self.target,
            stoploss=self.stoploss,
            p_l='N/A' if self.is_live else round((self.sell_price - self.buy_price) * self.option.lot_size, 2),
            exit_type=('TGT' if self.exit_type == ExitType.TARGET_HIT else 'SL') if self.exit_type else '')
