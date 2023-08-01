import requests

from ebayAlert.core.configs import configs
from ebayAlert.core.settings import settings
from urllib.parse import urlencode


def telegram_api_send(bottoken, chat_id):
    return settings.TELEGRAM_API_SEND.format(bottoken=bottoken, chat_id=chat_id)


def send_formatted_message(item, chat_id, priority):
    message = f"{configs.SOURCE_INDICATOR}{item.title}\n\n{item.print_price}\n\n{item.shipping}\n({item.location})\n\n"
    message += f'<a href="{item.link}">{item.link}</a>'
    message_encoded = urlencode({"text": message})
    sending_url = ""
    if priority:
        sending_url = telegram_api_send(configs.BOTTOKEN_PRIO, chat_id) + message_encoded
    else:
        sending_url = telegram_api_send(configs.BOTTOKEN, chat_id) + message_encoded

    requests.get(sending_url)
