import logging
import os
import glob
import subprocess
import threading
from queue import Queue
import tempfile
import shutil
from kokoro_onnx import Kokoro
import sounddevice as sd
import soundfile as sf
from pathlib import Path
import runpy
import json
from openai import OpenAI

from dotenv import load_dotenv
load_dotenv()


class TTSManager:
    # Available voices for each engine
    OPENAI_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "sage", "shimmer"]
    KOKORO_VOICES = ["af_alloy", "af_sarah", "am_eric", "am_fenrir", "bf_alice", "bf_lily", "bm_george", "bm_lewis"]

    def __init__(self):
        try:
            logging.info("Initializing TTS Manager...")
            self.speech_queue = Queue()
            self.is_speaking = False
            self.should_stop = False
            self.initialized = False
            self.temp_dir = None
            self.audio_thread = None
            self.disabled = False
            
            # Load settings
            self.settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'settings.json')
            self.load_settings()
            
            # Initialize the selected TTS engine
            if self.tts_engine == "kokoro":
                self._init_kokoro()
            elif self.tts_engine == "openai":
                self._init_openai()
            else:
                raise ValueError(f"Unsupported TTS engine: {self.tts_engine}")
            
            # Create temporary directory for audio files
            self.temp_dir = tempfile.mkdtemp(prefix='tts_audio_')
            
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

    def load_settings(self):
        """Load TTS settings from settings.json"""
        try:
            with open(self.settings_path, 'r') as f:
                settings = json.load(f)
                tts_settings = settings.get('tts', {})
                self.tts_engine = tts_settings.get('engine', 'kokoro')
                self.voice = tts_settings.get('voice', 'af_sarah')
                self.speed = tts_settings.get('speed', 1.0)
                self.lang = tts_settings.get('language', 'en-us')
        except Exception as e:
            logging.error(f"Error loading TTS settings: {e}")
            # Set defaults
            self.tts_engine = 'kokoro'
            self.voice = 'af_sarah'
            self.speed = 1.0
            self.lang = 'en-us'

    def _init_kokoro(self):
        """Initialize Kokoro TTS engine"""
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.kokoro_tts_path = os.path.join(script_dir, 'kokoro-tts', 'kokoro-tts')
        
        if not os.path.exists(self.kokoro_tts_path):
            raise FileNotFoundError(f"kokoro-tts script not found at {self.kokoro_tts_path}")
        if not os.access(self.kokoro_tts_path, os.X_OK):
            os.chmod(self.kokoro_tts_path, 0o755)
        
        self.chunk_text = runpy.run_path(str(Path(self.kokoro_tts_path)))['chunk_text']
        
        model_path = os.path.join(script_dir, 'kokoro-v1.0.onnx')
        voices_path = os.path.join(script_dir, 'voices-v1.0.bin')
        self.kokoro = Kokoro(model_path, voices_path)

    def _init_openai(self):
        """Initialize OpenAI TTS engine"""
        # Load OpenAI API key from environment
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set in environment")
        self.openai_client = OpenAI(api_key=api_key)

    def get_available_voices(self):
        """Get available voices for the current engine"""
        if self.tts_engine == "kokoro":
            return self.KOKORO_VOICES
        elif self.tts_engine == "openai":
            return self.OPENAI_VOICES
        return []

    def set_engine(self, engine: str):
        """Switch TTS engine"""
        if engine not in ["kokoro", "openai"]:
            raise ValueError(f"Unsupported TTS engine: {engine}")
        
        self.tts_engine = engine
        if engine == "kokoro":
            self._init_kokoro()
        else:
            self._init_openai()
        
        # Update settings
        self._save_settings()

    def _save_settings(self):
        """Save current TTS settings to settings.json"""
        try:
            with open(self.settings_path, 'r') as f:
                settings = json.load(f)
            
            settings['tts'] = {
                'engine': self.tts_engine,
                'voice': self.voice,
                'speed': self.speed,
                'language': self.lang
            }
            
            with open(self.settings_path, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving TTS settings: {e}")

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
            test_text = "Testing TTS system..."
            
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
                    '--speed', '1.0'
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
            if text != "":
                logging.info(f"Adding to speech queue: {text[:50]}...")
                self.speech_queue.put(text)
            else:
                logging.debug("Skipping empty text")
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
                text = self.speech_queue.get()
                logging.info("Processing next speech request...")
                self.is_speaking = True
                self.should_stop = False
                
                try:
                    if self.tts_engine == "kokoro":
                        self._process_kokoro_speech(text)
                    else:
                        self._process_openai_speech(text)
                        
                except Exception as e:
                    logging.error(f"Error in speech processing: {e}")
                
                self.speech_queue.task_done()
                self.is_speaking = False
                logging.info("Speech request completed")
                
            except Exception as e:
                logging.error(f"Error in speech processing: {e}")
                self.is_speaking = False

    def _process_kokoro_speech(self, text):
        """Process speech using Kokoro TTS"""
        for chunk in self.chunk_text(text, initial_chunk_size=500):
            if self.should_stop:
                break
            try:
                samples, samplerate = self.kokoro.create(chunk, voice=self.voice, speed=self.speed, lang=self.lang)
                sd.play(samples, samplerate)
                sd.wait()
            except Exception as e:
                logging.error(f"Error synthesizing or playing chunk: {e}")

    def _process_openai_speech(self, text):
        """Process speech using OpenAI TTS"""
        try:
            # Create a temporary file for the audio
            temp_file = os.path.join(self.temp_dir, 'temp_speech.mp3')
            
            with self.openai_client.audio.speech.with_streaming_response.create(
                model="tts-1",
                voice=self.voice,
                input=text,
            ) as response:
                response.stream_to_file(temp_file)
            
            # Play the audio file
            data, samplerate = sf.read(temp_file)
            sd.play(data, samplerate)
            sd.wait()
            
            # Clean up
            os.remove(temp_file)
            
        except Exception as e:
            logging.error(f"Error in OpenAI TTS processing: {e}")

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
