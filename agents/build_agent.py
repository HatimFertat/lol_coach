# build_agent.py

from agents.base_agent import Agent
from game_context.game_state import (GameStateContext, parse_game_state, summarize_players,
                                    summarize_all_stats, format_time, format_items_string)
from openai import OpenAI
import os
from dotenv import load_dotenv
from agents.lolalytics_client import get_build, ItemSet, Section, toggle_mapping
from agents.get_item_recipes import (get_legendary_items, get_non_consumable_items, download_json_or_load_local,
                                     get_max_entries, build_section_text, ITEM_URL, cache_path)

load_dotenv()
CURRENT_PATCH = os.getenv("CURRENT_PATCH", "15.7.1")
legendary_item_list = get_legendary_items(
    download_json_or_load_local(ITEM_URL.format(patch=CURRENT_PATCH), cache_path),
    map_id=11
)
non_consumable_item_list = get_non_consumable_items(
    download_json_or_load_local(ITEM_URL.format(patch=CURRENT_PATCH), cache_path),
    map_id=11
)

def build_section_text(section_name: str, item_sets: list[ItemSet]) -> str:
    header = f"== {section_name.replace('_', ' ').title()} =="
    lines = []
    for s in item_sets:
        item_list = ", ".join(s.items)
        lines.append(f"- {item_list} (WR: {s.winrate:.1f}%, PR: {s.pickrate:.1f}%, {s.games} games)")
    return f"{header}\n" + "\n".join(lines)

class BuildAgent(Agent):
    def get_reference_build_text(self, game_time: int, completed_items: list[str], champion: str, role: str, enemy: str) -> tuple[str, str]:
        build_sections = get_build(champion=champion, role=role, vs=enemy)
        reference_texts = []

        legendary_count = len([item for item in completed_items if item in legendary_item_list])

        if game_time < 600:
            section = next((s for s in build_sections if s.name == "early_items"), None)
            if section:
                top_k = get_max_entries("early_items", legendary_count)
                reference_texts.append(build_section_text("early_items", section.sets[:top_k]))

        for i in range(1, legendary_count + 2):
            section_name = f"item_{i}"
            section = next((s for s in build_sections if s.name == section_name), None)
            if section:
                top_k = get_max_entries(section_name, legendary_count)
                reference_texts.append(build_section_text(section_name, section.sets[:top_k]))

        reference_text = "\n\n".join(reference_texts)

        return reference_text

    def filter_items_by_timestamp(self, items: list[str], game_time: int) -> list[str]:
        """
        Filters items based on the game timestamp.
        - Before 20 minutes: Include component and legendary items.
        - After 20 minutes: Include only legendary items.
        - Exclude consumables at all times.
        """
        if game_time < 1200:  # 20 minutes in seconds
            return [item for item in items if item in legendary_item_list or item in non_consumable_item_list]
        return [item for item in items if item in legendary_item_list]
    
    def summarize_game_state(self, game_state: GameStateContext) -> str:
        game_time = game_state.timestamp
        champ = game_state.player_champion
        gold = game_state.active_player_gold
        items = next((c.items for c in game_state.player_team.champions if c.name == champ), [])
        role = game_state.role.lower()
        enemy = game_state.enemy_laner_champ or ""
        active_player_index = game_state.active_player_idx

        # Sanitize item names by stripping double quotes
        sanitized_items = [item.strip('"') for item in items]
        
        build_section = self.get_reference_build_text(game_time, sanitized_items, champ, role, enemy)

        active_player_summary = summarize_players([game_state.player_team.champions[active_player_index]], non_consumable_item_list)
        our_players = summarize_players([c for c in game_state.player_team.champions if c.name != game_state.player_champion], non_consumable_item_list)
        enemy_players = summarize_players(game_state.enemy_team.champions, non_consumable_item_list)

        summary = [
            f"Here is the current state of my league of legends game:\n",
            f"Game Time: {format_time(game_time)}",
            f"I am playing {champ} {role} with the following stats:",
            f"{summarize_all_stats(game_state.active_player_stats)}",
            f"{active_player_summary[0]}",
            f"\nAlly champions and their items:",
            "\n".join(our_players),
            f"\nEnemy champions and their items:",
            "\n".join(enemy_players),
            f"\nHere is a reference build for {champ} in the {role} role:",
            f"Each item is listed with its winrate, pickrate, and number of games played.",
            f"{build_section}"
        ]
        return "\n".join(summary)
    
    def run(self, game_state: GameStateContext) -> str:
        summary = self.summarize_game_state(game_state)
        prompt = (
            "Based on the following game state summary,:\n\n"
            f"{summary}\n\n"
            "What is the best next item to purchase, and briefly explain why. Think step by step."
            "Recommendation:"
        )
        print(prompt)
        try:
            client = OpenAI(
                api_key=os.getenv("GEMINI_API_KEY"),
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
            response = client.chat.completions.create(
                model="gemini-2.0-flash-lite",
                messages=[
                    {"role": "system", "content": "You are a League of Legends coach for item builds."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=512
            )
            reply = response.choices[0].message.content
            return f"BuildAgent:\n{reply}"
        except Exception as e:
            print(f"Prompt for debug:\n{prompt}")
            return f"BuildAgent Error: {str(e)}"

if __name__ == "__main__":
    import json

    # with open("examples/items_state.json", "r") as file:
    with open("examples/example_game_state.json", "r") as file:
        game_state_json = json.load(file)
    game_state = parse_game_state(game_state_json)
    game_state.role = "BOTTOM"
    agent = BuildAgent()
    summary = agent.summarize_game_state(game_state)
    # print(summary)
    advice = agent.run(game_state)
    print(advice)