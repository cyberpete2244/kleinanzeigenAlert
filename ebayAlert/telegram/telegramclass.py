import requests

from ebayAlert.core.configs import configs
from ebayAlert.core.settings import settings
from urllib.parse import urlencode


def telegram_api_send(bottoken, chat_id):
    return settings.TELEGRAM_API_SEND.format(bottoken=bottoken, chat_id=chat_id)


class TelegramClass:

    def send_message(self, message, chat_id):
        message_encoded = urlencode({"text": message})
        sending_url = telegram_api_send(configs.BOTTOKEN, chat_id) + message_encoded
        response = requests.get(sending_url)

        if response == 200:
            return response.json()["ok"]

    def send_formated_message(self, item, chat_id):
        message = f"{configs.SOURCE_INDICATOR}{item.title}\n\n{item.print_price}\n\n{item.shipping}\n({item.location})\n\n"
        url = f'<a href="{item.link}">{item.link}</a>'
        self.send_message(message + url, chat_id)


telegram = TelegramClass()
