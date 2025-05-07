# build_agent.py

from agents.base_agent import Agent
from game_context.game_state import GameStateContext
from openai import OpenAI
import os
from dotenv import load_dotenv
from agents.lolalytics_client import get_build, ItemSet, Section, toggle_mapping
from agents.get_item_recipes import get_legendary_items, download_json_or_load_local, get_max_entries, build_section_text, ITEM_URL, cache_path

load_dotenv()
CURRENT_PATCH = os.getenv("CURRENT_PATCH", "15.7.1")
legendary_item_list = get_legendary_items(
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
        build_url = f"https://lolalytics.com/lol/{champion}/build/?lane={role}"
        return reference_text, build_url

    def run(self, game_state: GameStateContext) -> str:
        game_time = game_state.timestamp
        champ = game_state.player_champion
        gold = game_state.active_player_gold
        items = next((c.items for c in game_state.player_team.champions if c.name == champ), [])
        role = game_state.role.lower()
        enemy = game_state.enemy_laner_champ or ""
        ally_champs = [game_state.player_team.champions[i].name for i in range(len(game_state.player_team.champions)) if game_state.player_team.champions[i].name != champ]
        enemy_champs = [game_state.enemy_team.champions[i].name for i in range(len(game_state.enemy_team.champions))]
        # Sanitize item names by stripping double quotes
        sanitized_items = [item.strip('"') for item in items]

        build_section, build_url = self.get_reference_build_text(game_time, sanitized_items, champ, role, enemy)

        prompt = (
            f"You are a League of Legends itemization expert.\n"
            f"The player is playing {champ} and currently owns {', '.join(sanitized_items) or 'no items'}.\n"
            f"Ally champions are {', '.join(ally_champs) or 'none'}. Enemy champions are {', '.join(enemy_champs) or 'none'}.\n"
            f"Here is a reference build for {champ} in the {role} role:\n\n"
            f"{build_section}\n\n"
            "What is the best next item to purchase given the comps, and briefly explain why. Think step by step."
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
            return f"BuildAgent:\n{reply}\n\nReference build source: {build_url}"
        except Exception as e:
            print(f"Prompt for debug:\n{prompt}")
            return f"BuildAgent Error: {str(e)}"

if __name__ == "__main__":
    from game_context.game_state import parse_game_state
    import json

    with open("examples/items_state.json", "r") as file:
        game_state_json = json.load(file)
    game_state = parse_game_state(game_state_json)
    game_state.role = "MIDDLE"
    agent = BuildAgent()
    
    # Print prompt for testing purposes
    champ = game_state.player_champion
    gold = game_state.active_player_gold
    items = next((c.items for c in game_state.player_team.champions if c.name == champ), [])
    role = game_state.role.lower()
    enemy = game_state.enemy_laner_champ or ""
    sanitized_items = [item.strip('"') for item in items]
    
    ally_champs = [game_state.player_team.champions[i].name for i in range(len(game_state.player_team.champions)) if game_state.player_team.champions[i].name != champ]
    enemy_champs = [game_state.enemy_team.champions[i].name for i in range(len(game_state.enemy_team.champions))]
    build_section, build_url = agent.get_reference_build_text(game_state.timestamp, sanitized_items, champ, role, enemy)

    advice = agent.run(game_state)
    print(advice)