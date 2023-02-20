import re
import sys
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.util import NoneType

from geopy.geocoders import Nominatim
from geopy import distance

from ebayAlert import create_logger
from ebayAlert.core.configs import configs
from ebayAlert.crud.base import crud_link, get_session
from ebayAlert.crud.post import crud_post
from ebayAlert.ebayscrapping import ebayclass
from ebayAlert.telegram.telegramclass import telegram

log = create_logger(__name__)

try:
    import click
    from click import BaseCommand
except ImportError:
    log.error("Click should be installed\npip install click")


@click.group()
def cli() -> BaseCommand:
    pass


@cli.command(options_metavar="<options>", help="Fetch new posts and send notifications.")
@click.option("-s", "--silent", is_flag=True, help="Do not send notifications.")
@click.option("-n", "--nonperm", is_flag=True, help="Do not edit database.")
@click.option("-e", "--exclusive", 'exclusive', metavar="<link id>", help="Run only one search.")
@click.option("-d", "--depth", 'depth', metavar="<pages n>", help="When available, scan n pages (default 1).")
def start(silent, nonperm, exclusive, depth):
    """
    cli related to the main package. Fetch new posts and send notifications.
    """
    # DEFAULTS HERE
    write_database = True
    telegram_message = True
    num_pages = 1
    exclusive_id = False

    starttime = datetime.now()
    print("----------------------------------------------------------------------------------")
    print(">> Starting ebayAlert @", starttime.strftime("%H:%M:%S"))
    if silent:
        print(">> No notifications.")
        telegram_message = False
    if nonperm:
        print(">> No changes to database.")
        write_database = False
    if depth:
        print(f">> Checking up to {depth} pages per search.")
        num_pages = int(depth)
    if exclusive:
        print(">> Checking only ID:", exclusive)
        exclusive_id = int(exclusive)
    with get_session() as db:
        get_all_post(db=db, exclusive_id=exclusive_id, write_database=write_database,
                     telegram_message=telegram_message, num_pages=num_pages)
    end = datetime.now()
    print("<< ebayAlert finished @", end.strftime("%H:%M:%S"), "Duration:", end - starttime)


def get_all_post(db: Session, exclusive_id=False, write_database=True, telegram_message=False, num_pages=1):
    searches = crud_link.get_all(db=db)
    if searches:
        for link_model in searches:
            if (exclusive_id is not False and exclusive_id == link_model.id) or exclusive_id is False:
                if link_model.status != 0:
                    """
                    every search has a status
                    0 = search disabled
                    1 = search active. update db and send messages
                    2 = search silent = update db but do not send messages
                    """
                    # scrape search pages and add new/changed items to db
                    locationfilterhint = ""
                    while True:
                        if type(link_model.zipcodes) != NoneType:
                            # DB setting takes priority
                            locationfilterhint = " (Area from: DB)"
                            break
                        if configs.LOCATION_FILTER != "":
                            locationfilterhint = " (Area from: configs.py)"
                            break
                        break
                    mode = ""
                    if type(link_model.price_target) != NoneType:
                        mode = f'\'TARGET 0\' = {link_model.price_target}€'
                    else:
                        mode = f'RANGE {link_model.price_low}€ - {link_model.price_high}€'
                    print(f'>> Searching ID:{link_model.id}: type \'{link_model.search_type}\', filter \'{link_model.search_string}\', mode: {mode}' + locationfilterhint)
                    post_factory = ebayclass.EbayItemFactory(link_model, num_pages)
                    message_items = crud_post.add_items_to_db(db=db, items=post_factory.item_list,
                                                              link_id=link_model.id, write_database=write_database)
                    if link_model.status == 1:
                        # check for items worth sending and send
                        if len(message_items) > 0:
                            filter_message_items(link_model, message_items, telegram_message=telegram_message)
                        else:
                            print(' Nothing to report.')
                    else:
                        # end output
                        print(' (Silent search)')


def calc_benefit(target) -> int:
    return round(target - target * 0.05 - 12)


def filter_message_items(link_model, message_items, telegram_message):
    firstmessagesent = False
    for item in message_items:
        evaluationlog = ""
        worth_messaging = False
        # current price as integer
        item_price = item.price
        item_price_num = re.findall(r'\d+', re.sub("\.", "", item_price))
        if len(item_price_num) == 0:
            item_price_num = 0
        else:
            item_price_num = int(item_price_num[0])

        # pricerange visual indicator
        pricerange = ""

        # check if message worth sending in two different modes
        if type(link_model.price_target) != NoneType:
            # Mode: TARGET (= reach break even price, 0€ loss/benefit)
            price_target = int(link_model.price_target)
            price_benefit = calc_benefit(price_target)
            if item_price_num <= 1:
                # price is 0 or 1
                item.pricehint = "[Offer]"
                worth_messaging = False  # LESS MESSAGES
                evaluationlog += 'o'
            elif item_price_num <= price_benefit and "defekt" not in item.title:
                item.pricehint = f'[DEAL]'
                worth_messaging = True
                evaluationlog += 'X'
            elif price_benefit < item_price_num <= price_target and "VB" in item_price:
                item.pricehint = "[Maybe]"
                worth_messaging = False  # LESS MESSAGES
                evaluationlog += 'b'
            elif price_target < item_price_num <= price_target + 10 and "VB" in item_price:
                item.pricehint = "[Nah]"
                worth_messaging = False  # LESS MESSAGES
                evaluationlog += 'n'
            item.pricehint += f"\n[{link_model.search_string}]"

            if type(link_model.price_info) != NoneType:
                infos = link_model.price_info.split('-')
                for info in infos:
                    pair = info.split(':')
                    target = int(pair[1])
                    benefit = calc_benefit(target)
                    pricerange += f"T0 {pair[0]}: {target}€ ({target - item_price_num}€) WIN: {benefit}€ ({benefit - item_price_num}€)\n"
            else:
                pricerange = f"T0: {price_target}€ ({price_target - item_price_num}€)\nWIN: {price_benefit}€ ({price_benefit - item_price_num}€)\n"
            item.pricerange = pricerange

        else:
            # Mode: PRICERANGE
            # maximal item price to be shown
            price_max = round(int(link_model.price_high) * 1.2)
            if (price_max - link_model.price_high) > 20:
                price_max = link_model.price_high + 20

            if int(link_model.price_low) <= item_price_num <= int(link_model.price_high):
                pricediff = int(link_model.price_high) - int(link_model.price_low)
                pricepos = round((item_price_num - int(link_model.price_low)) * 10 / pricediff)
                for x in range(0, 11):
                    if x == pricepos:
                        pricerange += "X"
                    else:
                        pricerange += "."
            else:
                pricerange = "......."
            if item_price_num <= 1:
                # price is 0 or 1
                worth_messaging = True
                evaluationlog += 'v'
            elif int(link_model.price_low) <= item_price_num <= int(link_model.price_high):
                # price within range
                worth_messaging = True
                evaluationlog += 'X'
            elif int(link_model.price_high) < item_price_num <= price_max \
                    and "VB" in item_price:
                # price is negotiable and max 20% over watching price max 20€
                item.pricehint = f"(+20%)"
                worth_messaging = True
                evaluationlog += 'h'
            elif int(link_model.price_low) * 0.7 <= item_price_num < int(link_model.price_low):
                # price is 30% below watch price
                item.pricehint = f"(-30%)"
                worth_messaging = True
                evaluationlog += 'l'
            pricerange = " [" + pricerange + "] "
            item.pricerange = f"{link_model.price_low}€{pricerange}{link_model.price_high}€"

        # calculate and check distances
        checkzipcodes = 0
        while True:
            if type(link_model.zipcodes) != NoneType:
                # DB setting takes priority
                checkzipcodes = 1
                break
            if configs.LOCATION_FILTER != "":
                checkzipcodes = 2
                break
            break
        item_inrange = False
        if checkzipcodes > 0 and worth_messaging and item.shipping == "No Shipping":
            evaluationlog += '?'
            # ZIPCODES in DB like this: dist1,zip11,zip12,..,zip1N-dist2,zip21..
            geocoder = Nominatim(user_agent="cyberpete2244/ebayKleinanzeigenAlert")
            geoloc_item = geocoder.geocode(re.findall(r'\d+', item.location))
            # cycle through areas and through zipcodes
            areas = link_model.zipcodes.split('-') if checkzipcodes == 1 else configs.LOCATION_FILTER.split('-')
            t = 0
            while t < len(areas):
                zipcodes = areas[t].split(',')
                max_distance = int(zipcodes[0])
                n = 1
                while n < len(zipcodes):
                    geoloc_filter = geocoder.geocode(zipcodes[n])
                    itemdistance = round(distance.distance((geoloc_item.latitude, geoloc_item.longitude),
                                                           (geoloc_filter.latitude, geoloc_filter.longitude)).km)
                    if itemdistance <= max_distance:
                        item_inrange = True
                        n = len(zipcodes)
                        t = len(areas)
                    else:
                        n += 1
                t += 1

        # send telegram message?
        if worth_messaging and telegram_message:
            dosend = worth_messaging
            if firstmessagesent is False:
                print('  Messages:', end=' ')
                firstmessagesent = True

            if checkzipcodes > 0 and item_inrange is True and item.shipping == "No Shipping":
                evaluationlog += '+'
            elif checkzipcodes > 0 and item_inrange is False and item.shipping == "No Shipping":
                evaluationlog += '-'
                dosend = False

            print(evaluationlog, end='')

            if dosend:
                telegram.send_formated_message(item)

    if firstmessagesent is False:
        print('  Nothing worth messaging.', end='')
    print('')


if __name__ == "__main__":
    cli(sys.argv[1:])
