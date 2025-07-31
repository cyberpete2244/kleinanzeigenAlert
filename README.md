# kleinanzeigenAlert - (ebayAlert)
Small CLI program that will send you a Telegram message for every new posts on the specific links of the Kleinanzeigen and to some extent Ebay websites. 

This is a fork from [vinc3PO/ebayKleinanzeigenAlert](https://github.com/vinc3PO/ebayKleinanzeigenAlert)

No API required - Only URL of the query.

## Install

1. Clone this repository
   ```sh
   git clone https://github.com/cyberpete2244/kleinanzeigenAlert
   ```
2. Navigate to the cloned repository
   ```sh
   cd kleinanzeigenAlert
   ```
3. Create a Telegram Bot
   1. Open the chat with [@BotFather](https://t.me/BotFather)
   2. Enter `/newbot`
   3. Enter the name of your Bot (e.g. Kleinanzeigen Bot)
   4. Enter an unique username for your bot (e.g. my_kleinanzeigen_bot)
   5. Copy the token
4. Get you Telegram Message ID
   1. Open the chat with [@RawDataBot](https://t.me/RawDataBot)
   2. Enter `/start`
   3. Copy the message ID. Either from `message/from/id` or `message/chat/id`. The message ID looks like `417417807`.
5. Set environment variables like BOTTOKEN and CHAT_ID and so on in `ebAlert/core/config.py`. Use `ebAlert/core/config.defaults.py` to create this file.
6. Start a conversation with the bot from your Telegram App, otherwise the Telegram Bot cannot contact you.
7. Create virtaul environment for application and install it
   ```sh
   python3 -m venv venv
   venv/bin/pip install .
   ```
8. Run the `ebayAlert` CLI
   ```sh
   venv/bin/python3 -m ebayAlert start
   ```
9. The first run will initiate a SQLite database. Now you will need to create search tasks. Currently possible in database only.

## Usage & Example
I removed the ability to add searches using CLI, might add it back later. Currently one need to set up searches using SQL queries directly in DB or by using any third party SQL manager (e.g. SQLite3). 
* ```ebayAlert start [opts] ``` to run script with options
* ```ebayAlert start --help ``` to get list of options

Run regular cli command to initialise DB:  

* ```ebayAlert start ``` to start receiving notification or init database

Typically, this would be run as a cron job on an hourly basis.

## Creating Searches (WIP)
Currently this process is not supported by cli. WIP

## Requirements
* A telegram bot API token and your personal conversation ID
* ScrapeOPS API token
* Python 3
* Libraries
  * click
  * requests
  * bs4
  * sqlalchemy
  * bs4
  * beautifulsoup4
  * geopy
  * setuptools
  * scrapeops-scrapy

## ChangeLog
  1.2 (forked) -> 2.0
* database rework
* searches are created in database directly (WIP)
* items filtering by distance (if shipping not available) possible
  * distance can be defined globally or per search
* headers for scraper are generated randomly using ScrapeOPS API
* searching Ebay is possible indirectly
  * matching Ebay items to Kleinanzeigen searches (main mode) is done on consequent executions
* two search modes:
  * A) items are searched within a price range
  * B) items are matched below a target price (benefit margin adjustable in configs.py)

## Future Plans
* add functionality to interact with script via telegram.
* add cli option to add, edit, remove searches and types
