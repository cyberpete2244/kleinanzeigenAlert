from typing import Generator

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from random import randint
from time import sleep

from ebayAlert import create_logger
from ebayAlert.core.settings import settings
from ebayAlert.scrapping.scrapeops import header_list, get_random_header

log = create_logger(__name__)


class BaseItem:
    def __init__(self, contents: Tag):
        self.contents = contents
        self.old_price = ""
        self.pricehint = ""
        self.pricerange = ""

    @property
    def print_price(self) -> str:
        print_price = self.price
        if self.old_price != "":
            print_price = "NEW:" + self.old_price + " --> " + print_price
        if self.pricehint != "":
            print_price += " " + self.pricehint
        if self.pricerange != "":
            print_price += "\n" + self.pricerange
        return print_price

    def __repr__(self):
        return '{}, {}; {}'.format(self.id, self.title, self.price)

    def _find_text_in_class(self, class_name: str):
        found = self.contents.find(attrs={"class": f"{class_name}"})
        if found:
            return found.text.strip()


class KleinItem(BaseItem):
    @property
    def link(self) -> str:
        if self.contents.a.get('href'):
            return settings.URL_BASE + self.contents.a.get('href')
        else:
            return "No url found."

    @property
    def shipping(self) -> str:
        return self._find_text_in_class("aditem-main--middle--price-shipping--shipping") or "No Shipping"

    @property
    def title(self) -> str:
        return self._find_text_in_class("ellipsis") or "No Title"

    @property
    def price(self) -> str:
        return self._find_text_in_class("aditem-main--middle--price-shipping--price") or "No Price"

    @property
    def description(self) -> str:
        description = self._find_text_in_class("aditem-main--middle--description")
        if description:
            return description.replace("\n", " ")
        else:
            return "No Description"

    @property
    def id(self) -> int:
        return int(self.contents.get('data-adid')) or 0

    @property
    def location(self):
        return self._find_text_in_class("aditem-main--top--left") or "No location"


class EbayItem(BaseItem):
    @property
    def link(self) -> str:
        url = self.contents.a.get('href')
        return url[:url.index("?")]

    @property
    def shipping(self) -> str:
        return self._find_text_in_class("s-item__shipping s-item__logisticsCost") or "No Shipping"

    @property
    def title(self) -> str:
        return self._find_text_in_class("s-item__title") or "No Title"

    @property
    def price(self) -> str:
        # strip EUR and add € at end
        price = self._find_text_in_class("s-item__price") or 0
        if price != 0:
            price = price[4:price.index(',')]
        return f'{price} €'

    @property
    def description(self) -> str:
        return "No Description"

    @property
    def id(self) -> int:
        ebaylink = self.contents.a.get('href')
        return int(ebaylink[ebaylink.rindex("/")+1:ebaylink.index("?")]) or 0

    @property
    def location(self):
        return "Ebay"


class ItemFactory:
    @staticmethod
    def get_webpage(url: str) -> BeautifulSoup:
        response = requests.get(url, headers=get_random_header(header_list))
        if response and response.status_code == 200:
            cleaned_response = response.text.replace("&#8203", "")
            soup = BeautifulSoup(cleaned_response, "html.parser")
            return soup
        else:
            print(f"<< webpage fetching error for url: {url} STATUS: {response.status_code} TEXT: {response.text}")


class KleinItemFactory(ItemFactory):
    def __init__(self, link_model, npage_max):
        self.item_list = []
        npage = 1
        while 0 < npage <= npage_max:
            web_page_soup = self.get_webpage(self.generate_url(link_model, npage))
            if web_page_soup:
                articles = self.extract_item_from_page(web_page_soup)
                self.item_list += [KleinItem(article) for article in articles]
                npage_found = len(web_page_soup.find(attrs={"class": "pagination-pages"}).find_all())
                if npage < npage_found and npage <= npage_max:
                    npage += 1
                    sleep(randint(0, 20) / 10)
                else:
                    npage = 0
            else:
                npage = 0

    @staticmethod
    def generate_url(link_model, npage=1) -> str:
        # generate url from DB using URL placeholders: {NPAGE} {SEARCH_TERM}
        current_page = ""
        if npage > 1:
            current_page = "seite:" + str(npage) + "/"
        search_term = ""
        if link_model.search_string != "":
            # in DB search sting can contain "exclusions" with "-xyz". These con not be part of URL. Exclusions need to be done when analysing results
            search_term_parts = link_model.search_string.split(" ")
            search_term_parts[:] = [x for x in search_term_parts if not x.startswith("-")]
            search_term = "-".join(str(y) for y in search_term_parts) + "/"
        # currently price is not considered in getting the results, articles are filtered later
        url = settings.URL_BASE
        url += getattr(settings, "URL_TYPE_"+link_model.search_type).format(SEARCH_TERM=search_term, NPAGE=current_page)
        # print(url)
        return url

    @staticmethod
    def extract_item_from_page(soup: BeautifulSoup) -> Generator:
        result = soup.find(attrs={"id": "srchrslt-adtable"})
        if result:
            for item in result.find_all(attrs={"class": "ad-listitem lazyload-item"}):
                if item.article:
                    yield item.article


class EbayItemFactory(ItemFactory):
    def __init__(self, link_model):
        self.item_list = []
        web_page_soup = self.get_webpage(link_model.search_string)
        if web_page_soup:
            articles = self.extract_item_from_page(web_page_soup)
            self.item_list += [EbayItem(article) for article in articles]

    @staticmethod
    def extract_item_from_page(soup: BeautifulSoup) -> Generator:
        result = soup.find(attrs={"class": "b-list__items_nofooter"})
        if result:
            for item in result.find_all(attrs={"class": "s-item s-item--large"}):
                if item:
                    yield item
