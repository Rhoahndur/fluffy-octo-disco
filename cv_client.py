"""
OpenCV/Modal Client

Direct port of web/src/lib/cv/modal-client.ts
Calls the Modal.com-hosted OpenCV worker for deterministic construction drawing analysis.
"""

import os
import json
from typing import Optional

import requests


def analyze_with_opencv(image_base64: str) -> Optional[dict]:
    """
    Call the Modal CV worker to analyze a construction image.
    Direct port of analyzeWithOpenCV from modal-client.ts.

    Args:
        image_base64: Base64-encoded image (with or without data URI prefix)

    Returns:
        dict with {"raw_for_llm": <ModalCVResponse>, "analysis": <CVAnalysis>}
        or None if Modal not configured or analysis fails.
    """
    modal_endpoint = os.environ.get("MODAL_ENDPOINT_URL")

    # If Modal endpoint not configured, return None (graceful degradation)
    if not modal_endpoint:
        print("Modal endpoint not configured, skipping OpenCV analysis")
        return None

    try:
        # Keep data URL prefix - the CV worker handles both formats
        response = requests.post(
            modal_endpoint,
            headers={"Content-Type": "application/json"},
            json={"image_base64": image_base64},
            timeout=120,
        )

        if not response.ok:
            print(f"Modal CV worker error: {response.status_code} {response.reason}")
            return None

        result = response.json()

        if result.get("error"):
            print(f"Modal CV worker returned error: {result['error']}")
            return None

        return {
            "raw_for_llm": result,                           # Full response for LLM agent
            "analysis": map_modal_response_to_cv_analysis(result),  # Simplified for frontend
        }

    except Exception as e:
        print(f"Failed to call Modal CV worker: {e}")
        return None


def map_modal_response_to_cv_analysis(result: dict) -> dict:
    """
    Map raw Modal CV worker response to simplified CVAnalysis format.
    Direct port of mapModalResponseToCVAnalysis from modal-client.ts.
    """
    takeoff = result.get("takeoff", {}) or {}

    def _get_value(key, default=0):
        item = takeoff.get(key)
        if isinstance(item, dict) and item.get("value") is not None:
            return item["value"]
        return default

    def _get_measurement(key):
        item = takeoff.get(key)
        if isinstance(item, dict) and item.get("value") is not None:
            return {"value": item["value"], "unit": item.get("unit", "")}
        return None

    text_extractions = result.get("text_extractions", {}) or {}
    scale_info = result.get("scale_info", {}) or {}
    materials_detected = result.get("materials_detected", {}) or {}

    return {
        "drawing_type": result.get("drawing_type", "unknown"),
        "counts": {
            "doors": _get_value("door_count"),
            "windows": _get_value("window_count"),
            "columns": _get_value("column_count"),
            "fixtures": 0,
            "rooms": _get_value("room_count"),
        },
        "measurements": {
            "total_area": _get_measurement("gross_floor_area"),
            "total_wall_length": _get_measurement("interior_wall_length"),
            "concrete_slab": _get_measurement("concrete_slab_volume"),
            "foundation": _get_measurement("foundation_volume"),
            "excavation": _get_measurement("excavation_volume"),
        },
        "materials": {
            k: v.get("detected", False) if isinstance(v, dict) else bool(v)
            for k, v in materials_detected.items()
        },
        "scale": {
            "detected": scale_info.get("detected", False),
            "source": scale_info.get("method"),
            "confidence": scale_info.get("confidence"),
        },
        "text_extraction": {
            "dimensions_found": text_extractions.get("dimension_strings", []),
            "grades_specs": text_extractions.get("grade_specifications", []),
            "sqft_from_text": text_extractions.get("area_callouts_sf", []),
        },
        "room_count": _get_value("room_count"),
        "confidence": result.get("analysis_confidence", 0.0),
    }


def analyze_image_basic(image_width: int, image_height: int) -> dict:
    """
    Fallback local analysis using basic heuristics (no OpenCV).
    Used when Modal is not configured.
    Direct port of analyzeImageBasic from modal-client.ts.
    """
    aspect_ratio = image_width / image_height if image_height > 0 else 1.0

    if 0.7 <= aspect_ratio <= 1.4:
        drawing_type = "floor_plan"
    elif 1.4 < aspect_ratio <= 3:
        drawing_type = "elevation"
    elif aspect_ratio > 3:
        drawing_type = "site_plan"
    else:
        drawing_type = "unknown"

    return {
        "drawing_type": drawing_type,
        "counts": {
            "doors": 0,
            "windows": 0,
            "columns": 0,
            "fixtures": 0,
            "rooms": 0,
        },
        "measurements": {
            "total_area": None,
            "total_wall_length": None,
            "concrete_slab": None,
            "foundation": None,
            "excavation": None,
        },
        "materials": {},
        "scale": {
            "detected": False,
        },
        "text_extraction": {
            "dimensions_found": [],
            "grades_specs": [],
            "sqft_from_text": [],
        },
        "room_count": 0,
        "confidence": 0.1,  # Very low confidence for basic analysis
    }


def get_analysis_only(result: Optional[dict]) -> Optional[dict]:
    """Helper to get just the CVAnalysis from the result."""
    return result.get("analysis") if result else None


def get_raw_for_llm(result: Optional[dict]) -> Optional[dict]:
    """Helper to get the raw LLM-ready response."""
    return result.get("raw_for_llm") if result else None
