from datetime import datetime
import cv2
import os
from pathlib import Path
import numpy as np
import logging

# Path to generic minimap template for validation
TEMPLATE_PATH = Path(__file__).parent / "map_semantics" / "SR_minimap_generic.png"
GENERIC_TEMPLATE = cv2.imread(str(TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)
if GENERIC_TEMPLATE is None:
    raise FileNotFoundError(f"Minimap template not found at {TEMPLATE_PATH}")
    
# ORB detector and BFMatcher for structural feature matching
ORB_DETECTOR = cv2.ORB_create(500)
template_kp, template_des = ORB_DETECTOR.detectAndCompute(GENERIC_TEMPLATE, None)
BF_MATCHER = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

def crop_border(img, threshold=10):
    """
    Crop away colored border until only the dark map interior remains.
    Returns the cropped image.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)
    coords = cv2.findNonZero(mask)
    x, y, w, h = cv2.boundingRect(coords)
    return img[y:y+h, x:x+w]

# Directory containing full-screen screenshots
SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def get_latest_full_screenshot(directory: Path):
    files = list(directory.glob("*.png"))
    candidates = [f for f in files if "_minimap" not in f.name]
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.stat().st_mtime)

def find_minimap_anchor_shape(full_img, minimap_right=True):
    h, w = full_img.shape[:2]
    y0 = int(h * 0.6)
    if minimap_right:
        x0 = int(w * 0.75)
        roi = full_img[y0:, x0:]
    else:
        x0 = 0
        roi = full_img[y0:, :int(w * 0.25)]
    
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    closed = cv2.morphologyEx(blurred, cv2.MORPH_CLOSE, kernel)
    edges = cv2.Canny(closed, 50, 150)

    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80, minLineLength=80, maxLineGap=2)
    if lines is None:
        return None

    # Collect vertical and horizontal lines separately
    vert_lines = []
    horiz_lines = []
    for line in lines:
        h_roi, w_roi = roi.shape[:2]
        x1, y1, x2, y2 = line[0]
        if abs(x1 - x2) < 5:  # vertical line
            vert_lines.append((x1, y1, x2, y2))
        elif abs(y1 - y2) < 5:  # horizontal line
            horiz_lines.append((x1, y1, x2, y2))

    if not vert_lines or not horiz_lines:
        return None

    # Determine the corner based on minimap side
    if minimap_right:
        # top-left corner: find lines closest to ROI origin
        best_point = None
        min_dist = float('inf')
        for vx1, vy1, vx2, vy2 in vert_lines:
            for hx1, hy1, hx2, hy2 in horiz_lines:
                px = vx1
                py = hy1
                dist = px * px + py * py
                if dist < min_dist:
                    min_dist = dist
                    best_point = (px, py)
    else:
        # top-right corner: rightmost vertical and topmost horizontal
        vx_candidates = [v[0] for v in vert_lines]
        hy_candidates = [h[1] for h in horiz_lines]
        if not vx_candidates or not hy_candidates:
            return None
        vx = max(vx_candidates)
        hy = min(hy_candidates)
        best_point = (vx, hy)

    if best_point is None:
        return None

    anchor_x = best_point[0] + x0 if minimap_right else best_point[0]
    anchor_y = best_point[1] + y0
    return (anchor_x, anchor_y)

def crop_minimap_from_anchor(img, anchor, minimap_right=True):
    x, y = anchor
    if minimap_right:
        return img[y:, x:]
    else:
        return img[y:, :x]

def save_minimap_crop(cropped_img, original_path: Path):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = original_path.with_name(f"{timestamp}_minimap.png")
    cv2.imwrite(str(out_path), cropped_img)
    original_path.unlink(missing_ok=True)
    return out_path

def process_minimap_crop(full_img_path: str, minimap_right: bool = True):
    full_img = cv2.imread(full_img_path)
    anchor = find_minimap_anchor_shape(full_img, minimap_right)
    if anchor is None:
        logging.error("Could not detect minimap anchor by shape.")
        return None

    cropped = crop_minimap_from_anchor(full_img, anchor, minimap_right)
    cropped = crop_border(cropped)
    cropped_gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
    # ORB feature detection on crop
    kp2, des2 = ORB_DETECTOR.detectAndCompute(cropped_gray, None)
    if des2 is None or len(kp2) < 10:
        logging.error("Not enough ORB keypoints, discarding.")
        return None
    # Match template descriptors to crop descriptors
    matches = BF_MATCHER.match(template_des, des2)
    matches = sorted(matches, key=lambda m: m.distance)
    good_matches = [m for m in matches if m.distance < 60]
    if len(good_matches) < 15:
        logging.error(f"ORB matches below threshold ({len(good_matches)}), discarding.")
        return None
    output_path = save_minimap_crop(cropped, Path(full_img_path))
    logging.info(f"Saved cropped minimap to: {output_path}")
    return str(output_path)

def process_latest_minimap_crop():
    latest = get_latest_full_screenshot(SCREENSHOT_DIR)
    if latest is None:
        logging.error("No uncropped screenshots found.")
        return None

    full_img = cv2.imread(str(latest))
    anchor = find_minimap_anchor_shape(full_img, minimap_right=True)
    # Save the region of interest used for anchor detection
    if anchor is None:
        logging.error("Could not detect minimap anchor by shape.")
        return None

    cropped = crop_minimap_from_anchor(full_img, anchor, minimap_right=True)
    cropped = crop_border(cropped)
    cropped_gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
    # ORB feature detection on crop
    kp2, des2 = ORB_DETECTOR.detectAndCompute(cropped_gray, None)
    if des2 is None or len(kp2) < 10:
        logging.error("Not enough ORB keypoints, discarding.")
        return None
    # Match template descriptors to crop descriptors
    matches = BF_MATCHER.match(template_des, des2)
    # Sort by distance (lower is better)
    matches = sorted(matches, key=lambda m: m.distance)
    # Count good matches under a distance threshold
    good_matches = [m for m in matches if m.distance < 60]
    if len(good_matches) < 15:
        logging.error(f"ORB matches below threshold ({len(good_matches)}), discarding.")
        return None
    output_path = save_minimap_crop(cropped, latest)
    logging.info(f"Saved cropped minimap to: {output_path}")
    return str(output_path)

if __name__ == "__main__":
    process_latest_minimap_crop()