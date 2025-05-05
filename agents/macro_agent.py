# macro_agent.py

from base_agent import Agent
from game_state.game_state import GameStateContext
import openai
import os
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

class MacroAgent(Agent):

    def summarize_game_state(self, game_state: GameStateContext) -> str:
        our_dragons = game_state.player_team.dragons_taken
        enemy_dragons = game_state.enemy_team.dragons_taken
        next_dragon = game_state.objectives.dragon_spawn
        our_towers = game_state.player_team.towers_remaining
        enemy_towers = game_state.enemy_team.towers_remaining
        game_time = game_state.game_time
        return (f"Game time: {game_time} seconds. "
                f"Our dragons taken: {our_dragons}, Enemy dragons taken: {enemy_dragons}. "
                f"Next dragon spawns in: {next_dragon} seconds. "
                f"Our towers remaining: {our_towers}, Enemy towers remaining: {enemy_towers}.")

    def run(self, game_state: GameStateContext) -> str:
        summary = self.summarize_game_state(game_state)
        prompt = (
            "Based on the following game state summary, provide a concise macro strategy recommendation:\n\n"
            f"{summary}\n\n"
            "Recommendation:"
        )
        response = openai.ChatCompletion.create(
            model="gemini-2.0-flash-lite",
            messages=[
                {"role": "system", "content": "You are a macro-level coach for a League of Legends game."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.7,
            n=1,
            stop=None,
        )
        advice = response.choices[0].message['content'].strip()
        return f"MacroAgent: {advice}"