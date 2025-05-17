import sys
import os
sys.path.insert(0, os.path.abspath("external/nix_tts"))
from external.nix_tts.nix.models.TTS import NixTTSInference
import numpy as np
import sounddevice as sd

# Initialize the Nix-TTS model
nix = NixTTSInference(model_dir="external/nix-tts/nix/models")  # adjust path if needed

# Prepare input text
text = "Hello, this is a test of Nix TTS."

# Tokenize and generate speech
c, c_length, _ = nix.tokenize(text)
waveform = nix.vocalize(c, c_length)

# Play the audio
audio = waveform[0, 0].astype(np.float32)
sd.play(audio, samplerate=22050)
sd.wait()