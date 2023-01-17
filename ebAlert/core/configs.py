import logging
import os


class Configs:
    LOGGING = os.environ.get("LOGGING") or logging.ERROR
    BOTTOKEN = os.environ.get("BOTTOKEN") or "BOTTOKEN"
    LOCATION_FILTER = ""  # example: "distance1,zip11,zip12,...zip1N-dist2,zip21,...,zip2N[...]" or ""
    CHAT_ID = os.environ.get("CHAT_ID") or "CHAT_ID"  # ID for test bot
    FILE_LOCATION = os.path.join(os.path.expanduser("~"), "ebayklein.db")
    MAX_PAGESTOSCRAPE = 2  # makes it search for up to n*25 recent items matching the search term
    SOURCE_INDICATOR = ""  # OPTIONAL: first characters of telegram message


configs = Configs()
