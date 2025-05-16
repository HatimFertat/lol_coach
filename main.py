# main.py
import os
from utils.get_item_recipes import CURRENT_PATCH, PREVIOUS_PATCH
os.environ["CURRENT_PATCH"] = CURRENT_PATCH
os.environ["PREVIOUS_PATCH"] = PREVIOUS_PATCH

from game_context.game_state import GameStateContext, TeamState, ChampionState, ObjectiveTimers
from agents.build_agent import BuildAgent
from agents.macro_agent import MacroAgent
import time
from dotenv import load_dotenv
from PySide6.QtWidgets import QApplication
#suppress the warning WARNING:darwin.py:This process is not trusted! Input event monitoring will not be possible until it is added to accessibility clients.
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="PySide6.QtWidgets")
load_dotenv()

from GUI.gui import LoLCoachGUI

if __name__ == "__main__":
    # Create QApplication instance before any widgets
    app = QApplication([])
    # Create the GUI window
    window = LoLCoachGUI()
    window.show()
    # Start the Qt event loop
    app.exec()