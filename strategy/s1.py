import threading
import time

from TradingBot.helper import Order, OrderType, Logger, KiteHelper


class OrderProcessor:
    INITIAL_TARGET = 10
    INITIAL_STOPLOSS = 20
    TARGET_INCREMENT = 10
    STOPLOSS_INCREMENT = 10

    def __init__(self, idx, option, lots):
        self.index = idx
        self.option = option
        self.lots = lots
        self.orders = None
        self.p_and_l = 0
        self.is_live = True

    def start(self):
        price_list = KiteHelper.place_order(self.option, lots=self.lots, order_type=OrderType.Market)
        orders = [Order(idx + 1, self.option, price) for idx, price in enumerate(price_list)]
        for order in orders:
            order.set_target(order.buy_price + OrderProcessor.INITIAL_TARGET)
            order.set_stoploss(order.buy_price - OrderProcessor.INITIAL_STOPLOSS)

        self.orders = orders
        self.dump_all_lots()

        t = threading.Thread(target=self.monitor)
        t.start()

    def sqaure_off_live_positions(self):
        Logger.log("[{}] Exiting all positions".format(self.index))
        for order in self.orders:
            if order.is_live:
                order.square_off()
                p_and_l = (order.sell_price - order.buy_price) * self.option.lot_size
                self.p_and_l += p_and_l
        self.dump_all_lots()
        self.is_live = False

    def dump(self):
        market_price = self.option.get_live_price()
        active_count = len([order for order in self.orders if order.is_live])

        Logger.log(
            "DUMP [{idx}] {option}| live price={price} | lots={lots} | active={active_count} | Net P_L={p_and_l}".format(
                idx=self.index, option=self.option, lots=self.lots, active_count=active_count,
                price=market_price, p_and_l=round(self.p_and_l, 2)))

    def dump_all_lots(self, live_only=False):
        msg = "[{index}] {option} \n".format(index=self.index, option=self.option)
        for order in self.orders:
            if live_only:
                if order.is_live:
                    msg += str(order)
                    msg += "\n"
            else:
                msg += str(order)
                msg += "\n"
        Logger.log(msg)
        self.dump()

    def monitor(self):
        ctr = 0
        while True and self.is_live:
            try:
                active_count = len([order for order in self.orders if order.is_live])
                if active_count == 0:
                    self.is_live = False
                    return

                time.sleep(5)
                market_price = self.option.get_live_price()

                target_hit = sl_hit = False
                for idx, order in enumerate(self.orders, 1):
                    if order.is_live:
                        if market_price >= order.target:
                            Logger.log(
                                "[{index}] TARGET HIT FOR LOT {lot_index} AT PRICE {price}".format(index=self.index,
                                                                                                   lot_index=idx,
                                                                                                   price=market_price))
                            order.square_off()
                            p_and_l = (order.sell_price - order.buy_price) * self.option.lot_size
                            Logger.log("[{index}] Lot {lot_no} sold @{price}. P_L={p_and_l}".format(index=self.index,
                                                                                                    lot_no=order.lot_no,
                                                                                                    price=order.sell_price,
                                                                                                    p_and_l=p_and_l))
                            self.p_and_l += p_and_l
                            target_hit = True
                            break
                        if market_price <= order.stoploss:
                            Logger.log(
                                "[{index}] STOPLOSS HIT FOR LOT {lot_index} AT PRICE {price}".format(index=self.index,
                                                                                                     lot_index=idx,
                                                                                                     price=market_price))
                            order.square_off()
                            p_and_l = (order.sell_price - order.buy_price) * self.option.lot_size
                            Logger.log("[{index}] Lot {lot_no} sold @{price}. P_L={p_and_l}".format(index=self.index,
                                                                                                    lot_no=order.lot_no,
                                                                                                    price=order.sell_price,
                                                                                                    p_and_l=p_and_l))
                            self.p_and_l += p_and_l
                            sl_hit = True
                            break

                if target_hit or sl_hit:
                    # increase target by 30 and stoploss by 20 for each live orders
                    if self.orders:
                        print("[{}] Trailing TGT/SL for live positions".format(self.index))
                    for order in self.orders:
                        if order.is_live:
                            if sl_hit:
                                order.trail(stoploss_by=-OrderProcessor.STOPLOSS_INCREMENT)
                            else:
                                order.trail(target_by=OrderProcessor.TARGET_INCREMENT,
                                            stoploss_by=OrderProcessor.STOPLOSS_INCREMENT)
                    self.dump_all_lots()
                ctr += 1
                if ctr % 50 == 0:
                    active_count = len([order for order in self.orders if order.is_live])

                    Logger.log(
                        "Monitoring [{idx}] {option}| live price={price} | lots={lots} | active={active_count} | Net P_L={p_and_l}".format(
                            idx=self.index, option=self.option, lots=self.lots, active_count=active_count,
                            price=market_price, p_and_l=round(self.p_and_l, 2)))
            except Exception as e:
                Logger.log('Something failed in thread {}'.format(str(e)))
        else:
            Logger.log(
                "Stopped monitoring [{idx}] {lots} lots for {option} | P_L={p_and_l}".format(idx=self.index,
                                                                                             lots=self.lots,
                                                                                             option=self.option,
                                                                                             p_and_l=round(
                                                                                                 self.p_and_l,
                                                                                                 2)))
