# lolalytics_client.py

import requests
from bs4 import BeautifulSoup
import json

def get_build_for(champ: str, role: str = "bottom", vs: str = None) -> dict:
    base_url = f"https://lolalytics.com/lol/{champ.lower()}/"
    if vs:
        url = f"{base_url}vs/{vs.lower()}/build/?lane={role.lower()}"
    else:
        url = f"{base_url}build/?lane={role.lower()}"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        raise ValueError(f"Lolalytics returned {res.status_code} for {url}")

    soup = BeautifulSoup(res.text, "html.parser")
    script_tag = soup.find("script", id="__NEXT_DATA__")

    if not script_tag:
        raise RuntimeError("Could not find __NEXT_DATA__ script tag on page.")

    data = json.loads(script_tag.string)
    try:
        core = data["props"]["pageProps"]["championBuild"]["itemBuilds"]["core"]
        core_items = [item["name"] for item in core]
        return {
            "core_items": core_items,
            "source": url,
            "champ": champ,
            "role": role,
            "vs": vs,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to parse build from JSON: {e}")