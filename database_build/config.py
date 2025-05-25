# config.py

import requests
import logging
import os

# Mapping for regions with platform (for summoner/league endpoints) and routing (for match endpoints)
REGIONS = {
    'NA': {'platform': 'na1', 'routing': 'americas'},
    'EUW': {'platform': 'euw1', 'routing': 'europe'},
    'EUNE': {'platform': 'eun1', 'routing': 'europe'},
    'KR': {'platform': 'kr', 'routing': 'asia'},
    'BR': {'platform': 'br1', 'routing': 'americas'},
    'LAN': {'platform': 'la1', 'routing': 'americas'},
    'LAS': {'platform': 'la2', 'routing': 'americas'},
    'OCE': {'platform': 'oc1', 'routing': 'sea'},
    'JP': {'platform': 'jp1', 'routing': 'asia'},
    # Add any additional regions as needed
}

# Ranked Solo/Duo queue ID (420)
RANKED_SOLO_QUEUE_ID = 420

# Define the start of the current patch (Unix timestamp).
# Update this timestamp at each new patch cycle.
PATCH_URL = "https://ddragon.leagueoflegends.com/api/versions.json"

def get_current_previous_patch():
    """
    Fetches the current patch version from the Riot API.
    """
    try:
        response = requests.get(PATCH_URL)
        response.raise_for_status()
        versions = response.json()
        if versions:
            return versions[0], versions[1]
        else:
            raise ValueError("No versions found in the response.")
    except requests.RequestException as e:
        print(f"Error fetching current patch: {e}")
        return None
    
CURRENT_PATCH, PREVIOUS_PATCH = get_current_previous_patch()
os.environ["CURRENT_PATCH"] = CURRENT_PATCH
os.environ["PREVIOUS_PATCH"] = PREVIOUS_PATCH

