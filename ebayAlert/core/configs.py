import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()


class Configs:
    LOGGING = os.environ.get("LOGGING") or logging.ERROR
    BOTTOKEN = os.environ.get("BOTTOKEN") or ""
    BOTTOKEN_PRIO = os.environ.get("BOTTOKEN_PRIO") or ""
    LOCATION_FILTER = os.environ.get("LOCATION_FILTER") or ""  # example: "distance1,zip11,zip12,...zip1N-dist2,zip21,...,zip2N[...]" or ""
    CHAT_ID = os.environ.get("CHAT_ID") or ""  # ID for test bot
    FILE_LOCATION = os.environ.get("FILE_LOCATION") or os.path.join(os.path.expanduser("~"), "kleinanzeigenAlert.db")
    SOURCE_INDICATOR = os.environ.get("SOURCE_INDICATOR") or ""  # OPTIONAL: first characters of telegram message
    SCRAPEOPS_API_KEY = os.environ.get("SCRAPEOPS_API_KEY") or ""
    TARGET_MODE_BENEFIT = float(os.environ.get("TARGET_MODE_BENEFIT") or 0.2)
    FORCE_PRIO_GEOLOC = int(os.environ.get("FORCE_PRIO_GEOLOC") or 1)


configs = Configs()
