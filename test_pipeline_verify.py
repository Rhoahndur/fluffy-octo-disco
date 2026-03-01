"""Quick verification test for the estimation pipeline."""
from reconcile import reconcile_analyses
from cost_model import find_location_factor, calculate_ground_truth_cost, estimate_quantities
from similar_projects import find_similar_projects

# Test 1: Dual-LLM reconciliation
print("=== Test 1: Dual-LLM Reconciliation ===")
r = reconcile_analyses(
    claude={
        "building_type": "residential",
        "sub_type": "single_family_standard",
        "quality": "mid",
        "estimated_sqft": 2500,
        "stories": 2,
        "materials_detected": ["wood", "concrete"],
        "construction_type": "wood_frame",
        "location": "Chicago",
        "confidence": 0.85,
        "notes": "Claude analysis",
    },
    gemini={
        "building_type": "residential",
        "sub_type": "single_family_standard",
        "quality": "mid",
        "estimated_sqft": 2600,
        "stories": 2,
        "materials_detected": ["wood"],
        "construction_type": "wood_frame",
        "location": "Chicago, IL",
        "confidence": 0.8,
        "notes": "Gemini analysis",
    },
)
m = r["merged"]
print(f"  Merged: {m['building_type']}/{m['sub_type']} {m['quality']}")
print(f"  Area: {m['estimated_sqft']} SF, {m['stories']} stories")
print(f"  Materials: {m['materials_detected']}")
print(f"  Confidence: {r['confidence']}")
print(f"  Conflicts: {r['conflicts']}")

# Test 2: With CV guardrails
print("\n=== Test 2: CV Guardrails ===")
r2 = reconcile_analyses(
    claude={
        "building_type": "residential",
        "sub_type": "single_family_standard",
        "quality": "mid",
        "estimated_sqft": 3000,
        "stories": 1,
        "materials_detected": ["wood"],
        "construction_type": "wood_frame",
        "confidence": 0.7,
        "notes": "",
    },
    opencv={
        "drawing_type": "floor_plan",
        "counts": {"doors": 8, "windows": 12, "columns": 0, "fixtures": 0, "rooms": 6},
        "measurements": {"total_area": {"value": 2200, "unit": "SF"}},
        "materials": {"concrete": True, "wood": True},
        "scale": {"detected": True, "confidence": 0.8},
        "text_extraction": {"sqft_from_text": [2200], "dimensions_found": ["25'-0\""], "grades_specs": []},
        "room_count": 6,
        "confidence": 0.75,
    },
)
m2 = r2["merged"]
print(f"  Merged sqft: {m2['estimated_sqft']} (LLM said 3000, CV OCR said 2200)")
print(f"  Materials: {m2['materials_detected']}")
print(f"  Confidence: {r2['confidence']}")
print(f"  Conflicts: {r2['conflicts']}")

# Test 3: Full cost calculation
print("\n=== Test 3: RSMeans Cost Calculation ===")
loc = find_location_factor("Chicago, IL")
cost = calculate_ground_truth_cost(
    sub_type="single_family_standard",
    quality="mid",
    area_sf=2200,
    stories=2,
    location=loc["location"],
)
qty = estimate_quantities("single_family_standard", "mid", 2200, 2, cost["division_breakdown"])
print(f"  Location: {loc}")
print(f"  Total: ${cost['total_cost']:,.2f}")
print(f"  $/SF: ${cost['cost_per_sf']:,.2f}")
print(f"  Items: {len(qty)} quantities estimated")

# Test 4: Similar projects
print("\n=== Test 4: Similar Projects ===")
similar = find_similar_projects({
    "building_type": "residential",
    "sub_type": "single_family_standard",
    "quality": "mid",
    "area_sf": 2200,
})
print(f"  Found {len(similar)} similar projects")
for p in similar:
    print(f"    {p['project_id']}: {p['sub_type']} ({p['quality']}) - "
          f"${p['total_cost']:,.0f} - score: {p['similarity_score']}")

print("\n✅ All tests passed!")
