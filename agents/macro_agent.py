# macro_agent.py

from agents.base_agent import Agent
from game_context.game_state import GameStateContext
from openai import OpenAI
import os
from dotenv import load_dotenv
import json

load_dotenv()

class MacroAgent(Agent):

    def summarize_game_state(self, game_state: GameStateContext) -> str:

        def format_time(seconds):
            minutes = int(seconds) // 60
            sec = int(seconds) % 60
            return f"{minutes}:{sec:02}"

        # Time
        time_str = format_time(game_state.timestamp)

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
        timers = filter(None, [
            format_obj_timer("Dragon", obj.dragon_respawn),
            format_obj_timer("Herald", obj.herald_respawn),
            format_obj_timer("Baron", obj.baron_respawn)
        ])
        timers_str = ", ".join(timers)

        # Buff timers (Baron/Elder) - show if either team has buff and it's active
        def format_buff_timer(label, ours, enemy):
            ours_str = format_time(ours) if ours and ours > game_state.timestamp else "None"
            enemy_str = format_time(enemy) if enemy and enemy > game_state.timestamp else "None"
            if (ours and ours > game_state.timestamp) or (enemy and enemy > game_state.timestamp):
                return f"{label} Buff - Ours: {ours_str} | Enemy: {enemy_str}"
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

        # Player summaries
        def summarize_players(champions):
            lines = []
            for champ in champions:
                role = champ.lane or "?"
                name = champ.name
                level = champ.level
                score = champ.score
                status = f"Respawning in {format_time(champ.respawn_timer)}" if champ.is_dead else "Alive"
                items = ", ".join(champ.items) if champ.items else "None"
                lines.append(f"[{role}] {name} (Lv {level}) | {score.kills}/{score.deaths}/{score.assists} | {status} | {items}")
            return lines

        our_players = summarize_players(game_state.player_team.champions)
        enemy_players = summarize_players(game_state.enemy_team.champions)

        # Final summary
        summary_lines = [
            f"Game Time: {time_str}",
            f"Turrets Fallen - Ours: {enemy_turrets or 'None'}",
            f"Turrets Fallen - Enemy: {our_turrets or 'None'}",
            f"Nexus Turrets Taken - Ours: {our_nexus} | Enemy: {enemy_nexus}",
            f"Inhibitors Taken - Ours: {our_inhibs} | Enemy: {enemy_inhibs}",
            f"Jungle Control - Ours: {our_jungle or 'None'}",
            f"Jungle Control - Enemy: {enemy_jungle or 'None'}",
        ]
        # Insert buff timers if present
        if baron_buff_line:
            summary_lines.append(baron_buff_line)
        if elder_buff_line:
            summary_lines.append(elder_buff_line)
        summary_lines += [
            f"Next Objectives: {timers_str or 'None'}",
            "",
            "Ours:"
        ] + our_players + ["", "Enemy:"] + enemy_players

        return "\n".join(summary_lines)

    def run(self, game_state: GameStateContext) -> str:
        client = OpenAI(
        api_key=os.getenv("GEMINI_API_KEY"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        summary = self.summarize_game_state(game_state)
        prompt = (
            "Based on the following game state summary, provide a concise macro strategy recommendation:\n\n"
            f"{summary}\n\n"
            "Recommendation:"
        )
        print(prompt)
        response = client.chat.completions.create(
            model="gemini-2.0-flash",
            messages=[
                {"role": "system", "content": "You are a macro-level coach for a League of Legends game."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1024)
        advice = response.choices[0].message.content
        return f"MacroAgent: {advice}"
    
if __name__ == "__main__":
    # get data from the examples folder
    from game_context.game_state import parse_game_state

    with open("examples/example.json", "r") as file:
        game_state_json = json.load(file)
    game_state = parse_game_state(game_state_json)
    agent = MacroAgent()
    summary = agent.summarize_game_state(game_state)
    # print(summary)
    advice = agent.run(game_state)
    print(advice)