# game_state_fetcher.py

import requests
from game_state import parse_game_state
import time

def fetch_game_state():
    print("[DEBUG] Starting fetch_game_state()")
    try:
        print("[DEBUG] Requesting game state...")
        res = requests.get("https://127.0.0.1:2999/liveclientdata/allgamedata", verify=False)
        print(f"[DEBUG] Status code: {res.status_code}")
        res.raise_for_status()
        data = res.json()
        print("[DEBUG] Data fetched successfully.")
    except Exception as e:
        print(f"[ERROR] Exception occurred: {e}")
        return None

    return parse_game_state(data)

if __name__ == "__main__":
    print("[TEST] Running standalone game state fetcher")
    result = fetch_game_state()
    if result:
        from pprint import pprint
        pprint(result)
    else:
        print("[TEST] No data returned")