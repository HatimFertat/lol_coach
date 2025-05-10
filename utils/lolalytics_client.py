from playwright.sync_api import sync_playwright
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict
import os
import json
import datetime
import pickle
from typing import Optional

@dataclass
class ItemSet:
    items: List[str]
    winrate: Optional[float]
    pickrate: Optional[float]
    games: Optional[int]

@dataclass
class Section:
    name: str
    sets: List[ItemSet]

toggle_mapping = {
        "Exact item count (no boots)": ["x_1", "x_2", "x_3", "x_4", "x_5"],
        "Exact item count (with boots)": ["xb_1", "xb_2", "xb_3", "xb_4", "xb_5", "xb_6"],
        "Actually built sets (no boots)": ["a_1", "a_2", "a_3", "a_4", "a_5"],
        "Actually built sets (with boots)": ["ab_1", "ab_2", "ab_3", "ab_4", "ab_5", "ab_6"],
        "Extrapolated sets (no boots)": ["e_2", "e_3", "e_4", "e_5"],
        "Extrapolated sets (with boots)": ["eb_2", "eb_3", "eb_4", "eb_5", "eb_6"],
        "Combined sets (no boots)": ["c_2", "c_3", "c_4"],
        "Combined sets (with boots)": ["cb_2", "cb_3", "cb_4", "cb_5"],
    }

section_mapping = {"starting_items": ["starting", "item sets"],
                "early_items": ["early"],
                "popular_items": ["popular"],
                "winning_items": ["winning"],
                "boots": ["boots"],
                "item_1": ["item", "1"],
                "item_2": ["item", "2"],
                "item_3": ["item", "3"],
                "item_4": ["item", "4"],
                "item_5": ["item", "5"],
                "item_sets": "win rate\npick rate\ngames"}

allowed_section_types = ['starting_items', 'early_items', 'boots', 'item_1', 'item_2', 'item_3', 'item_4', 'item_5']
    
logger = logging.getLogger(__name__)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(filename)s:%(message)s')
else:
    logging.basicConfig(level=logging.WARNING, format='%(levelname)s:%(filename)s:%(message)s')


def classify_section(label: str, mapping: dict) -> str:
    # logger.debug(f"Classifying section with label: {label}")
    for key, values in mapping.items():
        if isinstance(values, list):
            if all(v in label for v in values):
                return key
        elif label == values:
            return key
    return "unknown_section"

def scrape_actual_builds(champion="fiora", role='top', vs="singed", allowed_section_types=allowed_section_types, toggle=None) -> List[Section]:
    logger.debug(f"Starting scrape for champion: {champion}, role: {role}, toggle: {toggle}")
    champion = champion.replace("'", "").lower()
    base_url = f"https://lolalytics.com/lol/{champion}/"
    if vs:
        vs = vs.replace("'", "").lower()
        url = f"{base_url}vs/{vs.lower()}/build/?lane={role.lower()}"
        
    else:
        url = f"{base_url}build/?lane={role.lower()}"
        allowed_section_types = allowed_section_types + ['item_sets']

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # set to True for silent scraping
        page = browser.new_page()
        page.goto(url)
        logger.debug(f"Navigated to {url}")
        if vs:
            logger.debug(f"Attempting to scroll into early items section to force render")
            try:
                # Click the tab labeled 'Early Items (10 min)' to force scroll/render
                early_tab = page.locator("div[data-type='single'] >> text=Early Items (10 min)")
                if early_tab.count() > 0:
                    early_tab.first.click()
                    logger.debug("Clicked Early Items tab to trigger scroll/render")
                else:
                    logger.warning("Early Items tab not found")
                    print("URL", url)
                    raise KeyError("Early Items tab not found")
            except Exception as e:
                logger.exception("Failed to click Early Items tab")
        else:
            toggle_selector = f'div[data-type="{toggle}"]'
            logger.debug(f"Waiting for toggle selector: {toggle_selector}")
            toggle_locator = page.locator(toggle_selector)
            if toggle_locator.count() == 0:
                logger.warning(f"Toggle '{toggle}' not found on page. Skipping toggle click.")
            else:
                toggle_locator.click(force=True)
                logger.debug(f"Clicked on toggle for {toggle}")
                # Wait for the grid to update after toggle
                page.wait_for_function(
                    """() => {
                        const sections = document.querySelectorAll('div.cursor-grab.overflow-x-scroll');
                        return Array.from(sections).some(s => 
                            s.previousElementSibling?.innerText?.toLowerCase().includes('win rate')
                        );
                    }""",
                    timeout=5000
                )
        # Scrape all visible builds from the updated grid
        logger.debug("Classifying sections based on labels above scroll containers")
        sections = page.query_selector_all("div.cursor-grab.overflow-x-scroll")
        builds: List[Section] = []

        for section in sections:
            try:
                label_text = section.evaluate("el => el.previousElementSibling?.innerText || ''").strip().lower()
            except Exception as e:
                logger.exception("Failed to get label text")
                label_text = ""
            
            section_type = classify_section(label_text, section_mapping)

            if section_type not in allowed_section_types:
                continue

            try:
                section.scroll_into_view_if_needed()
                logger.debug(f"Scrolled to section: {section_type}")
                page.wait_for_function(
                    "(el) => el.querySelectorAll('div.flex.gap-\\\\[6px\\\\].text-center.text-\\\\[12px\\\\] > div').length > 0",
                    arg=section
                )
                logger.debug(f"Waited for section to render: {section_type}")
            except Exception as e:
                logger.warning(f"Failed to ensure rendering for section {section_type}: {e}")
                continue

            current_itemset = Section(name=section_type, sets=[])

            container = section.query_selector("div.flex.gap-\\[6px\\].text-center.text-\\[12px\\]")
            if not container:
                logger.warning("Could not find item sets container inside section")
                continue

            item_sets = container.query_selector_all(":scope > div")
            logger.debug(f"Total item set {section_type} blocks found: {len(item_sets)}")

            for block in item_sets:
                imgs = block.query_selector_all("img")
                items = []
                for img in imgs:
                    alt = img.get_attribute("alt")
                    if alt:
                        items.append(alt)

                if not items:
                    logger.debug("Skipping block with no items")
                    continue

                winrate = pickrate = games = None
                stats_divs = block.query_selector_all("div.my-1")
                if len(stats_divs) >= 3:
                    try:
                        winrate_span = stats_divs[0].query_selector("span")
                        if winrate_span:
                            winrate = float(winrate_span.inner_text().strip())
                        pickrate = float(stats_divs[1].inner_text().strip())
                        games = int(stats_divs[2].inner_text().replace(",", "").strip())
                    except Exception as e:
                        logger.exception("Failed to parse stats")

                current_itemset.sets.append(ItemSet(
                    items=items,
                    winrate=winrate,
                    pickrate=pickrate,
                    games=games
                ))

            builds.append(current_itemset)

        browser.close()
        logger.debug("Browser closed")
        for itemset in builds:
            logger.info(f"{itemset.name}: {len(itemset.sets)} sets")
        logger.debug(f"Returning {len(builds)} section builds")
        return builds


def get_build(champion: str, role: str, vs: str = "", toggle: Optional[str] = None, cache_dir: str = "cache_builds") -> List[Section]:
    os.makedirs(cache_dir, exist_ok=True)
    date_str = datetime.date.today().isoformat()
    champion = champion.replace("'", "").lower()
    vs = vs.replace("'", "").lower()
    role = role.replace("'", "").lower()
    cache_key = f"{champion}_{role}_{vs or 'none'}_{date_str}.pkl"
    cache_path = os.path.join(cache_dir, cache_key)

    if os.path.exists(cache_path):
        logger.debug(f"Loading cached build from {cache_path}")
        with open(cache_path, "rb") as f:
            return pickle.load(f)

    logger.debug(f"No cache found for {cache_key}, scraping new build data")
    try:
        builds = scrape_actual_builds(champion=champion, role=role, vs=vs, toggle=toggle)

        with open(cache_path, "wb") as f:
            pickle.dump(builds, f)
    except Exception as e:
        logger.error(f"Failed to scrape builds: {e}")
        return []
    return builds

if __name__ == "__main__":
    import time
    start = time.time()

    builds = scrape_actual_builds(champion="fiora", role="top", vs="", toggle="ab_5")
    print([build for build in builds if build.name == "item_sets"])
    print(f"Scraped {len(builds)} sections in {time.time() - start:.2f} seconds")