class Settings:

    TELEGRAM_API_SEND = "https://api.telegram.org/bot{bottoken}/sendMessage?chat_id={chat_id}&parse_mode=HTML&"

    KLEIN_URL_BASE = "https://www.kleinanzeigen.de"
    EBAY_URL_BASE = "https://www.ebay.de"
    EBAY_BASE_ITEM = EBAY_URL_BASE + "/itm/"


settings = Settings()
