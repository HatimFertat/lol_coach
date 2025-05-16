import pyttsx3
import threading
from queue import PriorityQueue
from typing import Optional
import logging
import os
import glob

class TTSManager:
    def __init__(self):
        self.engine = None
        self._init_engine()
        
        # Queue for text to be spoken, with priority
        # Lower number = higher priority
        self.speech_queue = PriorityQueue()
        
        # Current speaking thread
        self.current_speaking_thread: Optional[threading.Thread] = None
        self.is_speaking = False
        self.should_stop = False
        
        # Lock for thread safety
        self.lock = threading.Lock()
        
        # Start the speech processing thread
        self.process_thread = threading.Thread(target=self._process_speech_queue, daemon=True)
        self.process_thread.start()

    def _init_engine(self):
        """Initialize the TTS engine with proper settings."""
        try:
            if self.engine:
                try:
                    self.engine.stop()
                except:
                    pass
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 150)  # Speed of speech
            self.engine.setProperty('volume', 1.0)  # Volume (0.0 to 1.0)
        except Exception as e:
            logging.error(f"Error initializing TTS engine: {e}")
            self.engine = None

    def speak(self, text: str, priority: int = 1):
        """
        Add text to the speech queue.
        
        Args:
            text: Text to speak
            priority: Priority level (lower number = higher priority)
        """
        if not self.engine:
            self._init_engine()
            if not self.engine:
                logging.error("TTS engine not available")
                return

        with self.lock:
            self.speech_queue.put((priority, text))
            # If we're currently speaking, stop it to process the new text
            if self.is_speaking:
                self.should_stop = True
                if self.current_speaking_thread:
                    self.current_speaking_thread.join(timeout=0.1)

    def stop_speaking(self):
        """Stop the current speech and clear the queue."""
        with self.lock:
            self.should_stop = True
            self.speech_queue.queue.clear()
            if self.current_speaking_thread:
                self.current_speaking_thread.join(timeout=0.1)
            self.is_speaking = False

    def _process_speech_queue(self):
        """Process the speech queue in a separate thread."""
        while True:
            try:
                # Get the next text to speak
                priority, text = self.speech_queue.get()
                
                # Start speaking in a new thread
                self.current_speaking_thread = threading.Thread(
                    target=self._speak_text,
                    args=(text,),
                    daemon=True
                )
                self.current_speaking_thread.start()
                self.current_speaking_thread.join()
                
                # Mark task as done
                self.speech_queue.task_done()
                
            except Exception as e:
                logging.error(f"Error in speech processing: {e}")

    def _speak_text(self, text: str):
        """Speak the given text, respecting stop requests."""
        if not self.engine:
            self._init_engine()
            if not self.engine:
                logging.error("TTS engine not available")
                return

        with self.lock:
            self.is_speaking = True
            self.should_stop = False

        try:
            # Register callback for word boundary events
            def on_word(name, location, length):
                if self.should_stop:
                    try:
                        self.engine.stop()
                    except:
                        pass
                    return

            self.engine.connect('started-word', on_word)
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            logging.error(f"Error speaking text: {e}")
            # Try to reinitialize the engine on error
            self._init_engine()
        finally:
            with self.lock:
                self.is_speaking = False
                self.should_stop = False

    def cleanup(self):
        """Clean up resources."""
        try:
            self.stop_speaking()
            if self.engine:
                try:
                    self.engine.stop()
                except:
                    pass
                self.engine = None
        except Exception as e:
            logging.error(f"Error during TTS cleanup: {e}")

    @staticmethod
    def cleanup_screenshots():
        """Clean up all screenshots in the vision/screenshots folder."""
        try:
            screenshot_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'vision', 'screenshots')
            if os.path.exists(screenshot_dir):
                for file in glob.glob(os.path.join(screenshot_dir, '*')):
                    try:
                        os.remove(file)
                    except Exception as e:
                        logging.error(f"Error deleting screenshot {file}: {e}")
        except Exception as e:
            logging.error(f"Error cleaning up screenshots: {e}") 