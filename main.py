from trade_client import *
from store_order import *
from load_config import *

from collections import defaultdict
from datetime import datetime, time
import time

import json
import os.path


# loads local configuration
config = load_config('config.yml')


def get_all_coins():
    """
    Returns all coins from Binance
    """
    return client.get_all_tickers()


def generate_coin_seen_dict(all_coins):
    """
    This method should be used once before starting the loop.
    The value for every coin detected before the loop is set to True in the coin_seen_dict.
    All the new coins detected during the loop will have a value of False.
    """
    coin_seen_dict = defaultdict(bool)
    for old_coin in all_coins:
        coin_seen_dict[old_coin['symbol']] = True
    return coin_seen_dict


def get_new_coins(coin_seen_dict):
    """
    This method checks if there are new coins listed and returns them in a list.
    The value of the new coins in coin_seen_dict will be set to True to make them not get detected again.
    """
    result = []
    all_coins_recheck = get_all_coins()

    for new_coin in all_coins_recheck:
        if not coin_seen_dict[new_coin['symbol']]:
            result += [new_coin]
            # this line ensures the new coin isn't detected again
            coin_seen_dict[new_coin['symbol']] = True

    return result


def get_price(coin, pairing):
    """
    Get the latest price for a coin
    """
    return client.get_ticker(symbol=coin+pairing)['lastPrice']


def main():
    """
    Sells, adjusts TP and SL according to trailing values
    and buys new coins
    """
    # store config deets
    tp = config['TRADE_OPTIONS']['TP']
    sl = config['TRADE_OPTIONS']['SL']
    enable_tsl = config['TRADE_OPTIONS']['ENABLE_TSL']
    tsl = config['TRADE_OPTIONS']['TSL']
    ttp = config['TRADE_OPTIONS']['TTP']
    pairing = config['TRADE_OPTIONS']['PAIRING']
    qty = config['TRADE_OPTIONS']['QUANTITY']
    frequency = config['TRADE_OPTIONS']['RUN_EVERY']
    test_mode = config['TRADE_OPTIONS']['TEST']

    all_coins = get_all_coins()
    coin_seen_dict = generate_coin_seen_dict(all_coins)

    while True:
        try:

            # check if the order file exists and load the current orders
            # basically the sell block and update TP and SL logic
            if os.path.isfile('order.json'):
                order = load_order('order.json')

                for coin in list(order):

                    # store some necesarry trade info for a sell
                    stored_price = float(order[coin]['price'])
                    coin_tp = order[coin]['tp']
                    coin_sl = order[coin]['sl']
                    volume = order[coin]['volume']
                    symbol = coin.split(pairing)[0]


                    last_price = get_price(symbol, pairing)

                    # update stop loss and take profit values if threshold is reached
                    if float(last_price) > stored_price + (stored_price*coin_tp /100) and enable_tsl:
                        # increase as absolute value for TP
                        new_tp = float(last_price) + (float(last_price)*ttp /100)
                        # convert back into % difference from when the coin was bought
                        new_tp = float( (new_tp - stored_price) / stored_price*100)

                        # same deal as above, only applied to trailing SL
                        new_sl = float(last_price) - (float(last_price)*tsl /100)
                        new_sl = float((new_sl - stored_price) / stored_price*100)

                        # new values to be added to the json file
                        order[coin]['tp'] = new_tp
                        order[coin]['sl'] = new_sl
                        store_order('order.json', order)

                        print(f'updated tp: {round(new_tp, 3)} and sl: {round(new_sl, 3)}')

                    # close trade if tsl is reached or trail option is not enabled
                    elif float(last_price) < stored_price - (stored_price*sl /100) or float(last_price) > stored_price + (stored_price*tp /100) and not enable_tsl:

                        try:

                            # sell for real if test mode is set to false
                            if not test_mode:
                                sell = create_order(coin, coin['volume'], 'SELL')


                            print(f"sold {coin} at {(float(last_price) - stored_price) / float(stored_price)*100}")

                            # remove order from json file
                            order.pop(coin)
                            store_order('order.json', order)

                        except Exception as e:
                            print(e)

                        # store sold trades data
                        else:
                            if os.path.isfile('sold.json'):
                                sold_coins = load_order('sold.json')

                            else:
                                sold_coins = {}

                            if not test_mode:
                                sold_coins[coin] = sell
                                store_order('sold.json', sold_coins)
                            else:
                                sold_coins[coin] = {
                                            'symbol':coin,
                                            'price':last_price,
                                            'volume':volume,
                                            'time':datetime.timestamp(datetime.now()),
                                            'profit': float(last_price) - stored_price,
                                            'relative_profit': round((float(last_price) - stored_price) / stored_price*100, 3)
                                            }

                                store_order('sold.json', sold_coins)

            else:
                order = {}

            # check if new coins are listed
            new_coins = get_new_coins(coin_seen_dict)

            # the buy block and logic pass
            if len(new_coins) > 0:

                print(f'New coins detected: {new_coins}')

                for coin in new_coins:

                    # buy if the coin hasn't already been bought
                    if coin['symbol'] not in order and pairing in coin['symbol']:
                        symbol_only = coin['symbol'].split(pairing)[0]
                        print(f"Preparing to buy {coin['symbol']}")

                        price = get_price(symbol_only, pairing)
                        volume = convert_volume(coin['symbol'], qty, price)

                        try:
                            # Run a test trade if true
                            if config['TRADE_OPTIONS']['TEST']:
                                order[coin['symbol']] = {
                                            'symbol':symbol_only+pairing,
                                            'price':price,
                                            'volume':volume,
                                            'time':datetime.timestamp(datetime.now()),
                                            'tp': tp,
                                            'sl': sl
                                            }

                                print('PLACING TEST ORDER')

                            # place a live order if False
                            else:
                                order[coin['symbol']] = create_order(symbol_only+pairing, volume, 'BUY')
                                order[coin['symbol']]['tp'] = tp
                                order[coin['symbol']]['sl'] = sl

                        except Exception as e:
                            print(e)

                        else:
                            print(f"Order created with {volume} on {coin['symbol']}")

                            store_order('order.json', order)
                    else:
                        print(f"New coin detected, but {coin['symbol']} is currently in portfolio, or {pairing} does not match")

            else:
                pass

        except Exception as e:
            print(e)


if __name__ == '__main__':
    print('working...')
    main()
