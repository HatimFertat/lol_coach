import cv2
import numpy as np
from pathlib import Path
from .minimap_description import create_minimap_descriptor, parse_annotations
import xml.etree.ElementTree as ET

class MinimapCoordinateMapper:
    def __init__(self, reference_size=(512, 512)):
        """
        Initialize the coordinate mapper.
        
        Args:
            reference_size: The size of our reference minimap (width, height)
        """
        self.reference_size = reference_size
        self.descriptor = create_minimap_descriptor("vision/map_semantics/annotations.xml")
        self.regions = parse_annotations("vision/map_semantics/annotations.xml")
        
        # Define reference points in the 512x512 minimap
        # These are key points that we can reliably identify in any minimap
        self.reference_points = np.float32([
            [256, 256],  # Center
            [256, 0],    # Top center
            [256, 512],  # Bottom center
            [0, 256],    # Left center
            [512, 256],  # Right center
            [0, 0],      # Top-left
            [512, 0],    # Top-right
            [0, 512],    # Bottom-left
            [512, 512]   # Bottom-right
        ])
        
    def compute_homography(self, real_minimap_size):
        """
        Compute homography matrix between reference and real minimap.
        
        Args:
            real_minimap_size: (width, height) of the real minimap
            
        Returns:
            Homography matrix
        """
        width, height = real_minimap_size
        
        # Define corresponding points in the real minimap
        # These points should correspond to the reference points
        real_points = np.float32([
            [width/2, height/2],    # Center
            [width/2, 0],           # Top center
            [width/2, height],      # Bottom center
            [0, height/2],          # Left center
            [width, height/2],      # Right center
            [0, 0],                 # Top-left
            [width, 0],             # Top-right
            [0, height],            # Bottom-left
            [width, height]         # Bottom-right
        ])
        
        # Compute homography matrix
        H, _ = cv2.findHomography(self.reference_points, real_points)
        return H
    
    def normalize_coordinates(self, x, y, minimap_size):
        """
        Convert coordinates from a real minimap to our reference 512x512 minimap using homography.
        
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
    
    def denormalize_coordinates(self, x, y, minimap_size):
        """
        Convert coordinates from reference 512x512 minimap to real minimap size using homography.
        
        Args:
            x, y: Coordinates in the reference minimap
            minimap_size: (width, height) of the real minimap
            
        Returns:
            (x, y) coordinates in the real minimap
        """
        H = self.compute_homography(minimap_size)
        
        # Convert point to homogeneous coordinates and reshape for perspectiveTransform
        point = np.float32([[x, y]])
        transformed = cv2.perspectiveTransform(point.reshape(-1, 1, 2), H)
        
        return transformed[0][0]
    
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
        # norm_x, norm_y = x, y
        return self.descriptor(norm_x, norm_y)
    
    def visualize_regions(self, image_path, output_path=None, alpha=0.3):
        """
        Visualize the annotated regions on top of a minimap image.
        
        Args:
            image_path: Path to the minimap image
            output_path: Path to save the visualization (if None, displays it)
            alpha: Transparency of the overlay (0-1)
        """
        # Read the image
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Could not read image: {image_path}")
        
        # Create a copy for drawing
        overlay = img.copy()
        minimap_size = img.shape[1], img.shape[0]
        
        # Draw each region
        for region in self.regions:
            # Get points of the polygon
            if isinstance(region['polygon'], np.ndarray):
                points = region['polygon']
            else:
                points = np.array(region['polygon'].exterior.coords, dtype=np.float32)
            
            # Convert points to the target image size
            scaled_points = []
            for x, y in points:
                real_x, real_y = self.denormalize_coordinates(x, y, minimap_size)
                scaled_points.append([real_x, real_y])
            scaled_points = np.array(scaled_points, dtype=np.int32)
            
            # Draw the polygon
            cv2.polylines(overlay, [scaled_points], True, (0, 255, 0), 2)
        
        # Blend the overlay with the original image
        result = cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0)
        
        if output_path:
            cv2.imwrite(str(output_path), result)
        else:
            cv2.imshow('Annotated Regions', result)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

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
    print("Press 'v' to visualize regions.")
    
    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r'):
            display_img = img.copy()
            cv2.imshow('Minimap', display_img)
        elif key == ord('v'):
            mapper.visualize_regions(image_path)
    
    cv2.destroyAllWindows()

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python minimap_coordinate_mapper.py <path_to_minimap_image>")
        sys.exit(1)
    
    image_path = Path(sys.argv[1])
    interactive_point_picker(image_path) 