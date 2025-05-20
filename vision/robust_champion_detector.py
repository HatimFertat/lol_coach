import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Set
from vision.map_semantics.minimap_coordinate_mapper import MinimapCoordinateMapper
from game_context.game_state import GameStateContext, role_mapping
from skimage.feature import hog
from scipy.spatial.distance import cosine

HALO_SIZE = 3
def create_circular_mask(icon: np.ndarray) -> np.ndarray:
    """
    Create a circular mask for the icon to match minimap icons.
    """
    h, w = icon.shape
    center = (w//2, h//2)
    radius = min(w, h)//2
    
    # Create circular mask
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(mask, center, radius, 255, -1)
    
    # Apply mask to icon
    masked_icon = cv2.bitwise_and(icon, icon, mask=mask)
    return masked_icon

def get_minimap_icon_size(minimap_shape: Tuple[int, int]) -> Tuple[int, int]:
    """
    Calculate the expected size of champion icons on the minimap.
    Icons are approximately 8-12% of the minimap size.
    """
    # Use 8% as per reference implementation
    icon_size = max(12, int(min(minimap_shape) * 0.08))  # Ensure minimum size of 16x16
    # Ensure even number for better scaling
    icon_size = (icon_size // 2) * 2
    return (icon_size, icon_size)

def filter_blue(minimap: np.ndarray) -> np.ndarray:
    """Filter blue team colors from minimap."""
    lower_blue = np.array([170, 130, 50])
    upper_blue = np.array([255, 170, 120])
    return cv2.inRange(minimap, lower_blue, upper_blue)

def filter_red(minimap: np.ndarray) -> np.ndarray:
    """Filter red team colors from minimap."""
    lower_red = np.array([20, 20, 150])
    upper_red = np.array([100, 100, 255])
    return cv2.inRange(minimap, lower_red, upper_red)

def calculate_champion_distances(
    positions_xy: Dict[str, Tuple[float, float]],
    reference_champion: str,
    target_champions: List[str]
) -> Dict[str, float]:
    """
    Calculate distances between a reference champion and a list of target champions.
    Uses League of Legends coordinate system where 15000 units = 512 pixels on minimap.
    
    Args:
        positions_xy: Dictionary mapping champion names to their (x, y) coordinates
        reference_champion: Name of the reference champion
        target_champions: List of champion names to calculate distances to
    
    Returns:
        Dictionary mapping target champion names to their distances from the reference champion in game units.
        Returns None for champions that are not visible.
    """
    # Check if reference champion is visible
    if reference_champion not in positions_xy or positions_xy[reference_champion] is None:
        return {champ: None for champ in target_champions}
    
    ref_x, ref_y = positions_xy[reference_champion]
    distances = {}
    
    # League of Legends coordinate system conversion
    # 15000 units = 512 pixels on minimap
    PIXELS_TO_UNITS = 15000 / 512
    
    for champ in target_champions:
        if champ not in positions_xy or positions_xy[champ] is None:
            distances[champ] = None
            continue
            
        target_x, target_y = positions_xy[champ]
        
        # Calculate Euclidean distance in pixels
        pixel_distance = ((target_x - ref_x) ** 2 + (target_y - ref_y) ** 2) ** 0.5
        
        # Convert to game units
        game_distance = pixel_distance * PIXELS_TO_UNITS
        distances[champ] = game_distance
    
    return distances

def format_champion_positions(
    game_state: GameStateContext,
    positions_str: Dict[str, str],
    positions_xy: Dict[str, Tuple[float, float]]
) -> str:
    """
    Format champion positions in a readable way for the macro agent.
    
    Args:
        game_state: GameStateContext object
        positions_str: Dictionary mapping champion names to their location descriptions
        positions_xy: Dictionary mapping champion names to their (x, y) coordinates
    
    Returns:
        String containing formatted positions for all champions
    """
    lines = []
    
    # Add ally positions
    lines.append("Ally Positions:")
    for role, champ in game_state.player_team.champions.items():
        if champ.name in positions_str:
            lines.append(f"[{role_mapping[role]}] {champ.name}: {positions_str[champ.name]}")
    
    # Add enemy positions
    lines.append("\nEnemy Positions:")
    for role, champ in game_state.enemy_team.champions.items():
        if champ.name in positions_str:
            lines.append(f"[{role_mapping[role]}] {champ.name}: {positions_str[champ.name]}")
    
    return "\n".join(lines)

def compute_circle_overlap(circle1: Tuple[int, int, int], circle2: Tuple[int, int, int]) -> float:
    """
    Compute the overlap ratio between two circles.
    
    Args:
        circle1: Tuple of (x, y, r) for first circle
        circle2: Tuple of (x, y, r) for second circle
        
    Returns:
        Float between 0 and 1 representing overlap ratio
    """
    x1, y1, r1 = map(float, circle1)
    x2, y2, r2 = map(float, circle2)
    
    # Calculate distance between centers
    dx = x2 - x1
    dy = y2 - y1
    distance = np.sqrt(dx * dx + dy * dy)
    
    # No overlap case
    if distance >= r1 + r2:
        return 0.0
    
    # One circle inside another
    if distance <= abs(r1 - r2):
        smaller_r = min(r1, r2)
        return (np.pi * smaller_r**2) / (np.pi * max(r1, r2)**2)
    
    # Partial overlap
    r1_sq = r1**2
    r2_sq = r2**2
    d_sq = distance**2
    
    # Area of circle 1 segment
    term1 = r1_sq * np.arccos((d_sq + r1_sq - r2_sq) / (2 * distance * r1))
    # Area of circle 2 segment
    term2 = r2_sq * np.arccos((d_sq + r2_sq - r1_sq) / (2 * distance * r2))
    # Area of the lens formed by the two segments
    term3 = 0.5 * np.sqrt((-distance + r1 + r2) * (distance + r1 - r2) * (distance - r1 + r2) * (distance + r1 + r2))
    
    intersection_area = term1 + term2 - term3
    union_area = np.pi * (r1_sq + r2_sq) - intersection_area
    
    return intersection_area / union_area


def classify_overlapping_circles(candidates: List[Tuple[int, int, int, float]]) -> List[Tuple[int, int, int, float, bool]]:
    """
    Classify circles as foreground or background based on overlaps.
    
    Args:
        candidates: List of (x, y, r, score) tuples for circle candidates
        
    Returns:
        List of (x, y, r, score, is_foreground) tuples
    """
    if not candidates:
        return []
    
    # Convert to (x, y, r) format for overlap computation
    circles = [(x, y, r) for x, y, r, _ in candidates]
    
    # Initialize all as foreground
    is_foreground = [True] * len(circles)
    
    # Check each pair of circles for overlap
    for i in range(len(circles)):
        for j in range(i+1, len(circles)):
            overlap_ratio = compute_circle_overlap(circles[i], circles[j])
            
            # If significant overlap (>15%), classify one as background
            if overlap_ratio > 0.15:
                # If nearly complete overlap, prioritize the circle with higher initial score
                if overlap_ratio > 0.8:
                    if candidates[i][3] < candidates[j][3]:
                        is_foreground[i] = False
                    else:
                        is_foreground[j] = False
                # Otherwise, smaller circle is typically in foreground (champion icons are similar size)
                elif circles[i][2] > circles[j][2]:
                    is_foreground[i] = False
                else:
                    is_foreground[j] = False
    
    # Return original candidates with foreground classification
    return [(x, y, r, score, fg) for (x, y, r, score), fg in zip(candidates, is_foreground)]

def create_occlusion_mask(current_circle: Tuple[int, int, int], 
                          all_circles: List[Tuple[int, int, int]], 
                          is_foreground: bool,
                          mask_size: Tuple[int, int]) -> np.ndarray:
    """
    Create occlusion mask for a circle based on foreground/background classification.
    
    Args:
        current_circle: Tuple of (x, y, r) for current circle
        all_circles: List of (x, y, r) tuples for all circles
        is_foreground: Whether current circle is in foreground
        mask_size: Size of the mask to create (width, height)
        
    Returns:
        Binary mask indicating visible parts of the circle
    """
    x, y, r = current_circle
    mask = np.zeros(mask_size, dtype=np.uint8)
    
    # Draw current circle (full mask for foreground, starting mask for background)
    cv2.circle(mask, (mask_size[0]//2, mask_size[1]//2), r, 255, -1)
    
    # For background circles, subtract overlapping foreground circles
    if not is_foreground:
        for other_x, other_y, other_r in all_circles:
            # Skip self
            if other_x == x and other_y == y and other_r == r:
                continue
                
            # Calculate relative position in mask coordinates
            rel_x = other_x - x + mask_size[0]//2
            rel_y = other_y - y + mask_size[1]//2
            
            # Check if the circles overlap
            distance = np.sqrt((other_x - x)**2 + (other_y - y)**2)
            if distance < r + other_r:
                # Create mask for overlapping region
                overlap_mask = np.zeros(mask_size, dtype=np.uint8)
                cv2.circle(overlap_mask, (rel_x, rel_y), other_r + HALO_SIZE + 2, 255, -1)
                
                # Subtract from main mask
                mask = cv2.bitwise_and(mask, cv2.bitwise_not(overlap_mask))
    
    return mask


def detect_champion_positions(
    minimap_path: str,
    ally_champions: List[str],
    enemy_champions: List[str],
    threshold: float = 0,
    debug: bool = False
) -> Tuple[Dict[str, str], Dict[str, Tuple[float, float]]]:
    """
    Detect champion positions on the minimap using color filtering and template matching.
    
    Args:
        minimap_path: Path to the minimap image
        ally_champions: List of ally champion names
        enemy_champions: List of enemy champion names
        threshold: Template matching threshold (0-1)
        debug: If True, show debug visualizations
    
    Returns:
        Tuple containing:
        - Dictionary mapping champion names to their location descriptions
        - Dictionary mapping champion names to their (x, y) coordinates
    """
    # Initialize coordinate mapper
    mapper = MinimapCoordinateMapper()
    
    # Read minimap image
    minimap = cv2.imread(minimap_path)
    if minimap is None:
        raise ValueError(f"Could not read minimap image at {minimap_path}")
    
    # Calculate icon size based on minimap dimensions
    icon_size = get_minimap_icon_size(minimap.shape[:2])  # Use only height and width
    
    if debug:
        cv2.imshow('Minimap', minimap)
        print(f"Minimap shape: {minimap.shape}")
        print(f"Calculated icon size: {icon_size}")
    
    # Filter colors for both teams
    blue_filtered = filter_blue(minimap)
    red_filtered = filter_red(minimap)
    
    if debug:
        # Show filtered images for both teams
        color_filters = np.hstack([blue_filtered, red_filtered])
        cv2.imshow('Color Filters (Blue | Red)', color_filters)
    
    # Process each team's champions
    positions_str = {}
    positions_xy = {}
    icons_dir = Path("vision/icons")
    
    # We'll still track matches for visualization but won't exclude them
    blue_matches = []
    red_matches = []
    
    def compute_hough_candidates(filtered_minimap, icon_size):
        blurred = cv2.GaussianBlur(filtered_minimap, (5, 5), 2)
        edges = cv2.Canny(blurred, 50, 150)
        icon_diameter = icon_size[0]
        icon_radius = icon_diameter // 2
        minDist = int(icon_diameter * 0.3)
        minRadius = int(icon_radius * 0.8)
        maxRadius = int(icon_radius * 1.2)
        circles = cv2.HoughCircles(
            edges,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=minDist,
            param1=100,
            param2=25,
            minRadius=minRadius,
            maxRadius=maxRadius
        )
        candidates = []
        if circles is not None:
            circles = np.uint16(np.around(circles[0, :]))
            circles = sorted(circles, key=lambda x: x[2], reverse=True)
            for (x_center, y_center, r) in circles:
                # Exclude outer region to avoid color halo
                inner_r = max(r - HALO_SIZE, 1)
                candidates.append((x_center, y_center, inner_r, 1.0))
                # candidates.append((x_center, y_center, r, 1.0))
        return candidates

    blue_candidates = compute_hough_candidates(blue_filtered, icon_size)
    red_candidates = compute_hough_candidates(red_filtered, icon_size)

    # Classify circles as foreground or background based on overlaps
    blue_classified = classify_overlapping_circles(blue_candidates)
    red_classified = classify_overlapping_circles(red_candidates)

    # Visualize all candidates once at the beginning
    if debug:
        # Create visualizations of all candidates with index numbers for both teams
        blue_vis = minimap.copy()
        red_vis = minimap.copy()
        
        # Draw blue candidates
        for i, (x_center, y_center, radius, _, is_foreground) in enumerate(blue_classified):
            color = (255, 0, 0) if is_foreground else (0, 255, 255)  # Blue for foreground, yellow for background
            cv2.circle(blue_vis, (x_center, y_center), radius, color, 2)
            cv2.putText(blue_vis, f"{i}{'F' if is_foreground else 'B'}", (x_center, y_center), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Draw red candidates
        for i, (x_center, y_center, radius, _, is_foreground) in enumerate(red_classified):
            color = (0, 0, 255) if is_foreground else (255, 0, 255)  # Red for foreground, magenta for background
            cv2.circle(red_vis, (x_center, y_center), radius, color, 2)
            cv2.putText(red_vis, f"{i}{'F' if is_foreground else 'B'}", (x_center, y_center), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Show both visualizations
        cv2.imshow('Blue Team Candidates', blue_vis)
        cv2.imshow('Red Team Candidates', red_vis)
        print(f"Found {len(blue_classified)} blue team candidates")
        print(f"Found {len(red_classified)} red team candidates")

    def process_champion(champ: str, filtered_minimap: np.ndarray, classified_candidates: List[Tuple[int, int, int, float, bool]], 
                        is_ally: bool, matches_list: List[Tuple[str, Tuple[int, int], float]]) -> None:
        """
        Process a champion to detect its position on the minimap using HOG + color histogram matching.
        
        Args:
            champ: Champion name
            filtered_minimap: Color-filtered minimap image
            classified_candidates: List of classified candidate circles (x, y, radius, score, is_foreground)
            is_ally: Whether this is an ally champion
            matches_list: List to store match results for visualization
        """
        icon_path = icons_dir / f"{champ}.png"
        if not icon_path.exists():
            print(f"Warning: Could not find icon for {champ}")
            positions_str[champ] = "Not visible"
            return

        # Read and preprocess icon
        icon = cv2.imread(str(icon_path))
        if icon is None:
            print(f"Warning: Could not read icon at {icon_path}")
            positions_str[champ] = "Not visible"
            return

        if debug:
            print(f"\nProcessing {champ}:")
            print(f"Original icon shape: {icon.shape}")

        # Validate icon dimensions
        if icon.shape[0] < icon_size[0] or icon.shape[1] < icon_size[1]:
            print(f"Warning: Icon for {champ} is too small ({icon.shape}) for target size {icon_size}")
            positions_str[champ] = "Not visible"
            return

        # Compute smaller template size (e.g., 80% of detected icon_size)
        shrink_factor = 1
        icon_small_w = max(2, (int(icon_size[0] * shrink_factor) // 2) * 2)
        icon_small_h = max(2, (int(icon_size[1] * shrink_factor) // 2) * 2)
        icon_small_size = (icon_small_w, icon_small_h)

        # Resize the icon to template size
        try:
            icon_small = cv2.resize(icon, icon_small_size, interpolation=cv2.INTER_AREA)
        except cv2.error as e:
            print(f"Error resizing icon for {champ}: {e}")
            positions_str[champ] = "Not visible"
            return
        print("shapes")
        print(f"pre shrink: {icon_size}")
        print(f"post shrink: {icon_small.shape}")
        # Create circular mask
        icon_mask = np.zeros(icon_small_size, dtype=np.uint8)
        cv2.circle(
            icon_mask,
            (icon_small_w // 2, icon_small_h // 2),
            icon_small_w // 2,
            255,
            -1
        )
        
        # Apply mask to icon
        icon_small_masked = cv2.bitwise_and(icon_small, icon_small, mask=icon_mask)
        
        # Convert to grayscale for HOG
        icon_gray = cv2.cvtColor(icon_small_masked, cv2.COLOR_BGR2GRAY)
        
        # Convert to HSV for color histogram
        icon_hsv = cv2.cvtColor(icon_small_masked, cv2.COLOR_BGR2HSV)
        
        # HOG Parameters
        orientations = 8
        pixels_per_cell = (4, 4)
        cells_per_block = (2, 2)
        
        # Extract base HOG features for the icon template (full circular mask)
        icon_base_hog_features, icon_hog_image = hog(
            icon_gray, 
            orientations=orientations, 
            pixels_per_cell=pixels_per_cell,
            cells_per_block=cells_per_block, 
            visualize=True,
            feature_vector=True
        )
        
        # Normalize HOG features
        if np.linalg.norm(icon_base_hog_features) > 0:
            icon_base_hog_features = icon_base_hog_features / np.linalg.norm(icon_base_hog_features)
        
        # Extract color histogram parameters for the icon
        h_bins, s_bins, v_bins = 8, 8, 8
        h_ranges, s_ranges, v_ranges = (0, 180), (0, 256), (0, 256)
        
        # Extract base color histograms (full circular mask)
        icon_base_h_hist = cv2.calcHist([icon_hsv], [0], icon_mask, [h_bins], h_ranges)
        icon_base_s_hist = cv2.calcHist([icon_hsv], [1], icon_mask, [s_bins], s_ranges)
        icon_base_v_hist = cv2.calcHist([icon_hsv], [2], icon_mask, [v_bins], v_ranges)
        
        # Normalize histograms
        cv2.normalize(icon_base_h_hist, icon_base_h_hist, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(icon_base_s_hist, icon_base_s_hist, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(icon_base_v_hist, icon_base_v_hist, 0, 1, cv2.NORM_MINMAX)
        
        # Handle NaN values that can occur with normalization
        icon_base_h_hist = np.nan_to_num(icon_base_h_hist)
        icon_base_s_hist = np.nan_to_num(icon_base_s_hist)
        icon_base_v_hist = np.nan_to_num(icon_base_v_hist)
        
        # Create a synthetic visualization of the icon and its features
        if debug:
            # Convert HOG image to display format
            icon_hog_image = (icon_hog_image * 255).astype(np.uint8)
            
            # Create histograms visualization
            hist_h = np.zeros((100, h_bins * 10, 3), dtype=np.uint8)
            hist_s = np.zeros((100, s_bins * 10, 3), dtype=np.uint8)
            hist_v = np.zeros((100, v_bins * 10, 3), dtype=np.uint8)
            
            for i in range(h_bins):
                h_val = int(icon_base_h_hist[i] * 100)
                cv2.rectangle(hist_h, (i * 10, 100), ((i + 1) * 10, 100 - h_val), (255, 0, 0), -1)
                
            for i in range(s_bins):
                s_val = int(icon_base_s_hist[i] * 100)
                cv2.rectangle(hist_s, (i * 10, 100), ((i + 1) * 10, 100 - s_val), (0, 255, 0), -1)
                
            for i in range(v_bins):
                v_val = int(icon_base_v_hist[i] * 100)
                cv2.rectangle(hist_v, (i * 10, 100), ((i + 1) * 10, 100 - v_val), (0, 0, 255), -1)
            
            # Create an HSV channels visualization
            h, s, v = cv2.split(icon_hsv)
            
            # Resize everything to the same height for display
            icon_vis = cv2.resize(icon_small_masked, (100, 100))
            icon_gray_vis = cv2.cvtColor(cv2.resize(icon_gray, (100, 100)), cv2.COLOR_GRAY2BGR)
            icon_hog_vis = cv2.cvtColor(cv2.resize(icon_hog_image, (100, 100)), cv2.COLOR_GRAY2BGR)
            
            # Combine all visualizations
            top_row = np.hstack([icon_vis, icon_gray_vis, icon_hog_vis])
            bottom_row = np.hstack([hist_h, hist_s, hist_v])
            
            # Resize bottom row to match top row width
            if bottom_row.shape[1] != top_row.shape[1]:
                bottom_row = cv2.resize(bottom_row, (top_row.shape[1], bottom_row.shape[0]))
            
            icon_features_vis = np.vstack([top_row, bottom_row])
            cv2.putText(icon_features_vis, f"Icon: {champ}", (5, 15), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.imshow(f'Icon Features - {champ}', icon_features_vis)
            
            print(f"HOG feature size: {icon_base_hog_features.shape}")
        
        best_match = None
        best_score = threshold
        best_similarity = threshold
        best_hog_similarity = 0
        best_color_similarity = 0
        best_index = -1
        
        if debug:
            print(f"Processing {len(classified_candidates)} candidates for {champ}")
        
        pad = max(4, icon_size[0] // 6)  # ~16-20% extra around the circle
        
        # Create a comparison table for debugging all candidates
        if debug:
            candidate_results = []
        
        # For visualization, keep track of top 3 candidates
        top_candidates = []
        
        # Extract circle positions for occlusion mask creation
        all_circles = [(x, y, r) for x, y, r, _, _ in classified_candidates]
        
        for i, (x_center, y_center, radius, _, is_foreground) in enumerate(classified_candidates):
            half_w = icon_size[0] // 2 + pad // 2
            half_h = icon_size[1] // 2 + pad // 2
            x, y = x_center - half_w, y_center - half_h
            w = icon_size[0] + pad
            h = icon_size[1] + pad
                
            # Skip if region is out of bounds
            if x < 0 or y < 0 or x + w >= minimap.shape[1] or y + h >= minimap.shape[0]:
                if debug:
                    print(f"Skipping candidate {i} - out of bounds")
                continue
                
            # Create a region mask based on foreground/background classification
            region_occlusion_mask = create_occlusion_mask(
                (x_center, y_center, radius), 
                all_circles, 
                is_foreground, 
                (w, h)
            )
            
            # Extract the region
            region = minimap[y:y+h, x:x+w].copy()
            
            # Apply mask to region
            masked_region = cv2.bitwise_and(region, region, mask=region_occlusion_mask)
            
            # Resize icon to match region size
            resized_icon = cv2.resize(icon, (w, h), interpolation=cv2.INTER_AREA)

            # Resize masks to match region size
            circular_mask_resized = cv2.resize(icon_mask, (w, h), interpolation=cv2.INTER_AREA)
            icon_occlusion_mask = cv2.resize(region_occlusion_mask, (w, h), interpolation=cv2.INTER_AREA)

            # Combine circular and occlusion masks
            combined_mask = cv2.bitwise_and(circular_mask_resized, icon_occlusion_mask)

            # Apply combined mask to the template icon
            masked_icon = cv2.bitwise_and(resized_icon, resized_icon, mask=combined_mask)

            # Convert to grayscale for HOG
            region_gray = cv2.cvtColor(masked_region, cv2.COLOR_BGR2GRAY)
            masked_icon_gray = cv2.cvtColor(masked_icon, cv2.COLOR_BGR2GRAY)

            if champ == "Ziggs" and i == 0:
                cv2.imshow("icon_occlusion_mask", icon_occlusion_mask)
                cv2.imshow("masked_icon_gray", masked_icon_gray)

            # Compute template matching scores for each channel
            template_scores = []
            for c in range(3):  # BGR channels
                region_channel = masked_region[:, :, c]
                icon_channel = masked_icon[:, :, c]
                result = cv2.matchTemplate(region_channel, icon_channel, cv2.TM_CCOEFF_NORMED)
                template_scores.append(np.max(result))

            # Average template matching score across channels
            template_match_score = np.mean(template_scores)

            # Convert to HSV for color histogram
            region_hsv = cv2.cvtColor(masked_region, cv2.COLOR_BGR2HSV)
            masked_icon_hsv = cv2.cvtColor(masked_icon, cv2.COLOR_BGR2HSV)
            
            # Extract HOG features with occlusion mask
            region_hog_features, region_hog_image = hog(
                region_gray, 
                orientations=orientations, 
                pixels_per_cell=pixels_per_cell,
                cells_per_block=cells_per_block, 
                visualize=True,
                feature_vector=True
            )
            
            # Also extract HOG features for the masked icon
            masked_icon_hog_features, masked_icon_hog_image = hog(
                masked_icon_gray, 
                orientations=orientations, 
                pixels_per_cell=pixels_per_cell,
                cells_per_block=cells_per_block, 
                visualize=True,
                feature_vector=True
            )
            
            # Normalize HOG features
            if np.linalg.norm(region_hog_features) > 0:
                region_hog_features = region_hog_features / np.linalg.norm(region_hog_features)
            
            if np.linalg.norm(masked_icon_hog_features) > 0:
                masked_icon_hog_features = masked_icon_hog_features / np.linalg.norm(masked_icon_hog_features)
            
            # Calculate HOG similarity (inverse cosine distance) using masked icon features
            hog_similarity = 1.0 - cosine(masked_icon_hog_features, region_hog_features)
            # Ensure valid HOG similarity (handle potential NaN values)
            if np.isnan(hog_similarity):
                hog_similarity = 0.0
            
            # Extract color histograms for region with occlusion mask
            region_h_hist = cv2.calcHist([region_hsv], [0], region_occlusion_mask, [h_bins], h_ranges)
            region_s_hist = cv2.calcHist([region_hsv], [1], region_occlusion_mask, [s_bins], s_ranges)
            region_v_hist = cv2.calcHist([region_hsv], [2], region_occlusion_mask, [v_bins], v_ranges)

            # Extract color histograms for masked icon
            masked_icon_h_hist = cv2.calcHist([masked_icon_hsv], [0], combined_mask, [h_bins], h_ranges)
            masked_icon_s_hist = cv2.calcHist([masked_icon_hsv], [1], combined_mask, [s_bins], s_ranges)
            masked_icon_v_hist = cv2.calcHist([masked_icon_hsv], [2], combined_mask, [v_bins], v_ranges)
            
            # Normalize histograms
            cv2.normalize(region_h_hist, region_h_hist, 0, 1, cv2.NORM_MINMAX)
            cv2.normalize(region_s_hist, region_s_hist, 0, 1, cv2.NORM_MINMAX)
            cv2.normalize(region_v_hist, region_v_hist, 0, 1, cv2.NORM_MINMAX)
            
            cv2.normalize(masked_icon_h_hist, masked_icon_h_hist, 0, 1, cv2.NORM_MINMAX)
            cv2.normalize(masked_icon_s_hist, masked_icon_s_hist, 0, 1, cv2.NORM_MINMAX)
            cv2.normalize(masked_icon_v_hist, masked_icon_v_hist, 0, 1, cv2.NORM_MINMAX)
            
            # Handle NaN values in histograms
            region_h_hist = np.nan_to_num(region_h_hist)
            region_s_hist = np.nan_to_num(region_s_hist)
            region_v_hist = np.nan_to_num(region_v_hist)
            
            masked_icon_h_hist = np.nan_to_num(masked_icon_h_hist)
            masked_icon_s_hist = np.nan_to_num(masked_icon_s_hist)
            masked_icon_v_hist = np.nan_to_num(masked_icon_v_hist)
            
            # Calculate histogram similarities using Bhattacharyya distance
            h_similarity = cv2.compareHist(masked_icon_h_hist, region_h_hist, cv2.HISTCMP_BHATTACHARYYA)
            s_similarity = cv2.compareHist(masked_icon_s_hist, region_s_hist, cv2.HISTCMP_BHATTACHARYYA)
            v_similarity = cv2.compareHist(masked_icon_v_hist, region_v_hist, cv2.HISTCMP_BHATTACHARYYA)
            
            # Handle NaN values that can occur with empty histograms
            h_similarity = 0.0 if np.isnan(h_similarity) else h_similarity
            s_similarity = 0.0 if np.isnan(s_similarity) else s_similarity
            v_similarity = 0.0 if np.isnan(v_similarity) else v_similarity
            
            # Convert distances to similarities (Bhattacharyya distance of 0 means perfect match)
            h_similarity = 1.0 - h_similarity
            s_similarity = 1.0 - s_similarity
            v_similarity = 1.0 - v_similarity
            
            # Weighted average of HSV similarities
            color_similarity = 0.7 * h_similarity + 0.2 * s_similarity + 0.1 * v_similarity
            
            alpha = 0.5
            # Combine HOG and color features with weighted average
            combined_similarity = alpha * hog_similarity + (1 - alpha) * color_similarity
            
            # Handle any remaining NaN values
            if np.isnan(combined_similarity):
                combined_similarity = 0.0
            
            if debug:
                # Save all results for the comparison table
                candidate_results.append((i, x_center, y_center, is_foreground, hog_similarity, color_similarity, combined_similarity))
                
                # Keep track of top 5 candidates for visualization
                occlusion_vis = cv2.cvtColor(region_occlusion_mask, cv2.COLOR_GRAY2BGR)
                occlusion_vis[:, :, 0:2] = 0  # Make it red for visualization
                
                top_candidates.append((i, x_center, y_center, radius, is_foreground, masked_region, 
                                      region_hog_image, occlusion_vis, masked_icon.copy(), 
                                      hog_similarity, color_similarity, combined_similarity,
                                      template_match_score))
                top_candidates.sort(key=lambda x: x[-1], reverse=True)
                if len(top_candidates) > 5:
                    top_candidates = top_candidates[:5]
            
            if combined_similarity > best_similarity:
                best_similarity = combined_similarity
                best_match = (x_center, y_center)
                best_score = combined_similarity
                best_hog_similarity = hog_similarity
                best_color_similarity = color_similarity
                best_index = i
                
                if debug:
                    print(f"New best match found! Candidate: {i}, Score: {best_similarity:.3f}")
        
        # Display comparison table of all candidates
        if debug and candidate_results:
            print("\nCandidate comparison table for champion:", champ)
            print("Index | Center (x,y) | Foreground | HOG Score | Color Score | Combined Score")
            print("-" * 75)
            for idx, x, y, fg, hog_sim, color_sim, combined_sim in candidate_results:
                is_best = "✓" if idx == best_index else " "
                fg_str = "Yes" if fg else "No"
                print(f"{idx:5} | ({x:3},{y:3}) | {fg_str:9} | {hog_sim:.3f} | {color_sim:.3f} | {combined_sim:.3f} {is_best}")
            print("-" * 75)
            if best_index >= 0:
                print(f"Best match: Candidate {best_index} with score {best_similarity:.3f}")
            else:
                print("No suitable match found")
            
            # Visualize top candidates in a single window
            if top_candidates:
                # Create a grid visualization of top candidates
                rows = []
                for rank, (idx, x, y, radius, is_fg, region_img, hog_img, mask_img, masked_icon_candidate, hog_sim, color_sim, combined_sim, template_score) in enumerate(top_candidates):
                    # Convert HOG image to display format
                    hog_img = (hog_img * 255).astype(np.uint8)
                    
                    # Resize images for display
                    region_vis = cv2.resize(region_img, (100, 100))
                    hog_vis = cv2.cvtColor(cv2.resize(hog_img, (100, 100)), cv2.COLOR_GRAY2BGR)
                    mask_vis = cv2.resize(mask_img, (100, 100))
                    
                    # Create masked icon visualization
                    masked_icon_vis = cv2.resize(masked_icon_candidate, (100, 100))

                    if champ == "Ziggs" and idx == 0:
                        cv2.imshow("masked_icon_vis", masked_icon_vis)
                    
                    # Create color histograms for both masked icon and region
                    h_bins, s_bins, v_bins = 16, 16, 16
                    h_ranges, s_ranges, v_ranges = (0, 180), (0, 256), (0, 256)
                    
                    # Convert to HSV for histogram
                    masked_icon_hsv = cv2.cvtColor(masked_icon_candidate, cv2.COLOR_BGR2HSV)
                    region_hsv = cv2.cvtColor(region_img, cv2.COLOR_BGR2HSV)
                    
                    # Calculate histograms
                    icon_h_hist = cv2.calcHist([masked_icon_hsv], [0], combined_mask, [h_bins], h_ranges)
                    icon_s_hist = cv2.calcHist([masked_icon_hsv], [1], combined_mask, [s_bins], s_ranges)
                    icon_v_hist = cv2.calcHist([masked_icon_hsv], [2], combined_mask, [v_bins], v_ranges)
                    
                    region_h_hist = cv2.calcHist([region_hsv], [0], region_occlusion_mask, [h_bins], h_ranges)
                    region_s_hist = cv2.calcHist([region_hsv], [1], region_occlusion_mask, [s_bins], s_ranges)
                    region_v_hist = cv2.calcHist([region_hsv], [2], region_occlusion_mask, [v_bins], v_ranges)
                    
                    # Normalize histograms
                    cv2.normalize(icon_h_hist, icon_h_hist, 0, 1, cv2.NORM_MINMAX)
                    cv2.normalize(icon_s_hist, icon_s_hist, 0, 1, cv2.NORM_MINMAX)
                    cv2.normalize(icon_v_hist, icon_v_hist, 0, 1, cv2.NORM_MINMAX)
                    
                    cv2.normalize(region_h_hist, region_h_hist, 0, 1, cv2.NORM_MINMAX)
                    cv2.normalize(region_s_hist, region_s_hist, 0, 1, cv2.NORM_MINMAX)
                    cv2.normalize(region_v_hist, region_v_hist, 0, 1, cv2.NORM_MINMAX)
                    
                    # Create histogram visualizations
                    icon_hist_h = np.zeros((100, h_bins * 10, 3), dtype=np.uint8)
                    icon_hist_s = np.zeros((100, s_bins * 10, 3), dtype=np.uint8)
                    icon_hist_v = np.zeros((100, v_bins * 10, 3), dtype=np.uint8)
                    
                    region_hist_h = np.zeros((100, h_bins * 10, 3), dtype=np.uint8)
                    region_hist_s = np.zeros((100, s_bins * 10, 3), dtype=np.uint8)
                    region_hist_v = np.zeros((100, v_bins * 10, 3), dtype=np.uint8)
                    
                    # Draw icon histograms
                    for i in range(h_bins):
                        h_val = int(icon_h_hist[i] * 100)
                        cv2.rectangle(icon_hist_h, (i * 10, 100), ((i + 1) * 10, 100 - h_val), (255, 0, 0), -1)
                        
                    for i in range(s_bins):
                        s_val = int(icon_s_hist[i] * 100)
                        cv2.rectangle(icon_hist_s, (i * 10, 100), ((i + 1) * 10, 100 - s_val), (0, 255, 0), -1)
                        
                    for i in range(v_bins):
                        v_val = int(icon_v_hist[i] * 100)
                        cv2.rectangle(icon_hist_v, (i * 10, 100), ((i + 1) * 10, 100 - v_val), (0, 0, 255), -1)
                    
                    # Draw region histograms
                    for i in range(h_bins):
                        h_val = int(region_h_hist[i] * 100)
                        cv2.rectangle(region_hist_h, (i * 10, 100), ((i + 1) * 10, 100 - h_val), (255, 0, 0), -1)
                        
                    for i in range(s_bins):
                        s_val = int(region_s_hist[i] * 100)
                        cv2.rectangle(region_hist_s, (i * 10, 100), ((i + 1) * 10, 100 - s_val), (0, 255, 0), -1)
                        
                    for i in range(v_bins):
                        v_val = int(region_v_hist[i] * 100)
                        cv2.rectangle(region_hist_v, (i * 10, 100), ((i + 1) * 10, 100 - v_val), (0, 0, 255), -1)
                    
                    # Combine histograms
                    icon_hist = np.vstack([icon_hist_h, icon_hist_s, icon_hist_v])
                    region_hist = np.vstack([region_hist_h, region_hist_s, region_hist_v])
                    
                    # Add labels to histograms
                    cv2.putText(icon_hist, "Template Histograms", (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                    cv2.putText(region_hist, "Candidate Histograms", (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                    
                    # Resize histograms to match info panel height
                    icon_hist = cv2.resize(icon_hist, (icon_hist.shape[1], 140))
                    region_hist = cv2.resize(region_hist, (region_hist.shape[1], 140))

                    # Create info area with additional metrics
                    info = np.ones((140, 200, 3), dtype=np.uint8) * 50
                    cv2.putText(info, f"Candidate #{idx}", (5, 20), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    cv2.putText(info, f"Position: ({x}, {y})", (5, 40), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    cv2.putText(info, f"Foreground: {is_fg}", (5, 60), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    cv2.putText(info, f"HOG: {hog_sim:.3f}", (5, 80), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    cv2.putText(info, f"Color: {color_sim:.3f}", (5, 100), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    cv2.putText(info, f"Template: {template_score:.3f}", (5, 120), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
                    # Create row with all visualizations
                    top_row = np.hstack([region_vis, masked_icon_vis, mask_vis, hog_vis])
                    bottom_row = np.hstack([icon_hist, region_hist, info])
                    
                    # Resize bottom row to match top row width
                    if bottom_row.shape[1] != top_row.shape[1]:
                        bottom_row = cv2.resize(bottom_row, (top_row.shape[1], bottom_row.shape[0]))
                    
                    # Combine rows
                    row = np.vstack([top_row, bottom_row])
                    rows.append(row)
                
                # Stack rows vertically
                top_candidates_vis = np.vstack(rows) if len(rows) > 0 else None
                if top_candidates_vis is not None:
                    # Resize for better visibility (double size)
                    scale_factor = 2
                    enlarged = cv2.resize(
                        top_candidates_vis,
                        (top_candidates_vis.shape[1] * scale_factor, top_candidates_vis.shape[0] * scale_factor),
                        interpolation=cv2.INTER_LINEAR
                    )
                    cv2.namedWindow(f'Top Candidates - {champ}', cv2.WINDOW_NORMAL)
                    cv2.imshow(f'Top Candidates - {champ}', enlarged)

        if best_match is not None:
            x, y = best_match
            position = mapper.normalize_coordinates(x, y, minimap.shape[:2])
            positions_xy[champ] = position
            location = mapper.describe_location(x, y, minimap.shape[:2])
            positions_str[champ] = location
            # Add match result to list for final visualization
            matches_list.append((champ, best_match, best_score))
            
            if debug:
                print(f"Final position for {champ}: {location}")
                print(f"Match score: {best_score:.3f} (HOG: {best_hog_similarity:.3f}, Color: {best_color_similarity:.3f})")
        else:
            positions_str[champ] = "Not visible"
            if debug:
                print(f"No match found above threshold for {champ}")
    
    # Process all champions
    for champ in ally_champions:
        process_champion(champ, blue_filtered, blue_classified, True, blue_matches)

    for champ in enemy_champions:
        process_champion(champ, red_filtered, red_classified, False, red_matches)
    
    # Show final matches visualization
    if debug:
        final_vis = minimap.copy()
        
        # First draw all the detected circles with their foreground/background status
        for i, (x_center, y_center, radius, _, is_foreground) in enumerate(blue_classified):
            # Draw circle outline
            color = (255, 0, 0) if is_foreground else (128, 128, 255)  # Dark blue for background
            cv2.circle(final_vis, (x_center, y_center), radius, color, 1)
        
        for i, (x_center, y_center, radius, _, is_foreground) in enumerate(red_classified):
            # Draw circle outline
            color = (0, 0, 255) if is_foreground else (128, 0, 128)  # Purple for background
            cv2.circle(final_vis, (x_center, y_center), radius, color, 1)
        
        # Draw ally matches with solid circles
        for champ, pos, score in blue_matches:
            cv2.circle(final_vis, pos, 5, (255, 255, 0), -1)  # Yellow dot for center
            cv2.putText(final_vis, f"{champ} ({score:.2f})", (pos[0] - 20, pos[1] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # Draw enemy matches
        for champ, pos, score in red_matches:
            cv2.circle(final_vis, pos, 5, (0, 255, 255), -1)  # Cyan dot for center
            cv2.putText(final_vis, f"{champ} ({score:.2f})", (pos[0] - 20, pos[1] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # Add legend
        legend_y = 20
        cv2.putText(final_vis, "Blue Team:", (10, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        legend_y += 20
        cv2.circle(final_vis, (20, legend_y), 5, (255, 0, 0), 1)
        cv2.putText(final_vis, "Foreground", (30, legend_y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        legend_y += 20
        cv2.circle(final_vis, (20, legend_y), 5, (128, 128, 255), 1)
        cv2.putText(final_vis, "Background", (30, legend_y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        legend_y += 30
        cv2.putText(final_vis, "Red Team:", (10, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        legend_y += 20
        cv2.circle(final_vis, (20, legend_y), 5, (0, 0, 255), 1)
        cv2.putText(final_vis, "Foreground", (30, legend_y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        legend_y += 20
        cv2.circle(final_vis, (20, legend_y), 5, (128, 0, 128), 1)
        cv2.putText(final_vis, "Background", (30, legend_y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        cv2.imshow('Final Champion Detections with Occlusion Handling', final_vis)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    
    return positions_str, positions_xy


if __name__ == "__main__":
    import time
    start_time = time.time()

    minimap_path = "vision/screenshots/20250519_142807_minimap.png"
    ally_champions = ["Ahri", "Ziggs", "Zyra", "Nasus", "Wukong"]  # Blue team
    enemy_champions = ["Lulu", "Cho'Gath", "Lucian", "Urgot", "Xin Zhao"]  # Red team
    
    minimap_path = "vision/screenshots/20250516_201606_minimap.png"
    ally_champions = ["Vayne", "Poppy", "Viktor", "Shyvana", "Wukong"]  # Blue team
    enemy_champions = ["Nasus", "Vex", "Sejuani", "Urgot", "Xin Zhao"]  # Red team

    positions_str, positions_xy = detect_champion_positions(minimap_path, ally_champions, enemy_champions, debug=True)
    for champ, pos in positions_str.items():
        print(champ, pos)

    end_time = time.time()
    print(f"Time taken: {end_time - start_time:.2f} seconds")

    # Print formatted positions
    print("\nChampion Positions:")
    # print(format_champion_positions(positions_str, positions_xy, ally_champions, enemy_champions))
