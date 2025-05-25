# riot_api.py

import time
import requests
import logging
from dotenv import load_dotenv
import os
from config import REGIONS, RANKED_SOLO_QUEUE_ID

logger = logging.getLogger()
load_dotenv()
RIOT_API_KEY = os.getenv("RIOT_API_KEY")

BASE_URL_TEMPLATE = "https://{host}.api.riotgames.com"

def call_api(url, params=None):
    if params is None:
        params = {}
    headers = {
        "X-Riot-Token": RIOT_API_KEY,
        "User-Agent": "Build_Data_Visual/1.0.0 (+https://github.com/build_data_visual)"
    }
    # logger.info(f"Calling API URL: {url} with params: {params}")
    try:
        response = requests.get(url, params=params, headers=headers)
    except Exception as e:
        logger.error(f"Exception during API call: {e}")
        return None
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", "1"))
        logger.warning(f"Rate limited. Retrying after {retry_after} seconds.")
        time.sleep(retry_after)
        return call_api(url, params)
    elif response.status_code != 200:
        logger.error(f"API call failed: {response.status_code} - {response.text}")
        # logger.error(f"Response headers: {response.headers}")
        return None
    return response.json()

def fetch_league_players(region, tier="CHALLENGER", division=None):
    platform = REGIONS[region]['platform']
    base_url = BASE_URL_TEMPLATE.format(host=platform)
    if tier.upper() in ["CHALLENGER", "MASTER", "GRANDMASTER"]:
        url = f"{base_url}/lol/league/v4/{tier.lower()}leagues/by-queue/RANKED_SOLO_5x5"
        return call_api(url)
    else:
        # For tiers with multiple divisions (e.g., Platinum, Diamond)
        if division:
            url = f"{base_url}/lol/league/v4/entries/RANKED_SOLO_5x5/{tier.upper()}/{division}"
            return call_api(url)
        else:
            divisions = ["I", "II", "III", "IV"]
            combined_results = []
            for div in divisions:
                url = f"{base_url}/lol/league/v4/entries/RANKED_SOLO_5x5/{tier.upper()}/{div}"
                result = call_api(url)
                if result:
                    combined_results.extend(result)
            return {"entries": combined_results}

def fetch_match_ids_by_puuid(region, puuid, start_time, count=20):
    routing = REGIONS[region]['routing']
    base_url = BASE_URL_TEMPLATE.format(host=routing)
    url = f"{base_url}/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {
        "queue": RANKED_SOLO_QUEUE_ID,
        "startTime": start_time,
        "count": count
    }
    return call_api(url, params=params)

def fetch_match_details(region, match_id):
    routing = get_routing_for_match(match_id, region)
    base_url = BASE_URL_TEMPLATE.format(host=routing)
    url = f"{base_url}/lol/match/v5/matches/{match_id}"
    return call_api(url)

def fetch_match_timeline(region, match_id):
    routing = get_routing_for_match(match_id, region)
    base_url = BASE_URL_TEMPLATE.format(host=routing)
    url = f"{base_url}/lol/match/v5/matches/{match_id}/timeline"
    return call_api(url)

def get_routing_for_match(match_id, region):
    # Infer routing based on the match_id prefix
    prefix = match_id.split('_')[0]
    prefix_to_routing = {
        "NA1": "americas",
        "BR1": "americas",
        "LA1": "americas",
        "LA2": "americas",
        "OC1": "sea",
        "EUW1": "europe",
        "EUN1": "europe",
        "TR1": "europe",
        "RU": "europe",
        "KR": "asia",
        "JP1": "asia",
    }
    if prefix in prefix_to_routing:
        return prefix_to_routing[prefix]
    return REGIONS[region]['routing']