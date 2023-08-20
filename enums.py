import datetime

MARKET_CLOSE = datetime.time(15, 30, 0)

class TransactionType:
    Buy = 'Buy'
    Sell = 'Sell'


class OrderType:
    Limit = 'Limit'
    Market = 'Market'


class ExitType:
    SL_HIT = 'SL'
    TARGET_HIT = 'TGT'
    MARKET = 'MKT'
