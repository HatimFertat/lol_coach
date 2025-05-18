import subprocess
import soundfile as sf
import sounddevice as sd
import tempfile
import glob
import os

text = "Hello, this is a Kokoro TTS test."
command = ["python",
    "./external/kokoro-tts/kokoro-tts", "/dev/stdin",
    "--stream",
    "--lang", "en-us",
    "--voice", "af_sarah",
    "--speed", "1.0"
]

# Pipe the text into kokoro-tts and stream playback
proc = subprocess.Popen(command, stdin=subprocess.PIPE)
proc.communicate(input=text.encode("utf-8"))

# Second test: chunked output to ./chunks directory and playback
text2 = "This is the second test for Kokoro TTS chunked output."
with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as tf2:
    tf2.write(text2)
    temp_txt2 = tf2.name

chunks_dir = "./chunks"
os.makedirs(chunks_dir, exist_ok=True)

cmd2 = [
    "python",
    "./external/kokoro-tts/kokoro-tts",
    temp_txt2,
    "--split-output", chunks_dir,
    "--format", "wav",
    "--lang", "en-us",
    "--voice", "af_sarah",
    "--speed", "1.0"
]
print(f"Running second test command: {' '.join(cmd2)}")
proc2 = subprocess.Popen(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
stdout2, stderr2 = proc2.communicate()
if stdout2:
    print("stdout:", stdout2.decode())
if stderr2:
    print("stderr:", stderr2.decode())
if proc2.returncode != 0:
    print(f"Second test failed with return code {proc2.returncode}")

# Play back each generated chunk
for audio_file in sorted(glob.glob(os.path.join(chunks_dir, '*.wav'))):
    print(f"Playing {audio_file}")
    data, samplerate = sf.read(audio_file)
    sd.play(data, samplerate)
    sd.wait()

# Clean up temporary text file
try:
    os.remove(temp_txt2)
except OSError as e:
    print(f"Error removing temp file {temp_txt2}: {e}")