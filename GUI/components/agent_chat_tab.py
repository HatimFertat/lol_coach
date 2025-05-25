import logging
import os
import threading
import tempfile
import pyaudio
import wave
from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtWidgets import (QWidget, QTextEdit, QLineEdit, QPushButton,
                             QLabel, QVBoxLayout, QHBoxLayout, QApplication)
from PySide6.QtGui import QFont, QColor, QTextCursor, QTextCharFormat, QIcon
from google.genai import types
from google import genai
from dotenv import load_dotenv

load_dotenv()

from GUI.events.custom_events import EventType, _UpdateTextEvent, _UpdateGameStateEvent

class AgentChatTab(QWidget):
    def __init__(self, agent, agent_name, get_game_state_func, auto_clear_var, tts_manager):
        super().__init__()
        self.agent = agent
        self.agent_name = agent_name
        self.get_game_state_func = get_game_state_func
        self.auto_clear = auto_clear_var
        self.tts_manager = tts_manager
        
        # Initialize audio recording variables
        self.is_recording = False
        self.audio = None  # Initialize PyAudio only when needed
        self.frames = []
        self.stream = None
        self.recording_thread = None
        
        # Initialize Google AI
        self.client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
        
        self._setup_ui()
        self._setup_event_handling()

    def _setup_ui(self):
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
        
        self.mic_button = QPushButton("🎤")
        self.mic_button.setFixedWidth(40)
        self.mic_button.clicked.connect(self.toggle_recording)
        self.mic_button.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
            QPushButton:pressed {
                background-color: #1d1d1d;
            }
        """)
        
        self.update_button = QPushButton("Update")
        self.update_button.clicked.connect(self._on_update_button_clicked)
        
        self.reset_button = QPushButton("Clear")
        self.reset_button.clicked.connect(self.clear_conversation)
        
        # Add widgets to controls layout
        controls_layout.addWidget(self.entry, 1)  # 1 is the stretch factor
        controls_layout.addWidget(self.mic_button)
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

    def _setup_event_handling(self):
        self.entry.returnPressed.connect(self.send_message)
        
    def _on_update_button_clicked(self):
        """
        Button click handler for the "Update" button.
        For all agents, this will trigger an update with game state but WITHOUT screenshots.
        This is in contrast to keyboard shortcuts and timer triggers which use screenshots
        for macro and vision agents.
        """
        logging.debug(f"{self.agent_name}: Update button clicked - requesting update without screenshot")
        # Always update without a screenshot when button is clicked
        self.update_with_game_state(None)

    def display_message(self, sender, message, curated_message=None):
        cursor = self.text_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # Use the appropriate format based on sender
        if sender == "You":
            cursor.insertText(f"{sender}: ", self.user_format)
            cursor.insertText(f"{message}\n")
        else:
            cursor.insertText(f"{sender}: ", self.agent_format)
            cursor.insertText(f"{message}\n")
            
            # Speak only the curated message if available, otherwise use the full message
            message_to_speak = curated_message or message
            if message_to_speak: # Ensure message_to_speak is not None or empty
                # Speak the message with priority based on agent type
                priority = 0 if self.agent_name == "VisionAgent" else 1
                self.tts_manager.speak(message_to_speak, priority)
        
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
                prompt, response, curated_response = self.agent.run(None, user_message)
                # Update UI on the main thread
                QApplication.instance().postEvent(self, _UpdateTextEvent(self.agent_name, response, curated_response))
            
            threading.Thread(target=process_message, daemon=True).start()
        except Exception as e:
            logging.exception("Exception in send_message")
            self.status_label.setText("Error during processing")

    def update_with_game_state(self, game_state=None):
        try:
            self.status_label.setText("Fetching and processing game state...")
            if self.auto_clear and self.auto_clear.isChecked():
                self.agent.conversation_history = []
            logging.debug(f"update_with_game_state called for {self.agent_name}")
            user_message = self.entry.text().strip()
            self.entry.clear()
            
            # Process in background to keep UI responsive
            def process_game_state():
                # Use provided game_state or fetch if None
                current_game_state = game_state
                if current_game_state is None:
                    logging.debug(f"AgentChatTab ({self.agent_name}): game_state is None, calling get_game_state_func.")                    
                    current_game_state = self.get_game_state_func()
  
                prompt, response, curated_response = self.agent.run(current_game_state, user_message)
                # Update UI on the main thread
                QApplication.instance().postEvent(self, _UpdateGameStateEvent(prompt, response, curated_response))
            
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
                try:
                    game_state = self.get_game_state_func()
                        
                    prompt, response, curated_response = self.agent.run(game_state, user_message, image_path=image_path)
                    # Update UI on the main thread
                    QApplication.instance().postEvent(self, _UpdateGameStateEvent(prompt, response, curated_response))
                    # Delete the screenshot after the agent has finished processing it
                    if image_path and os.path.exists(image_path):
                        try:
                            os.remove(image_path)
                            logging.debug(f"Deleted screenshot after processing: {image_path}")
                        except Exception as e:
                            logging.error(f"Error deleting screenshot {image_path}: {e}")
                except Exception as e:
                    logging.exception("Error in process_with_image")
                    self.status_label.setText("Error during processing")
            
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
            self.display_message(event.sender, event.message, event.curated_message)
            self.status_label.setText("")
        elif event.type() == EventType.UpdateGameState:
            self.display_message("You", event.prompt)
            self.display_message(self.agent_name, event.response, event.curated_response)
            self.status_label.setText("")
        elif event.type() == EventType.PushToTalkTrigger:
            # Toggle recording state
            if not self.is_recording:
                self.start_recording()
            else:
                self.stop_recording()

    def toggle_recording(self):
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        if self.is_recording:  # Prevent starting if already recording
            return
        logging.debug(f"start_recording called for {self.agent_name}")
        
        # Initialize PyAudio if not already initialized
        if not self.audio:
            self.audio = pyaudio.PyAudio()
        
        self.is_recording = True
        self.frames = []
        self.mic_button.setText("⏺")
        self.mic_button.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                border: 1px solid #ff6666;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #ff6666;
            }
            QPushButton:pressed {
                background-color: #ff2222;
            }
        """)
        self.status_label.setText("Recording...")
        
        # Initialize audio stream
        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=44100,
                input=True,
                frames_per_buffer=1024
            )
            
            # Start recording in a separate thread
            self.recording_thread = threading.Thread(target=self._record_audio, daemon=True)
            self.recording_thread.start()
        except Exception as e:
            logging.error(f"Error starting audio recording: {e}")
            self.cleanup_audio()
            self.status_label.setText("Error starting recording")

    def _record_audio(self):
        while self.is_recording:
            try:
                data = self.stream.read(1024)
                self.frames.append(data)
            except Exception as e:
                logging.error(f"Error recording audio: {e}")
                self.stop_recording()
                break

    def stop_recording(self):
        if not self.is_recording:  # Prevent stopping if not recording
            return
            
        self.is_recording = False
        self.mic_button.setText("🎤")
        self.mic_button.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
            QPushButton:pressed {
                background-color: #1d1d1d;
            }
        """)
        self.status_label.setText("Processing speech...")
        
        # Wait for recording thread to finish
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=1.0)  # Wait up to 1 second
        
        # Cleanup audio resources
        self.cleanup_audio()
        
        # Process the recorded audio in a new thread
        processing_thread = threading.Thread(target=self._process_audio, daemon=True)
        processing_thread.start()

    def cleanup_audio(self):
        """Clean up audio resources."""
        try:
            if self.stream:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except Exception as e:
                    logging.error(f"Error closing audio stream: {e}")
                self.stream = None
            
            if self.audio:
                try:
                    self.audio.terminate()
                except Exception as e:
                    logging.error(f"Error terminating PyAudio: {e}")
                self.audio = None
        except Exception as e:
            logging.error(f"Error in cleanup_audio: {e}")

    def closeEvent(self, event):
        """Handle cleanup when the tab is closed."""
        try:
            if self.is_recording:
                self.stop_recording()
            self.cleanup_audio()
        except Exception as e:
            logging.error(f"Error in closeEvent: {e}")
        super().closeEvent(event)

    def _process_audio(self):
        if not self.frames:  # No audio data to process
            self.status_label.setText("No audio recorded")
            return
            
        temp_file = None
        try:
            # Create temporary file for audio
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            
            # Save audio to WAV file
            with wave.open(temp_file.name, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # Using constant value since we know it's paInt16
                wf.setframerate(44100)
                wf.writeframes(b''.join(self.frames))
            
            # Clear frames to free memory
            self.frames = []
            
            # Upload file to Gemini
            myfile = self.client.files.upload(file=temp_file.name)
            prompt = "Please transcribe the following audio exactly as spoken, without interpretation or summarization, even if it is a question."
            
            # Generate transcript
            response = self.client.models.generate_content(
                model='gemini-2.0-flash',
                contents=[prompt, myfile]
            )
            
            # Update UI with transcribed text and send message
            if response and hasattr(response, 'text'):
                transcribed_text = response.text.strip()
                if transcribed_text:
                    logging.info(f"Transcribed text: {transcribed_text}")
                    # Use QTimer to ensure UI updates happen on the main thread
                    QApplication.instance().postEvent(self, _UpdateTextEvent("You", transcribed_text))
                    # Process the message in a background thread
                    threading.Thread(target=lambda: self._process_transcribed_message(transcribed_text), daemon=True).start()
                else:
                    logging.warning("No text in transcription response")
                    self.status_label.setText("No speech detected")
            else:
                logging.warning("Invalid response from Gemini")
                self.status_label.setText("Error processing speech")
                
        except Exception as e:
            logging.error(f"Error processing audio: {e}")
            self.status_label.setText("Error processing speech")
        finally:
            # Clean up temporary file
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except Exception as e:
                    logging.error(f"Error deleting temporary file: {e}")
            self.status_label.setText("")  # Clear status if successful

    def _process_transcribed_message(self, text):
        """Process the transcribed message in a background thread."""
        try:
            logging.info(f"Processing transcribed message: {text}")
            self.status_label.setText("Processing...")
            
            # Get the response from the agent
            prompt, response, curated_response = self.agent.run(None, text)
            
            # Update UI on the main thread
            QApplication.instance().postEvent(self, _UpdateTextEvent(self.agent_name, response, curated_response))
            self.status_label.setText("")
            
        except Exception as e:
            logging.error(f"Error processing transcribed message: {e}")
            self.status_label.setText("Error processing message")

    def display_message(self, sender, message, curated_message=None):
        cursor = self.text_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # Use the appropriate format based on sender
        if sender == "You":
            cursor.insertText(f"{sender}: ", self.user_format)
            cursor.insertText(f"{message}\n")
        else:
            cursor.insertText(f"{sender}: ", self.agent_format)
            cursor.insertText(f"{message}\n")
            
            # Speak only the curated message if available, otherwise use the full message
            message_to_speak = curated_message or message
            if message_to_speak: # Ensure message_to_speak is not None or empty
                # Speak the message with priority based on agent type
                priority = 0 if self.agent_name == "VisionAgent" else 1
                self.tts_manager.speak(message_to_speak, priority)
        
        # Scroll to the bottom
        cursor.movePosition(QTextCursor.End)
        self.text_area.setTextCursor(cursor) 