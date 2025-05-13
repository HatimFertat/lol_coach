import os
import platform
from datetime import datetime
from pynput import keyboard
import mss
from PIL import Image
import time
from vision.minimap_cropper import process_minimap_crop  # Adjust if your cropper function has a different name

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
            process_minimap_crop(screenshot_path)
            print('Minimap cropper called successfully.')
        except Exception as e:
            print(f'Error calling minimap cropper: {e}')

def main():
    print(f'Listening for keyboard shortcuts to take a screenshot and crop minimap... (OS: {platform.system()})')
    # The keyboard listener is now managed by the GUI
    pass

if __name__ == '__main__':
    main()
