import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from ebayAlert import create_logger
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

    def _find_text_in_child_of_class(self, class_name: str):
        found = self.contents.find(attrs={"class": f"{class_name}"})
        if found:
            found = found.contents[0]
            if found:
                return found.text.strip()


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





