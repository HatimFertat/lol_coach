import os
import platform
from datetime import datetime
from pynput import keyboard
import mss
from PIL import Image
import time
from vision.minimap_cropper import process_minimap_crop  # Adjust if your cropper function has a different name
import logging
# Directory to save screenshots
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), 'screenshots')
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def take_screenshot_and_crop():
    # Take screenshot
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # Full screen
        sct_img = sct.grab(monitor)
        img = Image.frombytes('RGB', sct_img.size, sct_img.rgb)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        screenshot_path = os.path.join(SCREENSHOT_DIR, f'{timestamp}_full.png')
        img.save(screenshot_path)
        print(f'Screenshot saved to {screenshot_path}')
        # Call minimap cropper
        try:
            minimap_path = process_minimap_crop(screenshot_path)
            logging.info(f'Minimap cropper called successfully, saved at {minimap_path}')
            #cleanup full screenshot
            # os.remove(screenshot_path)
            return minimap_path
        except Exception as e:
            logging.error(f'Error calling minimap cropper: {e}')
            return None
