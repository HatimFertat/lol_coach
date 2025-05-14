import cv2
import numpy as np
from pathlib import Path
from .minimap_description import create_minimap_descriptor

class MinimapCoordinateMapper:
    def __init__(self, reference_size=(512, 512)):
        """
        Initialize the coordinate mapper.
        
        Args:
            reference_size: The size of our reference minimap (width, height)
        """
        self.reference_size = reference_size
        self.descriptor = create_minimap_descriptor("vision/map_semantics/annotations.xml")
        
    def normalize_coordinates(self, x, y, minimap_size):
        """
        Convert coordinates from a real minimap to our reference 512x512 minimap.
        
        Args:
            x, y: Coordinates in the real minimap
            minimap_size: (width, height) of the real minimap
            
        Returns:
            (x, y) coordinates normalized to 512x512
        """
        width, height = minimap_size
        norm_x = (x / width) * self.reference_size[0]
        norm_y = (y / height) * self.reference_size[1]
        return norm_x, norm_y
    
    def describe_location(self, x, y, minimap_size):
        """
        Get location description for a point in a real minimap.
        
        Args:
            x, y: Coordinates in the real minimap
            minimap_size: (width, height) of the real minimap
            
        Returns:
            String description of the location
        """
        norm_x, norm_y = self.normalize_coordinates(x, y, minimap_size)
        return self.descriptor(norm_x, norm_y)

def get_minimap_size(image_path):
    """Get the size of a minimap image."""
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")
    return img.shape[1], img.shape[0]  # width, height

def interactive_point_picker(image_path):
    """
    Interactive tool to pick points on a minimap and get their descriptions.
    
    Args:
        image_path: Path to the minimap image
    """
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")
    
    # Create a copy of the image for drawing
    display_img = img.copy()
    minimap_size = img.shape[1], img.shape[0]
    mapper = MinimapCoordinateMapper()
    
    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            description = mapper.describe_location(x, y, minimap_size)
            print(f"Location at ({x}, {y}): {description}")
            
            # Draw point and label on image
            cv2.circle(display_img, (x, y), 3, (0, 255, 0), -1)
            
            # Split description into lines for better readability
            words = description.split()
            lines = []
            current_line = []
            for word in words:
                current_line.append(word)
                if len(' '.join(current_line)) > 30:  # Adjust line length as needed
                    lines.append(' '.join(current_line[:-1]))
                    current_line = [word]
            if current_line:
                lines.append(' '.join(current_line))
            
            # Draw each line of text
            for i, line in enumerate(lines):
                y_offset = y - 5 - (i * 20)  # Adjust vertical spacing
                cv2.putText(display_img, line, (x + 5, y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            cv2.imshow('Minimap', display_img)
    
    cv2.namedWindow('Minimap')
    cv2.setMouseCallback('Minimap', mouse_callback)
    cv2.imshow('Minimap', display_img)
    
    print("Click on the minimap to get location descriptions.")
    print("Press 'q' to quit.")
    print("Press 'r' to reset the image.")
    
    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r'):
            display_img = img.copy()
            cv2.imshow('Minimap', display_img)
    
    cv2.destroyAllWindows()

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python minimap_coordinate_mapper.py <path_to_minimap_image>")
        sys.exit(1)
    
    image_path = Path(sys.argv[1])
    interactive_point_picker(image_path) 