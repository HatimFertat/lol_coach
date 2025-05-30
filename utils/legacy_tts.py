import logging
import os
import glob
import subprocess
import threading
from queue import Queue
from sys import stdout, stderr
import time
import tempfile
import shutil
import sounddevice as sd
import soundfile as sf

class TTSManager:
    def __init__(self):
        try:
            logging.info("Initializing TTS Manager with Kokoro TTS...")
            self.speech_queue = Queue()
            self.is_speaking = False
            self.should_stop = False
            self.current_process = None
            self.initialized = False
            self.temp_dir = None
            self.audio_thread = None
            self.disabled = False
            
            # Get the absolute path to the kokoro-tts script
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.kokoro_tts_path = os.path.join(script_dir, 'kokoro-tts', 'kokoro-tts')
            
            # Verify the script exists and is executable
            if not os.path.exists(self.kokoro_tts_path):
                raise FileNotFoundError(f"kokoro-tts script not found at {self.kokoro_tts_path}")
            if not os.access(self.kokoro_tts_path, os.X_OK):
                os.chmod(self.kokoro_tts_path, 0o755)
            
            # Create temporary directory for audio files
            self.temp_dir = tempfile.mkdtemp(prefix='tts_audio_')
            
            logging.info(f"Found kokoro-tts at: {self.kokoro_tts_path}")
            logging.info(f"Using temporary directory: {self.temp_dir}")
            
            # Test the TTS system with a simple message
            # self._test_tts()

            # Start the speech processing thread
            self.process_thread = threading.Thread(target=self._process_speech_queue, daemon=True)
            self.process_thread.start()
            logging.info("TTS Manager initialized successfully")
            self.initialized = True

        except Exception as e:
            logging.error(f"Failed to initialize TTS Manager: {e}")
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
            raise
    def _delayed_greeting(self):
        """Send the greeting after a short delay to ensure TTS is ready."""
        try:
            if self.enable_tts.isChecked():
                self.speak("Hello, I am the League of Legends Coach. How can I help you today?")
        except Exception as e:
            logging.error(f"Error sending greeting: {e}")

    def set_disabled(self, disabled: bool):
        """Enable or disable TTS functionality."""
        self.disabled = disabled
        if disabled:
            self.stop_speaking()
            logging.info("TTS has been disabled")
        else:
            logging.info("TTS has been enabled")

    def _test_tts(self):
        """Test the TTS system with a simple message."""
        try:
            logging.info("Testing TTS system...")
            test_text = "Testing text to speech system."
            
            # Create a temporary file for the test text
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                temp_file.write(test_text)
                temp_path = temp_file.name
            
            try:
                # Generate output WAV file path
                output_wav = os.path.join(self.temp_dir, 'test_output.wav')
                
                cmd = [
                    'python3',
                    self.kokoro_tts_path,
                    temp_path,
                    output_wav,
                    '--lang', 'en-us',
                    '--voice', 'af_sarah',
                    '--speed', '1.0',
                    '--debug'
                ]
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    bufsize=1
                )
                
                stdout, stderr = process.communicate()
                
                if process.returncode != 0:
                    logging.error(f"TTS test failed with return code: {process.returncode}")
                    if stderr:
                        logging.error(f"TTS test error: {stderr}")
                    raise Exception("TTS test failed")
                else:
                    logging.info("TTS test successful")
                    
                    # Play the generated audio
                    try:
                        data, samplerate = sf.read(output_wav)
                        sd.play(data, samplerate)
                        sd.wait()
                    except Exception as e:
                        logging.error(f"Error playing test audio: {e}")
                        raise
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logging.warning(f"Failed to delete temporary test file: {e}")
                
        except Exception as e:
            logging.error(f"Error during TTS test: {e}")
            raise

    def speak(self, text: str, priority: int = 1):
        """
        Add text to the speech queue.
        
        Args:
            text: Text to speak
            priority: Priority level (not used in current implementation)
        """
        if not self.initialized or self.disabled:
            logging.debug("TTS Manager not initialized or disabled, skipping speech")
            return
            
        # Remove asterisk symbols to avoid them being read aloud
        text = text.replace("*", "")
        try:
            logging.info(f"Adding to speech queue: {text[:50]}...")
            self.speech_queue.put(text)
        except Exception as e:
            logging.error(f"Error adding text to queue: {e}")

    def stop_speaking(self):
        """Stop the current speech."""
        try:
            logging.info("Stopping speech...")
            self.should_stop = True
            
            # Stop any ongoing audio playback
            if self.audio_thread and self.audio_thread.is_alive():
                sd.stop()
                self.audio_thread.join(timeout=1.0)
            
            # Terminate the current process if it exists
            if self.current_process:
                logging.info("Terminating current process...")
                try:
                    self.current_process.terminate()
                    self.current_process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    self.current_process.kill()
                self.current_process = None
            
            # Clear the queue
            while not self.speech_queue.empty():
                self.speech_queue.get()
            
            self.is_speaking = False
            logging.info("Speech stopped successfully")
        except Exception as e:
            logging.error(f"Error stopping speech: {e}")

    def _process_speech_queue(self):
        """Process the speech queue in a separate thread."""
        while True:
            try:
                # Get the next text to speak
                text = self.speech_queue.get()
                logging.info("Processing next speech request...")
                self.is_speaking = True
                self.should_stop = False
                
                try:
                    # Create a temporary file for the text
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                        temp_file.write(text)
                        temp_path = temp_file.name
                    
                    try:
                        # Generate unique output WAV file path
                        output_wav = os.path.join(self.temp_dir, f'output_{int(time.time())}.wav')
                        
                        logging.info("Starting kokoro-tts process...")
                        cmd = [
                            'python3',
                            self.kokoro_tts_path,
                            temp_path,
                            output_wav,
                            '--lang', 'en-us',
                            '--voice', 'af_sarah',
                            '--speed', '1.0',
                            '--debug'
                        ]
                        logging.info(f"Running command: {' '.join(cmd)}")
                        
                        # Create the process
                        self.current_process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            universal_newlines=True,
                            bufsize=1
                        )
                        
                        # Stream output in real time
                        # for line in self.current_process.stdout:
                            # print(f"[kokoro-tts stdout] {line}", end='')
                        # for line in self.current_process.stderr:
                            # print(f"[kokoro-tts stderr] {line}", end='')
                        self.current_process.wait()
                        
                        # Check return code
                        if self.current_process.returncode != 0:
                            logging.error(f"kokoro-tts failed with return code: {self.current_process.returncode}")
                            if stderr:
                                logging.error(f"Detailed error: {stderr}")
                            continue
                        
                        # Play the audio
                        try:
                            data, samplerate = sf.read(output_wav)
                            sd.play(data, samplerate)
                            sd.wait()
                        except Exception as e:
                            logging.error(f"Error playing audio: {e}")
                        
                    finally:
                        # Clean up temporary files
                        try:
                            os.unlink(temp_path)
                            if os.path.exists(output_wav):
                                os.unlink(output_wav)
                        except Exception as e:
                            logging.warning(f"Failed to delete temporary file: {e}")
                        
                except Exception as e:
                    logging.error(f"Error running kokoro-tts: {e}")
                    if hasattr(e, 'output'):
                        logging.error(f"Process output: {e.output}")
                
                # Mark task as done
                self.speech_queue.task_done()
                self.is_speaking = False
                logging.info("Speech request completed")
                
            except Exception as e:
                logging.error(f"Error in speech processing: {e}")
                self.is_speaking = False

    def cleanup(self):
        """Clean up resources."""
        try:
            logging.info("Cleaning up TTS Manager...")
            self.stop_speaking()
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
            logging.info("TTS Manager cleanup completed")
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