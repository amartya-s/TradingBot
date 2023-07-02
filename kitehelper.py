from TradingBot.enums import OrderType, TransactionType
from TradingBot.logger import Logger


class KiteHelper:

    @staticmethod
    def place_order(option, lots, price=None, target=None, stoploss=None, order_type=OrderType.Market,
                    transaction_type=TransactionType.Buy):
        """ place order at given price"""

        price = price if order_type == OrderType.Limit else option.get_live_price()

        if transaction_type == TransactionType.Sell:
            # verify if we have an active position
            pass

        Logger.log("Order placed [{transaction_type}] for {option} {lots} lots".format(
            transaction_type=transaction_type, option=str(option), lots=lots))

        orders = [price for lot in range(lots)]

        return orders
