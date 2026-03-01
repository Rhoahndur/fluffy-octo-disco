"""
LLM Prompts for Construction Analysis

Direct port of web/src/lib/llm/prompts.ts
Provides system/user prompts and context types for LLM-based construction estimation.
"""

import json
from typing import Optional, Any

# ─── SYSTEM PROMPT ────────────────────────────────────────────────────

ANALYSIS_SYSTEM_PROMPT = """You are an expert construction cost estimator analyzing project images, descriptions, and extracted data. Your task is to identify key characteristics that affect construction costs.

You may receive pre-processed data from:
1. **OpenCV Analysis** - Deterministic measurements from construction drawings (counts, areas, dimensions)
2. **PDF Extraction** - Text and data extracted from specification documents

IMPORTANT: When pre-processed data is provided:
- Use OpenCV sqft values (from area_callouts_sf or gross_floor_area) as ground truth for estimated_sqft
- Use OpenCV counts (doors, windows, rooms) to inform your analysis
- Use PDF-extracted specifications to determine quality and materials
- Your role is to INTERPRET and CLASSIFY, not re-measure what has already been measured
- If OpenCV and your visual analysis disagree on counts/measurements, trust OpenCV

You must return a valid JSON object with the following structure:
{
  "building_type": "residential" | "commercial" | "industrial" | "institutional" | "infrastructure",
  "sub_type": "<specific building sub-type>",
  "quality": "low" | "mid" | "high",
  "estimated_sqft": <number>,
  "stories": <number>,
  "materials_detected": ["<material1>", "<material2>", ...],
  "construction_type": "wood_frame" | "steel_frame" | "concrete" | "masonry" | "mixed",
  "location": "<city or region if identifiable>",
  "confidence": <0.0 to 1.0>,
  "notes": "<any relevant observations>"
}

Valid sub_types by building_type:
- residential: single_family_economy, single_family_standard, single_family_premium, single_family_custom, multi_family_duplex, multi_family_triplex, multi_family_fourplex, apartment_lowrise, apartment_midrise, apartment_garden, townhouse_standard, townhouse_luxury, condo_midrise, luxury_estate, custom_architectural
- commercial: office_lowrise, office_midrise, office_highrise, retail_strip, retail_bigbox, restaurant_casual, restaurant_fine, hotel_limited, hotel_full_service, bank_branch, medical_office, mixed_use
- industrial: warehouse_light, warehouse_heavy, manufacturing_light, manufacturing_heavy, data_center, research_lab, cold_storage, food_processing
- institutional: school_elementary, school_high, university_classroom, university_science, hospital_acute, clinic_outpatient, church_standard, church_cathedral, library_public, community_center
- infrastructure: parking_surface, parking_structured, fire_station, police_station, transit_station, bus_maintenance, water_treatment, electrical_substation

Quality indicators:
- low: Basic finishes, standard materials, minimal architectural detail
- mid: Good quality finishes, standard construction, some architectural features
- high: Premium finishes, high-end materials, significant architectural detail

Be conservative in your estimates. If uncertain, indicate lower confidence and explain in notes."""


# ─── CONTEXT TYPES ────────────────────────────────────────────────────

# These mirror the TypeScript interfaces CVAnalysisForLLM, PDFExtractionForLLM, AnalysisContext
# In Python we use plain dicts with these as documentation


def build_analysis_user_prompt(
    description: str,
    has_images: bool,
    context: Optional[dict] = None,
) -> str:
    """
    Build the user prompt for LLM analysis.
    Direct port of ANALYSIS_USER_PROMPT from prompts.ts.

    Args:
        description: Project description text
        has_images: Whether images are included
        context: Optional dict with 'cv_analysis' and/or 'pdf_extraction' keys
    """
    prompt = "Analyze the following construction project and provide your assessment as JSON.\n\n"

    # Add CV analysis context if available
    cv_analysis = context.get("cv_analysis") if context else None
    if cv_analysis:
        prompt += "## Pre-Processed OpenCV Analysis\n"
        prompt += "The following data was extracted from the drawing using computer vision. Use these measurements as ground truth:\n\n"
        prompt += "```json\n"
        prompt += json.dumps(cv_analysis, indent=2)
        prompt += "\n```\n\n"
        prompt += "Key points from CV analysis:\n"

        text_extractions = cv_analysis.get("text_extractions", {})
        area_callouts = text_extractions.get("area_callouts_sf", [])
        if area_callouts:
            prompt += f"- Area from drawing text: {max(area_callouts)} SF (use this for estimated_sqft)\n"

        takeoff = cv_analysis.get("takeoff", {})
        if isinstance(takeoff, dict):
            gfa = takeoff.get("gross_floor_area")
            if isinstance(gfa, dict) and gfa.get("value"):
                prompt += f"- Calculated floor area: {gfa['value']} SF\n"
            door_count = takeoff.get("door_count")
            if isinstance(door_count, dict) and door_count.get("value"):
                prompt += f"- Door count: {door_count['value']}\n"
            window_count = takeoff.get("window_count")
            if isinstance(window_count, dict) and window_count.get("value"):
                prompt += f"- Window count: {window_count['value']}\n"
            room_count = takeoff.get("room_count")
            if isinstance(room_count, dict) and room_count.get("value"):
                prompt += f"- Room count: {room_count['value']}\n"

        prompt += "\n"

    # Add PDF extraction context if available
    pdf_extraction = context.get("pdf_extraction") if context else None
    if pdf_extraction:
        prompt += "## Pre-Processed PDF Extraction\n"
        prompt += "The following data was extracted from specification documents:\n\n"
        prompt += "```json\n"
        prompt += json.dumps(pdf_extraction, indent=2)
        prompt += "\n```\n\n"

        project_info = pdf_extraction.get("project_info", {})
        if project_info.get("total_area"):
            prompt += f"- Project specified area: {project_info['total_area']} SF\n"
        if project_info.get("location"):
            prompt += f"- Project location: {project_info['location']}\n"
        prompt += "\n"

    if has_images:
        prompt += "I have provided image(s) of the project. Please analyze them carefully.\n\n"

    if description:
        prompt += f"## Project Description\n{description}\n\n"

    prompt += "## Your Task\n"
    prompt += "Provide your analysis as a valid JSON object following the schema described in the system prompt.\n"

    if cv_analysis or pdf_extraction:
        prompt += "Remember: Use the pre-processed measurements as ground truth. Your job is to classify and interpret, not re-measure."

    return prompt


FOLLOWUP_SYSTEM_PROMPT = """You are helping gather additional information for a construction cost estimate. Based on the initial analysis, ask clarifying questions to improve the estimate accuracy.

Focus on:
1. Square footage if not clear
2. Location if not specified
3. Quality level preferences
4. Specific features that affect cost (e.g., basement, garage, special equipment)
5. Timeline requirements

Be concise and ask only the most important questions."""
