import re
import sys
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.util import NoneType

from geopy.geocoders import Nominatim
from geopy import distance

from ebAlert import create_logger
from ebAlert.core.configs import configs
from ebAlert.crud.base import crud_link, get_session
from ebAlert.crud.post import crud_post
from ebAlert.ebayscrapping import ebayclass
from ebAlert.telegram.telegramclass import telegram

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
def start(silent, nonperm, exclusive):
    """
    cli related to the main package. Fetch new posts and send notifications.
    """
    # DEFAULTS HERE
    write_database = True
    telegram_message = True
    starttime = datetime.now()
    print(">> Starting Ebay alert @", starttime.strftime("%H:%M:%S"))
    if silent:
        print(">> No notifications.")
        telegram_message = False
    if nonperm:
        print(">> No changes to database.")
        write_database = False
    if exclusive:
        print(">> Checking only ID:", exclusive)
        with get_session() as db:
            get_all_post(db=db, exclusive_id=int(exclusive), write_database=write_database, telegram_message=telegram_message)
    else:
        with get_session() as db:
            get_all_post(db=db, write_database=write_database, telegram_message=telegram_message)
    end = datetime.now()
    print("<< Ebay alert finished @", end.strftime("%H:%M:%S"), "Duration:", end-starttime)


def get_all_post(db: Session, exclusive_id=False, write_database=True, telegram_message=False):
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
                    print(f'>> Searching ID:{link_model.id}: Type \'{link_model.search_type}\', filter \'{link_model.search_string}\', range: {link_model.price_low}€ - {link_model.price_high}€')
                    post_factory = ebayclass.EbayItemFactory(link_model)
                    message_items = crud_post.add_items_to_db(db=db, items=post_factory.item_list, link_id=link_model.id, write_database=write_database)
                    if link_model.status == 1:
                        # check for items worth sending and send
                        if len(message_items) > 0:
                            filter_message_items(link_model, message_items, telegram_message=telegram_message)
                        else:
                            print('Nothing to report')
                    else:
                        # end output
                        print('Silent search')


def filter_message_items(link_model, message_items, telegram_message):
    if type(link_model.zipcodes) != NoneType or configs.LOCATION_FILTER != "":
        print("Show only local offers within specified areas")
    print('Telegram:', end=' ')
    for item in message_items:
        worth_messaging = False
        # current price as integer
        item_price = item.price
        item_price_num = re.findall(r'\d+', re.sub("\.", "", item_price))
        if len(item_price_num) == 0:
            item_price_num = 0
        else:
            item_price_num = int(item_price_num[0])
        # pricerange visual indicator
        pricerange= ""
        if int(link_model.price_low) <= item_price_num <= int(link_model.price_high):
            pricediff = int(link_model.price_high) - int(link_model.price_low)
            pricepos = round((item_price_num - int(link_model.price_low))*10/pricediff)
            for x in range(0, 11):
                if x == pricepos:
                    pricerange += "X"
                else:
                    pricerange += "."
        else:
            pricerange = "......."
        pricerange = " [" + pricerange + "] "
        item.pricerange = f"{link_model.price_low}€{pricerange}{link_model.price_high}€"
        # TODO hardcoded flag here and both over and underrange hints
        # maximal item price to be shown
        price_max = round(int(link_model.price_high) * 1.2)
        if (price_max - link_model.price_high) > 20:
            price_max = link_model.price_high + 20
        # CHECK if message worth sending
        if item_price_num <= 1:
            # price is 0 or 1
            worth_messaging = True
            print('V', end='')
        elif int(link_model.price_low) <= item_price_num <= int(link_model.price_high):
            # price within range
            worth_messaging = True
            print('!', end='')
        elif int(link_model.price_high) < item_price_num <= price_max \
                and "VB" in item_price:
            # price is negotiable and max 20% over watching price max 20€
            item.pricehint = f"(+20%)"
            worth_messaging = True
            print('h', end='')
        elif int(link_model.price_low) * 0.7 <= item_price_num < int(link_model.price_low):
            # price is 30% below watch price
            item.pricehint = f"(-30%)"
            worth_messaging = True
            print('l', end='')
        # calculate distance
        checkzipcodes = 0
        if type(link_model.zipcodes) != NoneType:
            checkzipcodes = 1
        elif configs.LOCATION_FILTER != "":
            checkzipcodes = 2
        if checkzipcodes > 0 and worth_messaging and item.shipping == "No Shipping":
            # ZIPCODES in DB like this: dist1,zip11,zip12,..,zip1N-dist2,zip21..
            geocoder = Nominatim(user_agent="cyberpete2244/ebayKleinanzeigenAlert")
            geoloc_item = geocoder.geocode(re.findall(r'\d+', item.location))
            # cycle through areas and through zipcodes
            areas = link_model.zipcodes.split('-') if checkzipcodes == 1 else configs.LOCATION_FILTER.split('-')
            item_inrange = False
            t = 0
            while t < len(areas):
                zipcodes = areas[t].split(',')
                max_distance = int(zipcodes[0])
                n = 1
                while n < len(zipcodes):
                    geoloc_filter = geocoder.geocode(zipcodes[n])
                    itemdistance = round(distance.distance((geoloc_item.latitude, geoloc_item.longitude),(geoloc_filter.latitude, geoloc_filter.longitude)).km)
                    if itemdistance <= max_distance:
                        item_inrange = True
                        n = len(zipcodes)
                        t = len(areas)
                    else:
                        n += 1
                t += 1
            if item_inrange:
                print('+', end='')
            else:
                worth_messaging = False
                print('-', end='')
        # send telegram
        if worth_messaging and telegram_message:
            telegram.send_formated_message(item)
    print('')

"""
IDEAS:
prepare vor search only having max price for example
make searches go to individual chat ids

MAYBE: react to a telegram message marks the item as favored in ebay and sends the seller a text?
"""


if __name__ == "__main__":
    cli(sys.argv[1:])
