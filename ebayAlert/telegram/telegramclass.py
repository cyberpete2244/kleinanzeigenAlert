import requests

from ebayAlert.core.configs import configs
from ebayAlert.core.settings import settings
from ebayAlert.ebayscrapping.ebayclass import EbayItem
from urllib.parse import urlencode


def send_message(message):
    send_text_url = settings.TELEGRAM_API_URL + message + ""
    response = requests.get(send_text_url)
    return response.json()['ok']


class SendingClass:

    def send_message(self, message):
        message_encoded = urlencode({"text": message})
        sending_url = settings.TELEGRAM_API_URL + message_encoded + ""
        response = requests.get(sending_url)

        if response == 200:
            return response.json()["ok"]

    def send_formated_message(self, item: EbayItem):
        message = f"{configs.SOURCE_INDICATOR}{item.title}\n\n{item.print_price}\n\n{item.shipping}\n({item.location})\n\n"
        url = f'<a href="{item.link}">{item.link}</a>'
        self.send_message(message + url)


telegram = SendingClass()