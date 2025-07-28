import logging
import os


class Configs:
    LOGGING = os.environ.get("LOGGING") or logging.ERROR
    BOTTOKEN = os.environ.get("BOTTOKEN") or ""  # BOTToken for usual cases
    BOTTOKEN_PRIO = os.environ.get("BOTTOKEN_PRIO") or ""  # BOTToken for priority cases (geoloc)
    LOCATION_FILTER = ""  # example: "distance1,zip11,zip12,...zip1N-dist2,zip21,...,zip2N[...]" or ""
    CHAT_ID = os.environ.get("CHAT_ID") or ""  # ID for receiving Telegram user
    FILE_LOCATION = os.path.join(os.path.expanduser("~"), "kleinanzeigenAlert.db") # Path and name od SQLite database
    SOURCE_INDICATOR = ""  # OPTIONAL: first characters of telegram message
    SCRAPEOPS_API_KEY = ''
    TARGET_MODE_BENEFIT = 0.2  # Example for search mode when expecting at least 20% benefit when reselling
    FORCE_PRIO_GEOLOC = 1  # Force distance anytime and send to priority telegram chat if in range


configs = Configs()