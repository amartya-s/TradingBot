from TradingBot.logger import Logger
from TradingBot.strategy.s1 import OrderProcessor as Strategy1


class OrderProcessor(Strategy1):
    TARGET_INCREMENT = 20
    STOPLOSS_INCREMENT = 20

    def adjust_sl_target(self, market_price):
        last_n_orders = 2
        if all([not order.is_live for order in self.orders[:-last_n_orders]]):  # if all previous orders were exited
            for index, order in enumerate(self.orders[-last_n_orders:], 1):
                if order.is_live:
                    if market_price >= order.target:
                        Logger.log("TRAILING SL and TGT for ORDER {}".format(
                            len(self.orders) - len(self.orders[-last_n_orders:]) + index))
                        order.trail(target_by=OrderProcessor.TARGET_INCREMENT,
                                    stoploss_by=OrderProcessor.STOPLOSS_INCREMENT)
                        Logger.log(str(order))
