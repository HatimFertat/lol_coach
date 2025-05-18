import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from vision.map_semantics.minimap_coordinate_mapper import MinimapCoordinateMapper
from game_context.game_state import GameStateContext, role_mapping
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

def detect_champion_positions(
    minimap_path: str,
    ally_champions: List[str],
    enemy_champions: List[str],
    threshold: float = 0.4,
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
        cv2.imshow('Blue Filtered', blue_filtered)
        cv2.imshow('Red Filtered', red_filtered)
    
    # Process each team's champions
    positions_str = {}
    positions_xy = {}
    icons_dir = Path("vision/icons")
    
    def process_champion(champ: str, filtered_minimap: np.ndarray, is_ally: bool) -> None:
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
        
        # Resize icon
        try:
            icon = cv2.resize(icon, icon_size, interpolation=cv2.INTER_AREA)
            if debug:
                print(f"Resized icon shape: {icon.shape}")
                cv2.imshow(f'Icon - {champ}', icon)
        except cv2.error as e:
            print(f"Error resizing icon for {champ}: {e}")
            positions_str[champ] = "Not visible"
            return
        
        # Find contours in filtered image
        contours, _ = cv2.findContours(filtered_minimap, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if debug:
            print(f"Found {len(contours)} contours")
        
        best_match = None
        best_val = threshold
        
        for i, contour in enumerate(contours):
            (x, y), r = cv2.minEnclosingCircle(contour)
            center = (int(x), int(y))
            radius = int(r)
            
            # Check if circle size is reasonable for a champion icon
            if 12 < r < 40:
                if debug:
                    cv2.circle(minimap, center, radius, (255, 0, 0) if is_ally else (0, 0, 255), 1)
                
                x, y = int(x) - radius, int(y) - radius
                w = h = radius * 2
                
                # Ensure coordinates are within bounds
                if x >= 0 and y >= 0 and x + w < minimap.shape[1] and y + h < minimap.shape[0]:
                    # Extract region and try template matching
                    region = minimap[y:y+h, x:x+w]
                    
                    if debug:
                        print(f"\nContour {i}:")
                        print(f"Region shape: {region.shape}")
                        print(f"Region bounds: x={x}, y={y}, w={w}, h={h}")
                    
                    result = cv2.matchTemplate(region, icon, cv2.TM_CCOEFF_NORMED)
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                    
                    if debug:
                        print(f"Match value: {max_val:.3f} (threshold: {threshold})")
                        # Show the region being matched
                        cv2.imshow(f'Region {i} - {champ}', region)
                        # Show the match result heatmap
                        # result_vis = cv2.normalize(result, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
                        # result_vis = cv2.applyColorMap(result_vis, cv2.COLORMAP_JET)
                        # cv2.imshow(f'Match Heatmap {i} - {champ}', result_vis)
                    
                    if max_val > best_val:
                        best_val = max_val
                        best_match = (x + max_loc[0] + w//2, y + max_loc[1] + h//2)
                        if debug:
                            print(f"New best match found! Value: {max_val:.3f}")
        
        if best_match is not None:
            x, y = best_match
            position = mapper.normalize_coordinates(x, y, minimap.shape[:2])
            positions_xy[champ] = position
            location = mapper.describe_location(x, y, minimap.shape[:2])
            positions_str[champ] = location
            if debug:
                print(f"Final position: {location}")
        else:
            positions_str[champ] = "Not visible"
            if debug:
                print("No match found above threshold")
            
        if debug:
            minimap_vis = minimap.copy()
            if best_match is not None:
                cv2.circle(minimap_vis, best_match, 5, (255, 0, 0) if is_ally else (0, 0, 255), -1)
                cv2.putText(minimap_vis, champ, (best_match[0] - 20, best_match[1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.imshow(f'Detection - {champ}', minimap_vis)
    
    # Process allies (blue team)
    for champ in ally_champions:
        process_champion(champ, blue_filtered, True)
    
    # Process enemies (red team)
    for champ in enemy_champions:
        process_champion(champ, red_filtered, False)
    
    if debug:
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    
    return positions_str, positions_xy

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

if __name__ == "__main__":
    # Example usage
    minimap_path = "vision/screenshots/20250519_000056_minimap.png"
    
    # Example champion lists
    ally_champions = ["Kai'sa", "Galio", "Veigar", "Master Yi", "Darius"]  # Blue team
    enemy_champions = ["Rumble", "Soraka", "Jinx", "Irelia", "Xin Zhao"]  # Red team
    
    positions_str, positions_xy = detect_champion_positions(minimap_path, ally_champions, enemy_champions, debug=False)
    
    # Print formatted positions
    print("\nChampion Positions:")
    print(format_champion_positions(positions_str, positions_xy, ally_champions, enemy_champions))
    
    # Example of distance calculation
    print("\nDistances from Darius to allies:")
    champ = "Darius"
    ally_distances = calculate_champion_distances(positions_xy, champ, ally_champions)
    for champ, dist in ally_distances.items():
        if dist is not None:
            print(f"{champ}: {dist:.0f} units")
        else:
            print(f"{champ}: Not visible")
    
    print("\nDistances from Darius to enemies:")
    enemy_distances = calculate_champion_distances(positions_xy, champ, enemy_champions)
    for champ, dist in enemy_distances.items():
        if dist is not None:
            print(f"{champ}: {dist:.0f} units")
        else:
            print(f"{champ}: Not visible")