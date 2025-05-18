# build_agent.py

from agents.base_agent import Agent
from game_context.game_state import (GameStateContext, ChampionState, parse_game_state, summarize_players,
                                    summarize_all_stats, format_time, format_items_string, role_mapping)
from openai import OpenAI
import os
from dotenv import load_dotenv
from utils.lolalytics_client import get_build, ItemSet, Section, toggle_mapping
from utils.get_item_recipes import (get_legendary_items, get_non_consumable_items, download_json_or_load_local,
                                     get_max_entries, build_section_text, ITEM_URL, CHAMPION_TAGS_URL, cache_path, champion_tags)
from typing import Tuple, Optional
import logging
load_dotenv()
CURRENT_PATCH = os.getenv("CURRENT_PATCH", "15.7.1")
legendary_item_list = get_legendary_items(
    download_json_or_load_local(ITEM_URL.format(patch=CURRENT_PATCH), cache_path, "items.json"),
    map_id=11
)
non_consumable_item_list = get_non_consumable_items(
    download_json_or_load_local(ITEM_URL.format(patch=CURRENT_PATCH), cache_path, "items.json"),
    map_id=11
)

champion_name_to_lolalytics = {champ_data['name']: champ_data['id'] for champ_data in champion_tags['data'].values()}
champion_name_to_lolalytics['MonkeyKing'] = 'Wukong'
def build_section_text(section_name: str, item_sets: list[ItemSet]) -> str:
    header = f"== {section_name.replace('_', ' ').title()} =="
    lines = []
    for s in item_sets:
        item_list = ", ".join(s.items)
        lines.append(f"- {item_list} (WR: {s.winrate:.1f}%, PR: {s.pickrate:.1f}%, {s.games} games)")
    return f"{header}\n" + "\n".join(lines)

class BuildAgent(Agent):
    def __init__(self):
        self.conversation_history = []
        self.champion_to_lolalytics = {}

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
        # Get items from the champion in the player's lane
        items = game_state.player_team.champions.get(game_state.role, ChampionState(name="", items=[])).items
        role = game_state.role.lower()
        enemy = game_state.enemy_laner_champ or ""
        active_player_index = game_state.active_player_idx

        # Sanitize item names by stripping double quotes
        sanitized_items = [item.strip('"') for item in items]
        
        build_section = self.get_reference_build_text(game_time, sanitized_items, champ, role, enemy)

        # Get active player and other players
        active_player = game_state.player_team.champions.get(game_state.role)
        active_player_summary = summarize_players([active_player] if active_player else [], non_consumable_item_list)
        our_players = summarize_players([c for lane, c in game_state.player_team.champions.items() if lane != game_state.role], non_consumable_item_list)
        enemy_players = summarize_players([c for c in game_state.enemy_team.champions.values()], non_consumable_item_list)

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
    
    def standalone_message(self, user_message: str) -> str:
        # Free-form chat, just append user message

        self.conversation_history.append({"role": "user", "content": user_message})
        try:
            client = OpenAI(
                api_key=os.getenv("GEMINI_API_KEY"),
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
            messages = [{"role": "system", "content": "You are a League of Legends coach for item builds."}] + self.conversation_history
            response = client.chat.completions.create(
                model="gemini-2.0-flash-lite",
                messages=messages,
                max_tokens=256
            )
            reply = response.choices[0].message.content
            self.conversation_history.append({"role": "assistant", "content": reply})
            return reply
        except Exception as e:
            return f"BuildAgent Error: {str(e)}"
        
    def check_for_summary(self, advice: str) -> str:
        if "Final recommendation: " in advice:
            return advice.split("Final recommendation:")[-1]
        else:
            return "Read the full response to get the item recommendation."
        
    def run(self, game_state: Optional[GameStateContext] = None, user_message: str = None, image_path: str = None) -> Tuple[str, str, str]:
        if game_state is None and user_message is not None:
            return user_message, self.standalone_message(user_message), ""
        
        # Summarize game state
        summary = self.summarize_game_state(game_state)
        prefix = "Based on the following game state summary, what is the best next item to purchase, and briefly explain why. Think step by step."
        suffix = "Your response must always end with the exact sentence: 'Final recommendation: I recommend you build <item>.' Replace <item> with the item name"
        suffix += "Recommendation:"
        if user_message:
            suffix = user_message + "\n" + suffix

        # Add user message to conversation history
        prompt = f"{prefix}\n{summary}\n{suffix}"
        self.conversation_history.append({"role": "user", "content": prompt})
        try:
            client = OpenAI(
                api_key=os.getenv("GEMINI_API_KEY"),
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
            # Always start with a system prompt
            messages = [{"role": "system", "content": "You are a League of Legends coach for item builds."}] + self.conversation_history
            response = client.chat.completions.create(
                model="gemini-2.0-flash-lite",
                messages=messages,
                max_tokens=512
            )
            reply = response.choices[0].message.content
            # Add assistant reply to conversation history
            self.conversation_history.append({"role": "assistant", "content": reply})
            curated_reply = self.check_for_summary(reply)
            logging.debug(f"BuildAgent curated reply: {curated_reply}")
            return prompt, reply, curated_reply
        except Exception as e:
            error_msg = f"BuildAgent Error: {str(e)}"
            return error_msg, error_msg, ""

if __name__ == "__main__":
    import json

    with open("data/examples/example_game_state.json", "r") as file:
        game_state_json = json.load(file)
    game_state = parse_game_state(game_state_json)
    game_state.role = "BOTTOM"
    agent = BuildAgent()
    summary = agent.summarize_game_state(game_state)
    # print(summary)
    advice = agent.run(game_state)
    print(advice)