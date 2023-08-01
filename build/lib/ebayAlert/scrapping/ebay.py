from typing import Generator
from bs4 import BeautifulSoup

from ebayAlert.core.settings import settings
from ebayAlert.scrapping.items import BaseItem, ItemFactory
from ebayAlert import create_logger

log = create_logger(__name__)


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
        return self._find_text_in_class("s-item__title").removeprefix("Neues Angebot") or "No Title"

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
        url = self.contents.a.get('href')
        return int(url[url.rindex("/") + 1:url.index("?")]) or 0

    @property
    def location(self):
        return "Ebay"


class EbayItemFactory(ItemFactory):
    def __init__(self, link_model):
        self.item_list = []
        web_page_soup = self.get_webpage(settings.EBAY_URL_BASE + link_model.url)
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
