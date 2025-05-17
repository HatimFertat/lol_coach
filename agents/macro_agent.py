# macro_agent.py

from agents.base_agent import Agent
from game_context.game_state import GameStateContext, format_time, summarize_all_stats, summarize_players, role_mapping
from openai import OpenAI
import os
from dotenv import load_dotenv
import json
from utils.get_item_recipes import (get_legendary_items, get_non_consumable_items, download_json_or_load_local,
                                     get_max_entries, build_section_text, ITEM_URL, cache_path, download_champion_icons, champion_tags)
import base64
from typing import Tuple, Optional
from vision.champion_detector import detect_champion_positions, format_champion_positions

load_dotenv()
CURRENT_PATCH = os.getenv("CURRENT_PATCH", "15.7.1")
non_consumable_item_list = get_non_consumable_items(
    download_json_or_load_local(ITEM_URL.format(patch=CURRENT_PATCH), cache_path, "items.json"),
    map_id=11
)


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

class MacroAgent(Agent):

    def __init__(self):
        self.conversation_history = []
        download_champion_icons()

    def summarize_game_state(self, game_state: GameStateContext, minimap_path: Optional[str] = None) -> str:
        time_str = format_time(game_state.timestamp)
        active_player_index = game_state.active_player_idx
        
        # Get champion positions if minimap is available
        champion_positions = ""
        if minimap_path:
            ally_champions = [c.name for c in game_state.player_team.champions]
            enemy_champions = [c.name for c in game_state.enemy_team.champions]
            positions_str, positions_xy = detect_champion_positions(minimap_path, ally_champions, enemy_champions, debug=False)
            champion_positions = format_champion_positions(positions_str, positions_xy, ally_champions, enemy_champions)
        #replace [Ally] and [Enemy] by the lane of the champions
        # champion_positions = champion_positions.replace("[Ally]", game_state.player_team.champions[active_player_index].lane)
        # champion_positions = champion_positions.replace("[Enemy]", game_state.enemy_team.champions[active_player_index].lane)
        # Turrets Taken (per lane if > 0)
        def summarize_lane_turrets(turrets):
            return ", ".join(
                f"{lane} {len(tiers)}" for lane, tiers in turrets.items() if tiers
            )

        our_turrets = summarize_lane_turrets(game_state.player_team.turrets_taken)
        enemy_turrets = summarize_lane_turrets(game_state.enemy_team.turrets_taken)

        # Nexus turrets
        def count_nexus_turrets(turrets_taken):
            return sum(
                1 for tiers in turrets_taken.values()
                for tier in tiers if "Nexus" in tier
            )

        our_nexus = count_nexus_turrets(game_state.player_team.turrets_taken)
        enemy_nexus = count_nexus_turrets(game_state.enemy_team.turrets_taken)

        # Inhibs taken
        our_inhibs = ", ".join(game_state.player_team.inhibs_taken) or "None"
        enemy_inhibs = ", ".join(game_state.enemy_team.inhibs_taken) or "None"

        # Jungle control
        def summarize_monsters(counts):
            return ", ".join(f"{k} x{v}" for k, v in counts.items())

        our_jungle = summarize_monsters(game_state.player_team.monster_counts)
        enemy_jungle = summarize_monsters(game_state.enemy_team.monster_counts)

        # Objective timers
        def format_obj_timer(label, value):
            return f"{label} at {format_time(value)}" if value and value > game_state.timestamp else None

        obj = game_state.objectives
        dragon_type = obj.dragon_type or ""
        timers = filter(None, [
            format_obj_timer(dragon_type + " " + "Dragon", obj.dragon_respawn),
            format_obj_timer("Herald", obj.herald_respawn),
            format_obj_timer("Baron", obj.baron_respawn)
        ])
        timers_str = ", ".join(timers)

        # Buff timers (Baron/Elder)
        def format_buff_timer(label, ours, enemy):
            ours_str = format_time(ours) if ours and ours > game_state.timestamp else "None"
            enemy_str = format_time(enemy) if enemy and enemy > game_state.timestamp else "None"
            which_team = "Our" if ours_str != "None" else "Enemy"
            which_str = ours_str if ours_str != "None" else enemy_str
            if (ours and ours > game_state.timestamp) or (enemy and enemy > game_state.timestamp):
                return f"{label} Buff expiry - {which_team} team: {which_str}"
            return None

        baron_buff_line = format_buff_timer(
            "Baron",
            getattr(game_state.player_team, "baron_buff_expires_at", None),
            getattr(game_state.enemy_team, "baron_buff_expires_at", None)
        )
        elder_buff_line = format_buff_timer(
            "Elder",
            getattr(game_state.player_team, "elder_buff_expires_at", None),
            getattr(game_state.enemy_team, "elder_buff_expires_at", None)
        )
        
        active_player_summary = summarize_players([c for c in game_state.player_team.champions if c.name == game_state.player_champion], non_consumable_item_list, role_mapping)
        our_players = summarize_players([c for c in game_state.player_team.champions if c.name != game_state.player_champion], non_consumable_item_list, role_mapping)
        enemy_players = summarize_players(game_state.enemy_team.champions, non_consumable_item_list, role_mapping)

        role = role_mapping.get(game_state.role, game_state.role).capitalize()
        champ = game_state.player_champion

        # Final summary
        summary_lines = [
            f"Here is the current state of my league of legends game:\n",
            f"Game Time: {time_str}",

            f"Our team is {'blue' if game_state.team_side == 'ORDER' else 'red'} side",
            f"I am playing {champ} {role} with the following stats:",
            f"{summarize_all_stats(game_state.active_player_stats)}",
            f"{active_player_summary[0]}\n",
        ]

        # Add champion positions if available
        if champion_positions:
            summary_lines.append("Champion Positions:")
            summary_lines.append(champion_positions)
            summary_lines.append("")

        summary_lines.extend([
            f"Turrets destroyed by our team: {our_turrets or 'None'} | by enemy team: {enemy_turrets or 'None'}",
            f"Nexus Turrets destroyed by our team: {our_nexus} | by enemy team: {enemy_nexus}",
            f"Inhibitors destroyed by our team: {our_inhibs} | by enemy team: {enemy_inhibs}",
            f"Jungle epic monsters taken by our team: {our_jungle or 'None'} | by enemy team: {enemy_jungle or 'None'}",
        ])

        # Insert buff timers if present
        if baron_buff_line:
            summary_lines.append(baron_buff_line)
        if elder_buff_line:
            summary_lines.append(elder_buff_line)
        summary_lines += [
            f"Next Objectives not spawn yet: {timers_str or 'all spawned already'}",
            "",
            "My teammates:"
        ] + our_players + ["", "Enemy team:"] + enemy_players

        return "\n".join(summary_lines)

    def standalone_message(self, user_message: str) -> str:
        self.conversation_history.append({"role": "user", "content": user_message})
        try:
            client = OpenAI(
                api_key=os.getenv("GEMINI_API_KEY"),
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
            messages = [{"role": "system", "content": "You are a macro-level coach for a League of Legends game."}] + self.conversation_history
            response = client.chat.completions.create(
                model="gemini-2.0-flash",
                messages=messages,
                max_tokens=256
            )
            advice = response.choices[0].message.content
            self.conversation_history.append({"role": "assistant", "content": advice})
            return advice
        except Exception as e:
            return f"MacroAgent Error: {str(e)}"
        
    def run(self, game_state: Optional[GameStateContext] = None, user_message: str = None, image_path: str = None) -> tuple[str, str]:
        if user_message is not None and game_state is None:
            return user_message, self.standalone_message(user_message)

        # Summarize game state
        summary = self.summarize_game_state(game_state, image_path)
        prefix = "Based on the following game state summary"
        if image_path:
            prefix += " and the champion positions"
        prefix += ", provide a quick macro strategy recommendation for the next 2 minutes."
        
        suffix = ""
        if image_path:
            suffix += "Consider the champion positions when making your recommendation.\n"
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
            messages = [{"role": "system", "content": "You are a macro-level coach for a League of Legends game."}] + self.conversation_history
            response = client.chat.completions.create(
                model="gemini-2.0-flash-lite",
                messages=messages,
                max_tokens=2048
            )
            advice = response.choices[0].message.content
            self.conversation_history.append({"role": "assistant", "content": advice})
            return prompt, advice
        except Exception as e:
            return f"MacroAgent Error: {str(e)}"
    
if __name__ == "__main__":
    # get data from the examples folder
    from game_context.game_state import parse_game_state

    with open("examples/example_game_state.json", "r") as file:
        game_state_json = json.load(file)
    game_state = parse_game_state(game_state_json)
    game_state.role = "BOTTOM"
    agent = MacroAgent()
    summary = agent.summarize_game_state(game_state)
    # print(summary)
    advice = agent.run(game_state)
    print(advice)
