from TradingBot.logger import Logger
from TradingBot.strategy.s1 import OrderProcessor as Strategy1


class OrderProcessor(Strategy1):

    def adjust_sl_target(self, market_price):

        if all([not order.is_live for order in self.orders[:-1]]):  # if all previous orders were exited
            last_order = self.orders[-1]
            if market_price >= last_order.target:
                Logger.log("TRAILING SL and TGT for LAST ORDER")
                last_order.trail(target_by=Strategy1.TARGET_INCREMENT,
                                 stoploss_by=Strategy1.STOPLOSS_INCREMENT)
                Logger.log(str(last_order))
