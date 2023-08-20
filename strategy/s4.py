from TradingBot.logger import Logger
from TradingBot.strategy.s3 import OrderProcessor as Strategy3
from TradingBot.common import KiteHelper, Order
from TradingBot.enums import TransactionType, ExitType


class OrderProcessor(Strategy3):
    """ if order target hit and target price greater than buy price then sell all live lots and book (live lots - 1)
    lots at market price"""

    INITIAL_TARGET = 15
    INITIAL_STOPLOSS = 15

    def __init__(self, idx, option, lots):
        super().__init__(idx, option, lots)
        self.new_lots = self.lots

    def dump_all_lots(self, live_only=False):
        orders = self.orders[-self.new_lots:]
        lot_buy_price = orders[0].buy_price if orders else 0  # all lots have same buy price
        msg = "[{index}] {option}@{bp}\n".format(index=self.index, option=self.option, bp=lot_buy_price)
        for order in orders:
            if live_only:
                if order.is_live:
                    msg += str(order)
                    msg += "\n"
            else:
                msg += str(order)
                msg += "\n"
        Logger.log(msg)
        self.dump()

    def adjust_sl_target(self, market_price):

        super().adjust_sl_target(market_price)

        live_orders = [order for order in self.orders if order.is_live]
        if live_orders:
            order = live_orders[0]  # first order
            if market_price >= order.target > order.buy_price:
                Logger.log("{index} TGT HIT FOR LOT {lot_no} @ {mp} AND MP > BP. EXITING ALL({lots}) LIVE ORDERS".format(
                    index=self.index, lot_no=order.lot_no, mp=market_price, lots=len(live_orders)))
                self.sqaure_off_live_positions()

                # book len(exited_orders)-1 lots
                total_new_orders_cnt = len(live_orders) - 1
                Logger.log("[{index}] Placing order for {lots} lots".format(index=self.index, lots=total_new_orders_cnt))
                price = KiteHelper.place_order(symbol=self.option.symbol,
                                               qty=total_new_orders_cnt * self.option.lot_size,
                                               transaction_type=TransactionType.Buy)

                last_lot_index = live_orders[-1].lot_no
                new_orders = [Order(self.index, lot_idx + last_lot_index + 1, self.option) for lot_idx in
                              range(total_new_orders_cnt)]

                for order in new_orders:
                    order.buy(price)
                    order.set_target(order.buy_price + OrderProcessor.INITIAL_TARGET)
                    order.set_stoploss(order.buy_price - OrderProcessor.INITIAL_STOPLOSS)

                self.new_lots = total_new_orders_cnt
                self.lots += self.new_lots

                self.orders.extend(new_orders)
                self.dump_all_lots()
