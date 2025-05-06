# build_agent.py

from base_agent import Agent
from game_context.game_state import GameStateContext
import openai
import os
from dotenv import load_dotenv
from lolalytics_client import get_build_for

load_dotenv()
openai.api_key = os.getenv("GEMINI_API_KEY")  # You’re using Gemini key but calling OpenAI library

class BuildAgent(Agent):
    def run(self, game_state: GameStateContext) -> str:
        champ = game_state.player_champion
        gold = game_state.active_player_gold
        items = next((c.items for c in game_state.player_team.champions if c.name == champ), [])

        build = get_build_for(champ, game_state.role.lower(), )
        reference_build = build["items"]
        build_url = build["url"]

        prompt = (
            f"You are a League of Legends itemization expert. "
            f"The player is playing {champ} with {gold} gold and currently owns {', '.join(items) or 'no items'}. "
            f"Here is a reference build for {champ} in the bottom role: {', '.join(reference_build)}. "
            "What is the best next item to purchase given the current gold, and briefly explain why?"
        )

        try:
            response = openai.ChatCompletion.create(
                model="gemini-2.0-flash-lite",
                messages=[
                    {"role": "system", "content": "You are a League of Legends item coach."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100
            )
            reply = response.choices[0].message["content"]
            return f"BuildAgent:\n{reply}\n\nReference build source: {build_url}"
        except Exception as e:
            return f"BuildAgent Error: {str(e)}"