"""
OpenCV-based construction drawing analyzer for Modal.com

Deploy with: modal deploy cv_worker.py
Test with: modal run cv_worker.py

This worker analyzes construction drawings and photos to extract:
- Quantitative takeoff data (counts, linear measurements, areas, volumes)
- Material specifications and callouts
- Dimensions and scale information
- Room counts and classifications
"""

import modal
import base64
import io
import re
from typing import Optional

# Define the Modal app
app = modal.App("construction-cv-worker")

# Define the image with OpenCV, OCR, and dependencies
cv_image = modal.Image.debian_slim(python_version="3.11").apt_install(
    "tesseract-ocr",
    "tesseract-ocr-eng",
).pip_install(
    "opencv-python-headless",
    "numpy",
    "pillow",
    "pytesseract",
)


@app.function(image=cv_image, timeout=120)
@modal.web_endpoint(method="POST")
def analyze(image_base64: str) -> dict:
    """
    Analyze a construction drawing or photo.

    Args:
        image_base64: Base64 encoded image data (with or without data URI prefix)

    Returns:
        dict with comprehensive takeoff data:
        - counts: doors, windows, fixtures, columns
        - linear_measurements: wall lengths, pipe runs
        - areas: room areas, floor area
        - volumes: concrete, excavation estimates
        - materials: detected material types and grades
        - dimensions: scale info, room dimensions
        - drawing_type: floor_plan, elevation, site_plan, photo
        - confidence: overall analysis confidence
    """
    import cv2
    import numpy as np
    from PIL import Image

    try:
        # Handle data URI prefix if present
        if image_base64.startswith('data:'):
            # Extract base64 part after the comma
            image_base64 = image_base64.split(',', 1)[1]

        # Decode base64 image
        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data))

        # Convert to OpenCV format
        img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape[:2]

        # Run all analyses
        drawing_type = classify_drawing_type(gray)
        lines_data = detect_lines(gray)
        rooms_data = detect_rooms(gray)
        rectangles_data = detect_rectangles(gray)
        scale_data = detect_scale_bar(gray)
        text_data = extract_text_ocr(gray)

        # Dimension-based calibration (highest priority for scale)
        calibration_data = calibrate_from_dimensions(gray)

        # Calculate derived measurements
        takeoff = calculate_takeoff(
            drawing_type=drawing_type,
            lines=lines_data,
            rooms=rooms_data,
            rectangles=rectangles_data,
            scale=scale_data,
            text=text_data,
            image_size=(width, height),
            calibration=calibration_data
        )

        # Calculate overall confidence
        confidence = calculate_confidence(
            drawing_type, rooms_data, rectangles_data, text_data, scale_data, calibration_data
        )

        # Build response optimized for LLM aggregation
        total_sf = takeoff["areas"].get("total_sf")
        total_wall_lf = takeoff["linear"].get("total_wall_lf")
        volumes = takeoff["volumes"]
        counts = takeoff["counts"]
        scale_confidence = takeoff["scale"].get("confidence", 0)

        # Format for LLM consumption with context and CSI division hints
        return {
            "source": "opencv_analysis",
            "drawing_type": drawing_type,
            "analysis_confidence": confidence,

            # Quantitative takeoff with CSI division mapping
            "takeoff": {
                # Division 01 - General (for overhead calculations)
                "gross_floor_area": {
                    "value": int(total_sf) if total_sf else None,
                    "unit": "SF",
                    "confidence": scale_confidence,
                    "csi_divisions": ["01_general_requirements"],
                    "use": "Base for percentage-based costs and overhead calculations",
                } if total_sf else None,

                # Division 03 - Concrete
                "concrete_slab_volume": {
                    "value": volumes.get('concrete_slab_cy'),
                    "unit": "CY",
                    "confidence": scale_confidence * 0.8,  # Derived estimate
                    "csi_divisions": ["03_concrete"],
                    "use": "4-inch slab-on-grade estimate. Multiply by local concrete cost per CY.",
                    "assumptions": "4-inch thickness, no reinforcement included",
                } if volumes.get('concrete_slab_cy') else None,

                "foundation_volume": {
                    "value": volumes.get('foundation_cy'),
                    "unit": "CY",
                    "confidence": scale_confidence * 0.6,  # Lower confidence estimate
                    "csi_divisions": ["03_concrete"],
                    "use": "Foundation wall estimate. Verify with structural drawings.",
                    "assumptions": "8-inch width, 3-foot depth, 10% of walls as exterior",
                } if volumes.get('foundation_cy') else None,

                # Division 02 - Existing Conditions / Sitework
                "excavation_volume": {
                    "value": volumes.get('excavation_cy'),
                    "unit": "CY",
                    "confidence": scale_confidence * 0.5,
                    "csi_divisions": ["02_existing_conditions"],
                    "use": "Site excavation estimate for slab prep.",
                    "assumptions": "1.5-foot average depth, 10% over-dig allowance",
                } if volumes.get('excavation_cy') else None,

                # Division 06/09 - Interior construction
                "interior_wall_length": {
                    "value": int(total_wall_lf) if total_wall_lf else None,
                    "unit": "LF",
                    "confidence": scale_confidence * 0.7,
                    "csi_divisions": ["06_wood_plastics_composites", "09_finishes"],
                    "use": "Linear feet for drywall, framing, base trim, and paint calculations.",
                } if total_wall_lf else None,

                # Division 08 - Openings
                "door_count": {
                    "value": counts.get('doors', 0),
                    "unit": "EA",
                    "confidence": 0.6,  # Shape detection has moderate accuracy
                    "csi_divisions": ["08_openings"],
                    "use": "Count for door assemblies. Verify sizes from drawings.",
                } if counts.get('doors', 0) > 0 else None,

                "window_count": {
                    "value": counts.get('windows', 0),
                    "unit": "EA",
                    "confidence": 0.5,
                    "csi_divisions": ["08_openings"],
                    "use": "Count for window assemblies. Verify sizes from drawings.",
                } if counts.get('windows', 0) > 0 else None,

                # Structural
                "column_count": {
                    "value": counts.get('columns', 0),
                    "unit": "EA",
                    "confidence": 0.5,
                    "csi_divisions": ["03_concrete", "05_metals"],
                    "use": "Structural column count. Material type unknown.",
                } if counts.get('columns', 0) > 0 else None,

                # Room/space count
                "room_count": {
                    "value": counts.get('rooms', 0),
                    "unit": "EA",
                    "confidence": 0.7,
                    "use": "Number of enclosed spaces. Use for fixture counts and HVAC zoning.",
                } if counts.get('rooms', 0) > 0 else None,
            },

            # Materials detected from OCR (for cost database lookup)
            "materials_detected": {
                material: {
                    "detected": True,
                    "source": "ocr",
                    "use": f"Verify {material} specification and include in relevant CSI division",
                }
                for material, found in text_data.get("materials", {}).items() if found
            },

            # Raw text extractions (for LLM to parse further)
            "text_extractions": {
                "dimension_strings": text_data.get("dimensions", []),
                "grade_specifications": text_data.get("grades_specs", []),
                "area_callouts_sf": text_data.get("sqft_from_text", []),
            },

            # Scale detection metadata
            "scale_info": {
                "detected": calibration_data.get("calibrated", False) or text_data.get("scale_info", {}).get("scale_found", False),
                "method": takeoff["scale"].get("source"),
                "confidence": scale_confidence,
                "note": "Measurements are estimates. Higher confidence when scale is detected from dimension calibration.",
            },

            # Aggregation guidance for the LLM
            "aggregation_notes": {
                "priority": "Use area_callouts_sf from text_extractions if available (most accurate). Fall back to gross_floor_area.",
                "conflicts": "If PDF provides different values, prefer PDF for areas and this analysis for counts.",
                "missing_data": [
                    "ceiling_height" if not total_sf else None,
                    "exterior_wall_area",
                    "roof_area",
                    "MEP_fixtures",
                ],
            },
        }

    except Exception as e:
        return {
            "drawing_type": "unknown",
            "counts": {},
            "linear_measurements": {},
            "areas": {},
            "volumes": {},
            "materials": {},
            "dimensions": {"scale_detected": False},
            "room_count": 0,
            "confidence": 0.0,
            "error": str(e),
        }


def classify_drawing_type(gray) -> str:
    """Classify: floor_plan, elevation, site_plan, or photo."""
    import cv2
    import numpy as np

    height, width = gray.shape[:2]
    edges = cv2.Canny(gray, 50, 150)

    lines = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi/180, threshold=50,
        minLineLength=50, maxLineGap=10
    )

    if lines is None or len(lines) < 10:
        return "photo"

    horizontal = 0
    vertical = 0

    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)

        if angle < 15 or angle > 165:
            horizontal += 1
        elif 75 < angle < 105:
            vertical += 1

    total = len(lines)
    density = total / (width * height) * 1000000

    if density > 50:
        ratio = horizontal / max(vertical, 1)
        if 0.5 < ratio < 2.0:
            return "floor_plan"
        elif ratio < 0.5:
            return "elevation"
        else:
            return "site_plan"

    return "photo"


def detect_lines(gray) -> dict:
    """Detect all lines - walls, edges, structural elements."""
    import cv2
    import numpy as np

    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    lines = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi/180, threshold=50,
        minLineLength=30, maxLineGap=10
    )

    if lines is None:
        return {"total": 0, "total_length_px": 0, "horizontal": 0, "vertical": 0}

    total_length = 0
    horizontal = 0
    vertical = 0
    line_lengths = []

    for line in lines:
        x1, y1, x2, y2 = line[0]
        length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        total_length += length
        line_lengths.append(length)

        angle = abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
        if angle < 15 or angle > 165:
            horizontal += 1
        elif 75 < angle < 105:
            vertical += 1

    return {
        "total": len(lines),
        "total_length_px": round(total_length, 2),
        "horizontal": horizontal,
        "vertical": vertical,
        "avg_length_px": round(np.mean(line_lengths), 2) if line_lengths else 0,
    }


def detect_rooms(gray) -> dict:
    """Count and measure enclosed spaces."""
    import cv2
    import numpy as np

    height, width = gray.shape[:2]
    img_area = width * height
    min_area = img_area * 0.005
    max_area = img_area * 0.4

    # Binary threshold
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

    # Close gaps
    kernel = np.ones((5, 5), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    rooms = []
    total_area_px = 0

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_area < area < max_area:
            perimeter = cv2.arcLength(cnt, True)
            x, y, w, h = cv2.boundingRect(cnt)
            aspect = w / max(h, 1)

            if 0.3 < aspect < 3.0:
                rooms.append({
                    "area_px": area,
                    "perimeter_px": perimeter,
                    "width_px": w,
                    "height_px": h,
                    "aspect_ratio": round(aspect, 2),
                })
                total_area_px += area

    return {
        "count": len(rooms),
        "total_area_px": total_area_px,
        "room_details": rooms[:15],  # Limit to 15 rooms
    }


def detect_rectangles(gray) -> dict:
    """Detect doors, windows, and other rectangular elements."""
    import cv2
    import numpy as np

    height, width = gray.shape[:2]
    img_area = width * height

    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    doors = []
    windows = []
    columns = []
    fixtures = []

    for cnt in contours:
        epsilon = 0.02 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)

        if len(approx) == 4:
            area = cv2.contourArea(cnt)
            ratio = area / img_area

            if ratio < 0.0005:
                continue  # Too small

            x, y, w, h = cv2.boundingRect(cnt)
            aspect = max(w, h) / min(w, h) if min(w, h) > 0 else 0

            # Door: tall and narrow, 1.5-3 aspect ratio
            if 0.001 < ratio < 0.02 and 1.5 < aspect < 3 and h > w:
                doors.append({"w": w, "h": h, "area": area})

            # Window: medium size, various aspects
            elif 0.001 < ratio < 0.03 and aspect < 2.5:
                windows.append({"w": w, "h": h, "area": area})

            # Column: small and roughly square
            elif 0.0005 < ratio < 0.005 and aspect < 1.5:
                columns.append({"w": w, "h": h, "area": area})

            # Small fixtures
            elif 0.0005 < ratio < 0.01:
                fixtures.append({"w": w, "h": h, "area": area})

    return {
        "doors": len(doors),
        "windows": len(windows),
        "columns": len(columns),
        "fixtures": len(fixtures),
        "door_details": doors[:10],
        "window_details": windows[:10],
    }


def detect_scale_bar(gray) -> dict:
    """Detect scale bar and calculate pixels per foot."""
    import cv2
    import numpy as np

    height, width = gray.shape[:2]
    edges = cv2.Canny(gray, 50, 150)

    lines = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi/180, threshold=100,
        minLineLength=100, maxLineGap=5
    )

    if lines is None:
        return {"scale_detected": False}

    # Look for horizontal lines near edges (scale bars usually there)
    candidates = []

    for line in lines:
        x1, y1, x2, y2 = line[0]
        if abs(y2 - y1) < 10:  # Horizontal
            length = abs(x2 - x1)
            # Check if near top/bottom 15% of image
            if y1 < height * 0.15 or y1 > height * 0.85:
                candidates.append({
                    "length_px": length,
                    "y": y1,
                    "location": "top" if y1 < height * 0.15 else "bottom"
                })

    if candidates:
        best = max(candidates, key=lambda x: x["length_px"])
        return {
            "scale_detected": True,
            "scale_bar_px": best["length_px"],
            "location": best["location"],
        }

    return {"scale_detected": False}


def calibrate_from_dimensions(gray) -> dict:
    """
    Calibrate pixel-to-feet ratio by matching dimension text to dimension lines.

    This finds dimension strings like "25'-0"" in the OCR, locates them in the image,
    finds nearby dimension lines, and calculates exact px_per_ft.

    Returns:
        dict with calibration info:
        - calibrated: bool
        - px_per_ft: float (if calibrated)
        - method: str describing how it was calibrated
        - confidence: float
        - samples: list of dimension matches used
    """
    import cv2
    import numpy as np

    try:
        import pytesseract
    except ImportError:
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

        # Parse dimension value
        feet, inches = parse_dimension_string(text.strip())
        if feet is None:
            continue

        total_feet = feet + (inches / 12.0 if inches else 0)
        if total_feet < 1 or total_feet > 500:  # Sanity check
            continue

        # Get bounding box of this text
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

    # Detect all lines in the image
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi/180, threshold=50,
        minLineLength=50, maxLineGap=10
    )

    if lines is None:
        return {"calibrated": False, "reason": "No lines detected"}

    # For each dimension, find the closest parallel line
    calibration_samples = []

    for dim in dimension_locations:
        cx, cy = dim["center"]
        target_feet = dim["feet"]

        best_match = None
        best_distance = float('inf')

        for line in lines:
            x1, y1, x2, y2 = line[0]
            line_length = np.sqrt((x2-x1)**2 + (y2-y1)**2)

            # Skip very short lines
            if line_length < 30:
                continue

            # Calculate distance from dimension text to line
            # Use distance to line midpoint
            line_cx = (x1 + x2) / 2
            line_cy = (y1 + y2) / 2
            dist = np.sqrt((cx - line_cx)**2 + (cy - line_cy)**2)

            # Dimension text is usually within 50-150 pixels of its line
            if dist < 200 and dist < best_distance:
                # Check if line orientation matches typical dimension line
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
                "confidence": max(0, 1 - (best_distance / 200)),  # Closer = more confident
            })

    if not calibration_samples:
        return {"calibrated": False, "reason": "Could not match dimensions to lines"}

    # Use weighted average of samples (weight by confidence)
    total_weight = sum(s["confidence"] for s in calibration_samples)
    if total_weight == 0:
        return {"calibrated": False, "reason": "No confident matches"}

    weighted_px_per_ft = sum(s["px_per_ft"] * s["confidence"] for s in calibration_samples) / total_weight
    avg_confidence = total_weight / len(calibration_samples)

    # Sanity check: px_per_ft should be reasonable (10-200 for typical drawings)
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
        # Keep px_per_ft internally for calculations
        "px_per_ft": round(weighted_px_per_ft, 2),
    }


def parse_dimension_string(text: str):
    """
    Parse an architectural dimension string into feet and inches.

    Examples:
        "25'-0\"" -> (25, 0)
        "12'-6\"" -> (12, 6)
        "30'" -> (30, None)
        "6\"" -> (0, 6)
        "25" -> (25, None) if looks like feet

    Returns:
        (feet, inches) tuple, or (None, None) if not a dimension
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
        if 5 <= val <= 200:  # Reasonable feet range
            return val, None

    return None, None


def extract_text_ocr(gray) -> dict:
    """Extract text using OCR - dimensions, materials, specs, and SCALE."""
    import cv2

    try:
        import pytesseract
    except ImportError:
        return {"ocr_available": False}

    # Preprocess
    denoised = cv2.fastNlMeansDenoising(gray)

    # Extract text
    text = pytesseract.image_to_string(denoised)

    # === SCALE EXTRACTION (critical for pixel-to-feet conversion) ===
    scale_info = extract_scale_from_text(text)

    # Dimension patterns
    dimension_patterns = [
        r"\d+'-\d+\"",           # 12'-6"
        r"\d+\s*(?:ft|feet|')",  # 12 ft
        r"\d+\s*(?:in|\")",      # 36"
        r"\d+\.?\d*\s*m\b",      # 3.5m
        r"\d{1,3}(?:,?\d{3})*\s*(?:sf|sq\.?\s*ft)", # 2,500 SF
    ]

    dimensions = []
    for pattern in dimension_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        dimensions.extend(matches)

    # Material keywords
    material_keywords = {
        "concrete": ["concrete", "conc", "slab"],
        "drywall": ["drywall", "gypsum", "gyp", "sheetrock"],
        "steel": ["steel", "metal", "stl"],
        "wood": ["wood", "lumber", "timber", "plywood", "osb", "lvl"],
        "brick": ["brick", "masonry", "cmu", "block"],
        "glass": ["glass", "glazing", "window"],
        "insulation": ["insulation", "batt", "foam", "r-value"],
        "roofing": ["roofing", "shingle", "membrane", "tpo", "epdm"],
        "flooring": ["flooring", "tile", "carpet", "hardwood", "vinyl", "lvt"],
    }

    materials_found = {}
    text_lower = text.lower()
    for category, keywords in material_keywords.items():
        for kw in keywords:
            if kw in text_lower:
                materials_found[category] = True
                break

    # Grade/spec patterns
    grades = []
    grade_patterns = [
        r"[Gg]rade\s+[A-Z]?\d*",
        r"[Tt]ype\s+[A-Z0-9]+",
        r"[Cc]lass\s+[A-Z0-9]+",
        r"[Aa]\d{3}",  # Steel grades like A36, A992
        r"[Rr]-?\d+",  # R-values like R-19
    ]
    for pattern in grade_patterns:
        matches = re.findall(pattern, text)
        grades.extend(matches)

    # Area specifications (try to find SF numbers)
    sf_pattern = r"(\d{1,3}(?:,?\d{3})*)\s*(?:sf|sq\.?\s*ft|square\s*feet)"
    sf_matches = re.findall(sf_pattern, text, re.IGNORECASE)
    sqft_values = [int(m.replace(',', '')) for m in sf_matches]

    return {
        "ocr_available": True,
        "dimensions": dimensions[:20],
        "materials": materials_found,
        "grades_specs": grades[:15],
        "sqft_from_text": sqft_values,
        "scale_info": scale_info,  # Critical for pixel-to-feet conversion
        "text_length": len(text),
    }


def extract_scale_from_text(text: str) -> dict:
    """
    Extract architectural scale notation from OCR text.

    Common formats:
    - 1/4" = 1'-0"  (quarter inch = one foot)
    - 1/8" = 1'-0"  (eighth inch = one foot)
    - 1" = 10'      (one inch = ten feet)
    - Scale: 1:100  (metric ratio)
    - 1:50, 1:200   (metric ratio)

    Returns dict with:
    - scale_found: bool
    - scale_text: the raw matched text
    - inches_per_foot: conversion factor (how many inches on paper = 1 foot real)
    - ratio: numeric ratio (e.g., 48 means 1:48 or 1/4" = 1')
    """
    result = {
        "scale_found": False,
        "scale_text": None,
        "inches_per_foot": None,
        "ratio": None,
    }

    text_clean = text.replace('\n', ' ').replace('  ', ' ')

    # Pattern 1: Fractional inch = feet  (1/4" = 1'-0", 1/8" = 1'-0", etc.)
    # This is the most common architectural format
    frac_pattern = r'(\d+)/(\d+)\s*["\u201d]\s*=\s*1\s*[\'\u2019]\s*-?\s*0?\s*["\u201d]?'
    frac_match = re.search(frac_pattern, text_clean, re.IGNORECASE)
    if frac_match:
        numerator = int(frac_match.group(1))
        denominator = int(frac_match.group(2))
        inches_per_foot = numerator / denominator
        ratio = 12 / inches_per_foot  # 12 inches in a foot
        result.update({
            "scale_found": True,
            "scale_text": frac_match.group(0),
            "inches_per_foot": inches_per_foot,
            "ratio": ratio,
        })
        return result

    # Pattern 2: Whole inch = feet (1" = 10', 1" = 20', etc.)
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

    # Pattern 3: Metric ratio (1:100, 1:50, Scale 1:200)
    ratio_pattern = r'(?:scale\s*:?\s*)?1\s*:\s*(\d+)'
    ratio_match = re.search(ratio_pattern, text_clean, re.IGNORECASE)
    if ratio_match:
        ratio = int(ratio_match.group(1))
        # For metric: 1:100 means 1cm = 1m (100cm), or 1 unit = 100 units
        # Convert to inches_per_foot equivalent (assuming metric drawing)
        # 1:100 in metric ≈ 1/8" = 1'-0" in imperial
        inches_per_foot = 12 / ratio  # Approximate conversion
        result.update({
            "scale_found": True,
            "scale_text": ratio_match.group(0),
            "inches_per_foot": inches_per_foot,
            "ratio": ratio,
        })
        return result

    # Pattern 4: Common scale keywords
    scale_keywords = {
        "quarter inch": (0.25, 48),
        "1/4 inch": (0.25, 48),
        "eighth inch": (0.125, 96),
        "1/8 inch": (0.125, 96),
        "half inch": (0.5, 24),
        "1/2 inch": (0.5, 24),
        "three-quarter": (0.75, 16),
        "3/4 inch": (0.75, 16),
        "full scale": (12.0, 1),
        "1:1": (12.0, 1),
    }

    text_lower = text_clean.lower()
    for keyword, (ipr, rat) in scale_keywords.items():
        if keyword in text_lower:
            result.update({
                "scale_found": True,
                "scale_text": keyword,
                "inches_per_foot": ipr,
                "ratio": rat,
            })
            return result

    return result


def calculate_takeoff(drawing_type, lines, rooms, rectangles, scale, text, image_size, calibration=None) -> dict:
    """Calculate comprehensive takeoff data with proper scale conversion."""
    width, height = image_size
    calibration = calibration or {}

    # === SCALE CONVERSION (the critical part) ===
    # Priority 1: Dimension-based calibration (MOST ACCURATE - matches dimension strings to lines)
    # Priority 2: OCR-extracted scale notation (e.g., "1/4" = 1'-0"")
    # Priority 3: Use detected scale bar + assumptions
    # Priority 4: Estimate from image size (least accurate)

    px_per_ft = None
    scale_source = "none"
    scale_confidence = 0.0

    # Priority 1: Dimension-based calibration (highest accuracy)
    # This matches dimension strings like "25'-0"" to their actual dimension lines
    if calibration.get("calibrated") and calibration.get("px_per_ft"):
        px_per_ft = calibration["px_per_ft"]
        scale_source = "dimension_calibration"
        scale_confidence = min(0.95, calibration.get("confidence", 0.8) + 0.1)  # High confidence

    # Priority 2: OCR-extracted scale notation (e.g., "1/4" = 1'-0"")
    elif text.get("scale_info", {}).get("scale_found"):
        scale_info = text["scale_info"]
        inches_per_foot = scale_info.get("inches_per_foot", 0.25)

        # We need DPI to convert. Assume 150 DPI for typical scans.
        assumed_dpi = 150
        pixels_per_inch = assumed_dpi
        px_per_ft = pixels_per_inch * inches_per_foot

        scale_source = "ocr_scale_notation"
        scale_confidence = 0.8

    # Priority 3: Scale bar detected but no OCR scale text
    elif scale.get("scale_detected") and scale.get("scale_bar_px"):
        # Graphic scale bars are usually 10' or 20' or similar
        # Look for nearby text that might indicate the length
        # For now, assume 10' as common default
        assumed_scale_bar_feet = 10
        px_per_ft = scale["scale_bar_px"] / assumed_scale_bar_feet
        scale_source = "scale_bar_estimated"
        scale_confidence = 0.4

    # Priority 4: No scale info - rough estimate from image size
    else:
        # Typical floor plan on letter paper at 1/4" scale, 150 DPI:
        # 8" drawing area * 150 DPI = 1200 pixels
        # 8" * 4 ft/inch = 32 feet
        # So roughly 37.5 px/ft
        px_per_ft = 37.5
        scale_source = "default_estimate"
        scale_confidence = 0.2

    px_per_sf = px_per_ft ** 2

    # Calculate areas
    total_area_sf = None
    if rooms["total_area_px"] > 0:
        total_area_sf = round(rooms["total_area_px"] / px_per_sf, 0)

    # Override with OCR-detected sqft if available
    if text.get("sqft_from_text"):
        # Use the largest value found (likely total)
        total_area_sf = max(text["sqft_from_text"])

    # Linear measurements
    total_wall_lf = round(lines["total_length_px"] / px_per_ft, 0) if px_per_ft > 0 else None

    # Volume estimates (assuming standard construction)
    volumes = {}
    if total_area_sf:
        # Concrete slab: 4" thick = 0.33 ft
        slab_cf = total_area_sf * 0.33
        volumes["concrete_slab_cy"] = round(slab_cf / 27, 1)

        # Foundation wall: assume 100 LF, 8" wide, 3ft deep
        if total_wall_lf:
            foundation_cf = (total_wall_lf * 0.1) * 0.67 * 3  # 10% of walls are exterior
            volumes["foundation_cy"] = round(foundation_cf / 27, 1)

        # Excavation: slab area + 2ft perimeter, 1ft deep
        excavation_sf = total_area_sf * 1.1  # Add 10% for over-dig
        excavation_cf = excavation_sf * 1.5   # 1.5ft average depth
        volumes["excavation_cy"] = round(excavation_cf / 27, 1)

    return {
        "counts": {
            "doors": rectangles.get("doors", 0),
            "windows": rectangles.get("windows", 0),
            "columns": rectangles.get("columns", 0),
            "fixtures": rectangles.get("fixtures", 0),
            "rooms": rooms.get("count", 0),
        },
        "linear": {
            "total_wall_lf": total_wall_lf,
        },
        "areas": {
            "total_sf": total_area_sf,
        },
        "volumes": volumes,
        "scale": {
            "source": scale_source,
            "confidence": scale_confidence,
            "ratio": text.get("scale_info", {}).get("ratio"),
        },
    }


def calculate_confidence(drawing_type, rooms, rectangles, text, scale, calibration=None) -> float:
    """Calculate overall confidence score."""
    calibration = calibration or {}
    score = 0.2  # Base

    if drawing_type in ["floor_plan", "elevation"]:
        score += 0.15

    if rooms.get("count", 0) > 0:
        score += 0.15

    if rooms.get("count", 0) > 3:
        score += 0.1

    if rectangles.get("doors", 0) > 0:
        score += 0.1

    if rectangles.get("windows", 0) > 0:
        score += 0.1

    if text.get("dimensions"):
        score += 0.1

    if text.get("materials"):
        score += 0.05

    if scale.get("scale_detected"):
        score += 0.15

    if text.get("sqft_from_text"):
        score += 0.1

    # Boost for successful dimension-based calibration (most accurate scale source)
    if calibration.get("calibrated"):
        score += 0.15
        # Extra boost for multiple calibration samples
        if calibration.get("num_samples", 0) >= 3:
            score += 0.05

    return min(round(score, 2), 1.0)


# Local test entrypoint
@app.local_entrypoint()
def main():
    """Test with a sample image."""
    print("OpenCV Construction Analyzer")
    print("Deploy with: modal deploy cv_worker.py")
    print("\nTo test, call the endpoint with a base64 image.")
