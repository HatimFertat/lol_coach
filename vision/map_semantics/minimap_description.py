import xml.etree.ElementTree as ET
import numpy as np
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
import math

def parse_annotations(xml_path):
    """Parse CVAT XML annotations and return a list of labeled regions."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    regions = []
    for polygon in root.findall('.//polygon'):
        label = polygon.get('label')
        points_str = polygon.get('points')
        if points_str:
            points = []
            for point_str in points_str.split(';'):
                x, y = map(float, point_str.split(','))
                points.append((x, y))
            regions.append({
                'label': label,
                'polygon': Polygon(points)
            })
    
    for ellipse in root.findall('.//ellipse'):
        label = ellipse.get('label')
        cx = float(ellipse.get('cx'))
        cy = float(ellipse.get('cy'))
        rx = float(ellipse.get('rx'))
        ry = float(ellipse.get('ry'))
        rotation = float(ellipse.get('rotation', 0))
        
        # Create a polygon approximation of the ellipse
        points = []
        for angle in np.linspace(0, 2*math.pi, 32):
            x = cx + rx * math.cos(angle) * math.cos(math.radians(rotation)) - ry * math.sin(angle) * math.sin(math.radians(rotation))
            y = cy + rx * math.cos(angle) * math.sin(math.radians(rotation)) + ry * math.sin(angle) * math.cos(math.radians(rotation))
            points.append((x, y))
        
        regions.append({
            'label': label,
            'polygon': Polygon(points)
        })
    
    return regions

def find_closest_regions(point, regions, n=3):
    """Find the n closest labeled regions to a given point."""
    point = Point(point)
    distances = []
    
    for region in regions:
        # Calculate minimum distance between point and polygon
        distance = point.distance(region['polygon'])
        distances.append((distance, region['label']))
    
    # Sort by distance and get top n
    distances.sort()
    return [label for _, label in distances[:n]]

def get_location_description(x, y, regions, n_closest=3):
    """
    Get a description of a location based on nearby labeled regions.
    
    Args:
        x, y: Coordinates on the minimap (0-512)
        regions: List of labeled regions from parse_annotations
        n_closest: Number of closest regions to consider
        
    Returns:
        String description of the location
    """
    point = (x, y)
    point_obj = Point(point)
    
    # Find all regions that contain the point
    containing_regions = []
    for region in regions:
        if point_obj.within(region['polygon']):
            containing_regions.append(region['label'])
    
    if containing_regions:
        if len(containing_regions) == 1:
            return f"inside {containing_regions[0]}"
        else:
            return f"inside {', '.join(containing_regions[:-1])} and {containing_regions[-1]}"
    
    # If not inside any region, describe based on proximity
    closest_regions = find_closest_regions(point, regions, n_closest)
    if len(closest_regions) == 1:
        return f"near {closest_regions[0]}"
    else:
        return f"between {', '.join(closest_regions[:-1])} and {closest_regions[-1]}"

def create_minimap_descriptor(xml_path):
    """
    Create a function that maps points to location descriptions.
    
    Args:
        xml_path: Path to the CVAT XML annotations file
        
    Returns:
        Function that takes (x,y) coordinates and returns a location description
    """
    regions = parse_annotations(xml_path)
    
    def describe_location(x, y):
        return get_location_description(x, y, regions)
    
    return describe_location

# Example usage:
if __name__ == "__main__":
    descriptor = create_minimap_descriptor("vision/map_semantics/annotations.xml")
    
    # Test some points
    test_points = [
        (256, 256),  # Center of map
        (100, 100),  # Top-left area
        (400, 400),  # Bottom-right area
        (27, 237),
    ]
    
    for x, y in test_points:
        print(f"Location at ({x}, {y}): {descriptor(x, y)}")
