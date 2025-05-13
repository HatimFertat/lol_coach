import logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
import os
import json
import time
import threading
from pathlib import Path
from datetime import datetime

# Remove Tkinter imports
from PySide6.QtCore import Qt, QSize, Signal, Slot, QEvent
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QTabWidget, 
                             QTextEdit, QLineEdit, QPushButton, QCheckBox,
                             QLabel, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QSplitter)
from PySide6.QtGui import QFont, QColor, QTextCursor, QTextCharFormat

from agents.build_agent import BuildAgent
from agents.macro_agent import MacroAgent
from game_context.game_state import parse_game_state
from game_context.game_state_fetcher import fetch_game_state
from vision.screenshot_listener import take_screenshot_and_crop
from vision.minimap_cropper import SCREENSHOT_DIR

from pynput import keyboard

MOCK = False

class AgentChatTab(QWidget):
    def __init__(self, agent, agent_name, get_game_state_func, auto_clear_var):
        super().__init__()
        self.agent = agent
        self.agent_name = agent_name
        self.get_game_state_func = get_game_state_func
        self.auto_clear = auto_clear_var
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Text area for chat display
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setFont(QFont("Courier New", 14))
        # Dark theme styling
        self.text_area.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #444;
                padding: 4px;
            }
        """)
        
        # Create user and agent text formats
        self.user_format = QTextCharFormat()
        self.user_format.setForeground(QColor("#a6e22e"))
        self.user_format.setFontWeight(QFont.Bold)
        
        self.agent_format = QTextCharFormat()
        self.agent_format.setForeground(QColor("#4fc1ff"))
        self.agent_format.setFontWeight(QFont.Bold)
        
        # Controls container
        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        
        # Input field
        self.entry = QLineEdit()
        
        # Buttons
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        
        self.update_button = QPushButton("Update")
        self.update_button.clicked.connect(self.update_with_game_state)
        
        self.reset_button = QPushButton("Clear")
        self.reset_button.clicked.connect(self.clear_conversation)
        
        # Add widgets to controls layout
        controls_layout.addWidget(self.entry, 1)  # 1 is the stretch factor
        controls_layout.addWidget(self.send_button)
        controls_layout.addWidget(self.update_button)
        controls_layout.addWidget(self.reset_button)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: orange;")
        
        # Add all components to main layout
        layout.addWidget(self.text_area)
        layout.addWidget(controls)
        layout.addWidget(self.status_label)
        
        # Set up event handling
        self.entry.returnPressed.connect(self.send_message)

    def display_message(self, sender, message):
        cursor = self.text_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # Use the appropriate format based on sender
        if sender == "You":
            cursor.insertText(f"{sender}: ", self.user_format)
            cursor.insertText(f"{message}\n")
        else:
            cursor.insertText(f"{sender}: ", self.agent_format)
            cursor.insertText(f"{message}\n")
        
        # Scroll to the bottom
        cursor.movePosition(QTextCursor.End)
        self.text_area.setTextCursor(cursor)

    def send_message(self):
        try:
            logging.debug(f"send_message called for {self.agent_name}")
            user_message = self.entry.text().strip()
            if not user_message:
                return
            self.status_label.setText("Processing...")
            self.display_message("You", user_message)
            self.entry.clear()
            
            # Process in background to keep UI responsive
            def process_message():
                response = self.agent.run(None, user_message)
                # Update UI on the main thread
                QApplication.instance().postEvent(self, _UpdateTextEvent(self.agent_name, response))
            
            threading.Thread(target=process_message, daemon=True).start()
        except Exception as e:
            logging.exception("Exception in send_message")
            self.status_label.setText("Error during processing")

    def update_with_game_state(self):
        try:
            self.status_label.setText("Fetching and processing game state...")
            if self.auto_clear and self.auto_clear.isChecked():
                self.agent.conversation_history = []
            logging.debug(f"update_with_game_state called for {self.agent_name}")
            user_message = self.entry.text().strip()
            self.entry.clear()
            
            # Process in background to keep UI responsive
            def process_game_state():
                game_state = self.get_game_state_func()
                prompt, response = self.agent.run(game_state, user_message)
                # Update UI on the main thread
                QApplication.instance().postEvent(self, _UpdateGameStateEvent(prompt, response))
            
            threading.Thread(target=process_game_state, daemon=True).start()
        except Exception as e:
            logging.exception("Exception in update_with_game_state")
            self.status_label.setText("Error during processing")

    def update_with_game_state_and_image(self, image_path=None):
        try:
            self.status_label.setText("Fetching and processing game state (with minimap)...")
            if self.auto_clear and self.auto_clear.isChecked():
                self.agent.conversation_history = []
            user_message = self.entry.text().strip()
            self.entry.clear()
            
            # Process in background to keep UI responsive
            def process_with_image():
                game_state = self.get_game_state_func()
                prompt, response = self.agent.run(game_state, user_message, image_path=image_path)
                # Update UI on the main thread
                QApplication.instance().postEvent(self, _UpdateGameStateEvent(prompt, response))
            
            threading.Thread(target=process_with_image, daemon=True).start()
        except Exception as e:
            logging.exception("Exception in update_with_game_state_and_image")
            self.status_label.setText("Error during processing")

    def clear_conversation(self):
        try:
            logging.debug(f"clear_conversation called for {self.agent_name}")
            self.agent.conversation_history = []
            self.text_area.clear()
        except Exception as e:
            logging.exception("Exception in clear_conversation")
    
    # Event handlers for thread-safe UI updates
    def customEvent(self, event):
        if event.type() == EventType.UpdateText:
            self.display_message(event.sender, event.message)
            self.status_label.setText("")
        elif event.type() == EventType.UpdateGameState:
            self.display_message("You", event.prompt)
            self.display_message(self.agent_name, event.response)
            self.status_label.setText("")

# Custom event types for thread-safe UI updates
# Define custom event types
class EventType:
    UpdateText = QEvent.Type(QEvent.registerEventType())
    UpdateGameState = QEvent.Type(QEvent.registerEventType())
    ScreenshotReady = QEvent.Type(QEvent.registerEventType())
    ScreenshotError = QEvent.Type(QEvent.registerEventType())

class _UpdateTextEvent(QEvent):
    def __init__(self, sender, message):
        super().__init__(EventType.UpdateText)
        self.sender = sender
        self.message = message

class _UpdateGameStateEvent(QEvent):
    def __init__(self, prompt, response):
        super().__init__(EventType.UpdateGameState)
        self.prompt = prompt
        self.response = response

class _ScreenshotReadyEvent(QEvent):
    def __init__(self, image_path):
        super().__init__(EventType.ScreenshotReady)
        self.image_path = image_path

class _ScreenshotErrorEvent(QEvent):
    def __init__(self, error_msg):
        super().__init__(EventType.ScreenshotError)
        self.error_msg = error_msg

class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # Keyboard shortcut settings
        shortcut_group = QWidget()
        shortcut_layout = QHBoxLayout(shortcut_group)
        
        shortcut_label = QLabel("Screenshot Shortcut:")
        self.shortcut_input = QLineEdit()
        self.shortcut_input.setPlaceholderText("Press keys...")
        self.shortcut_input.setReadOnly(True)
        self.shortcut_input.setFocusPolicy(Qt.StrongFocus)
        self.shortcut_input.installEventFilter(self)
        
        shortcut_layout.addWidget(shortcut_label)
        shortcut_layout.addWidget(self.shortcut_input)
        
        # Add a note about the shortcut
        note_label = QLabel("Note: Press the desired key combination to set the shortcut")
        note_label.setStyleSheet("color: #888; font-size: 10px;")
        
        layout.addWidget(shortcut_group)
        layout.addWidget(note_label)
        layout.addStretch()
        
        # Initialize with default shortcut
        self.current_shortcut = {keyboard.Key.shift, keyboard.Key.tab}
        self.update_shortcut_display()
    
    def eventFilter(self, obj, event):
        if obj == self.shortcut_input and event.type() == QEvent.KeyPress:
            key = event.key()
            modifiers = event.modifiers()
            
            # Convert Qt key to pynput key
            qt_to_pynput = {
                Qt.Key_Shift: keyboard.Key.shift,
                Qt.Key_Control: keyboard.Key.ctrl,
                Qt.Key_Alt: keyboard.Key.alt,
                Qt.Key_Meta: keyboard.Key.cmd,
                Qt.Key_Tab: keyboard.Key.tab,
                Qt.Key_Space: keyboard.Key.space,
            }
            
            # Get the pynput key if it exists
            pynput_key = qt_to_pynput.get(key)
            if pynput_key:
                self.current_shortcut = {pynput_key}
                if modifiers & Qt.ShiftModifier:
                    self.current_shortcut.add(keyboard.Key.shift)
                if modifiers & Qt.ControlModifier:
                    self.current_shortcut.add(keyboard.Key.ctrl)
                if modifiers & Qt.AltModifier:
                    self.current_shortcut.add(keyboard.Key.alt)
                if modifiers & Qt.MetaModifier:
                    self.current_shortcut.add(keyboard.Key.cmd)
                
                self.update_shortcut_display()
                return True
            
        return super().eventFilter(obj, event)
    
    def update_shortcut_display(self):
        key_names = []
        for key in self.current_shortcut:
            if hasattr(key, 'name'):
                key_names.append(key.name.capitalize())
            else:
                key_names.append(str(key))
        self.shortcut_input.setText(' + '.join(key_names))

class LoLCoachGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LoL Coach Agents")
        self.resize(800, 500)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        
        # Mode frame at top
        mode_frame = QWidget()
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(5, 2, 5, 2)
        
        # Add screenshot button
        # screenshot_button = QPushButton("Take Screenshot")
        # screenshot_button.clicked.connect(self._take_screenshot_and_process)
        # mode_layout.addWidget(screenshot_button)
        
        # Mock mode checkbox
        self.use_mock = QCheckBox("Use mock game state")
        self.use_mock.setChecked(MOCK)
        mode_layout.addWidget(self.use_mock)
        
        # Auto-clear checkbox
        self.auto_clear = QCheckBox("Auto-Reset after Update")
        self.auto_clear.setChecked(False)
        mode_layout.addStretch(1)  # Push auto-clear to the right
        mode_layout.addWidget(self.auto_clear)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        
        # Define the game state function
        def get_game_state():
            if self.use_mock.isChecked():
                with open(os.path.join(os.path.dirname(__file__), '../examples/example_game_state.json')) as f:
                    game_state_json = json.load(f)
                return parse_game_state(game_state_json)
            else:
                return fetch_game_state()
        
        # Create the agent tabs
        self.build_agent = BuildAgent()
        self.macro_agent = MacroAgent()
        
        self.macro_tab = AgentChatTab(self.macro_agent, "MacroAgent", get_game_state, self.auto_clear)
        self.build_tab = AgentChatTab(self.build_agent, "BuildAgent", get_game_state, self.auto_clear)
        self.settings_tab = SettingsTab()
        
        self.tab_widget.addTab(self.macro_tab, "Macro Agent")
        self.tab_widget.addTab(self.build_tab, "Build Agent")
        self.tab_widget.addTab(self.settings_tab, "Settings")
        
        # Add everything to the main layout
        main_layout.addWidget(mode_frame)
        main_layout.addWidget(self.tab_widget)
        
        # Initialize keyboard shortcut handling
        self.current_keys = set()
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            key = event.key()
            modifiers = event.modifiers()
            
            # Convert Qt key to pynput key
            qt_to_pynput = {
                Qt.Key_Shift: keyboard.Key.shift,
                Qt.Key_Control: keyboard.Key.ctrl,
                Qt.Key_Alt: keyboard.Key.alt,
                Qt.Key_Meta: keyboard.Key.cmd,
                Qt.Key_Tab: keyboard.Key.tab,
                Qt.Key_Space: keyboard.Key.space,
            }
            
            # Get the pynput key if it exists
            pynput_key = qt_to_pynput.get(key)
            if pynput_key:
                self.current_keys.add(pynput_key)
                if modifiers & Qt.ShiftModifier:
                    self.current_keys.add(keyboard.Key.shift)
                if modifiers & Qt.ControlModifier:
                    self.current_keys.add(keyboard.Key.ctrl)
                if modifiers & Qt.AltModifier:
                    self.current_keys.add(keyboard.Key.alt)
                if modifiers & Qt.MetaModifier:
                    self.current_keys.add(keyboard.Key.cmd)
                
                # Check if the current key combination matches the shortcut
                if self.current_keys == self.settings_tab.current_shortcut:
                    self._take_screenshot_and_process()
                    return True
        
        elif event.type() == QEvent.KeyRelease:
            key = event.key()
            modifiers = event.modifiers()
            
            # Convert Qt key to pynput key
            qt_to_pynput = {
                Qt.Key_Shift: keyboard.Key.shift,
                Qt.Key_Control: keyboard.Key.ctrl,
                Qt.Key_Alt: keyboard.Key.alt,
                Qt.Key_Meta: keyboard.Key.cmd,
                Qt.Key_Tab: keyboard.Key.tab,
                Qt.Key_Space: keyboard.Key.space,
            }
            
            # Get the pynput key if it exists
            pynput_key = qt_to_pynput.get(key)
            if pynput_key:
                self.current_keys.discard(pynput_key)
                if not (modifiers & Qt.ShiftModifier):
                    self.current_keys.discard(keyboard.Key.shift)
                if not (modifiers & Qt.ControlModifier):
                    self.current_keys.discard(keyboard.Key.ctrl)
                if not (modifiers & Qt.AltModifier):
                    self.current_keys.discard(keyboard.Key.alt)
                if not (modifiers & Qt.MetaModifier):
                    self.current_keys.discard(keyboard.Key.cmd)
        
        return super().eventFilter(obj, event)

    def _take_screenshot_and_process(self):
        """Safe version of screenshot processing that runs entirely on the main thread"""
        try:
            self.macro_tab.status_label.setText("Taking screenshot...")
            # Use threading to prevent UI freeze
            def process_screenshot():
                try:
                    logging.info("Taking screenshot...")
                    take_screenshot_and_crop()
                    
                    logging.info("Screenshot taken, finding most recent minimap image...")
                    # Find the most recent minimap image
                    minimaps = list(Path(SCREENSHOT_DIR).glob("*_minimap.png"))
                    if minimaps:
                        # Sort by timestamp in filename
                        minimaps.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                        minimap_path = str(minimaps[0])
                        
                        logging.info(f"Using most recent minimap: {minimap_path}")
                        # Update UI on main thread
                        QApplication.instance().postEvent(self, _ScreenshotReadyEvent(minimap_path))
                    else:
                        logging.info("No minimap images found.")
                        QApplication.instance().postEvent(self, _ScreenshotErrorEvent("No minimap images found"))
                except Exception as e:
                    logging.exception("Error in screenshot processing")
                    QApplication.instance().postEvent(self, _ScreenshotErrorEvent(str(e)[:50]))
            
            threading.Thread(target=process_screenshot, daemon=True).start()
        except Exception as e:
            logging.exception("Error starting screenshot process")
            self.macro_tab.status_label.setText(f"Screenshot error: {str(e)[:50]}")

    # Handle custom events
    def customEvent(self, event):
        if event.type() == EventType.ScreenshotReady:
            self.macro_tab.update_with_game_state_and_image(event.image_path)
        elif event.type() == EventType.ScreenshotError:
            self.macro_tab.status_label.setText(f"Screenshot error: {event.error_msg}")

# For standalone testing
if __name__ == "__main__":
    app = QApplication([])
    window = LoLCoachGUI()
    window.show()
    app.exec()