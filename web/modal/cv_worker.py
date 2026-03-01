"""
OpenCV-based construction drawing analyzer for Modal.com

Deploy with: modal deploy cv_worker.py
Test with: modal run cv_worker.py

This worker analyzes construction drawings and photos to extract:
- Dimensions and scale information
- Room counts
- Drawing type classification
"""

import modal
import base64
import io
from typing import Optional

# Define the Modal app
app = modal.App("construction-cv-worker")

# Define the image with OpenCV and dependencies
cv_image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "opencv-python-headless",
    "numpy",
    "pillow",
)


@app.function(image=cv_image, timeout=60)
@modal.web_endpoint(method="POST")
def analyze(image_base64: str) -> dict:
    """
    Analyze a construction drawing or photo.

    Args:
        image_base64: Base64 encoded image data

    Returns:
        dict with dimensions, room_count, drawing_type, and confidence
    """
    import cv2
    import numpy as np
    from PIL import Image

    try:
        # Decode base64 image
        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data))

        # Convert to OpenCV format
        img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Get image dimensions
        height, width = gray.shape[:2]

        # Analyze the image
        drawing_type = classify_drawing_type(gray)
        room_count = count_rooms(gray) if drawing_type == 'floor_plan' else 0
        dimensions = extract_dimensions(gray, drawing_type)

        # Calculate confidence based on analysis quality
        confidence = calculate_confidence(drawing_type, room_count, dimensions)

        return {
            "dimensions": dimensions,
            "room_count": room_count,
            "drawing_type": drawing_type,
            "confidence": confidence,
            "image_size": {"width": width, "height": height},
        }

    except Exception as e:
        return {
            "dimensions": {"scale_detected": False},
            "room_count": 0,
            "drawing_type": "unknown",
            "confidence": 0.0,
            "error": str(e),
        }


def classify_drawing_type(gray) -> str:
    """
    Classify the type of drawing based on image features.

    Uses edge detection and line analysis to determine if the image
    is a floor plan, elevation, site plan, or photo.
    """
    import cv2
    import numpy as np

    height, width = gray.shape[:2]

    # Detect edges
    edges = cv2.Canny(gray, 50, 150)

    # Detect lines using Hough transform
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi/180,
        threshold=50,
        minLineLength=50,
        maxLineGap=10
    )

    if lines is None:
        # Few lines suggest a photo
        return "photo"

    # Analyze line orientations
    horizontal_lines = 0
    vertical_lines = 0

    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)

        if angle < 15 or angle > 165:  # Horizontal
            horizontal_lines += 1
        elif 75 < angle < 105:  # Vertical
            vertical_lines += 1

    total_lines = len(lines)
    line_density = total_lines / (width * height) * 1000000

    # Classification logic
    if line_density > 50:
        # High line density suggests architectural drawing
        h_v_ratio = horizontal_lines / max(vertical_lines, 1)

        if 0.5 < h_v_ratio < 2.0:
            # Balanced horizontal/vertical suggests floor plan
            return "floor_plan"
        elif h_v_ratio < 0.5:
            # More vertical lines suggest elevation
            return "elevation"
        else:
            # More horizontal lines suggest site plan
            return "site_plan"
    else:
        # Low line density suggests photo or simple diagram
        return "photo"


def count_rooms(gray) -> int:
    """
    Count enclosed spaces (rooms) in a floor plan.

    Uses contour detection to find enclosed areas that could be rooms.
    """
    import cv2
    import numpy as np

    height, width = gray.shape[:2]
    min_room_area = (width * height) * 0.01  # Minimum 1% of image
    max_room_area = (width * height) * 0.4   # Maximum 40% of image

    # Apply threshold
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

    # Morphological operations to clean up
    kernel = np.ones((5, 5), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

    # Find contours
    contours, _ = cv2.findContours(
        binary,
        cv2.RETR_TREE,
        cv2.CHAIN_APPROX_SIMPLE
    )

    # Filter contours by area (room-sized)
    room_count = 0
    for contour in contours:
        area = cv2.contourArea(contour)
        if min_room_area < area < max_room_area:
            # Check if roughly rectangular (rooms usually are)
            _, _, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / max(h, 1)
            if 0.3 < aspect_ratio < 3.0:
                room_count += 1

    return room_count


def extract_dimensions(gray, drawing_type: str) -> dict:
    """
    Attempt to extract dimension information from the drawing.

    Looks for scale bars and dimension lines.
    """
    import cv2
    import numpy as np

    height, width = gray.shape[:2]

    result = {
        "scale_detected": False,
        "estimated_sqft": None,
        "rooms": [],
    }

    if drawing_type not in ["floor_plan", "site_plan"]:
        return result

    # Look for scale bar (typically a line with text nearby)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi/180,
        threshold=100,
        minLineLength=100,
        maxLineGap=5
    )

    if lines is not None:
        # Find the longest horizontal line (potential scale bar)
        longest_h_line = None
        longest_length = 0

        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)

            if angle < 10 or angle > 170:  # Horizontal
                length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
                if length > longest_length:
                    longest_length = length
                    longest_h_line = line[0]

        if longest_h_line is not None and longest_length > width * 0.1:
            # Found a significant horizontal line
            # Estimate scale based on typical floor plan conventions
            # Assume the drawing fills ~80% of the image width
            drawing_width_px = width * 0.8

            # Common residential sizes: 30-60 feet wide
            # Estimate 45 feet as average
            estimated_width_ft = 45
            pixels_per_foot = drawing_width_px / estimated_width_ft

            # Calculate estimated sqft based on image dimensions
            drawing_height_px = height * 0.8
            estimated_height_ft = drawing_height_px / pixels_per_foot
            estimated_sqft = estimated_width_ft * estimated_height_ft

            result["scale_detected"] = True
            result["estimated_sqft"] = int(estimated_sqft)
            result["scale_factor"] = pixels_per_foot

    return result


def calculate_confidence(drawing_type: str, room_count: int, dimensions: dict) -> float:
    """
    Calculate overall confidence in the analysis.
    """
    confidence = 0.3  # Base confidence

    # Drawing type confidence
    if drawing_type in ["floor_plan", "elevation"]:
        confidence += 0.2
    elif drawing_type == "photo":
        confidence += 0.1

    # Room count confidence (if floor plan)
    if drawing_type == "floor_plan" and room_count > 0:
        confidence += min(0.2, room_count * 0.05)

    # Scale detection confidence
    if dimensions.get("scale_detected"):
        confidence += 0.2

    return min(confidence, 1.0)


# Test function for local development
@app.local_entrypoint()
def main():
    """Test the analyzer with a sample image."""
    import os

    # Create a simple test image
    test_image = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10\x08\x02\x00\x00\x00\x90\x91h6\x00\x00\x00\x1dIDAT\x08\x99c\xf8\x0f\x00\x00\x01\x01\x01\x00\x18\xdd\x8d\xb4\xfc\xda\xbc!\x00\x00\x00\x00IEND\xaeB`\x82'

    test_b64 = base64.b64encode(test_image).decode()

    result = analyze.remote(test_b64)
    print("Analysis result:", result)
