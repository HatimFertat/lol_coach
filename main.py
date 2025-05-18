# main.py
import logging

# Set global logging to ERROR to suppress other lower level logs
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("phonemizer").setLevel(logging.ERROR)
logging.getLogger("words_mismatch").setLevel(logging.ERROR)
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
logging.getLogger("numba").setLevel(logging.ERROR)
logging.getLogger("utils").setLevel(logging.ERROR)

import os
from utils.get_item_recipes import CURRENT_PATCH, PREVIOUS_PATCH
os.environ["CURRENT_PATCH"] = CURRENT_PATCH
os.environ["PREVIOUS_PATCH"] = PREVIOUS_PATCH

from dotenv import load_dotenv
from PySide6.QtWidgets import QApplication
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="PySide6.QtWidgets")
warnings.filterwarnings("ignore", category=UserWarning, module="phonemizer")
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