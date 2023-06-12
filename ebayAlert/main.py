import re
import sys
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.util import NoneType

from geopy.geocoders import Nominatim
from geopy import distance

from ebayAlert import create_logger
from ebayAlert.core.configs import configs
from ebayAlert.core.settings import settings
from ebayAlert.crud.base import crud_search, get_session
from ebayAlert.crud.post import crud_klein, crud_ebay
from ebayAlert.models.sqlmodel import EbayPost
from ebayAlert.scrapping import items
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
    searches = crud_search.get_all(db=db)
    if searches:
        for link_model in searches:
            if (exclusive_id is not False and exclusive_id == link_model.id) or exclusive_id is False:
                if link_model.status != 0 and link_model.search_type != "EBAY":
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
                    klein_factory = items.KleinItemFactory(link_model, num_pages)
                    message_items = crud_klein.add_items_to_db(db=db, items=klein_factory.item_list,
                                                              link_id=link_model.id, write_database=write_database)

                    if link_model.status == 1:
                        # check if there are unmatched ebay items and match them
                        db_results = crud_ebay.get_all_matching({"link_id": None}, db)
                        if db_results:
                            for item in db_results:
                                # check if ebay item fits the search terms considering the exclusions
                                item_matching = True
                                item_title = item.title.lower()
                                search_terms = link_model.search_string.split(" ")
                                for term in search_terms:
                                    if not term.startswith("-"):
                                        if item_title.find(term) == -1:
                                            item_matching = False
                                    elif term.startswith("-"):
                                        if item_title.find(term) > -1:
                                            item_matching = False
                                if item_matching:
                                    # update link_id for ebay item
                                    if write_database:
                                        crud_ebay.update({"identifier": "post_id", "post_id": int(item.post_id), "link_id": int(link_model.id)}, db=db)
                                    # add to message items
                                    item.location = "Ebay"
                                    item.link = settings.EBAY_BASE_ITEM + str(item.post_id)
                                    message_items.append(item)

                        # check for items worth sending and send
                        if len(message_items) > 0:
                            filter_message_items(link_model, message_items, telegram_message=telegram_message)
                        else:
                            print(' Nothing to report.')
                    else:
                        # end output
                        print(' (Silent search)')
                elif link_model.status != 0 and link_model.search_type == "EBAY":
                    """
                    searches on ebay just require an URL.
                    - all items that are not in the separate table in db yet are added
                    - matching to regular searches is done while processing the specified search
                    - time delay 
                    """
                    print(f'>> Searching ID:{link_model.id}: type \'{link_model.search_type}\'')
                    ebay_factory = items.EbayItemFactory(link_model)
                    crud_ebay.add_items_to_db(db=db, items=ebay_factory.item_list, write_database=write_database)


def calc_benefit(target) -> int:
    return round(target - target * configs.TARGET_MODE_BENEFIT)


def filter_message_items(link_model, message_items, telegram_message):
    firstmessagesent = False
    for item in message_items:
        evaluationlog = ""
        # default is true
        worth_messaging = True
        # current price as integer
        item_price = item.price
        item_price_num = re.findall(r'\d+', re.sub("\.", "", item_price))
        if len(item_price_num) == 0:
            item_price_num = 0
        else:
            item_price_num = int(item_price_num[0])

        # pricerange visual indicator
        pricerange = ""

        # check if search string exclusions exclude this result
        if link_model.search_string != "":
            search_term_parts = link_model.search_string.split(" ")
            search_term_parts[:] = [x[1:] for x in search_term_parts if x.startswith("-")]
            # generally exclude "defekt" items
            search_term_parts.append("defekt")
            for x in search_term_parts:
                if worth_messaging and item.title.lower().find(x) > -1:
                    worth_messaging = False
                    evaluationlog += 'f'

        # check if message worth sending by price in two different modes
        # METHOD 1
        if worth_messaging and type(link_model.price_target) != NoneType:
            # Mode: TARGET (= reach break even price, 0€ loss/benefit)
            price_low = int(link_model.price_target) * 0.7
            price_target = int(link_model.price_target)
            price_benefit = calc_benefit(price_target)

            # price range not hit by default
            worth_messaging = False
            item.pricehint = ""

            if item_price_num <= 1:
                # price is 0 or 1
                item.pricehint = "[Offer]"
                worth_messaging = False  # LESS MESSAGES
                evaluationlog += 'o'
            elif price_low <= item_price_num <= price_benefit:
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
            if type(item) == EbayPost:
                item.print_price = f'{item.price}\n{item.pricerange}'

        # METHOD 2
        if worth_messaging and type(link_model.price_high) != NoneType:
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

            # price range not hit by default
            worth_messaging = False

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
                chat_id = configs.CHAT_ID
                if type(link_model.chat_id) != NoneType:
                    chat_id = link_model.chat_id
                telegram.send_formated_message(item, chat_id)

    if firstmessagesent is False:
        print('  Nothing worth messaging.', end='')
    print('')


if __name__ == "__main__":
    cli(sys.argv[1:])
