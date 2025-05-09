# main.py
import os
from utils.get_item_recipes import CURRENT_PATCH
os.environ["CURRENT_PATCH"] = CURRENT_PATCH

from game_context.game_state import GameStateContext, TeamState, ChampionState, ObjectiveTimers
from agents.build_agent import BuildAgent
from agents.macro_agent import MacroAgent
import time
from dotenv import load_dotenv

load_dotenv()

from GUI.gui import LoLCoachGUI

if __name__ == "__main__":
    app = LoLCoachGUI()
    app.mainloop()
