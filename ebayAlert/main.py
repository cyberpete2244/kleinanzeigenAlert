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
from ebayAlert.crud.base import crud_search, get_session, crud_search_type
from ebayAlert.crud.post import crud_klein, crud_ebay
from ebayAlert.models.sqlmodel import EbayPost
from ebayAlert.scrapping.ebay import EbayItemFactory
from ebayAlert.scrapping.klein import KleinItemFactory
from ebayAlert.telegram.telegram import send_formatted_message

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
@click.option("-v", "--verbose", is_flag=True, help="Show more near matches.")
@click.option("-e", "--exclusive", 'exclusive', metavar="<link id>", help="Run only one search by ID.")
@click.option("-d", "--depth", 'depth', metavar="<pages n>", help="When available (on Kleinanzeigen), scan n pages of pagination (default 1).")
def start(silent, nonperm, exclusive, depth, verbose):
    """
    cli related to the main package. Fetch new posts and send notifications.
    """
    # DEFAULTS HERE
    write_database = True
    telegram_message = True
    verbose_mode = False
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
    if verbose:
        print(">> Showing near misses also.")
        verbose_mode = True
    with get_session() as db:
        get_all_post(db=db, exclusive_id=exclusive_id, write_database=write_database,
                     telegram_message=telegram_message, num_pages=num_pages, verbose=verbose_mode)
    end = datetime.now()
    print("<< ebayAlert finished @", end.strftime("%H:%M:%S"), "Duration:", end - starttime)


def get_all_post(db: Session, exclusive_id, write_database, telegram_message, num_pages, verbose):
    searches = crud_search.get_all(db=db)
    if searches:
        for link_model in searches:
            if (exclusive_id is not False and exclusive_id == link_model.id) or exclusive_id is False:
                # get URL by search_type
                db_search_type = crud_search_type.get_by_key({"search_type": link_model.search_type}, db)
                link_model.url = db_search_type.search_url
                search_type = link_model.search_type.split("_")
                if link_model.status != 0 and search_type[0] == "KLEIN":
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
                    klein_factory = KleinItemFactory(link_model, num_pages)
                    message_items = crud_klein.add_items_to_db(db=db, items=klein_factory.item_list, link_id=link_model.id, write_database=write_database)

                    if link_model.status == 1: # run matching only search is active (!silent)

                        # EBAY search enrichment
                        # check if there are unmatched ebay items for same search type and match them
                        db_results = crud_ebay.get_all_matching({"link_id": None, "search_type": search_type[1]}, db)
                        if db_results:
                            enrich_count = 0
                            for item in db_results:
                                # check if ebay item fits the search terms considering the exclusions
                                item_matching = True
                                item_title = item.title.lower()
                                search_terms = link_model.search_string.split(" ")

                                if not match_title(item_title, search_terms):
                                    item_matching = False

                                if item_matching:
                                    enrich_count += 1
                                    # update link_id for ebay item if matched
                                    if write_database:
                                        crud_ebay.update({"identifier": "post_id", "post_id": int(item.post_id), "link_id": int(link_model.id)}, db=db)
                                    # add to message items
                                    item.location = "Ebay"
                                    item.link = settings.EBAY_BASE_ITEM + str(item.post_id)
                                    message_items.append(item)
                            if enrich_count > 0:
                                print(' Matched from Ebay:' + str(enrich_count), end='')

                        # check for items worth sending and send
                        if len(message_items) > 0:
                            filter_message_items(link_model, message_items, telegram_message=telegram_message, verbose=verbose)
                        else:
                            print(' Nothing to report.')
                    else:
                        # end output
                        print(' (Silent search)')
                elif link_model.status == 1 and search_type[0] == "EBAY":
                    """
                    EBAY search enrichment
                    - all items that are not in the db (by ebay ID) are added
                    - matching to "regular" searches is done while processing the specified search on next script execution
                    """
                    print(f'>> Searching ID:{link_model.id}: type \'{link_model.search_type}\'')
                    ebay_factory = EbayItemFactory(link_model)
                    crud_ebay.add_items_to_db(db=db, items=ebay_factory.item_list, search_type=search_type[1], write_database=write_database)


def calc_benefit(target) -> int:
    return round(target - target * configs.TARGET_MODE_BENEFIT)


def match_title(item_title, search_terms):
    title_matching = True

    for term in search_terms:
        if not term.startswith("-"):
            # positive search terms
            if not match_title_cases(item_title, term):
                title_matching = False
        elif term.startswith("-"):
            # negative search terms
            term = term[1:]
            if match_title_cases(item_title, term):
                title_matching = False

    return title_matching


def match_title_cases(item_title, term):
    if term.isdigit():
        return item_title.find(term) > -1
    if re.search(r"\b" + re.escape(term) + r"\b", item_title):
        return True
    if re.search(r"\d" + re.escape(term) + r"\b", item_title):
        return True
    return False


def filter_message_items(link_model, message_items, telegram_message, verbose):
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

            if item_price_num <= 1 and verbose:
                # price is 0 or 1
                item.pricehint = "[Offer]"
                worth_messaging = True
                evaluationlog += 'o'
            elif price_low <= item_price_num <= price_benefit:
                item.pricehint = f'[DEAL]'
                worth_messaging = True
                evaluationlog += 'X'
            elif price_benefit < item_price_num <= price_target and "VB" in item_price and verbose:
                item.pricehint = "[Bargain]"
                worth_messaging = True
                evaluationlog += 'b'
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
                item.print_price = f'{item.price}\n[{link_model.search_string}]\n{item.pricerange}'

        # METHOD 2
        if worth_messaging and type(link_model.price_high) != NoneType:
            # Mode: PRICERANGE
            # maximal item price to be shown (20% range)
            price_max = round(int(link_model.price_high) * 1.2)
            if (price_max - link_model.price_high) > 20:
                price_max = link_model.price_high + 20
            # INFO: lowest price to show in verbose is 30% below minimal price

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
                evaluationlog += 'V'
            elif int(link_model.price_low) <= item_price_num <= int(link_model.price_high):
                # price within range
                worth_messaging = True
                evaluationlog += 'X'
            elif int(link_model.price_high) < item_price_num <= price_max \
                    and "VB" in item_price and verbose:
                # price is negotiable and max 20% over watching price max 20€
                item.pricehint = f"(+20%)"
                worth_messaging = True
                evaluationlog += 'h'
            elif int(link_model.price_low) * 0.7 <= item_price_num < int(link_model.price_low) and verbose:
                # price is 30% below watch price
                item.pricehint = f"(-30%)"
                worth_messaging = True
                evaluationlog += 'l'
            pricerange = " [" + pricerange + "] "
            item.pricerange = f"{link_model.price_low}€{pricerange}{link_model.price_high}€"

        # should you calculate and check distances ?
        do_geoloc = False
        geoloc_areas = ""
        while True:
            if type(link_model.zipcodes) != NoneType:
                # DB setting takes priority: allows per search setting
                do_geoloc = True
                geoloc_areas = link_model.zipcodes.split('-')
                break
            if configs.LOCATION_FILTER != "":
                # Setting in config file is general filtering
                do_geoloc = True
                geoloc_areas = configs.LOCATION_FILTER.split('-')
                break
            break

        force_prio_geoloc = True if configs.FORCE_PRIO_GEOLOC == "1" else False
        item_noshipping = True if item.shipping == "No Shipping" else False

        # calculate distance
        item_inrange = False
        if worth_messaging and ((do_geoloc and item_noshipping) or force_prio_geoloc):
            evaluationlog += '?'
            # ZIPCODES in DB like this: dist1,zip11,zip12,..,zip1N-dist2,zip21..
            geocoder = Nominatim(user_agent="cyberpete2244/kleinanzeigenAlert")
            geoloc_item = geocoder.geocode(re.findall(r'\d+', item.location))
            # cycle through areas and through zipcodes
            t = 0
            while t < len(geoloc_areas) and not item_inrange:
                distancegroup = geoloc_areas[t].split(',')
                max_distance = int(distancegroup[0])
                n = 1
                while n < len(distancegroup) and not item_inrange:
                    geoloc_filter = geocoder.geocode(distancegroup[n])
                    itemdistance = round(distance.distance((geoloc_item.latitude, geoloc_item.longitude),
                                                           (geoloc_filter.latitude, geoloc_filter.longitude)).km)
                    if itemdistance <= max_distance:
                        item_inrange = True
                        n = len(distancegroup)
                        t = len(geoloc_areas)
                    else:
                        n += 1
                t += 1
            if item_inrange:
                evaluationlog += '+'
            elif not item_inrange:
                evaluationlog += '-'

        # still worth_messaging?
        if item_noshipping and do_geoloc and not item_inrange:
            worth_messaging = False

        # send telegram message?
        if worth_messaging and telegram_message:
            if firstmessagesent is False:
                print(' Messages:', end=' ')
                firstmessagesent = True

            print(evaluationlog, end='')

            # if this search has specified target chat, override here
            chat_id = configs.CHAT_ID
            if type(link_model.chat_id) is not NoneType:
                chat_id = link_model.chat_id

            send_formatted_message(item, chat_id, False)

            # is a priority chat available?
            if configs.BOTTOKEN_PRIO != "":
                priority_send = False
                while True:
                    if type(item) is EbayPost:
                        priority_send = True
                        break
                    if force_prio_geoloc and item_inrange:
                        priority_send = True
                        break
                    break

                if priority_send:
                    send_formatted_message(item, chat_id, True)

    if firstmessagesent is False:
        print(' Nothing worth messaging.', end='')
    print('')


if __name__ == "__main__":
    cli(sys.argv[1:])
