from typing import Generator
from bs4 import BeautifulSoup
from random import randint
from time import sleep

from ebayAlert.scrapping.items import BaseItem, ItemFactory
from ebayAlert import create_logger
from ebayAlert.core.settings import settings

log = create_logger(__name__)


class KleinItem(BaseItem):
    @property
    def link(self) -> str:
        if self.contents.a.get('href'):
            return settings.KLEIN_URL_BASE + self.contents.a.get('href')
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
        url = settings.KLEIN_URL_BASE + link_model.url.format(PAGENSEARCH=current_page+search_term)
        # print(url)
        return url

    @staticmethod
    def extract_item_from_page(soup: BeautifulSoup) -> Generator:
        result = soup.find(attrs={"id": "srchrslt-adtable"})
        if result:
            for item in result.find_all(attrs={"class": "ad-listitem lazyload-item"}):
                if item.article:
                    yield item.article