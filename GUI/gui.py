import logging
import os
import json
import time
import threading
from pathlib import Path
from datetime import datetime

# Remove Tkinter imports
from PySide6.QtCore import Qt, QSize, Signal, Slot, QEvent, QTimer, QThread, QCoreApplication
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QTabWidget, 
                             QTextEdit, QLineEdit, QPushButton, QCheckBox,
                             QLabel, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QSplitter, QFileDialog, QMessageBox)
from PySide6.QtGui import QFont, QColor, QTextCursor, QTextCharFormat, QIntValidator, QKeySequence

from agents.build_agent import BuildAgent
from agents.macro_agent import MacroAgent
from agents.vision_agent import VisionAgent
from game_context.game_state import parse_game_state
from game_context.game_state_fetcher import fetch_game_state
from vision.screenshot_listener import take_screenshot_and_crop
from vision.minimap_cropper import SCREENSHOT_DIR
from utils.tts_manager import TTSManager
# from utils.legacy_tts import TTSManager

from pynput import keyboard

from GUI.components.agent_chat_tab import AgentChatTab
from GUI.components.settings_tab import SettingsTab
from GUI.components.screenshot_handler import ScreenshotHandler
from GUI.events.custom_events import EventType
from GUI.event_handlers import EventHandlers

MOCK = False

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LoL Coach")
        self.setGeometry(100, 100, 800, 600)
        
        # Initialize components
        self.tts_manager = TTSManager()
        self.screenshot_handler = ScreenshotHandler(self)
        self.settings_tab = SettingsTab()
        
        # Create agents
        self.build_agent = BuildAgent()
        self.macro_agent = MacroAgent()
        self.vision_agent = VisionAgent()
        
        # Create agent chat tabs
        self.build_tab = AgentChatTab(self.build_agent, "BuildAgent", self.get_game_state, self.settings_tab.auto_clear, self.tts_manager)
        self.macro_tab = AgentChatTab(self.macro_agent, "MacroAgent", self.get_game_state, self.settings_tab.auto_clear, self.tts_manager)
        self.vision_tab = AgentChatTab(self.vision_agent, "VisionAgent", self.get_game_state, self.settings_tab.auto_clear, self.tts_manager)
        
        self.event_handlers = EventHandlers(self)
        
        # Connect settings signals
        self.settings_tab.mock_mode_changed.connect(self._on_mock_mode_changed)
        self.settings_tab.vision_interval_changed.connect(self._on_vision_interval_changed)
        self.settings_tab.macro_interval_changed.connect(self._on_macro_interval_changed)
        self.settings_tab.model_changed.connect(self._on_model_changed)
        self.settings_tab.tts_settings_changed.connect(self._on_tts_settings_changed)
        
        # Setup UI
        self._setup_ui()
        self.start_keyboard_listener()
        self._setup_timers()
        
        # Initialize mock mode
        self._on_mock_mode_changed(self.settings_tab.is_mock_mode())
        
        # Initialize model
        self._on_model_changed(self.settings_tab.get_selected_model())
        
        # Initialize TTS settings
        self._on_tts_settings_changed(self.settings_tab.get_tts_settings())
        
        # Show greeting after a short delay
        QTimer.singleShot(1000, self._delayed_greeting)

    def _setup_ui(self):
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Add tabs
        self.tab_widget.addTab(self.macro_tab, "Macro Agent")
        self.tab_widget.addTab(self.build_tab, "Build Agent")
        self.tab_widget.addTab(self.vision_tab, "Vision Agent")
        self.tab_widget.addTab(self.settings_tab, "Settings")
        
        layout.addWidget(self.tab_widget)

    def _parse_shortcut_string(self, shortcut_str):
        """
        Convert a shortcut string like "Ctrl+Alt+M" to a set of pynput keys.
        Returns an empty set if the shortcut string is invalid.
        """
        if not shortcut_str:
            return set()
        
        keys = set()
        parts = shortcut_str.split('+')
        
        # Map Qt key names to pynput keys
        key_map = {
            'ctrl': keyboard.Key.ctrl,
            'alt': keyboard.Key.alt,
            'shift': keyboard.Key.shift,
            'cmd': keyboard.Key.cmd,
            'meta': keyboard.Key.cmd,
            'space': keyboard.Key.space,
            'esc': keyboard.Key.esc,
            'escape': keyboard.Key.esc,
            'tab': keyboard.Key.tab,
            'return': keyboard.Key.enter,
            'enter': keyboard.Key.enter,
            # Add other special keys if needed
        }
        
        for part in parts:
            part = part.strip().lower()  # Convert to lowercase for case-insensitive matching
            
            if part in key_map:
                keys.add(key_map[part])
            elif len(part) == 1:  # Single character keys (a-z, 0-9)
                keys.add(keyboard.KeyCode.from_char(part))
            elif part.isdigit():  # Handle numeric keys
                keys.add(keyboard.KeyCode.from_char(part))
                
        # logging.debug(f"Parsed shortcut '{shortcut_str}' to key set: {keys}")
        return keys

    def start_keyboard_listener(self):
        self.current_keys = set()
        self.listener = None
        self.last_shortcut_time = {}  # Track when shortcuts were last triggered

        def on_press(key):
            try:
                # Add the key to the set of currently pressed keys
                self.current_keys.add(key)
                # logging.debug(f"on_press: key = {key}, current_keys = {self.current_keys}")
                
                # Define which shortcuts trigger which event types
                shortcut_actions = {
                    "build_agent": EventType.BuildAgentTrigger,
                    "macro_agent": EventType.MacroAgentTrigger,
                    "vision_agent": EventType.VisionAgentTrigger,
                    "tts_stop": EventType.TTSStopTrigger,
                    "push_to_talk": EventType.PushToTalkTrigger,
                }
                
                # Check each shortcut against current keys
                for shortcut_name, event_type in shortcut_actions.items():
                    shortcut_str = self.settings_tab.get_shortcut(shortcut_name)
                    if not shortcut_str:  # Skip empty shortcuts
                        continue
                        
                    target_keys = self._parse_shortcut_string(shortcut_str)
                    if not target_keys:  # Skip invalid shortcuts
                        continue
                        
                    # logging.debug(f"Checking shortcut: {shortcut_name} ('{shortcut_str}') -> pynput_set: {target_keys}")
                    
                    # Check if all required keys are pressed (current_keys contains all target_keys)
                    if target_keys and target_keys.issubset(self.current_keys) and len(target_keys) == len(self.current_keys):
                        # For push-to-talk, implement toggle behavior
                        if shortcut_name == "push_to_talk":
                            current_time = time.time()
                            last_time = self.last_shortcut_time.get(shortcut_name, 0)
                            # Only trigger if enough time has passed since last trigger (debounce)
                            if current_time - last_time > 0.3:  # 300ms debounce
                                self.last_shortcut_time[shortcut_name] = current_time
                                logging.info(f"Shortcut TOGGLED: {shortcut_name} ({shortcut_str})")
                                # Post the event to the current active tab
                                current_tab = self.tab_widget.currentWidget()
                                if isinstance(current_tab, AgentChatTab):
                                    QCoreApplication.postEvent(current_tab, QEvent(event_type))
                        else:
                            logging.info(f"Shortcut ACTIVATED: {shortcut_name} ({shortcut_str})")
                            QCoreApplication.postEvent(self, QEvent(event_type))
                        break
            except Exception as e:
                logging.exception(f"Error in keyboard listener on_press: {e}")

        def on_release(key):
            try:
                # Remove the key from the set of currently pressed keys
                self.current_keys.discard(key)
                # logging.debug(f"on_release: key = {key}, current_keys = {self.current_keys}")
            except Exception as e:
                logging.exception(f"Error in keyboard listener on_release: {e}")
        
        # Start the listener only once
        if self.listener is None:
            self.listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            self.listener.start()
            logging.info("Pynput keyboard listener started.")

    def _setup_timers(self):
        # Vision update timer
        self.vision_timer = QTimer()
        self.vision_timer.timeout.connect(self.event_handlers.trigger_vision_agent_update)
        
        # Macro update timer
        self.macro_timer = QTimer()
        self.macro_timer.timeout.connect(self.event_handlers.trigger_macro_agent_update)
        
        # Start timers with initial intervals
        self._update_timer_intervals()

    def _update_timer_intervals(self):
        # Update vision timer
        vision_interval = self.settings_tab.get_vision_interval()
        if vision_interval > 0:
            self.vision_timer.start(vision_interval * 1000)
        else:
            self.vision_timer.stop()
        
        # Update macro timer
        macro_interval = self.settings_tab.get_macro_interval()
        if macro_interval > 0:
            self.macro_timer.start(macro_interval * 1000)
        else:
            self.macro_timer.stop()

    @Slot(bool)
    def _on_mock_mode_changed(self, use_mock: bool):
        # Update event handlers with mock mode
        self.event_handlers.set_mock_mode(use_mock)
        
        # Update timers based on mock mode
        # Mock mode should still respect user-defined intervals (0 means off)
        self._update_timer_intervals()

    @Slot(int)
    def _on_vision_interval_changed(self, interval: int):
        """Handle vision interval change from settings"""
        logging.info(f"Vision interval changed: {interval}")
        if interval <= 0:
            if self.vision_timer.isActive():
                logging.info("Stopping vision timer (interval ≤ 0)")
                self.vision_timer.stop()
        else:
            if not self.vision_timer.isActive() or self.vision_timer.interval() != interval * 1000:
                logging.info(f"Setting vision timer to {interval}s")
                self.vision_timer.start(interval * 1000)

    @Slot(int)
    def _on_macro_interval_changed(self, interval: int):
        """Handle macro interval change from settings"""
        logging.info(f"Macro interval changed: {interval}")
        if interval <= 0:
            if self.macro_timer.isActive():
                logging.info("Stopping macro timer (interval ≤ 0)")
                self.macro_timer.stop()
        else:
            if not self.macro_timer.isActive() or self.macro_timer.interval() != interval * 1000:
                logging.info(f"Setting macro timer to {interval}s")
                self.macro_timer.start(interval * 1000)

    @Slot(str)
    def _on_model_changed(self, model_name: str):
        """Handle model selection change from settings."""
        logging.info(f"Model changed to: {model_name}")
        try:
            self.macro_agent.set_model(model_name)
            self.build_agent.set_model(model_name)
        except Exception as e:
            logging.error(f"Error setting model: {e}")
            QMessageBox.warning(self, "Model Error", f"Failed to set model: {str(e)}")

    @Slot(dict)
    def _on_tts_settings_changed(self, settings: dict):
        """Handle TTS settings changes"""
        logging.info(f"TTS settings changed: {settings}")
        try:
            # Update TTS engine
            self.tts_manager.set_engine(settings["engine"])
            
            # Update voice and speed
            self.tts_manager.voice = settings["voice"]
            self.tts_manager.speed = settings["speed"]
            
        except Exception as e:
            logging.error(f"Error updating TTS settings: {e}")
            QMessageBox.warning(self, "TTS Error", f"Failed to update TTS settings: {str(e)}")

    def get_game_state(self):
        try:
            if self.settings_tab.is_mock_mode():
                mock_file_path = os.path.join(os.path.dirname(__file__), '../data/examples/with_minimap.json')
                logging.debug(f"Attempting to load mock game state from: {mock_file_path}")
                if os.path.exists(mock_file_path):
                    with open(mock_file_path) as f:
                        game_state_json = json.load(f)
                    parsed_state = parse_game_state(game_state_json)
                    return parsed_state
                else:
                    logging.error(f"Mock game state file not found: {mock_file_path}")
                    logging.debug(f"MainWindow.get_game_state (mock, file not found) returning: None")
                    return None
            else:
                logging.debug("Attempting to fetch real game state.")
                game_state_data = fetch_game_state()
                # Explicitly ensure we don't return a boolean
                if isinstance(game_state_data, bool):
                    logging.error(f"Real game state fetch returned a boolean: {game_state_data}, returning None instead")
                    return None
                logging.debug(f"Fetched real game data type: {type(game_state_data)}")
                if game_state_data:
                    # logging.debug(f"Fetched real game data: {game_state_data}") # Can be very verbose
                    # parsed_state = parse_game_state(game_state_data) # No longer needed here, fetch_game_state does it
                    logging.debug(f"MainWindow.get_game_state (real) returning: {type(game_state_data)}")
                    return game_state_data
                else:
                    logging.error("Failed to fetch real game state.")
                    logging.debug(f"MainWindow.get_game_state (real, fetch failed) returning: None")
                    return None
        except Exception as e:
            logging.exception("Exception in MainWindow.get_game_state")
            logging.debug(f"MainWindow.get_game_state (exception) returning: None")
            return None

    def closeEvent(self, event):
        logging.info("Close event triggered. Stopping keyboard listener.")
        if self.listener:
            self.listener.stop()
            self.listener.join() # Wait for listener thread to finish
            self.listener = None
            logging.info("Pynput keyboard listener stopped.")
        self.tts_manager.stop_speaking()
        self.tts_manager.cleanup() # Cleanup TTS resources
        
        # Stop timers
        self.vision_timer.stop()
        self.macro_timer.stop()
        logging.info("Timers stopped.")

        # Clean up screenshots (if this is desired, from legacy)
        try:
            # Path to screenshot_handler's screenshot directory if known, or a general one
            # This might need to be more robust if ScreenshotHandler manages its own dir.
            screenshot_output_dir = Path(getattr(self.screenshot_handler, 'SCREENSHOT_DIR', 'screenshots'))
            if screenshot_output_dir.exists():
                for file_item in screenshot_output_dir.iterdir():
                    if file_item.is_file() and file_item.name.endswith('.png'):
                        try:
                            file_item.unlink()
                            logging.debug(f"Deleted screenshot during cleanup: {file_item.name}")
                        except Exception as e:
                            logging.error(f"Error deleting screenshot {file_item.name} during cleanup: {e}")
        except Exception as e:
            logging.error(f"Error during screenshot cleanup: {e}")
            
        super().closeEvent(event)

    def customEvent(self, event):
        # Handle events posted by the pynput listener or screenshot_handler
        event_type = event.type()
        #if mock mode pass the mock image path
        if self.settings_tab.is_mock_mode():
            event.image_path = os.path.join(os.path.dirname(__file__), '../data/example_screenshots/20250519_142807_minimap.png')

        if event_type == EventType.BuildAgentTrigger:
            logging.debug("BuildAgentTrigger event received by MainWindow")
            self.event_handlers.trigger_build_agent_update()
        elif event_type == EventType.MacroAgentTrigger:
            logging.debug("MacroAgentTrigger event received by MainWindow")
            self.event_handlers.trigger_macro_agent_update()
        elif event_type == EventType.VisionAgentTrigger:
            logging.debug("VisionAgentTrigger event received by MainWindow")
            self.event_handlers.trigger_vision_agent_update()
        elif event_type == EventType.TTSStopTrigger:
            logging.debug("TTSStopTrigger event received by MainWindow")
            self.event_handlers.stop_tts()
        elif event_type == EventType.ScreenshotReady: # Make sure ScreenshotHandler posts this event
            logging.debug(f"ScreenshotReady event received for {event.agent_name}")
            if event.agent_name == "MacroAgent":
                self.macro_tab.update_with_game_state_and_image(event.image_path)
            elif event.agent_name == "VisionAgent":
                self.vision_tab.update_with_game_state_and_image(event.image_path)
        elif event_type == EventType.ScreenshotError: # Make sure ScreenshotHandler posts this event
            logging.error(f"ScreenshotError event received: {event.error_msg}")
            # Display this error appropriately, e.g., on the relevant tab's status label
            # For now, logging it. You might want to update status_label of the current tab or all tabs.
            # Example: self.macro_tab.status_label.setText(f"Screenshot error: {event.error_msg}")
            #          self.vision_tab.status_label.setText(f"Screenshot error: {event.error_msg}")
            # This requires knowing which tab was active or intended for the screenshot.
            # For simplicity, let's assume the error can be shown on a general status or logged.
            if self.macro_tab: # Check if tabs exist
                 self.macro_tab.status_label.setText(f"Screenshot error: {event.error_msg}")
            if self.vision_tab:
                 self.vision_tab.status_label.setText(f"Screenshot error: {event.error_msg}")

    def _delayed_greeting(self):
        # Show initial greeting
        # self.macro_tab.display_message("MacroAgent", "Hello! I'm the League of Legends Coach.")
        self.macro_tab.display_message("MacroAgent", "Hello!!")

def main():
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling) # Optional: for better HiDPI support
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()

# For standalone testing
if __name__ == "__main__":
    main()