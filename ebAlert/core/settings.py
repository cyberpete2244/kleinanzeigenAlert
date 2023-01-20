from ebAlert.core.configs import configs


class Settings:

    TELEGRAM_API_URL = f"https://api.telegram.org/bot{configs.BOTTOKEN}/sendMessage?chat_id={configs.CHAT_ID}&parse_mode=HTML&"""
    URL_BASE = "https://www.ebay-kleinanzeigen.de"
    URL_TYPE_GPU = "/s-pc-zubehoer-software/grafikkarten/anbieter:privat/anzeige:angebote/{NPAGE}{" \
                   "SEARCH_TERM}k0c225+pc_zubehoer_software.art_s:grafikkarten"
    URL_TYPE_HIFI = "/s-audio-hifi/anbieter:privat/{NPAGE}{SEARCH_TERM}k0c172"
    URL_TYPE_IPHONE = "/s-handy-telekom/apple/anbieter:privat/anzeige:angebote/{NPAGE}{" \
                      "SEARCH_TERM}k0c173+handy_telekom.art_s:apple+handy_telekom.condition_s:condition_used"
    URL_TYPE_MONITOR = "/s-pc-zubehoer-software/monitore/anbieter:privat/anzeige:angebote/{NPAGE}{" \
                       "SEARCH_TERM}k0c225+pc_zubehoer_software.art_s:monitore"
    URL_TYPE_CPU = "/s-pc-zubehoer-software/prozessor_cpu/anbieter:privat/anzeige:angebote/{NPAGE}{" \
                       "SEARCH_TERM}k0c225+pc_zubehoer_software.art_s:prozessor_cpu"
    URL_TYPE_MEMORY = "/s-pc-zubehoer-software/speicher/anbieter:privat/anzeige:angebote/{NPAGE}{" \
                       "SEARCH_TERM}k0c225+pc_zubehoer_software.art_s:speicher"


settings = Settings()
