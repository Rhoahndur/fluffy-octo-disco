"""
Construction Cost Estimation Agent

Direct port of web/src/app/api/estimate/route.ts
Full pipeline: OpenCV → dual LLM (Claude + Gemini) → Reconciliation → RSMeans → Similar Projects

Usage:
    python cost_estimator.py --input results/test_extraction.json --output results/test_cost_estimations.json

Environment variables:
    ANTHROPIC_API_KEY     - Required for Claude analysis
    GOOGLE_AI_API_KEY     - Required for Gemini analysis
    MODAL_ENDPOINT_URL    - Optional, for OpenCV analysis (graceful degradation if not set)
"""

import os
import sys
import json
import uuid
import base64
import argparse
import concurrent.futures
from pathlib import Path
from datetime import datetime, timezone

# Local modules (direct ports of web app TypeScript)
from cv_client import analyze_with_opencv
from llm_claude import analyze_with_claude
from llm_gemini import analyze_with_gemini
from reconcile import reconcile_analyses
from cost_model import (
    calculate_ground_truth_cost,
    find_location_factor,
    estimate_quantities,
    SUBTYPE_TO_PROFILE,
    CSI_DIVISION_PROFILES,
    CSI_DIVISIONS,
    COST_PER_SF,
)
from similar_projects import find_similar_projects


def encode_image(image_path: str) -> str:
    """Encodes an image to base64 with data URI prefix."""
    suffix = Path(image_path).suffix.lower()
    mime_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix, "image/jpeg")

    with open(image_path, "rb") as image_file:
        b64 = base64.b64encode(image_file.read()).decode("utf-8")
    return f"data:{mime_type};base64,{b64}"


def get_floor_plan_images(project_id: str, floor_plans_dir: str = "rich_floor_plans") -> list[str]:
    """Retrieves and encodes all floor plan images for a given project."""
    project_dir = Path(floor_plans_dir) / project_id
    image_messages = []

    if not project_dir.exists() or not project_dir.is_dir():
        print(f"  Warning: No floor plan directory found for {project_id} at {project_dir}")
        return image_messages

    for image_path in sorted(project_dir.glob("*.[jp][pn][g]")):  # Matches .jpg, .png, .jpeg
        image_messages.append(encode_image(str(image_path)))
        print(f"  Loaded floor plan: {image_path.name}")

    return image_messages


def estimate_project(project_data: dict, floor_plan_images: list[str], description: str = "") -> dict:
    """
    Run the full estimation pipeline for a single project.
    Direct port of the POST handler in web/src/app/api/estimate/route.ts.

    Pipeline:
      1. OpenCV analysis (deterministic, fast)
      2. Dual LLM analysis (Claude + Gemini) with CV context
      3. Reconcile all sources
      4. Location factor lookup
      5. RSMeans cost calculation
      6. Similar project matching

    Returns:
        EstimateResponse-shaped dict
    """
    images = floor_plan_images

    # Build description from project data if not provided
    if not description:
        qualitative = project_data.get("qualitative_insights", {})
        structured = project_data.get("structured_fields", {})
        parts = []
        if qualitative:
            parts.append(json.dumps(qualitative, indent=2))
        if structured:
            parts.append(json.dumps(structured, indent=2))
        description = "\n\n".join(parts)

    # ── Step 1: OpenCV Analysis (deterministic, fast) ──────────────────
    print("  Step 1: OpenCV analysis...")
    opencv_result = None
    if images:
        try:
            opencv_result = analyze_with_opencv(images[0])
            if opencv_result:
                print(f"    ✓ OpenCV: {opencv_result['analysis'].get('drawing_type', 'unknown')} "
                      f"(confidence: {opencv_result['analysis'].get('confidence', 0):.2f})")
            else:
                print("    ○ OpenCV: skipped (Modal not configured)")
        except Exception as err:
            print(f"    ✗ OpenCV: failed ({err})")

    # Extract CV data for LLM context and reconciliation
    opencv_analysis = opencv_result["analysis"] if opencv_result else None
    opencv_for_llm = opencv_result["raw_for_llm"] if opencv_result else None

    # Build context for LLMs (CV + PDF data)
    llm_context = {
        "cv_analysis": opencv_for_llm,
        "pdf_extraction": None,  # Could be populated from pdf_pipeline output
    }

    # ── Step 2: Dual LLM Analysis (parallel, with CV context) ──────────
    print("  Step 2: Dual LLM analysis (Claude + Gemini)...")
    claude_result = None
    gemini_result = None

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        claude_future = executor.submit(analyze_with_claude, images, description, llm_context)
        gemini_future = executor.submit(analyze_with_gemini, images, description, llm_context)

        try:
            claude_result = claude_future.result(timeout=120)
        except Exception as err:
            print(f"    ✗ Claude: failed ({err})")
            claude_result = None

        try:
            gemini_result = gemini_future.result(timeout=120)
        except Exception as err:
            print(f"    ✗ Gemini: failed ({err})")
            gemini_result = None

    # Extract successful results
    claude_analysis = claude_result.get("data") if claude_result and claude_result.get("success") else None
    gemini_analysis = gemini_result.get("data") if gemini_result and gemini_result.get("success") else None

    if claude_analysis:
        print(f"    ✓ Claude: {claude_analysis.get('building_type', '?')} / "
              f"{claude_analysis.get('sub_type', '?')} "
              f"(confidence: {claude_analysis.get('confidence', 0):.2f})")
    else:
        error_msg = claude_result.get("error", {}).get("error", "unknown") if claude_result else "not configured"
        print(f"    ✗ Claude: {error_msg}")

    if gemini_analysis:
        print(f"    ✓ Gemini: {gemini_analysis.get('building_type', '?')} / "
              f"{gemini_analysis.get('sub_type', '?')} "
              f"(confidence: {gemini_analysis.get('confidence', 0):.2f})")
    else:
        error_msg = gemini_result.get("error", {}).get("error", "unknown") if gemini_result else "not configured"
        print(f"    ✗ Gemini: {error_msg}")

    # ── Step 3: Reconcile all sources ──────────────────────────────────
    print("  Step 3: Reconciling analyses...")

    # Check if we have at least one LLM result
    if not claude_analysis and not gemini_analysis:
        print("    ⚠ No LLM results available - using fallback")
        reconciliation = reconcile_analyses(
            claude=None,
            gemini=None,
            opencv=opencv_analysis,
        )
    else:
        reconciliation = reconcile_analyses(
            claude=claude_analysis,
            gemini=gemini_analysis,
            opencv=opencv_analysis,
        )

    merged = reconciliation["merged"]
    confidence = reconciliation["confidence"]

    print(f"    Result: {merged['building_type']} / {merged['sub_type']} "
          f"({merged['quality']}) — {merged['estimated_sqft']} SF, "
          f"{merged['stories']} stories (confidence: {confidence:.2f})")

    if reconciliation["conflicts"]:
        for c in reconciliation["conflicts"][:3]:
            print(f"    ⚡ {c}")

    # ── Step 4: Location factor ────────────────────────────────────────
    print("  Step 4: Location factor lookup...")
    location_text = merged.get("location") or "national"
    location_info = find_location_factor(location_text)
    print(f"    Location: {location_info['location']} (factor: {location_info['factor']})")

    # ── Step 5: RSMeans cost calculation ───────────────────────────────
    print("  Step 5: RSMeans cost calculation...")

    sub_type = merged["sub_type"]
    quality = merged["quality"]
    area_sf = merged["estimated_sqft"]
    stories = merged["stories"]

    # Validate sub_type exists in cost data
    if sub_type not in COST_PER_SF:
        print(f"    ⚠ Sub-type '{sub_type}' not in cost data, defaulting to single_family_standard")
        sub_type = "single_family_standard"

    # Validate quality
    if quality not in ("low", "mid", "high"):
        quality = "mid"

    # Validate location for cost model (must be exact match)
    location_key = location_info["location"]

    cost_result = calculate_ground_truth_cost(
        sub_type=sub_type,
        quality=quality,
        area_sf=area_sf,
        stories=stories,
        location=location_key,
    )

    # Add item quantities (from web app's estimateQuantities)
    item_quantities = estimate_quantities(
        sub_type=sub_type,
        quality=quality,
        area_sf=area_sf,
        stories=stories,
        breakdown=cost_result["division_breakdown"],
    )
    cost_result["item_quantities"] = item_quantities

    print(f"    Total: ${cost_result['total_cost']:,.2f}")
    print(f"    $/SF:  ${cost_result['cost_per_sf']:,.2f}")

    # ── Step 6: Similar project matching ───────────────────────────────
    print("  Step 6: Finding similar projects...")
    similar_projects = find_similar_projects({
        "building_type": merged["building_type"],
        "sub_type": merged["sub_type"],
        "quality": merged["quality"],
        "area_sf": merged["estimated_sqft"],
    })
    print(f"    Found {len(similar_projects)} similar projects")

    # ── Build response (matching web app's EstimateResponse) ──────────
    estimate_id = str(uuid.uuid4())
    response = {
        "id": estimate_id,
        "project_id": project_data.get("project_id", ""),
        "status": "complete",
        "estimate": cost_result,
        "analysis": reconciliation,
        "similar_projects": similar_projects,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    return response


def main():
    parser = argparse.ArgumentParser(
        description="Construction cost estimation agent. "
                    "Mirrors the web app pipeline: OpenCV → dual LLM → reconcile → RSMeans → similar projects."
    )
    parser.add_argument("--input", default="results/test_extraction.json",
                        help="Path to the input JSON file.")
    parser.add_argument("--output", default="results/test_cost_estimations.json",
                        help="Path to save the output.")
    parser.add_argument("--floor_plans", default="rich_floor_plans",
                        help="Directory containing floor plan subdirectories.")
    args = parser.parse_args()

    # Check for at least one LLM API key
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_google = bool(os.environ.get("GOOGLE_AI_API_KEY"))
    has_modal = bool(os.environ.get("MODAL_ENDPOINT_URL"))

    print("=" * 60)
    print("Construction Cost Estimation Agent")
    print("=" * 60)
    print(f"  Claude (Anthropic):  {'✓ configured' if has_anthropic else '✗ ANTHROPIC_API_KEY not set'}")
    print(f"  Gemini (Google AI):  {'✓ configured' if has_google else '✗ GOOGLE_AI_API_KEY not set'}")
    print(f"  OpenCV (Modal):      {'✓ configured' if has_modal else '○ MODAL_ENDPOINT_URL not set (optional)'}")
    print()

    if not has_anthropic and not has_google:
        print("WARNING: No LLM API keys configured. Results will be CV-only fallback estimates.")
        print("Set ANTHROPIC_API_KEY and/or GOOGLE_AI_API_KEY environment variables.")
        print()

    # Load input JSON
    try:
        with open(args.input, "r") as f:
            projects = json.load(f)
    except Exception as e:
        print(f"Failed to load input file {args.input}: {e}")
        return

    print(f"Processing {len(projects)} projects from {args.input}")
    print()

    results = []

    for i, project in enumerate(projects, 1):
        project_id = project.get("project_id", f"project_{i}")

        print(f"{'─' * 60}")
        print(f"Project {i}/{len(projects)}: {project_id}")
        print(f"{'─' * 60}")

        # 1. Load floor plan images
        floor_plan_images = get_floor_plan_images(project_id, args.floor_plans)

        # 2. Run full estimation pipeline
        result = estimate_project(project, floor_plan_images)

        print(f"\n  ✅ Estimated cost: ${result['estimate']['total_cost']:,.2f}")
        print()

        results.append(result)

    # Output results
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)

    print(f"{'=' * 60}")
    print(f"Saved {len(results)} estimations to {args.output}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
