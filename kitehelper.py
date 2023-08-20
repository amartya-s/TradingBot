import pyotp
import time
from kiteconnect import KiteConnect
from kiteconnect.exceptions import TokenException
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

from TradingBot.enums import OrderType, TransactionType
from TradingBot.logger import Logger

DUMMY_ORDER = False


class AutoLogin:
    API_KEY = '***'
    API_SECRET = '***'
    TOTP_KEY = '***'  # '***'
    USER_ID = '***'
    PWD = '***'

    def __init__(self):
        self.kite = None
        self.access_token = None

    def fetch_request_token(self):
        Logger.log('[KiteAutoLogin] Initiating Auto Login to %s' % AutoLogin.USER_ID)
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("enable-automation")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)
        driver.get(f'https://kite.trade/connect/login?api_key={AutoLogin.API_KEY}&v=3')
        Logger.log("[KiteAutoLogin] entering login Id")
        login_id = WebDriverWait(driver, 10).until(lambda x: x.find_element('xpath', '//*[@id="userid"]'))
        login_id.send_keys(AutoLogin.USER_ID)

        Logger.log("[KiteAutoLogin] entering password")
        pwd = WebDriverWait(driver, 10).until(lambda x: x.find_element('xpath', '//*[@id="password"]'))
        pwd.send_keys(AutoLogin.PWD)

        submit = WebDriverWait(driver, 10).until(
            lambda x: x.find_element('xpath', '//*[@id="container"]/div/div/div[2]/form/div[4]/button'))
        submit.click()

        time.sleep(1)
        # adjustment to code to include totp
        totp = WebDriverWait(driver, 10).until(lambda x: x.find_element('xpath', '//*[@label="External TOTP"]'))
        authkey = pyotp.TOTP(AutoLogin.TOTP_KEY)
        Logger.log("[KiteAutoLogin] entering TOTP")
        totp.send_keys(authkey.now())
        # adjustment complete

        Logger.log("[KiteAutoLogin] Waiting for redirection")
        time.sleep(2)

        url = driver.current_url
        initial_token = url.split('request_token=')[1]
        request_token = initial_token.split('&')[0]

        driver.close()

        return request_token

    def login(self):
        try:

            request_token = self.fetch_request_token()
            self.kite = self.kite or KiteConnect(api_key=AutoLogin.API_KEY)

            data = self.kite.generate_session(request_token, api_secret=AutoLogin.API_SECRET)
            self.kite.set_access_token(data['access_token'])

            Logger.log("[KiteAutoLogin] Login successful ")

            self.access_token = data['access_token']
            self.kite.set_session_expiry_hook(self.login_expired_hook)

        except Exception as e:
            import traceback
            traceback.print_exc()
            Logger.log("[KiteAutoLogin] Login failed %s" % e)
            raise e

    def login_expired_hook(self):

        Logger.log("[KiteLogin] Session expired. Refreshing token")
        self.login()


class KiteHelper:

    kite = None

    @staticmethod
    def login():
        if not KiteHelper.kite:
            login_helper = AutoLogin()
            login_helper.login()
            KiteHelper.kite = login_helper.kite

    @staticmethod
    def handle_auth_error(method, retries=3):
        def _retry(*args, **kwargs):
            try:
                return method(*args, **kwargs)
            except TokenException:  # any auth related error caught here
                cnt = 1
                while cnt <= retries:
                    try:
                        return method(*args, **kwargs)
                    except TokenException as e:
                        cnt += 1
                        Logger.log("Authentication failure %s. Retrying..." % str(e))
                        time.sleep(0.5)
                else:
                    Logger.log("Retried %s times" % retries)
                    raise Exception("Authentication failure")

        return _retry

    @staticmethod
    @handle_auth_error
    def place_order(symbol, qty, price=None, target=None, stoploss=None, order_type=OrderType.Market,
                    transaction_type=TransactionType.Buy):
        """ place order at given price"""

        if not DUMMY_ORDER:
            order_id = KiteHelper.kite.place_order(tradingsymbol=symbol,
                                                   exchange=KiteHelper.kite.EXCHANGE_NFO,
                                                   transaction_type=KiteHelper.kite.TRANSACTION_TYPE_BUY if transaction_type == TransactionType.Buy else KiteHelper.kite.TRANSACTION_TYPE_SELL,
                                                   quantity=qty,
                                                   variety=KiteHelper.kite.VARIETY_REGULAR,
                                                   order_type=KiteHelper.kite.ORDER_TYPE_MARKET if order_type == OrderType.Market else KiteHelper.kite.ORDER_TYPE_LIMIT,
                                                   product=KiteHelper.kite.PRODUCT_NRML,
                                                   validity=KiteHelper.kite.VALIDITY_DAY,
                                                   price=price)

            order_details = KiteHelper.kite.order_trades(order_id)
            if not order_details:
                retry = 3
                while retry > 0:
                    Logger.log("Order not filled yet")
                    time.sleep(0.5)
                    order_details = KiteHelper.kite.order_trades(order_id)
                    if order_details:
                        break
                    retry -= 1
                else:
                    raise Exception("Failed placing order. Order Id {order_id}".format(order_id=order_id))
            price = order_details[0]['average_price']
        else:
            price = price if order_type == OrderType.Limit else KiteHelper.ltp(symbol)

        if transaction_type == TransactionType.Sell:
            # verify if we have an active position
            pass
        #
        print("{IsDummy} Order placed [{transaction_type}] for {option} {qty} qty@{price}".format(
            transaction_type=transaction_type, option=symbol, qty=qty, IsDummy='Dummy' if DUMMY_ORDER else '',price=price))

        return price

    @staticmethod
    @handle_auth_error
    def ltp(symbol):
        result = KiteHelper.kite.ltp(['NFO:' + symbol])
        if result:
            return result['NFO:' + symbol]['last_price']
        else:
            raise Exception("Unable to fetch ltp for %s" % symbol)

    @staticmethod
    @handle_auth_error
    def margin():
        return float(KiteHelper.kite.margins('equity')['available']['live_balance'])
