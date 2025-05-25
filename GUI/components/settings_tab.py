import logging
import json
import os
from pathlib import Path
from PySide6.QtCore import Qt, QEvent, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QSpinBox, QGroupBox, QCheckBox, QPushButton,
                             QComboBox)
from PySide6.QtGui import QIntValidator
from agents.modelnames import get_available_models
from utils.tts_manager import TTSManager

class SettingsTab(QWidget):
    # Signal to notify when mock mode changes
    mock_mode_changed = Signal(bool)
    # Signal to notify when timer intervals change
    vision_interval_changed = Signal(int)
    macro_interval_changed = Signal(int)
    # Signal to notify when model changes
    model_changed = Signal(str)
    # Signal to notify when TTS settings change
    tts_settings_changed = Signal(dict)
    
    # Default settings
    DEFAULT_SHORTCUTS = {
        "build_agent": "Ctrl+Alt+B",
        "macro_agent": "Ctrl+Alt+M",
        "vision_agent": "Ctrl+Alt+V",
        "tts_stop": "Ctrl+Alt+L",
        "push_to_talk": "Ctrl+Alt+T"  # Changed to T for Toggle
    }
    DEFAULT_VISION_INTERVAL = 5
    DEFAULT_MACRO_INTERVAL = 60
    DEFAULT_USE_MOCK = False
    DEFAULT_AUTO_CLEAR = False
    DEFAULT_MODEL = "gemini"  # Default to Gemini if available
    DEFAULT_TTS = {
        "engine": "kokoro",
        "voice": "af_sarah",
        "speed": 1.0,
        "language": "en-us"
    }
    
    def __init__(self):
        super().__init__()
        self.settings_file = Path("settings.json")
        self.shortcuts = self.DEFAULT_SHORTCUTS.copy()
        self.vision_interval = self.DEFAULT_VISION_INTERVAL
        self.macro_interval = self.DEFAULT_MACRO_INTERVAL
        self.use_mock = self.DEFAULT_USE_MOCK
        self.selected_model = self.DEFAULT_MODEL
        self.tts_settings = self.DEFAULT_TTS.copy()
        
        self._load_settings()
        self._setup_ui()
        self._setup_event_handling()

    def _load_settings(self):
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    data = json.load(f)
                    self.shortcuts = data.get('shortcuts', self.shortcuts)
                    self.vision_interval = data.get('vision_interval', 5)
                    self.macro_interval = data.get('macro_interval', 60)
                    self.use_mock = data.get('use_mock', False)
                    self.selected_model = data.get('selected_model', self.DEFAULT_MODEL)
                    self.tts_settings = data.get('tts', self.DEFAULT_TTS)
            except Exception as e:
                print(f"Error loading settings: {e}")

    def _save_settings(self):
        try:
            with open(self.settings_file, 'w') as f:
                json.dump({
                    'shortcuts': self.shortcuts,
                    'vision_interval': self.vision_interval,
                    'macro_interval': self.macro_interval,
                    'use_mock': self.use_mock,
                    'auto_clear': self.auto_clear.isChecked(),
                    'selected_model': self.selected_model,
                    'tts': self.tts_settings
                }, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Model selection settings
        model_group = QGroupBox("LLM Settings")
        model_layout = QHBoxLayout()
        
        model_label = QLabel("Select Model:")
        self.model_selector = QComboBox()
        self._update_model_selector()
        self.model_selector.currentTextChanged.connect(self._on_model_changed)
        
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_selector)
        model_group.setLayout(model_layout)
        
        # TTS settings
        tts_group = QGroupBox("TTS Settings")
        tts_layout = QVBoxLayout()
        
        # Engine selection
        engine_layout = QHBoxLayout()
        engine_label = QLabel("TTS Engine:")
        self.engine_selector = QComboBox()
        self.engine_selector.addItems(["kokoro", "openai"])
        self.engine_selector.setCurrentText(self.tts_settings["engine"])
        self.engine_selector.currentTextChanged.connect(self._on_tts_engine_changed)
        
        engine_layout.addWidget(engine_label)
        engine_layout.addWidget(self.engine_selector)
        tts_layout.addLayout(engine_layout)
        
        # Voice selection
        voice_layout = QHBoxLayout()
        voice_label = QLabel("Voice:")
        self.voice_selector = QComboBox()
        self._update_voice_selector()
        self.voice_selector.currentTextChanged.connect(self._on_tts_voice_changed)
        
        voice_layout.addWidget(voice_label)
        voice_layout.addWidget(self.voice_selector)
        tts_layout.addLayout(voice_layout)
        
        # Speed setting
        speed_layout = QHBoxLayout()
        speed_label = QLabel("Speed:")
        self.speed_input = QSpinBox()
        self.speed_input.setRange(50, 200)  # 0.5x to 2.0x speed
        self.speed_input.setValue(int(self.tts_settings["speed"] * 100))
        self.speed_input.setSuffix("%")
        self.speed_input.valueChanged.connect(self._on_tts_speed_changed)
        
        speed_layout.addWidget(speed_label)
        speed_layout.addWidget(self.speed_input)
        tts_layout.addLayout(speed_layout)
        
        tts_group.setLayout(tts_layout)
        
        # Mock mode settings
        mock_group = QGroupBox("Game State Settings")
        mock_layout = QHBoxLayout()
        
        self.mock_checkbox = QCheckBox("Use Mock Game State")
        self.mock_checkbox.setChecked(self.use_mock)
        self.mock_checkbox.stateChanged.connect(self._on_mock_mode_changed)
        
        mock_layout.addWidget(self.mock_checkbox)
        mock_group.setLayout(mock_layout)
        
        # Vision interval settings
        vision_group = QGroupBox("Vision Settings")
        vision_layout = QHBoxLayout()
        
        vision_label = QLabel("Vision Update Interval (seconds):")
        self.vision_interval_input = QSpinBox()
        self.vision_interval_input.setRange(0, 3600)  # Allow 0 to disable, up to 1 hour
        self.vision_interval_input.setValue(self.vision_interval)
        self.vision_interval_input.valueChanged.connect(self._on_vision_interval_changed)
        
        vision_layout.addWidget(vision_label)
        vision_layout.addWidget(self.vision_interval_input)
        vision_group.setLayout(vision_layout)
        
        # Macro interval settings
        macro_group = QGroupBox("Macro Settings")
        macro_layout = QHBoxLayout()
        
        macro_label = QLabel("Macro Update Interval (seconds):")
        self.macro_interval_input = QSpinBox()
        self.macro_interval_input.setRange(0, 3600)  # Allow 0 to disable, up to 1 hour
        self.macro_interval_input.setValue(self.macro_interval)
        self.macro_interval_input.valueChanged.connect(self._on_macro_interval_changed)
        
        macro_layout.addWidget(macro_label)
        macro_layout.addWidget(self.macro_interval_input)
        macro_group.setLayout(macro_layout)
        
        # Auto-clear settings
        auto_clear_group = QGroupBox("Chat Settings")
        auto_clear_layout = QHBoxLayout()
        
        self.auto_clear = QCheckBox("Auto-Reset after Update")
        self.auto_clear.setChecked(False)
        self.auto_clear.stateChanged.connect(self._save_settings)
        
        auto_clear_layout.addWidget(self.auto_clear)
        auto_clear_group.setLayout(auto_clear_layout)
        
        # Shortcut settings
        shortcut_group = QGroupBox("Keyboard Shortcuts")
        shortcut_layout = QVBoxLayout()
        
        # Create shortcut input fields
        self.shortcut_inputs = {}
        for shortcut_type in ["build_agent", "macro_agent", "vision_agent", "tts_stop", "push_to_talk"]:
            group = self._create_shortcut_group(shortcut_type)
            shortcut_layout.addWidget(group)
        
        shortcut_group.setLayout(shortcut_layout)
        
        # Add all groups to main layout
        layout.addWidget(model_group)
        layout.addWidget(tts_group)
        layout.addWidget(mock_group)
        layout.addWidget(vision_group)
        layout.addWidget(macro_group)
        layout.addWidget(auto_clear_group)
        layout.addWidget(shortcut_group)
        
        # Reset Settings button
        reset_button = QPushButton("Reset All Settings to Default")
        reset_button.clicked.connect(self.reset_to_defaults)
        layout.addWidget(reset_button)
        
        layout.addStretch()

    def _setup_event_handling(self):
        # Install event filter on all shortcut input fields
        for input_field in self.shortcut_inputs.values():
            input_field.installEventFilter(self)

    def _on_mock_mode_changed(self, state):
        self.use_mock = bool(state)
        self._save_settings()
        self.mock_mode_changed.emit(self.use_mock)

    def _on_vision_interval_changed(self):
        self.vision_interval = self.vision_interval_input.value()
        logging.debug(f"Vision interval changed to {self.vision_interval}")
        self._save_settings()
        # Emit signal to notify MainWindow that interval has changed
        self.vision_interval_changed.emit(self.vision_interval)

    def _on_macro_interval_changed(self):
        self.macro_interval = self.macro_interval_input.value()
        logging.debug(f"Macro interval changed to {self.macro_interval}")
        self._save_settings()
        # Emit signal to notify MainWindow that interval has changed
        self.macro_interval_changed.emit(self.macro_interval)

    def _create_shortcut_group(self, label_text):
        group = QWidget()
        layout = QHBoxLayout()
        
        # Customize label text for better readability
        display_text = label_text.replace('_', ' ').title()
        if label_text == "push_to_talk":
            display_text = "Speech-to-Text Toggle"
        
        label = QLabel(f"{display_text}:")
        input_field = QLineEdit()
        input_field.setReadOnly(True)
        input_field.setPlaceholderText("Click and press keys to set shortcut")
        
        # Add clear button
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(lambda: self._clear_shortcut(label_text, input_field))
        
        # Store the input field reference
        self.shortcut_inputs[label_text] = input_field
        
        # Set initial value if exists
        if label_text in self.shortcuts:
            input_field.setText(self.shortcuts[label_text])
        
        layout.addWidget(label)
        layout.addWidget(input_field)
        layout.addWidget(clear_button)
        group.setLayout(layout)
        
        return group

    def _clear_shortcut(self, shortcut_type, input_field):
        """Clear the shortcut for the given type"""
        input_field.clear()
        if shortcut_type in self.shortcuts:
            del self.shortcuts[shortcut_type]
        self._save_settings()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and obj in self.shortcut_inputs.values():
            try:
                # Get the shortcut type from the input field
                shortcut_type = next(k for k, v in self.shortcut_inputs.items() if v == obj)
                
                # Get the key combination
                key = event.key()
                modifiers = event.modifiers()
                
                # List of keys to ignore when pressed alone
                ignore_standalone_keys = (
                    Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta,
                    Qt.Key_CapsLock, Qt.Key_NumLock, Qt.Key_ScrollLock,
                    Qt.Key_Super_L, Qt.Key_Super_R, Qt.Key_Menu,
                    Qt.Key_AltGr, Qt.Key_Meta
                )
                
                # Ignore standalone modifier keys and lock keys
                if key in ignore_standalone_keys:
                    return True
                
                # Special handling for Tab key to prevent window focus issues
                if key == Qt.Key_Tab:
                    event.accept()
                
                # Convert to string representation
                shortcut = self._key_to_string(key, modifiers)
                if shortcut:
                    # Update the input field and store the shortcut
                    obj.setText(shortcut)
                    self.shortcuts[shortcut_type] = shortcut
                    self._save_settings()
                    # Clear focus to prevent further key events
                    obj.clearFocus()
                
                # Always consume the key press event
                return True
            except Exception as e:
                logging.error(f"Error in keyboard shortcut handling: {e}")
                return True
        
        return super().eventFilter(obj, event)

    def _key_to_string(self, key, modifiers):
        try:
            # Convert Qt key and modifiers to string representation
            key_str = []
            
            # Add modifier keys in a consistent order
            if modifiers & Qt.ControlModifier:
                key_str.append("Ctrl")
            if modifiers & Qt.AltModifier:
                key_str.append("Alt")
            if modifiers & Qt.ShiftModifier:
                key_str.append("Shift")
            if modifiers & Qt.MetaModifier:
                key_str.append("Meta")
            
            # Add the main key
            main_key = None
            
            # Handle special keys first
            special_keys = {
                Qt.Key_Tab: "Tab",
                Qt.Key_Space: "Space",
                Qt.Key_Return: "Enter",
                Qt.Key_Enter: "Enter",
                Qt.Key_Escape: "Esc",
                Qt.Key_Backspace: "Backspace",
                Qt.Key_Delete: "Delete",
                Qt.Key_Home: "Home",
                Qt.Key_End: "End",
                Qt.Key_PageUp: "PgUp",
                Qt.Key_PageDown: "PgDn",
                Qt.Key_Insert: "Insert",
                Qt.Key_Up: "Up",
                Qt.Key_Down: "Down",
                Qt.Key_Left: "Left",
                Qt.Key_Right: "Right",
                Qt.Key_CapsLock: "CapsLock",
                Qt.Key_NumLock: "NumLock",
                Qt.Key_ScrollLock: "ScrollLock",
                Qt.Key_Pause: "Pause",
                Qt.Key_Print: "PrintScreen",
                Qt.Key_Help: "Help",
                Qt.Key_Menu: "Menu",
                Qt.Key_VolumeDown: "VolumeDown",
                Qt.Key_VolumeMute: "VolumeMute",
                Qt.Key_VolumeUp: "VolumeUp",
                Qt.Key_MediaPlay: "MediaPlay",
                Qt.Key_MediaStop: "MediaStop",
                Qt.Key_MediaPrevious: "MediaPrevious",
                Qt.Key_MediaNext: "MediaNext",
            }
            
            if key in special_keys:
                main_key = special_keys[key]
            # Handle F1-F12 keys
            elif Qt.Key_F1 <= key <= Qt.Key_F12:
                main_key = f"F{key - Qt.Key_F1 + 1}"
            # Handle letter keys
            elif Qt.Key_A <= key <= Qt.Key_Z:
                main_key = chr(key)
            # Handle number keys
            elif Qt.Key_0 <= key <= Qt.Key_9:
                main_key = str(key - Qt.Key_0)
            # Handle numpad keys
            elif Qt.Key_0 <= key <= Qt.Key_9:
                main_key = f"Num{key - Qt.Key_0}"
            
            # Only return a shortcut if we have a valid main key and at least one modifier
            # (except for function keys and special keys which can be used alone)
            if main_key:
                if (len(key_str) > 0 or 
                    main_key.startswith('F') or 
                    main_key in ['Esc', 'PrintScreen', 'Pause', 'Insert', 'Delete']):
                    key_str.append(main_key)
                    return "+".join(key_str)
            
            return None
        except Exception as e:
            logging.error(f"Error converting key to string: {e}")
            return None

    def update_shortcut_display(self, input_field, shortcut):
        input_field.setText(shortcut)

    def update_all_shortcut_displays(self):
        for shortcut_type, input_field in self.shortcut_inputs.items():
            if shortcut_type in self.shortcuts:
                self.update_shortcut_display(input_field, self.shortcuts[shortcut_type])

    def get_shortcut(self, shortcut_type):
        return self.shortcuts.get(shortcut_type)

    def get_vision_interval(self) -> int:
        return self.vision_interval

    def get_macro_interval(self) -> int:
        return self.macro_interval

    def is_mock_mode(self) -> bool:
        return self.use_mock 

    def reset_to_defaults(self):
        """Reset all settings to their default values"""
        # Store original values to check for changes
        old_vision_interval = self.vision_interval
        old_macro_interval = self.macro_interval
        old_use_mock = self.use_mock
        
        # Update internal values
        self.shortcuts = self.DEFAULT_SHORTCUTS.copy()
        self.vision_interval = self.DEFAULT_VISION_INTERVAL
        self.macro_interval = self.DEFAULT_MACRO_INTERVAL
        self.use_mock = self.DEFAULT_USE_MOCK
        self.selected_model = self.DEFAULT_MODEL
        self.tts_settings = self.DEFAULT_TTS.copy()
        
        # Update UI to reflect defaults
        self.mock_checkbox.setChecked(self.DEFAULT_USE_MOCK)
        self.vision_interval_input.setValue(self.DEFAULT_VISION_INTERVAL)
        self.macro_interval_input.setValue(self.DEFAULT_MACRO_INTERVAL)
        self.auto_clear.setChecked(self.DEFAULT_AUTO_CLEAR)
        
        # Update shortcut displays
        for shortcut_type, shortcut in self.DEFAULT_SHORTCUTS.items():
            if shortcut_type in self.shortcut_inputs:
                self.shortcut_inputs[shortcut_type].setText(shortcut)
        
        # Save the defaults to the settings file
        self._save_settings()
        
        # Emit signals for all changes
        if old_use_mock != self.DEFAULT_USE_MOCK:
            self.mock_mode_changed.emit(self.DEFAULT_USE_MOCK)
            
        if old_vision_interval != self.DEFAULT_VISION_INTERVAL:
            self.vision_interval_changed.emit(self.DEFAULT_VISION_INTERVAL)
            
        if old_macro_interval != self.DEFAULT_MACRO_INTERVAL:
            self.macro_interval_changed.emit(self.DEFAULT_MACRO_INTERVAL)
            
        logging.info("All settings reset to defaults")

    def _update_model_selector(self):
        """Update the model selector with available models."""
        self.model_selector.clear()
        available_models = get_available_models()
        if not available_models:
            self.model_selector.addItem("No models available")
            self.model_selector.setEnabled(False)
            return
            
        self.model_selector.setEnabled(True)
        for name, config in available_models.items():
            self.model_selector.addItem(config.name, name)
            
        # Set the current selection
        index = self.model_selector.findData(self.selected_model)
        if index >= 0:
            self.model_selector.setCurrentIndex(index)

    def _on_model_changed(self, model_name: str):
        """Handle model selection change."""
        index = self.model_selector.currentIndex()
        if index >= 0:
            self.selected_model = self.model_selector.currentData()
            self._save_settings()
            self.model_changed.emit(self.selected_model)

    def get_selected_model(self) -> str:
        """Returns the currently selected model name."""
        return self.selected_model 

    def _update_voice_selector(self):
        """Update the voice selector based on the current TTS engine"""
        self.voice_selector.clear()
        if self.tts_settings["engine"] == "kokoro":
            voices = TTSManager.KOKORO_VOICES
        else:
            voices = TTSManager.OPENAI_VOICES

        self.voice_selector.addItems(voices)
        
        # Set current voice if it exists in the new list
        current_voice = self.tts_settings["voice"]
        index = self.voice_selector.findText(current_voice)
        if index >= 0:
            self.voice_selector.setCurrentIndex(index)
        else:
            # If current voice not available, use first available voice
            self.tts_settings["voice"] = voices[0]
            self.voice_selector.setCurrentIndex(0)

    def _on_tts_engine_changed(self, engine: str):
        """Handle TTS engine change"""
        self.tts_settings["engine"] = engine
        self._update_voice_selector()
        self._save_settings()
        self.tts_settings_changed.emit(self.tts_settings)

    def _on_tts_voice_changed(self, voice: str):
        """Handle TTS voice change"""
        self.tts_settings["voice"] = voice
        self._save_settings()
        self.tts_settings_changed.emit(self.tts_settings)

    def _on_tts_speed_changed(self, speed: int):
        """Handle TTS speed change"""
        self.tts_settings["speed"] = speed / 100.0  # Convert percentage to decimal
        self._save_settings()
        self.tts_settings_changed.emit(self.tts_settings)

    def get_tts_settings(self) -> dict:
        """Get current TTS settings"""
        return self.tts_settings.copy() 