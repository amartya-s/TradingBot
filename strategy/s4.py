from TradingBot.logger import Logger
from TradingBot.strategy.s3 import OrderProcessor as Strategy3
from TradingBot.common import KiteHelper, Order
from TradingBot.enums import TransactionType, ExitType


class OrderProcessor(Strategy3):
    """ if order target hit and target price greater than buy price then sell all live lots and book (live lots - 1)
    lots at market price"""

    INITIAL_TARGET = 15
    INITIAL_STOPLOSS = 15

    def adjust_sl_target(self, market_price):

        super().adjust_sl_target(market_price)

        live_orders = [order for order in self.orders if self.is_live]
        if live_orders:
            order = live_orders[0]  # first order
            if market_price >= order.target > order.buy_price:
                Logger.log("TGT HIT. EXITING ALL LIVE ORDERS")
                self.sqaure_off_live_positions()

                # book len(exited_orders)-1 lots
                total_new_orders_cnt = len(live_orders) - 1
                price = KiteHelper.place_order(symbol=self.option.symbol,
                                               qty=total_new_orders_cnt*self.option.lot_size,
                                               transaction_type=TransactionType.Buy)
                last_lot_index = live_orders[-1].lot_no
                new_orders = [Order(self.index, lot_idx + last_lot_index + 1, self.option) for lot_idx in
                              range(total_new_orders_cnt)]

                for order in new_orders:
                    order.buy(price)
                    order.set_target(order.buy_price + OrderProcessor.INITIAL_TARGET)
                    order.set_stoploss(order.buy_price - OrderProcessor.INITIAL_STOPLOSS)

                self.orders.extend(new_orders)
                self.dump_all_lots(live_only=True)
