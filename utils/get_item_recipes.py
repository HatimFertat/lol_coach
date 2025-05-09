import os
import json
import requests
from utils.lolalytics_client import ItemSet
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

PATCH_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
ITEM_URL = "https://ddragon.leagueoflegends.com/cdn/{patch}/data/en_US/item.json"


def download_json_or_load_local(url, cache_path):
    if os.path.exists(cache_path):
        logger.info(f"Loading cached data from {cache_path}")
        with open(cache_path, "r") as f:
            return json.load(f)
    else:
        logger.info(f"Downloading from {url}")
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        with open(cache_path, "w") as f:
            json.dump(data, f, indent=2)
        return data
    
def get_current_patch():
    """
    Fetches the current patch version from the Riot API.
    """
    try:
        response = requests.get(PATCH_URL)
        response.raise_for_status()
        versions = response.json()
        if versions:
            return versions[0]
        else:
            raise ValueError("No versions found in the response.")
    except requests.RequestException as e:
        logger.error(f"Error fetching current patch: {e}")
        return None
    
CURRENT_PATCH = get_current_patch()
os.environ["CURRENT_PATCH"] = CURRENT_PATCH
CACHE_DIR = "patch_item_data"
os.makedirs(CACHE_DIR, exist_ok=True)
cache_path = os.path.join(CACHE_DIR, f"items_{CURRENT_PATCH}.json")



def get_legendary_items(item_data, map_id):
    legendary_items = []
    data = item_data.get("data", {})
    for _, item in data.items():
        # Must be purchasable
        if not item.get("gold", {}).get("purchasable", False):
            continue
        # Must be on the specified map
        if not item.get("maps", {}).get(str(map_id), False):
            continue
        # Must not have "into" (indicating it's not a component)
        if "into" in item:
            continue
        # Must not be a consumable
        if "Consumable" in item.get("tags", []) or "Trinket" in item.get("tags", []):
            continue
        # Total cost must be different from base cost (exclude starter items)
        gold = item.get("gold", {})
        if gold.get("total", 0) == gold.get("base", 0) and gold.get("total", 0) < 1500:
            continue
        legendary_items.append(item["name"])
    return legendary_items

def get_non_consumable_items(item_data, map_id):
    non_consumable_items = []
    data = item_data.get("data", {})
    for _, item in data.items():
        # Must be purchasable
        if not item.get("gold", {}).get("purchasable", False):
            continue
        # Must be on the specified map
        if not item.get("maps", {}).get(str(map_id), False):
            continue
        # Must not be a consumable
        if "Consumable" in item.get("tags", []) or "Trinket" in item.get("tags", []):
            continue
        non_consumable_items.append(item["name"])
    return non_consumable_items

def get_max_entries(section_name: str, legendary_count: int) -> int:
    if section_name.startswith("item_"):
        try:
            slot = int(section_name[-1])
        except ValueError:
            return 3
        if slot <= legendary_count - 2: #old slots
            return 2
        elif slot == legendary_count - 1:
            return 4
        elif slot == legendary_count:
            return 6
        else:
            return 10
    elif section_name == "boots":
        return 3
    return 5 #default for early game items

def build_section_text(section_name: str, item_sets: list[ItemSet]) -> str:
    header = f"== {section_name.replace('_', ' ').title()} =="
    lines = []
    for s in item_sets:
        item_list = ", ".join(s.items)
        lines.append(f"- {item_list} (WR: {s.winrate:.1f}%, PR: {s.pickrate:.1f}%, {s.games} games)")
    return f"{header}\n" + "\n".join(lines)