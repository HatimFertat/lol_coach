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
from agents.vision_agent import VisionAgent
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
    BuildAgentTrigger = QEvent.Type(QEvent.registerEventType())
    MacroAgentTrigger = QEvent.Type(QEvent.registerEventType())
    VisionAgentTrigger = QEvent.Type(QEvent.registerEventType())

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
        
        # Create shortcut settings for each action
        self.shortcut_settings = {}
        
        # Screenshot shortcut
        screenshot_group = self._create_shortcut_group("Screenshot Shortcut:")
        self.shortcut_settings['screenshot'] = {
            'input': screenshot_group['input'],
            'shortcut': {keyboard.Key.shift, keyboard.Key.tab}  # Default
        }
        layout.addWidget(screenshot_group['widget'])
        
        # Build Agent shortcut
        build_group = self._create_shortcut_group("Build Agent Shortcut (Ctrl+Alt+B):")
        self.shortcut_settings['build'] = {
            'input': build_group['input'],
            'shortcut': {keyboard.Key.ctrl, keyboard.Key.alt, keyboard.KeyCode.from_char('b')}  # Default
        }
        layout.addWidget(build_group['widget'])
        
        # Macro Agent shortcut
        macro_group = self._create_shortcut_group("Macro Agent Shortcut (Ctrl+Alt+M):")
        self.shortcut_settings['macro'] = {
            'input': macro_group['input'],
            'shortcut': {keyboard.Key.ctrl, keyboard.Key.alt, keyboard.KeyCode.from_char('m')}  # Default
        }
        layout.addWidget(macro_group['widget'])
        
        # Vision Agent shortcut
        vision_group = self._create_shortcut_group("Vision Agent Shortcut (Ctrl+Alt+V):")
        self.shortcut_settings['vision'] = {
            'input': vision_group['input'],
            'shortcut': {keyboard.Key.ctrl, keyboard.Key.alt, keyboard.KeyCode.from_char('v')}  # Default
        }
        layout.addWidget(vision_group['widget'])
        
        # Add a note about the shortcut
        note_label = QLabel("Note: Press the desired key combination to set the shortcut")
        note_label.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(note_label)
        layout.addStretch()
        
        # Update all shortcut displays
        self.update_all_shortcut_displays()
    
    def _create_shortcut_group(self, label_text):
        """Helper method to create a shortcut input group"""
        group = QWidget()
        group_layout = QHBoxLayout(group)
        
        label = QLabel(label_text)
        input_field = QLineEdit()
        input_field.setPlaceholderText("Press keys...")
        input_field.setReadOnly(True)
        input_field.setFocusPolicy(Qt.StrongFocus)
        input_field.installEventFilter(self)
        
        group_layout.addWidget(label)
        group_layout.addWidget(input_field)
        
        return {
            'widget': group,
            'input': input_field
        }
    
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
                # Find which shortcut input field triggered this
                for shortcut_type, settings in self.shortcut_settings.items():
                    if obj == settings['input']:
                        new_shortcut = {pynput_key}
                        if modifiers & Qt.ShiftModifier:
                            new_shortcut.add(keyboard.Key.shift)
                        if modifiers & Qt.ControlModifier:
                            new_shortcut.add(keyboard.Key.ctrl)
                        if modifiers & Qt.AltModifier:
                            new_shortcut.add(keyboard.Key.alt)
                        if modifiers & Qt.MetaModifier:
                            new_shortcut.add(keyboard.Key.cmd)
                        
                        settings['shortcut'] = new_shortcut
                        self.update_shortcut_display(settings['input'], new_shortcut)
                        return True
            
        return super().eventFilter(obj, event)
    
    def update_shortcut_display(self, input_field, shortcut):
        """Update the display for a single shortcut"""
        key_names = []
        for key in shortcut:
            if hasattr(key, 'name'):
                key_names.append(key.name.capitalize())
            elif hasattr(key, 'char'):
                key_names.append(key.char.upper())
            else:
                key_names.append(str(key))
        input_field.setText(' + '.join(key_names))
    
    def update_all_shortcut_displays(self):
        """Update all shortcut displays"""
        for settings in self.shortcut_settings.values():
            self.update_shortcut_display(settings['input'], settings['shortcut'])
    
    def get_shortcut(self, shortcut_type):
        """Get the current shortcut for a specific type"""
        return self.shortcut_settings[shortcut_type]['shortcut']

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
        self.vision_agent = VisionAgent()
        
        self.macro_tab = AgentChatTab(self.macro_agent, "MacroAgent", get_game_state, self.auto_clear)
        self.build_tab = AgentChatTab(self.build_agent, "BuildAgent", get_game_state, self.auto_clear)
        self.vision_tab = AgentChatTab(self.vision_agent, "VisionAgent", get_game_state, self.auto_clear)
        self.settings_tab = SettingsTab()
        
        self.tab_widget.addTab(self.macro_tab, "Macro Agent")
        self.tab_widget.addTab(self.build_tab, "Build Agent")
        self.tab_widget.addTab(self.vision_tab, "Vision Agent")
        self.tab_widget.addTab(self.settings_tab, "Settings")
        
        # Add everything to the main layout
        main_layout.addWidget(mode_frame)
        main_layout.addWidget(self.tab_widget)
        
        # Initialize keyboard listener
        self.current_keys = set()
        self.listener = None
        self.start_keyboard_listener()

    def start_keyboard_listener(self):
        def on_press(key):
            try:
                # Add the key to current keys
                self.current_keys.add(key)
                
                # Get all current shortcuts
                screenshot_shortcut = self.settings_tab.get_shortcut('screenshot')
                build_shortcut = self.settings_tab.get_shortcut('build')
                macro_shortcut = self.settings_tab.get_shortcut('macro')
                vision_shortcut = self.settings_tab.get_shortcut('vision')
                
                # Check if the current keys match any shortcut
                if self.current_keys == screenshot_shortcut or self.current_keys == macro_shortcut:
                    # Switch to macro tab first
                    self.tab_widget.setCurrentWidget(self.macro_tab)
                    # Then trigger the update
                    QApplication.instance().postEvent(self, QEvent(EventType.MacroAgentTrigger))
                elif self.current_keys == build_shortcut:
                    # Switch to build tab first
                    self.tab_widget.setCurrentWidget(self.build_tab)
                    # Then trigger the update
                    QApplication.instance().postEvent(self, QEvent(EventType.BuildAgentTrigger))
                elif self.current_keys == vision_shortcut:
                    # Switch to vision tab first
                    self.tab_widget.setCurrentWidget(self.vision_tab)
                    # Then trigger the update
                    QApplication.instance().postEvent(self, QEvent(EventType.VisionAgentTrigger))
            except Exception as e:
                logging.exception("Error in keyboard listener on_press")

        def on_release(key):
            try:
                # Remove the released key from current keys
                self.current_keys.discard(key)
            except Exception as e:
                logging.exception("Error in keyboard listener on_release")

        # Start the listener in non-blocking mode
        self.listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self.listener.start()

    def closeEvent(self, event):
        # Stop the keyboard listener when the window is closed
        if self.listener:
            self.listener.stop()
        super().closeEvent(event)

    def customEvent(self, event):
        if event.type() == EventType.ScreenshotReady:
            self.macro_tab.update_with_game_state_and_image(event.image_path)
            self.vision_tab.update_with_game_state_and_image(event.image_path)
        elif event.type() == EventType.ScreenshotError:
            self.macro_tab.status_label.setText(f"Screenshot error: {event.error_msg}")
            self.vision_tab.status_label.setText(f"Screenshot error: {event.error_msg}")
        elif event.type() == EventType.BuildAgentTrigger:
            # Trigger build agent update
            self.build_tab.update_with_game_state()
        elif event.type() == EventType.MacroAgentTrigger:
            # Try to take a new screenshot and process it
            self._trigger_macro_agent_update()
        elif event.type() == EventType.VisionAgentTrigger:
            # Try to take a new screenshot and process it
            self._trigger_vision_agent_update()

    def _trigger_macro_agent_update(self):
        """Triggers macro agent update with a new screenshot or falls back to existing one"""
        try:
            self.macro_tab.status_label.setText("Taking screenshot...")
            # Use threading to prevent UI freeze
            def process_screenshot():
                try:
                    logging.info("Taking screenshot...")
                    minimap_path = take_screenshot_and_crop()
                    
                    if minimap_path:
                        logging.info(f"Using minimap: {minimap_path}")
                        # Update UI on main thread
                        QApplication.instance().postEvent(self, _ScreenshotReadyEvent(minimap_path))
                    else:
                        logging.info("No valid minimap found. Using regular update")
                        # Fall back to regular update if no screenshot is available
                        self.macro_tab.update_with_game_state()
                except Exception as e:
                    logging.exception("Error in screenshot processing")
                    QApplication.instance().postEvent(self, _ScreenshotErrorEvent(str(e)[:50]))
            
            threading.Thread(target=process_screenshot, daemon=True).start()
        except Exception as e:
            logging.exception("Error starting screenshot process")
            self.macro_tab.status_label.setText(f"Screenshot error: {str(e)[:50]}")

    def _trigger_vision_agent_update(self):
        """Triggers vision agent update with a new screenshot"""
        try:
            self.vision_tab.status_label.setText("Taking screenshot...")
            # Use threading to prevent UI freeze
            def process_screenshot():
                try:
                    logging.info("Taking screenshot...")
                    minimap_path = take_screenshot_and_crop()
                    
                    if minimap_path:
                        logging.info(f"Using minimap: {minimap_path}")
                        # Update UI on main thread
                        QApplication.instance().postEvent(self, _ScreenshotReadyEvent(minimap_path))
                    else:
                        logging.info("No valid minimap found. Using regular update")
                        # Fall back to regular update if no screenshot is available
                        self.vision_tab.update_with_game_state()
                except Exception as e:
                    logging.exception("Error in screenshot processing")
                    QApplication.instance().postEvent(self, _ScreenshotErrorEvent(str(e)[:50]))
            
            threading.Thread(target=process_screenshot, daemon=True).start()
        except Exception as e:
            logging.exception("Error starting screenshot process")
            self.vision_tab.status_label.setText(f"Screenshot error: {str(e)[:50]}")

# For standalone testing
if __name__ == "__main__":
    app = QApplication([])
    window = LoLCoachGUI()
    window.show()
    app.exec()