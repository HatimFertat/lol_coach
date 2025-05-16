# game_state_fetcher.py

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from game_context.game_state import parse_game_state
import time
import logging

logging.basicConfig(level=logging.DEBUG)
#suppress the warning InsecureRequestWarning: Unverified HTTPS request is being made to host '127.0.0.1'.
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def fetch_game_state():
    logging.debug("Starting fetch_game_state()")
    try:
        logging.debug("Requesting game state...")
        res = requests.get("https://127.0.0.1:2999/liveclientdata/allgamedata", verify=False)
        logging.debug(f"Status code: {res.status_code}")
        res.raise_for_status()
        data = res.json()
        logging.debug("Data fetched successfully.")
    except Exception as e:
        logging.error(f"Exception occurred: {e}")
        return None

    return parse_game_state(data)

if __name__ == "__main__":
    logging.debug("Running standalone game state fetcher")
    result = fetch_game_state()
    if result:
        from pprint import pprint
        pprint(result)
    else:
        logging.debug("No data returned")