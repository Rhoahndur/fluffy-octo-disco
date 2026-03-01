#!/usr/bin/env python3
"""
Local OpenCV testing script for construction drawing analysis.
Run: python test_cv_local.py <image_path>

Install dependencies:
  pip install opencv-python numpy pillow pytesseract

For OCR, also install Tesseract:
  macOS: brew install tesseract
  Ubuntu: sudo apt-get install tesseract-ocr
"""

import cv2
import numpy as np
import sys
import json
from pathlib import Path

# Optional OCR support
try:
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    print("Note: pytesseract not installed. OCR features disabled.")
    print("Install with: pip install pytesseract")


def load_image(path: str) -> np.ndarray:
    """Load image from file path."""
    img = cv2.imread(path)
    if img is None:
        raise ValueError(f"Could not load image: {path}")
    return img


def preprocess(img: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Convert to grayscale and create binary threshold."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Adaptive threshold works better for drawings with varying lighting
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
    )
    return gray, binary


def detect_lines(gray: np.ndarray) -> dict:
    """Detect lines using Hough transform - for walls, edges."""
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # Detect lines
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=50,
        minLineLength=30,
        maxLineGap=10
    )

    if lines is None:
        return {"total_lines": 0, "total_length_px": 0, "horizontal": 0, "vertical": 0}

    total_length = 0
    horizontal_count = 0
    vertical_count = 0

    for line in lines:
        x1, y1, x2, y2 = line[0]
        length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        total_length += length

        # Classify as horizontal or vertical
        angle = abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
        if angle < 15 or angle > 165:
            horizontal_count += 1
        elif 75 < angle < 105:
            vertical_count += 1

    return {
        "total_lines": len(lines),
        "total_length_px": round(total_length, 2),
        "horizontal": horizontal_count,
        "vertical": vertical_count,
    }


def detect_rooms(binary: np.ndarray, min_area_ratio: float = 0.005) -> dict:
    """Count enclosed spaces (rooms) using contour detection."""
    # Morphological closing to connect nearby lines
    kernel = np.ones((5, 5), np.uint8)
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)

    # Find contours
    contours, _ = cv2.findContours(closed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    # Filter by area - rooms should be significant portion of image
    img_area = binary.shape[0] * binary.shape[1]
    min_area = img_area * min_area_ratio
    max_area = img_area * 0.5  # No single room should be > 50% of image

    room_contours = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_area < area < max_area:
            # Check if roughly rectangular (rooms usually are)
            perimeter = cv2.arcLength(cnt, True)
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter ** 2)
                # Rectangles have circularity around 0.78
                if circularity > 0.3:
                    room_contours.append({
                        "area_px": area,
                        "perimeter_px": perimeter,
                        "circularity": round(circularity, 3)
                    })

    total_room_area = sum(r["area_px"] for r in room_contours)

    return {
        "room_count": len(room_contours),
        "total_room_area_px": total_room_area,
        "rooms": room_contours[:10],  # Limit detail output
    }


def detect_rectangles(gray: np.ndarray) -> dict:
    """Detect rectangular shapes - potential doors, windows, fixtures."""
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    rectangles = {"small": 0, "medium": 0, "large": 0}
    door_candidates = []
    window_candidates = []

    img_area = gray.shape[0] * gray.shape[1]

    for cnt in contours:
        # Approximate contour to polygon
        epsilon = 0.02 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)

        # Check if it's a rectangle (4 corners)
        if len(approx) == 4:
            area = cv2.contourArea(cnt)
            area_ratio = area / img_area

            if area_ratio < 0.001:
                continue  # Too small, noise

            # Get bounding rectangle
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = max(w, h) / min(w, h) if min(w, h) > 0 else 0

            # Classify by size relative to image
            if area_ratio < 0.01:
                rectangles["small"] += 1
                # Door-like: tall and narrow (aspect ratio 1.5-3)
                if 1.5 < aspect_ratio < 3 and h > w:
                    door_candidates.append({"w": w, "h": h, "area": area})
            elif area_ratio < 0.05:
                rectangles["medium"] += 1
                # Window-like: wider or square
                if aspect_ratio < 2:
                    window_candidates.append({"w": w, "h": h, "area": area})
            else:
                rectangles["large"] += 1

    return {
        "rectangle_counts": rectangles,
        "door_candidates": len(door_candidates),
        "window_candidates": len(window_candidates),
    }


def extract_scale_from_text(text: str) -> dict:
    """
    Extract architectural scale notation from OCR text.
    Returns scale info for pixel-to-feet conversion.
    """
    import re

    result = {
        "scale_found": False,
        "scale_text": None,
        "inches_per_foot": None,
        "ratio": None,
    }

    text_clean = text.replace('\n', ' ').replace('  ', ' ')

    # Pattern 1: Fractional inch = feet (1/4" = 1'-0")
    frac_pattern = r'(\d+)/(\d+)\s*["\u201d]\s*=\s*1\s*[\'\u2019]\s*-?\s*0?\s*["\u201d]?'
    frac_match = re.search(frac_pattern, text_clean, re.IGNORECASE)
    if frac_match:
        numerator = int(frac_match.group(1))
        denominator = int(frac_match.group(2))
        inches_per_foot = numerator / denominator
        ratio = 12 / inches_per_foot
        result.update({
            "scale_found": True,
            "scale_text": frac_match.group(0),
            "inches_per_foot": inches_per_foot,
            "ratio": ratio,
        })
        return result

    # Pattern 2: Whole inch = feet (1" = 10')
    whole_pattern = r'(\d+)\s*["\u201d]\s*=\s*(\d+)\s*[\'\u2019]'
    whole_match = re.search(whole_pattern, text_clean, re.IGNORECASE)
    if whole_match:
        inches_on_paper = int(whole_match.group(1))
        feet_real = int(whole_match.group(2))
        inches_per_foot = inches_on_paper / feet_real
        ratio = 12 / inches_per_foot
        result.update({
            "scale_found": True,
            "scale_text": whole_match.group(0),
            "inches_per_foot": inches_per_foot,
            "ratio": ratio,
        })
        return result

    # Pattern 3: Metric ratio (1:100, Scale 1:50)
    ratio_pattern = r'(?:scale\s*:?\s*)?1\s*:\s*(\d+)'
    ratio_match = re.search(ratio_pattern, text_clean, re.IGNORECASE)
    if ratio_match:
        ratio = int(ratio_match.group(1))
        inches_per_foot = 12 / ratio
        result.update({
            "scale_found": True,
            "scale_text": ratio_match.group(0),
            "inches_per_foot": inches_per_foot,
            "ratio": ratio,
        })
        return result

    return result


def extract_text_ocr(gray: np.ndarray) -> dict:
    """Extract text using OCR - for dimensions, labels, material callouts, and SCALE."""
    if not HAS_OCR:
        return {"ocr_available": False, "text": [], "dimensions": []}

    # Preprocess for better OCR
    denoised = cv2.fastNlMeansDenoising(gray)

    # Get all text
    text = pytesseract.image_to_string(denoised)

    # Also get text with bounding boxes
    data = pytesseract.image_to_data(denoised, output_type=pytesseract.Output.DICT)

    # === SCALE EXTRACTION (critical!) ===
    scale_info = extract_scale_from_text(text)

    # Extract dimension patterns (e.g., 12'-6", 3.5m, 2500 SF)
    import re
    dimension_patterns = [
        r"\d+'-\d+\"",  # 12'-6"
        r"\d+\s*(?:ft|feet|')",  # 12 ft, 12'
        r"\d+\s*(?:in|inch|\")",  # 36 in, 36"
        r"\d+\.?\d*\s*(?:m|meter)",  # 3.5m
        r"\d{1,3}(?:,?\d{3})*\s*(?:sf|sq\.?\s*ft|square\s*feet)",  # 2,500 SF
    ]

    dimensions = []
    for pattern in dimension_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        dimensions.extend(matches)

    # Look for material keywords
    material_keywords = [
        "concrete", "drywall", "gypsum", "steel", "wood", "lumber",
        "brick", "block", "glass", "aluminum", "copper", "pvc",
        "insulation", "sheathing", "plywood", "osb", "lvl",
    ]
    materials_found = [kw for kw in material_keywords if kw.lower() in text.lower()]

    # Look for grade/spec patterns
    grade_patterns = [
        r"[Gg]rade\s+[A-Za-z0-9]+",
        r"[Tt]ype\s+[A-Za-z0-9]+",
        r"[Cc]lass\s+[A-Za-z0-9]+",
    ]
    grades = []
    for pattern in grade_patterns:
        matches = re.findall(pattern, text)
        grades.extend(matches)

    return {
        "ocr_available": True,
        "raw_text_length": len(text),
        "dimensions_found": dimensions[:20],  # Limit output
        "materials_detected": materials_found,
        "grades_specs": grades[:10],
        "scale_info": scale_info,  # Critical for pixel-to-feet conversion
        "sample_text": text[:500] if text else "",
    }


def detect_scale_bar(gray: np.ndarray) -> dict:
    """Try to detect a scale bar and extract scale information."""
    # Scale bars are usually horizontal lines with tick marks
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=5)

    if lines is None:
        return {"scale_detected": False}

    # Look for prominent horizontal lines near edges of image
    h, w = gray.shape
    scale_candidates = []

    for line in lines:
        x1, y1, x2, y2 = line[0]
        # Check if horizontal
        if abs(y2 - y1) < 10:
            length = abs(x2 - x1)
            # Scale bars usually at bottom or top 20% of image
            if y1 < h * 0.2 or y1 > h * 0.8:
                scale_candidates.append({
                    "length_px": length,
                    "y_position": y1,
                    "location": "top" if y1 < h * 0.2 else "bottom"
                })

    if scale_candidates:
        # Return the longest candidate
        best = max(scale_candidates, key=lambda x: x["length_px"])
        return {
            "scale_detected": True,
            "scale_bar_length_px": best["length_px"],
            "location": best["location"],
        }

    return {"scale_detected": False}


def parse_dimension_string(text: str):
    """
    Parse an architectural dimension string into feet and inches.

    Examples:
        "25'-0\"" -> (25, 0)
        "12'-6\"" -> (12, 6)
        "30'" -> (30, None)
    """
    import re

    text = text.strip().replace('\u2019', "'").replace('\u201d', '"')

    # Pattern: feet'-inches"
    match = re.match(r"(\d+)'\s*-?\s*(\d+)\"?", text)
    if match:
        return int(match.group(1)), int(match.group(2))

    # Pattern: feet' only
    match = re.match(r"(\d+)'$", text)
    if match:
        return int(match.group(1)), None

    # Pattern: inches" only
    match = re.match(r"(\d+)\"$", text)
    if match:
        return 0, int(match.group(1))

    # Pattern: bare number (assume feet if reasonable)
    match = re.match(r"^(\d+)$", text)
    if match:
        val = int(match.group(1))
        if 5 <= val <= 200:
            return val, None

    return None, None


def calibrate_from_dimensions(gray: np.ndarray) -> dict:
    """
    Calibrate pixel-to-feet ratio by matching dimension text to dimension lines.

    This finds dimension strings like "25'-0\"" in the OCR, locates them in the image,
    finds nearby dimension lines, and calculates exact px_per_ft.
    """
    if not HAS_OCR:
        return {"calibrated": False, "reason": "OCR not available"}

    result = {
        "calibrated": False,
        "px_per_ft": None,
        "method": None,
        "confidence": 0.0,
        "samples": [],
    }

    height, width = gray.shape[:2]

    # Get OCR with bounding boxes
    denoised = cv2.fastNlMeansDenoising(gray)
    ocr_data = pytesseract.image_to_data(denoised, output_type=pytesseract.Output.DICT)

    # Find dimension strings and their locations
    dimension_locations = []

    for i, text in enumerate(ocr_data['text']):
        if not text.strip():
            continue

        feet, inches = parse_dimension_string(text.strip())
        if feet is None:
            continue

        total_feet = feet + (inches / 12.0 if inches else 0)
        if total_feet < 1 or total_feet > 500:
            continue

        x = ocr_data['left'][i]
        y = ocr_data['top'][i]
        w = ocr_data['width'][i]
        h = ocr_data['height'][i]

        dimension_locations.append({
            "text": text.strip(),
            "feet": total_feet,
            "bbox": (x, y, w, h),
            "center": (x + w//2, y + h//2),
        })

    if not dimension_locations:
        return {"calibrated": False, "reason": "No dimension strings found"}

    print(f"  Found {len(dimension_locations)} dimension strings")

    # Detect lines
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 50, minLineLength=50, maxLineGap=10)

    if lines is None:
        return {"calibrated": False, "reason": "No lines detected"}

    # Match dimensions to nearby lines
    calibration_samples = []

    for dim in dimension_locations:
        cx, cy = dim["center"]
        target_feet = dim["feet"]

        best_match = None
        best_distance = float('inf')

        for line in lines:
            x1, y1, x2, y2 = line[0]
            line_length = np.sqrt((x2-x1)**2 + (y2-y1)**2)

            if line_length < 30:
                continue

            line_cx = (x1 + x2) / 2
            line_cy = (y1 + y2) / 2
            dist = np.sqrt((cx - line_cx)**2 + (cy - line_cy)**2)

            if dist < 200 and dist < best_distance:
                angle = abs(np.arctan2(y2-y1, x2-x1) * 180 / np.pi)
                is_horizontal = angle < 20 or angle > 160
                is_vertical = 70 < angle < 110

                if is_horizontal or is_vertical:
                    best_match = {
                        "line_length_px": line_length,
                        "distance_to_text": dist,
                        "orientation": "horizontal" if is_horizontal else "vertical",
                    }
                    best_distance = dist

        if best_match:
            px_per_ft = best_match["line_length_px"] / target_feet
            calibration_samples.append({
                "dimension_text": dim["text"],
                "feet_value": target_feet,
                "line_length_px": best_match["line_length_px"],
                "px_per_ft": px_per_ft,
                "confidence": max(0, 1 - (best_distance / 200)),
            })

    if not calibration_samples:
        return {"calibrated": False, "reason": "Could not match dimensions to lines"}

    # Weighted average
    total_weight = sum(s["confidence"] for s in calibration_samples)
    if total_weight == 0:
        return {"calibrated": False, "reason": "No confident matches"}

    weighted_px_per_ft = sum(s["px_per_ft"] * s["confidence"] for s in calibration_samples) / total_weight
    avg_confidence = total_weight / len(calibration_samples)

    if weighted_px_per_ft < 5 or weighted_px_per_ft > 300:
        return {
            "calibrated": False,
            "reason": f"Calculated px_per_ft ({weighted_px_per_ft:.1f}) outside reasonable range"
        }

    return {
        "calibrated": True,
        "method": "dimension_line_matching",
        "confidence": round(avg_confidence, 2),
        "num_samples": len(calibration_samples),
        "dimensions_matched": [s["dimension_text"] for s in calibration_samples[:5]],
        # Internal use only
        "px_per_ft": round(weighted_px_per_ft, 2),
    }


def calculate_areas_and_volumes(rooms: dict, scale_px_per_foot: float = None) -> dict:
    """Estimate areas and suggest volumes based on detected rooms."""
    if not rooms.get("rooms"):
        return {}

    total_area_px = rooms["total_room_area_px"]

    # Only output real-world values if we have scale
    if scale_px_per_foot and scale_px_per_foot > 0:
        px_per_sf = scale_px_per_foot ** 2
        area_sf = total_area_px / px_per_sf

        # Volume estimates assuming 9ft ceiling
        ceiling_height = 9
        volume_cf = area_sf * ceiling_height

        # Concrete estimate: 4" slab
        slab_thickness = 0.33
        concrete_cf = area_sf * slab_thickness

        return {
            "total_area": {"value": int(area_sf), "unit": "SF"},
            "volume": {"value": int(volume_cf), "unit": "CF"},
            "concrete_slab": {"value": round(concrete_cf / 27, 1), "unit": "CY"},
        }
    else:
        return {"note": "No scale detected - cannot calculate real measurements"}


def analyze_drawing(img_path: str) -> dict:
    """Main analysis function - runs all detections."""
    print(f"\nAnalyzing: {img_path}")
    print("-" * 50)

    img = load_image(img_path)
    gray, binary = preprocess(img)

    print("Detecting lines (walls)...")
    lines = detect_lines(gray)

    print("Detecting rooms...")
    rooms = detect_rooms(binary)

    print("Detecting rectangles (doors/windows)...")
    rectangles = detect_rectangles(gray)

    print("Looking for scale bar...")
    scale = detect_scale_bar(gray)

    print("Extracting text (OCR)...")
    text_data = extract_text_ocr(gray)

    print("Calibrating from dimensions...")
    calibration = calibrate_from_dimensions(gray)

    # Use calibrated scale if available
    px_per_ft = calibration.get("px_per_ft") if calibration.get("calibrated") else None

    print("Calculating areas...")
    areas = calculate_areas_and_volumes(rooms, px_per_ft)

    # Classify drawing type
    if lines["horizontal"] > lines["vertical"] * 1.5:
        drawing_type = "floor_plan"
    elif lines["vertical"] > lines["horizontal"] * 1.5:
        drawing_type = "elevation"
    elif rooms["room_count"] > 2:
        drawing_type = "floor_plan"
    else:
        drawing_type = "unknown"

    # Build result with explicit units
    result = {
        "file": img_path,
        "drawing_type": drawing_type,
        "counts": {
            "rooms": rooms["room_count"],
            "doors": rectangles["door_candidates"],
            "windows": rectangles["window_candidates"],
        },
        "measurements": areas,  # Contains {value, unit} objects
        "scale": {
            "detected": calibration.get("calibrated", False),
            "source": calibration.get("method") if calibration.get("calibrated") else "none",
            "confidence": calibration.get("confidence", 0),
            "dimensions_matched": calibration.get("dimensions_matched", []),
        },
        "materials": text_data.get("materials_detected", []),
        "text_extraction": {
            "dimensions_found": text_data.get("dimensions_found", []),
        },
        "confidence": calculate_confidence(lines, rooms, rectangles, text_data),
    }

    return result


def calculate_confidence(lines, rooms, rectangles, text_data) -> float:
    """Calculate overall confidence in the analysis."""
    score = 0.0

    # Has significant line structure
    if lines["total_lines"] > 20:
        score += 0.2

    # Detected rooms
    if rooms["room_count"] > 0:
        score += 0.2
    if rooms["room_count"] > 3:
        score += 0.1

    # Found doors/windows
    if rectangles["door_candidates"] > 0:
        score += 0.1
    if rectangles["window_candidates"] > 0:
        score += 0.1

    # OCR found dimensions
    if text_data.get("dimensions_found"):
        score += 0.2

    # OCR found materials
    if text_data.get("materials_detected"):
        score += 0.1

    return min(score, 1.0)


def create_debug_image(img_path: str, output_path: str = None):
    """Create annotated debug image showing what was detected."""
    img = load_image(img_path)
    gray, binary = preprocess(img)
    debug_img = img.copy()

    # Draw detected lines in blue
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 50, minLineLength=30, maxLineGap=10)
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            cv2.line(debug_img, (x1, y1), (x2, y2), (255, 0, 0), 1)

    # Draw room contours in green
    kernel = np.ones((5, 5), np.uint8)
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(closed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    img_area = binary.shape[0] * binary.shape[1]
    min_area = img_area * 0.005
    max_area = img_area * 0.5
    room_count = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_area < area < max_area:
            cv2.drawContours(debug_img, [cnt], -1, (0, 255, 0), 2)
            room_count += 1

    # Add text overlay
    cv2.putText(debug_img, f"Rooms: {room_count}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(debug_img, f"Lines: {len(lines) if lines is not None else 0}", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

    if output_path is None:
        output_path = str(Path(img_path).stem) + "_debug.png"

    cv2.imwrite(output_path, debug_img)
    print(f"Debug image saved: {output_path}")
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_cv_local.py <image_path> [--debug]")
        print("\nExample:")
        print("  python test_cv_local.py floor_plan.png")
        print("  python test_cv_local.py floor_plan.png --debug")
        sys.exit(1)

    img_path = sys.argv[1]
    debug_mode = "--debug" in sys.argv

    # Run analysis
    result = analyze_drawing(img_path)

    # Print results
    print("\n" + "=" * 50)
    print("ANALYSIS RESULTS")
    print("=" * 50)
    print(json.dumps(result, indent=2, default=str))

    # Create debug image if requested
    if debug_mode:
        debug_path = create_debug_image(img_path)
        print(f"\nDebug image: {debug_path}")

    print("\n✅ Analysis complete!")
