import logging
import os
import glob
from gtts import gTTS
import tempfile
import pygame
import threading
from queue import Queue

class TTSManager:
    def __init__(self):
        try:
            logging.info("Initializing TTS Manager with gTTS...")
            # Initialize pygame mixer for audio playback
            pygame.mixer.init()
            # Queue for speech tasks
            self.speech_queue = Queue()
            # Start the speech processing thread
            self.speech_thread = threading.Thread(target=self._process_speech_queue, daemon=True)
            self.speech_thread.start()
            logging.info("TTS Manager initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize TTS Manager: {e}")
            raise

    def speak(self, text: str, priority: int = 1):
        """
        Add text to the speech queue.
        
        Args:
            text: Text to speak
            priority: Priority level (not used in current implementation)
        """
        try:
            logging.info(f"Adding to speech queue: {text[:50]}...")
            self.speech_queue.put(text)
        except Exception as e:
            logging.error(f"Error adding text to speech queue: {e}")

    def _process_speech_queue(self):
        """Process the speech queue in a separate thread."""
        while True:
            try:
                # Get text from queue
                text = self.speech_queue.get()
                if text is None:  # Shutdown signal
                    break
                
                # Create temporary file for audio
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                    temp_filename = temp_file.name
                
                # Generate speech
                tts = gTTS(text=text, lang='en', slow=False)
                tts.save(temp_filename)
                
                # Play the audio
                pygame.mixer.music.load(temp_filename)
                pygame.mixer.music.play()
                
                # Wait for audio to finish
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
                
                # Clean up temporary file
                try:
                    os.unlink(temp_filename)
                except:
                    pass
                
                # Mark task as done
                self.speech_queue.task_done()
                
            except Exception as e:
                logging.error(f"Error in speech processing: {e}")

    def stop_speaking(self):
        """Stop the current speech."""
        try:
            logging.info("Stopping speech...")
            pygame.mixer.music.stop()
            # Clear the queue
            while not self.speech_queue.empty():
                try:
                    self.speech_queue.get_nowait()
                    self.speech_queue.task_done()
                except:
                    pass
        except Exception as e:
            logging.error(f"Error stopping speech: {e}")

    def cleanup(self):
        """Clean up resources."""
        try:
            logging.info("Cleaning up TTS resources...")
            self.stop_speaking()
            # Signal thread to stop
            self.speech_queue.put(None)
            if self.speech_thread.is_alive():
                self.speech_thread.join(timeout=1.0)
            pygame.mixer.quit()
            logging.info("TTS cleanup completed")
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