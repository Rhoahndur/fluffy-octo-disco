"""
Reconciliation Logic for Merging LLM Outputs with OpenCV Guardrails

Direct port of web/src/lib/llm/reconcile.ts

Philosophy:
- OpenCV provides DETERMINISTIC measurements (counts, areas, dimensions)
- LLMs provide PROBABILISTIC interpretation (building type, quality, semantics)
- Reconciliation uses CV to constrain/validate LLM outputs
- When CV and LLM disagree on measurables, CV wins (with confidence weighting)
"""

from typing import Optional
from cost_model import COST_PER_SF


ALL_SUBTYPES = list(COST_PER_SF.keys())


def reconcile_analyses(
    claude: Optional[dict] = None,
    gemini: Optional[dict] = None,
    opencv: Optional[dict] = None,
) -> dict:
    """
    Reconcile analyses from Claude, Gemini, and OpenCV.
    Direct port of reconcileAnalyses from reconcile.ts.

    Args:
        claude: LLMAnalysisResponse from Claude (or None)
        gemini: LLMAnalysisResponse from Gemini (or None)
        opencv: CVAnalysis from OpenCV (or None)

    Returns:
        ReconciliationResult dict with merged, conflicts, confidence, sources
    """
    conflicts = []
    details = {
        "sqft_source": "default",
        "cv_overrides": [],
        "llm_consensus": [],
        "warnings": [],
    }

    # If we have no LLM results, try to build from CV alone
    if not claude and not gemini:
        return _build_from_cv_only(opencv, conflicts)

    # Determine primary and secondary LLM sources
    primary, secondary = _select_primary_llm(claude, gemini)

    # Start with LLM-based merged analysis
    merged = {
        "building_type": primary.get("building_type", "residential"),
        "sub_type": primary.get("sub_type", "single_family_standard"),
        "quality": primary.get("quality", "mid"),
        "estimated_sqft": primary.get("estimated_sqft", 2000),
        "stories": primary.get("stories", 1),
        "materials_detected": list(primary.get("materials_detected", [])),
        "construction_type": primary.get("construction_type", "unknown"),
        "location": primary.get("location"),
        "confidence": primary.get("confidence", 0.5),
        "notes": primary.get("notes", ""),
    }

    # Step 1: Reconcile between LLMs (semantic/classification tasks)
    if secondary:
        _reconcile_llms(merged, primary, secondary, conflicts, details)

    # Step 2: Apply CV guardrails (deterministic measurements override probabilistic)
    if opencv:
        _apply_cv_guardrails(merged, opencv, conflicts, details)

    # Step 3: Validate and finalize
    _validate_sub_type(merged, conflicts)
    final_confidence = _calculate_final_confidence(merged, conflicts, details, opencv)

    return {
        "merged": merged,
        "conflicts": conflicts,
        "confidence": round(final_confidence * 100) / 100,
        "sources": {
            "claude": claude,
            "gemini": gemini,
            "opencv": opencv,
        },
    }


def _select_primary_llm(
    claude: Optional[dict],
    gemini: Optional[dict],
) -> tuple:
    """
    Select primary and secondary LLM sources.
    Direct port of selectPrimaryLLM from reconcile.ts.
    """
    if claude and gemini:
        # Prefer higher confidence, but weight Claude slightly for construction
        claude_score = claude.get("confidence", 0) + 0.05
        gemini_score = gemini.get("confidence", 0)

        if claude_score >= gemini_score:
            return claude, gemini
        else:
            return gemini, claude

    return (claude or gemini), None


def _reconcile_llms(
    merged: dict,
    primary: dict,
    secondary: dict,
    conflicts: list,
    details: dict,
) -> None:
    """
    Reconcile between two LLM outputs (semantic/classification tasks).
    Direct port of reconcileLLMs from reconcile.ts.
    """
    # Building type - semantic, trust LLM consensus
    if primary.get("building_type") == secondary.get("building_type"):
        details["llm_consensus"].append("building_type")
    else:
        conflicts.append(f"Building type: {primary.get('building_type')} vs {secondary.get('building_type')}")

    # Sub-type consensus
    if primary.get("sub_type") == secondary.get("sub_type"):
        details["llm_consensus"].append("sub_type")
    else:
        conflicts.append(f"Sub-type: {primary.get('sub_type')} vs {secondary.get('sub_type')}")

    # Quality - semantic assessment, average if adjacent
    if primary.get("quality") == secondary.get("quality"):
        details["llm_consensus"].append("quality")
    else:
        conflicts.append(f"Quality: {primary.get('quality')} vs {secondary.get('quality')}")
        qualities = ["low", "mid", "high"]
        p_idx = qualities.index(primary["quality"]) if primary.get("quality") in qualities else 1
        s_idx = qualities.index(secondary["quality"]) if secondary.get("quality") in qualities else 1
        if abs(p_idx - s_idx) == 1:
            merged["quality"] = "mid"  # Split the difference

    # Square footage - average if significant difference (CV will override later if available)
    p_sqft = primary.get("estimated_sqft", 2000)
    s_sqft = secondary.get("estimated_sqft", 2000)
    sqft_diff = abs(p_sqft - s_sqft) / max(p_sqft, s_sqft) if max(p_sqft, s_sqft) > 0 else 0

    if sqft_diff > 0.2:
        conflicts.append(f"LLM sqft: {p_sqft} vs {s_sqft} ({round(sqft_diff * 100)}% diff)")
        merged["estimated_sqft"] = round((p_sqft + s_sqft) / 2)
        details["sqft_source"] = "llm_consensus"
    else:
        details["sqft_source"] = "llm_primary"

    # Stories - use lower (more conservative)
    p_stories = primary.get("stories", 1)
    s_stories = secondary.get("stories", 1)
    if p_stories != s_stories:
        conflicts.append(f"Stories: {p_stories} vs {s_stories}")
        merged["stories"] = min(p_stories, s_stories)

    # Merge materials (union of both)
    all_materials = set(primary.get("materials_detected", []) + secondary.get("materials_detected", []))
    merged["materials_detected"] = list(all_materials)


def _apply_cv_guardrails(
    merged: dict,
    cv: dict,
    conflicts: list,
    details: dict,
) -> None:
    """
    Apply OpenCV guardrails to override/validate LLM estimates.
    Direct port of applyCVGuardrails from reconcile.ts.
    """
    text_extraction = cv.get("text_extraction", {}) or {}
    measurements = cv.get("measurements", {}) or {}
    counts = cv.get("counts", {}) or {}
    scale = cv.get("scale", {}) or {}
    materials = cv.get("materials", {}) or {}

    # RULE 1: If CV extracted sqft from OCR text, that's ground truth
    sqft_from_text = text_extraction.get("sqft_from_text", [])
    if sqft_from_text:
        cv_sqft = max(sqft_from_text)
        llm_sqft = merged["estimated_sqft"]
        diff = abs(cv_sqft - llm_sqft) / max(cv_sqft, llm_sqft) if max(cv_sqft, llm_sqft) > 0 else 0

        if diff > 0.1:
            conflicts.append(f"CV OCR sqft ({cv_sqft}) vs LLM estimate ({llm_sqft}) - using OCR value")
            details["cv_overrides"].append("sqft_from_ocr")
        merged["estimated_sqft"] = cv_sqft
        details["sqft_source"] = "cv_ocr"

    # RULE 2: If CV measured area with scale, use weighted average
    elif (measurements.get("total_area") and
          isinstance(measurements["total_area"], dict) and
          measurements["total_area"].get("value") and
          scale.get("detected")):
        cv_sqft = measurements["total_area"]["value"]
        llm_sqft = merged["estimated_sqft"]
        diff = abs(cv_sqft - llm_sqft) / max(cv_sqft, llm_sqft) if max(cv_sqft, llm_sqft) > 0 else 0

        if diff > 0.25:
            conflicts.append(f"CV measured sqft ({cv_sqft}) vs LLM estimate ({llm_sqft})")
            # Weight CV more heavily when scale is detected
            merged["estimated_sqft"] = round(cv_sqft * 0.7 + llm_sqft * 0.3)
            details["cv_overrides"].append("sqft_from_measurement")
            details["sqft_source"] = "cv_measured"

    # RULE 3: Room count sanity check
    cv_rooms = counts.get("rooms", 0) or cv.get("room_count", 0) or 0
    if cv_rooms > 0:
        # Typical room sizes: 100-400 SF per room
        expected_min_sqft = cv_rooms * 100
        expected_max_sqft = cv_rooms * 500

        if merged["estimated_sqft"] < expected_min_sqft:
            details["warnings"].append(
                f"Sqft ({merged['estimated_sqft']}) seems low for {cv_rooms} rooms"
            )
        if merged["estimated_sqft"] > expected_max_sqft and merged["stories"] == 1:
            details["warnings"].append(
                f"Sqft ({merged['estimated_sqft']}) seems high for {cv_rooms} rooms on 1 story"
            )
        # If many rooms but single story, might be multi-story
        if cv_rooms > 8 and merged["stories"] == 1 and merged["building_type"] == "residential":
            details["warnings"].append(
                f"{cv_rooms} rooms detected but only 1 story - verify floor count"
            )

    # RULE 4: Door/window counts for quality validation
    doors = counts.get("doors", 0) or 0
    windows = counts.get("windows", 0) or 0

    if doors > 0 or windows > 0:
        sqft_thousands = merged["estimated_sqft"] / 1000 if merged["estimated_sqft"] > 0 else 1
        window_density = windows / sqft_thousands

        if window_density > 15 and merged["quality"] == "low":
            details["warnings"].append(
                f"High window density ({window_density:.1f}/1000sf) suggests higher quality"
            )
        if window_density < 5 and merged["quality"] == "high":
            details["warnings"].append(
                f"Low window density ({window_density:.1f}/1000sf) - verify quality level"
            )

    # RULE 5: Drawing type validation
    if cv.get("drawing_type") == "photo" and merged.get("construction_type") == "unknown":
        merged["construction_type"] = "existing_structure"

    # RULE 6: Merge CV-detected materials with LLM materials
    if materials:
        cv_materials = [k for k, v in materials.items() if v]
        existing = merged.get("materials_detected", [])
        new_materials = [m for m in cv_materials if m not in existing]
        if new_materials:
            merged["materials_detected"] = existing + new_materials
            details["cv_overrides"].append(f"materials: +{', '.join(new_materials)}")

    # RULE 7: Add CV-extracted specs/grades to notes
    grades_specs = text_extraction.get("grades_specs", [])
    if grades_specs:
        specs = ", ".join(grades_specs[:5])
        if merged.get("notes"):
            merged["notes"] = f"{merged['notes']} | CV specs: {specs}"
        else:
            merged["notes"] = f"CV specs: {specs}"

    # RULE 8: Use CV dimensions in notes if available
    dimensions_found = text_extraction.get("dimensions_found", [])
    if dimensions_found:
        dims = ", ".join(dimensions_found[:5])
        if merged.get("notes"):
            merged["notes"] = f"{merged['notes']} | Dimensions: {dims}"
        else:
            merged["notes"] = f"Dimensions: {dims}"


def _validate_sub_type(merged: dict, conflicts: list) -> None:
    """
    Validate and normalize sub_type against known types.
    Direct port of validateSubType from reconcile.ts.
    """
    if merged["sub_type"] in ALL_SUBTYPES:
        return

    original = merged["sub_type"]

    # Try to find a close match
    import re
    normalized = re.sub(r"[-\s]", "_", merged["sub_type"].lower())
    match = None
    for st in ALL_SUBTYPES:
        if st.lower() in normalized or normalized in st.lower().replace("_", ""):
            match = st
            break

    if match:
        merged["sub_type"] = match
        conflicts.append(f"Normalized sub_type: {original} → {match}")
    else:
        # Default based on building type
        defaults = {
            "residential": "single_family_standard",
            "commercial": "office_lowrise",
            "industrial": "warehouse_light",
            "institutional": "school_elementary",
            "infrastructure": "parking_surface",
        }
        merged["sub_type"] = defaults.get(merged["building_type"], "single_family_standard")
        conflicts.append(f"Unknown sub_type: {original}, defaulted to {merged['sub_type']}")


def _calculate_final_confidence(
    merged: dict,
    conflicts: list,
    details: dict,
    opencv: Optional[dict] = None,
) -> float:
    """
    Calculate final confidence score with boosts/penalties.
    Direct port of calculateFinalConfidence from reconcile.ts.
    """
    confidence = merged.get("confidence", 0.5)

    # Boost for CV validation
    if details["sqft_source"] == "cv_ocr":
        confidence += 0.15  # High confidence in OCR-extracted sqft
    elif details["sqft_source"] == "cv_measured":
        confidence += 0.10

    # Boost for LLM consensus
    if len(details["llm_consensus"]) >= 3:
        confidence += 0.10

    # Penalty for conflicts
    confidence -= len(conflicts) * 0.03

    # Penalty for warnings
    confidence -= len(details["warnings"]) * 0.02

    # Boost if CV has high confidence
    if opencv and opencv.get("confidence", 0) > 0.7:
        confidence += 0.05

    # Ensure valid range
    return max(0.1, min(1.0, confidence))


def _build_from_cv_only(
    opencv: Optional[dict],
    conflicts: list,
) -> dict:
    """
    Build a reconciliation result from CV data only (no LLM results).
    Direct port of buildFromCVOnly from reconcile.ts.
    """
    conflicts.append("No LLM analysis available - using CV data only")

    merged = {
        "building_type": "residential",
        "sub_type": "single_family_standard",
        "quality": "mid",
        "estimated_sqft": 2000,
        "stories": 1,
        "materials_detected": [],
        "construction_type": "unknown",
        "confidence": 0.2,
        "notes": "Built from CV analysis only",
    }

    if opencv:
        text_extraction = opencv.get("text_extraction", {}) or {}
        measurements = opencv.get("measurements", {}) or {}
        counts = opencv.get("counts", {}) or {}
        materials = opencv.get("materials", {}) or {}

        # Use CV sqft if available
        sqft_from_text = text_extraction.get("sqft_from_text", [])
        if sqft_from_text:
            merged["estimated_sqft"] = max(sqft_from_text)
            merged["confidence"] += 0.2
        elif (measurements.get("total_area") and
              isinstance(measurements["total_area"], dict) and
              measurements["total_area"].get("value")):
            merged["estimated_sqft"] = measurements["total_area"]["value"]
            merged["confidence"] += 0.1

        # Use CV materials
        if materials:
            merged["materials_detected"] = [k for k, v in materials.items() if v]

        # Infer building type from room count and drawing type
        rooms = counts.get("rooms", 0) or opencv.get("room_count", 0) or 0
        if opencv.get("drawing_type") == "floor_plan":
            if rooms > 20:
                merged["building_type"] = "commercial"
                merged["sub_type"] = "office_lowrise"
            elif rooms > 10:
                merged["building_type"] = "residential"
                merged["sub_type"] = "apartment_lowrise"

    return {
        "merged": merged,
        "conflicts": conflicts,
        "confidence": round(merged["confidence"] * 100) / 100,
        "sources": {"opencv": opencv},
    }
