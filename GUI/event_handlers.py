from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QMessageBox
import random
import json
from pathlib import Path
import logging

from GUI.events.custom_events import EventType, _ScreenshotReadyEvent, _ScreenshotErrorEvent

class EventHandlers(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.use_mock = False

    def set_mock_mode(self, use_mock):
        self.use_mock = use_mock

    def _get_mock_game_state(self):
        return self.main_window.get_game_state()

    @Slot()
    def trigger_build_agent_update(self):
        """
        Update the build agent with the current game state.
        This agent doesn't use screenshots, so it always just updates with game state.
        """
        try:
            if self.use_mock:
                game_state = self._get_mock_game_state()
                if game_state:
                    self.main_window.build_tab.update_with_game_state(game_state)
                else:
                    logging.warning("BuildAgent: Mock game state is None.")
            else:
                self.main_window.build_tab.update_with_game_state()
        except Exception as e:
            logging.exception("Error in build agent update")

    @Slot()
    def trigger_macro_agent_update(self):
        """
        Update the macro agent.
        When triggered by keyboard shortcut or timer, it will use screenshot.
        When triggered directly (via button click), it will use regular update.
        """
        try:
            # Always trigger with screenshot for timer or keyboard shortcut
            if self.use_mock:
                # In mock mode, we can't take real screenshots
                game_state = self._get_mock_game_state()
                if game_state:
                    self.main_window.macro_tab.update_with_game_state(game_state)
                else:
                    logging.warning("MacroAgent: Mock game state is None.")
            else:
                # In live mode, take a screenshot
                self.main_window.screenshot_handler.take_screenshot("MacroAgent")
        except Exception as e:
            logging.exception("Error in macro agent update")

    @Slot()
    def trigger_vision_agent_update(self):
        """
        Update the vision agent.
        When triggered by keyboard shortcut or timer, it will use screenshot.
        When triggered directly (via button click), it will use regular update.
        """
        try:
            # Always trigger with screenshot for timer or keyboard shortcut
            if self.use_mock:
                # In mock mode, we can't take real screenshots
                game_state = self._get_mock_game_state()
                if game_state:
                    self.main_window.vision_tab.update_with_game_state(game_state)
                else:
                    logging.warning("VisionAgent: Mock game state is None.")
            else:
                # In live mode, take a screenshot
                self.main_window.screenshot_handler.take_screenshot("VisionAgent")
        except Exception as e:
            logging.exception("Error in vision agent update")

    @Slot()
    def stop_tts(self):
        self.main_window.tts_manager.stop_speaking() 