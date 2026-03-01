"""
Construction Cost Calculation Engine

RSMeans-based cost model with hardcoded data tables derived from
RSMeans 2024-2025 national averages. Provides ground truth cost
calculations for the evaluation dataset.
"""

import random
from typing import Dict, Optional, Tuple

# ─── COST PER SQUARE FOOT ─────────────────────────────────────────────
# ~40 building sub-types × 3 quality levels (low / mid / high)
# Values derived from RSMeans 2024-2025 national average $/SF

COST_PER_SF: Dict[str, Dict[str, float]] = {
    # ── Residential ──
    "single_family_economy":    {"low": 120, "mid": 162, "high": 195},
    "single_family_standard":   {"low": 145, "mid": 195, "high": 260},
    "single_family_premium":    {"low": 195, "mid": 275, "high": 370},
    "single_family_custom":     {"low": 275, "mid": 385, "high": 525},
    "multi_family_duplex":      {"low": 130, "mid": 178, "high": 235},
    "multi_family_triplex":     {"low": 125, "mid": 172, "high": 225},
    "multi_family_fourplex":    {"low": 118, "mid": 165, "high": 218},
    "apartment_lowrise":        {"low": 140, "mid": 195, "high": 275},
    "apartment_midrise":        {"low": 175, "mid": 248, "high": 340},
    "apartment_garden":         {"low": 128, "mid": 178, "high": 245},
    "townhouse_standard":       {"low": 135, "mid": 185, "high": 250},
    "townhouse_luxury":         {"low": 210, "mid": 305, "high": 425},
    "condo_midrise":            {"low": 185, "mid": 265, "high": 380},
    "luxury_estate":            {"low": 350, "mid": 525, "high": 750},
    "custom_architectural":     {"low": 400, "mid": 600, "high": 900},

    # ── Commercial ──
    "office_lowrise":           {"low": 225, "mid": 362, "high": 530},
    "office_midrise":           {"low": 330, "mid": 562, "high": 870},
    "office_highrise":          {"low": 420, "mid": 685, "high": 1050},
    "retail_strip":             {"low": 145, "mid": 248, "high": 385},
    "retail_bigbox":            {"low": 110, "mid": 185, "high": 290},
    "restaurant_casual":        {"low": 250, "mid": 395, "high": 580},
    "restaurant_fine":          {"low": 380, "mid": 575, "high": 850},
    "hotel_limited":            {"low": 210, "mid": 342, "high": 495},
    "hotel_full_service":       {"low": 340, "mid": 548, "high": 820},
    "bank_branch":              {"low": 280, "mid": 425, "high": 620},
    "medical_office":           {"low": 290, "mid": 448, "high": 650},
    "mixed_use":                {"low": 260, "mid": 420, "high": 640},

    # ── Industrial ──
    "warehouse_light":          {"low":  90, "mid": 238, "high": 350},
    "warehouse_heavy":          {"low": 120, "mid": 285, "high": 420},
    "manufacturing_light":      {"low": 110, "mid": 268, "high": 395},
    "manufacturing_heavy":      {"low": 145, "mid": 325, "high": 490},
    "data_center":              {"low": 750, "mid": 1250, "high": 1950},
    "research_lab":             {"low": 480, "mid": 788, "high": 1150},
    "cold_storage":             {"low": 175, "mid": 348, "high": 520},
    "food_processing":          {"low": 220, "mid": 385, "high": 575},

    # ── Institutional ──
    "school_elementary":        {"low": 225, "mid": 365, "high": 520},
    "school_high":              {"low": 275, "mid": 432, "high": 620},
    "university_classroom":     {"low": 310, "mid": 488, "high": 700},
    "university_science":       {"low": 450, "mid": 725, "high": 1050},
    "hospital_acute":           {"low": 600, "mid": 888, "high": 1020},
    "clinic_outpatient":        {"low": 320, "mid": 498, "high": 700},
    "church_standard":          {"low": 180, "mid": 295, "high": 440},
    "church_cathedral":         {"low": 350, "mid": 575, "high": 880},
    "library_public":           {"low": 290, "mid": 452, "high": 650},
    "community_center":         {"low": 220, "mid": 358, "high": 520},

    # ── Infrastructure ──
    "parking_surface":          {"low":  25, "mid":  45, "high":  72},
    "parking_structured":       {"low":  65, "mid": 105, "high": 165},
    "fire_station":             {"low": 280, "mid": 432, "high": 620},
    "police_station":           {"low": 310, "mid": 475, "high": 680},
    "transit_station":          {"low": 350, "mid": 548, "high": 790},
    "bus_maintenance":          {"low": 195, "mid": 325, "high": 480},
    "water_treatment":          {"low": 420, "mid": 688, "high": 1020},
    "electrical_substation":    {"low": 380, "mid": 625, "high": 940},
}

# ─── CSI DIVISION PROFILES ────────────────────────────────────────────
# 10 profiles, each with 16 CSI MasterFormat divisions summing to ~100%
# Percentages represent typical cost distribution for each building type

CSI_DIVISIONS = [
    "01_general_requirements",
    "02_existing_conditions",
    "03_concrete",
    "04_masonry",
    "05_metals",
    "06_wood_plastics_composites",
    "07_thermal_moisture",
    "08_openings",
    "09_finishes",
    "10_specialties",
    "11_equipment",
    "12_furnishings",
    "13_special_construction",
    "14_conveying_equipment",
    "21_fire_suppression",
    "22_plumbing",
    "23_hvac",
    "26_electrical",
]

CSI_DIVISION_PROFILES: Dict[str, Dict[str, float]] = {
    "residential": {
        "01_general_requirements":    0.06,
        "02_existing_conditions":     0.02,
        "03_concrete":                0.08,
        "04_masonry":                 0.04,
        "05_metals":                  0.02,
        "06_wood_plastics_composites": 0.14,
        "07_thermal_moisture":        0.07,
        "08_openings":                0.06,
        "09_finishes":                0.12,
        "10_specialties":             0.02,
        "11_equipment":               0.01,
        "12_furnishings":             0.02,
        "13_special_construction":    0.01,
        "14_conveying_equipment":     0.00,
        "21_fire_suppression":        0.01,
        "22_plumbing":                0.08,
        "23_hvac":                    0.13,
        "26_electrical":              0.11,
    },
    "commercial_office": {
        "01_general_requirements":    0.08,
        "02_existing_conditions":     0.02,
        "03_concrete":                0.10,
        "04_masonry":                 0.04,
        "05_metals":                  0.10,
        "06_wood_plastics_composites": 0.03,
        "07_thermal_moisture":        0.06,
        "08_openings":                0.07,
        "09_finishes":                0.10,
        "10_specialties":             0.02,
        "11_equipment":               0.02,
        "12_furnishings":             0.02,
        "13_special_construction":    0.01,
        "14_conveying_equipment":     0.03,
        "21_fire_suppression":        0.03,
        "22_plumbing":                0.05,
        "23_hvac":                    0.12,
        "26_electrical":              0.10,
    },
    "commercial_retail": {
        "01_general_requirements":    0.07,
        "02_existing_conditions":     0.02,
        "03_concrete":                0.09,
        "04_masonry":                 0.06,
        "05_metals":                  0.08,
        "06_wood_plastics_composites": 0.04,
        "07_thermal_moisture":        0.07,
        "08_openings":                0.08,
        "09_finishes":                0.11,
        "10_specialties":             0.03,
        "11_equipment":               0.02,
        "12_furnishings":             0.03,
        "13_special_construction":    0.01,
        "14_conveying_equipment":     0.00,
        "21_fire_suppression":        0.03,
        "22_plumbing":                0.05,
        "23_hvac":                    0.12,
        "26_electrical":              0.09,
    },
    "commercial_hospitality": {
        "01_general_requirements":    0.07,
        "02_existing_conditions":     0.02,
        "03_concrete":                0.08,
        "04_masonry":                 0.04,
        "05_metals":                  0.07,
        "06_wood_plastics_composites": 0.05,
        "07_thermal_moisture":        0.06,
        "08_openings":                0.06,
        "09_finishes":                0.12,
        "10_specialties":             0.03,
        "11_equipment":               0.04,
        "12_furnishings":             0.05,
        "13_special_construction":    0.01,
        "14_conveying_equipment":     0.02,
        "21_fire_suppression":        0.03,
        "22_plumbing":                0.07,
        "23_hvac":                    0.10,
        "26_electrical":              0.08,
    },
    "industrial": {
        "01_general_requirements":    0.06,
        "02_existing_conditions":     0.03,
        "03_concrete":                0.12,
        "04_masonry":                 0.05,
        "05_metals":                  0.18,
        "06_wood_plastics_composites": 0.02,
        "07_thermal_moisture":        0.08,
        "08_openings":                0.04,
        "09_finishes":                0.05,
        "10_specialties":             0.01,
        "11_equipment":               0.05,
        "12_furnishings":             0.01,
        "13_special_construction":    0.02,
        "14_conveying_equipment":     0.02,
        "21_fire_suppression":        0.03,
        "22_plumbing":                0.04,
        "23_hvac":                    0.10,
        "26_electrical":              0.09,
    },
    "industrial_data_center": {
        "01_general_requirements":    0.05,
        "02_existing_conditions":     0.02,
        "03_concrete":                0.08,
        "04_masonry":                 0.02,
        "05_metals":                  0.10,
        "06_wood_plastics_composites": 0.01,
        "07_thermal_moisture":        0.05,
        "08_openings":                0.03,
        "09_finishes":                0.04,
        "10_specialties":             0.02,
        "11_equipment":               0.08,
        "12_furnishings":             0.01,
        "13_special_construction":    0.05,
        "14_conveying_equipment":     0.01,
        "21_fire_suppression":        0.04,
        "22_plumbing":                0.03,
        "23_hvac":                    0.18,
        "26_electrical":              0.18,
    },
    "institutional_education": {
        "01_general_requirements":    0.08,
        "02_existing_conditions":     0.02,
        "03_concrete":                0.09,
        "04_masonry":                 0.06,
        "05_metals":                  0.08,
        "06_wood_plastics_composites": 0.05,
        "07_thermal_moisture":        0.06,
        "08_openings":                0.07,
        "09_finishes":                0.10,
        "10_specialties":             0.03,
        "11_equipment":               0.03,
        "12_furnishings":             0.03,
        "13_special_construction":    0.01,
        "14_conveying_equipment":     0.01,
        "21_fire_suppression":        0.03,
        "22_plumbing":                0.05,
        "23_hvac":                    0.11,
        "26_electrical":              0.09,
    },
    "institutional_healthcare": {
        "01_general_requirements":    0.10,
        "02_existing_conditions":     0.02,
        "03_concrete":                0.09,
        "04_masonry":                 0.03,
        "05_metals":                  0.07,
        "06_wood_plastics_composites": 0.03,
        "07_thermal_moisture":        0.05,
        "08_openings":                0.05,
        "09_finishes":                0.08,
        "10_specialties":             0.03,
        "11_equipment":               0.06,
        "12_furnishings":             0.02,
        "13_special_construction":    0.02,
        "14_conveying_equipment":     0.03,
        "21_fire_suppression":        0.04,
        "22_plumbing":                0.07,
        "23_hvac":                    0.12,
        "26_electrical":              0.09,
    },
    "institutional_religious": {
        "01_general_requirements":    0.07,
        "02_existing_conditions":     0.02,
        "03_concrete":                0.08,
        "04_masonry":                 0.10,
        "05_metals":                  0.06,
        "06_wood_plastics_composites": 0.10,
        "07_thermal_moisture":        0.07,
        "08_openings":                0.08,
        "09_finishes":                0.12,
        "10_specialties":             0.03,
        "11_equipment":               0.02,
        "12_furnishings":             0.03,
        "13_special_construction":    0.01,
        "14_conveying_equipment":     0.00,
        "21_fire_suppression":        0.02,
        "22_plumbing":                0.04,
        "23_hvac":                    0.08,
        "26_electrical":              0.07,
    },
    "infrastructure": {
        "01_general_requirements":    0.08,
        "02_existing_conditions":     0.04,
        "03_concrete":                0.15,
        "04_masonry":                 0.05,
        "05_metals":                  0.12,
        "06_wood_plastics_composites": 0.02,
        "07_thermal_moisture":        0.06,
        "08_openings":                0.04,
        "09_finishes":                0.04,
        "10_specialties":             0.02,
        "11_equipment":               0.06,
        "12_furnishings":             0.01,
        "13_special_construction":    0.03,
        "14_conveying_equipment":     0.01,
        "21_fire_suppression":        0.03,
        "22_plumbing":                0.04,
        "23_hvac":                    0.10,
        "26_electrical":              0.10,
    },
}

# ─── LOCATION FACTORS ─────────────────────────────────────────────────
# 27 US cities — multiplier relative to national average (1.00)

LOCATION_FACTORS: Dict[str, float] = {
    "new_york":       1.30,
    "san_francisco":  1.27,
    "boston":          1.24,
    "los_angeles":    1.18,
    "chicago":        1.15,
    "seattle":        1.13,
    "washington_dc":  1.10,
    "denver":         1.08,
    "minneapolis":    1.06,
    "philadelphia":   1.05,
    "portland":       1.04,
    "detroit":        1.02,
    "national":       1.00,
    "miami":          0.98,
    "baltimore":      0.97,
    "las_vegas":      0.96,
    "pittsburgh":     0.95,
    "tampa":          0.93,
    "atlanta":        0.92,
    "phoenix":        0.91,
    "nashville":      0.90,
    "dallas":         0.88,
    "charlotte":      0.87,
    "houston":        0.86,
    "san_antonio":    0.85,
    "indianapolis":   0.84,
    "memphis":        0.82,
}

# ─── SUB-TYPE → CSI PROFILE MAPPING ──────────────────────────────────

SUBTYPE_TO_PROFILE: Dict[str, str] = {
    # Residential
    "single_family_economy":    "residential",
    "single_family_standard":   "residential",
    "single_family_premium":    "residential",
    "single_family_custom":     "residential",
    "multi_family_duplex":      "residential",
    "multi_family_triplex":     "residential",
    "multi_family_fourplex":    "residential",
    "apartment_lowrise":        "residential",
    "apartment_midrise":        "residential",
    "apartment_garden":         "residential",
    "townhouse_standard":       "residential",
    "townhouse_luxury":         "residential",
    "condo_midrise":            "residential",
    "luxury_estate":            "residential",
    "custom_architectural":     "residential",
    # Commercial
    "office_lowrise":           "commercial_office",
    "office_midrise":           "commercial_office",
    "office_highrise":          "commercial_office",
    "retail_strip":             "commercial_retail",
    "retail_bigbox":            "commercial_retail",
    "restaurant_casual":        "commercial_hospitality",
    "restaurant_fine":          "commercial_hospitality",
    "hotel_limited":            "commercial_hospitality",
    "hotel_full_service":       "commercial_hospitality",
    "bank_branch":              "commercial_office",
    "medical_office":           "institutional_healthcare",
    "mixed_use":                "commercial_office",
    # Industrial
    "warehouse_light":          "industrial",
    "warehouse_heavy":          "industrial",
    "manufacturing_light":      "industrial",
    "manufacturing_heavy":      "industrial",
    "data_center":              "industrial_data_center",
    "research_lab":             "industrial_data_center",
    "cold_storage":             "industrial",
    "food_processing":          "industrial",
    # Institutional
    "school_elementary":        "institutional_education",
    "school_high":              "institutional_education",
    "university_classroom":     "institutional_education",
    "university_science":       "institutional_education",
    "hospital_acute":           "institutional_healthcare",
    "clinic_outpatient":        "institutional_healthcare",
    "church_standard":          "institutional_religious",
    "church_cathedral":         "institutional_religious",
    "library_public":           "institutional_education",
    "community_center":         "institutional_education",
    # Infrastructure
    "parking_surface":          "infrastructure",
    "parking_structured":       "infrastructure",
    "fire_station":             "infrastructure",
    "police_station":           "infrastructure",
    "transit_station":          "infrastructure",
    "bus_maintenance":          "infrastructure",
    "water_treatment":          "infrastructure",
    "electrical_substation":    "infrastructure",
}

# ─── SUB-TYPE → BUILDING CATEGORY ────────────────────────────────────

SUBTYPE_TO_CATEGORY: Dict[str, str] = {
    "single_family_economy": "residential", "single_family_standard": "residential",
    "single_family_premium": "residential", "single_family_custom": "residential",
    "multi_family_duplex": "residential", "multi_family_triplex": "residential",
    "multi_family_fourplex": "residential", "apartment_lowrise": "residential",
    "apartment_midrise": "residential", "apartment_garden": "residential",
    "townhouse_standard": "residential", "townhouse_luxury": "residential",
    "condo_midrise": "residential", "luxury_estate": "residential",
    "custom_architectural": "residential",
    "office_lowrise": "commercial", "office_midrise": "commercial",
    "office_highrise": "commercial", "retail_strip": "commercial",
    "retail_bigbox": "commercial", "restaurant_casual": "commercial",
    "restaurant_fine": "commercial", "hotel_limited": "commercial",
    "hotel_full_service": "commercial", "bank_branch": "commercial",
    "medical_office": "commercial", "mixed_use": "commercial",
    "warehouse_light": "industrial", "warehouse_heavy": "industrial",
    "manufacturing_light": "industrial", "manufacturing_heavy": "industrial",
    "data_center": "industrial", "research_lab": "industrial",
    "cold_storage": "industrial", "food_processing": "industrial",
    "school_elementary": "institutional", "school_high": "institutional",
    "university_classroom": "institutional", "university_science": "institutional",
    "hospital_acute": "institutional", "clinic_outpatient": "institutional",
    "church_standard": "institutional", "church_cathedral": "institutional",
    "library_public": "institutional", "community_center": "institutional",
    "parking_surface": "infrastructure", "parking_structured": "infrastructure",
    "fire_station": "infrastructure", "police_station": "infrastructure",
    "transit_station": "infrastructure", "bus_maintenance": "infrastructure",
    "water_treatment": "infrastructure", "electrical_substation": "infrastructure",
}


def calculate_ground_truth_cost(
    sub_type: str,
    quality: str,
    area_sf: float,
    stories: int = 1,
    location: str = "national",
    csi_profile: Optional[str] = None,
    seed: Optional[int] = None,
) -> Dict:
    """
    Calculate ground truth construction cost for a building project.

    Args:
        sub_type: Building sub-type key (e.g. 'single_family_economy')
        quality: Quality level ('low', 'mid', 'high')
        area_sf: Total building area in square feet
        stories: Number of stories (premium applied above 3)
        location: City key from LOCATION_FACTORS
        csi_profile: Override CSI profile name (auto-detected if None)
        seed: Random seed for variance (None = no variance)

    Returns:
        Dict with total_cost, cost_per_sf, division_breakdown, and metadata
    """
    if sub_type not in COST_PER_SF:
        raise ValueError(f"Unknown building sub-type: {sub_type}")
    if quality not in ("low", "mid", "high"):
        raise ValueError(f"Quality must be 'low', 'mid', or 'high', got: {quality}")
    if location not in LOCATION_FACTORS:
        raise ValueError(f"Unknown location: {location}")

    # Base cost per SF
    base_cost_sf = COST_PER_SF[sub_type][quality]

    # Location adjustment
    loc_factor = LOCATION_FACTORS[location]
    adjusted_cost_sf = base_cost_sf * loc_factor

    # Story premium: +2.5% per floor above 3
    story_premium = 1.0
    if stories > 3:
        story_premium = 1.0 + 0.025 * (stories - 3)
    adjusted_cost_sf *= story_premium

    # Seeded random variance (±3%) for realism
    if seed is not None:
        rng = random.Random(seed)
        variance = rng.uniform(-0.03, 0.03)
        adjusted_cost_sf *= (1.0 + variance)

    # Total cost
    total_cost = adjusted_cost_sf * area_sf

    # CSI division breakdown
    profile_name = csi_profile or SUBTYPE_TO_PROFILE.get(sub_type, "commercial_office")
    profile = CSI_DIVISION_PROFILES[profile_name]
    division_breakdown = {}
    for div_name, pct in profile.items():
        division_breakdown[div_name] = round(total_cost * pct, 2)

    return {
        "total_cost": round(total_cost, 2),
        "cost_per_sf": round(adjusted_cost_sf, 2),
        "area_sf": area_sf,
        "stories": stories,
        "quality": quality,
        "location": location,
        "location_factor": loc_factor,
        "story_premium": round(story_premium, 4),
        "base_cost_sf": base_cost_sf,
        "csi_profile": profile_name,
        "division_breakdown": division_breakdown,
    }


def get_all_subtypes() -> list:
    """Return all available building sub-type keys."""
    return list(COST_PER_SF.keys())


def get_all_locations() -> list:
    """Return all available location keys."""
    return list(LOCATION_FACTORS.keys())


def get_category(sub_type: str) -> str:
    """Return the building category for a sub-type."""
    return SUBTYPE_TO_CATEGORY.get(sub_type, "unknown")


if __name__ == "__main__":
    # Quick self-test
    result = calculate_ground_truth_cost(
        sub_type="single_family_standard",
        quality="mid",
        area_sf=2200,
        stories=2,
        location="chicago",
        seed=42,
    )
    print(f"Single Family Standard (mid) — Chicago, 2200 SF, 2 stories:")
    print(f"  Total: ${result['total_cost']:,.2f}")
    print(f"  $/SF:  ${result['cost_per_sf']:,.2f}")
    print(f"  Location factor: {result['location_factor']}")
    div_sum = sum(result["division_breakdown"].values())
    print(f"  Division sum: ${div_sum:,.2f} (should ~ total)")
    print()

    # Verify profile sums
    for name, profile in CSI_DIVISION_PROFILES.items():
        total = sum(profile.values())
        status = "OK" if abs(total - 1.0) < 0.01 else f"WARN ({total:.3f})"
        print(f"  Profile '{name}': sum={total:.3f} [{status}]")


# ─── FUZZY LOCATION FACTOR LOOKUP ─────────────────────────────────────
# Direct port of findLocationFactor from web/src/lib/cost/data/location-factors.ts

# State-based approximations for when city isn't matched
_STATE_MAP: Dict[str, str] = {
    "california": "los_angeles",
    "ca": "los_angeles",
    "texas": "dallas",
    "tx": "dallas",
    "florida": "miami",
    "fl": "miami",
    "illinois": "chicago",
    "il": "chicago",
    "pennsylvania": "philadelphia",
    "pa": "philadelphia",
    "ohio": "detroit",
    "georgia": "atlanta",
    "ga": "atlanta",
    "arizona": "phoenix",
    "az": "phoenix",
    "colorado": "denver",
    "co": "denver",
    "washington": "seattle",
    "wa": "seattle",
    "oregon": "portland",
    "or": "portland",
    "massachusetts": "boston",
    "ma": "boston",
    "tennessee": "nashville",
    "tn": "nashville",
    "north_carolina": "charlotte",
    "nc": "charlotte",
    "nevada": "las_vegas",
    "nv": "las_vegas",
    "minnesota": "minneapolis",
    "mn": "minneapolis",
    "maryland": "baltimore",
    "md": "baltimore",
    "indiana": "indianapolis",
}


def find_location_factor(location_text: str) -> Dict[str, any]:
    """
    Find the best matching location factor from free-form text.
    Direct port of findLocationFactor from location-factors.ts.

    Args:
        location_text: Free-form location text (e.g., "New York, NY", "california")

    Returns:
        Dict with 'location' (normalized key) and 'factor' (multiplier)
    """
    import re
    normalized = re.sub(r"[^a-z]", "_", location_text.lower())

    # Direct match
    if normalized in LOCATION_FACTORS:
        return {"location": normalized, "factor": LOCATION_FACTORS[normalized]}

    # Partial match
    for loc, factor in LOCATION_FACTORS.items():
        if (normalized.replace("_", "") in loc.replace("_", "") or
                loc.replace("_", "") in normalized.replace("_", "")):
            return {"location": loc, "factor": factor}

    # State-based approximations
    for state, city in _STATE_MAP.items():
        if state in normalized:
            return {"location": city, "factor": LOCATION_FACTORS[city]}

    # Default to national average
    return {"location": "national", "factor": 1.0}


# ─── ITEM QUANTITY ESTIMATION ─────────────────────────────────────────
# Direct port of estimateQuantities from web/src/lib/cost/rsmeans.ts

def estimate_quantities(
    sub_type: str,
    quality: str,
    area_sf: float,
    stories: int,
    breakdown: Dict[str, float],
) -> list:
    """
    Estimate material quantities based on building type and area.
    Direct port of estimateQuantities from rsmeans.ts.

    Args:
        sub_type: Building sub-type key
        quality: Quality level (low/mid/high)
        area_sf: Total building area in square feet
        stories: Number of stories
        breakdown: CSI division breakdown (division code -> dollar amount)

    Returns:
        List of ItemQuantity dicts
    """
    quantities = []
    category = SUBTYPE_TO_CATEGORY.get(sub_type, "commercial")

    # Quality multipliers for material quantities
    quality_multiplier = 1.15 if quality == "high" else (0.85 if quality == "low" else 1.0)

    def _safe_div(numerator, denominator):
        return round(numerator / denominator, 2) if denominator and denominator != 0 else 0

    # Concrete (Division 03)
    concrete_yards = round(area_sf * 0.05 * quality_multiplier, 1)
    quantities.append({
        "item": "Concrete (foundation & slab)",
        "quantity": concrete_yards,
        "unit": "cubic yards",
        "unit_cost": _safe_div(breakdown.get("03_concrete", 0), concrete_yards),
        "total_cost": breakdown.get("03_concrete", 0),
        "division": "03_concrete",
    })

    # Lumber/Wood (Division 06) - mainly for residential
    if category == "residential":
        board_feet = round(area_sf * 12 * quality_multiplier)
        quantities.append({
            "item": "Framing lumber",
            "quantity": board_feet,
            "unit": "board feet",
            "unit_cost": _safe_div(breakdown.get("06_wood_plastics_composites", 0), board_feet),
            "total_cost": breakdown.get("06_wood_plastics_composites", 0),
            "division": "06_wood_plastics_composites",
        })

    # Structural steel (Division 05) - mainly for commercial/industrial
    if category != "residential":
        steel_tons = round(area_sf * 0.008 * quality_multiplier, 1)
        quantities.append({
            "item": "Structural steel",
            "quantity": steel_tons,
            "unit": "tons",
            "unit_cost": _safe_div(breakdown.get("05_metals", 0), steel_tons),
            "total_cost": breakdown.get("05_metals", 0),
            "division": "05_metals",
        })

    # Roofing (Division 07)
    roofing_sf = round(area_sf / stories * 1.1) if stories > 0 else round(area_sf * 1.1)
    thermal_cost = breakdown.get("07_thermal_moisture", 0)
    quantities.append({
        "item": "Roofing materials",
        "quantity": roofing_sf,
        "unit": "sq ft",
        "unit_cost": _safe_div(thermal_cost * 0.4, roofing_sf),
        "total_cost": round(thermal_cost * 0.4, 2),
        "division": "07_thermal_moisture",
    })

    # Insulation (Division 07)
    insulation_sf = round(area_sf * 1.5)
    quantities.append({
        "item": "Insulation",
        "quantity": insulation_sf,
        "unit": "sq ft",
        "unit_cost": _safe_div(thermal_cost * 0.6, insulation_sf),
        "total_cost": round(thermal_cost * 0.6, 2),
        "division": "07_thermal_moisture",
    })

    # Windows & Doors (Division 08)
    openings_cost = breakdown.get("08_openings", 0)
    window_count = round(area_sf / 150 * quality_multiplier)
    door_count = round(area_sf / 300)
    quantities.append({
        "item": "Windows",
        "quantity": window_count,
        "unit": "units",
        "unit_cost": _safe_div(openings_cost * 0.7, window_count),
        "total_cost": round(openings_cost * 0.7, 2),
        "division": "08_openings",
    })
    quantities.append({
        "item": "Doors (interior & exterior)",
        "quantity": door_count,
        "unit": "units",
        "unit_cost": _safe_div(openings_cost * 0.3, door_count),
        "total_cost": round(openings_cost * 0.3, 2),
        "division": "08_openings",
    })

    # Drywall (Division 09)
    finishes_cost = breakdown.get("09_finishes", 0)
    drywall_sf = round(area_sf * 3.5)
    quantities.append({
        "item": "Drywall",
        "quantity": drywall_sf,
        "unit": "sq ft",
        "unit_cost": _safe_div(finishes_cost * 0.3, drywall_sf),
        "total_cost": round(finishes_cost * 0.3, 2),
        "division": "09_finishes",
    })

    # Flooring (Division 09)
    quantities.append({
        "item": "Flooring materials",
        "quantity": area_sf,
        "unit": "sq ft",
        "unit_cost": _safe_div(finishes_cost * 0.4, area_sf),
        "total_cost": round(finishes_cost * 0.4, 2),
        "division": "09_finishes",
    })

    # Paint (Division 09)
    paint_sf = round(area_sf * 4)
    quantities.append({
        "item": "Paint & coatings",
        "quantity": paint_sf,
        "unit": "sq ft",
        "unit_cost": _safe_div(finishes_cost * 0.3, paint_sf),
        "total_cost": round(finishes_cost * 0.3, 2),
        "division": "09_finishes",
    })

    # Plumbing fixtures (Division 22)
    plumbing_cost = breakdown.get("22_plumbing", 0)
    fixture_count = round(area_sf / 400 * quality_multiplier)
    quantities.append({
        "item": "Plumbing fixtures",
        "quantity": fixture_count,
        "unit": "fixtures",
        "unit_cost": _safe_div(plumbing_cost * 0.6, fixture_count),
        "total_cost": round(plumbing_cost * 0.6, 2),
        "division": "22_plumbing",
    })

    # HVAC (Division 23)
    hvac_cost = breakdown.get("23_hvac", 0)
    hvac_tons = round(area_sf / 500 * quality_multiplier, 1)
    quantities.append({
        "item": "HVAC system",
        "quantity": hvac_tons,
        "unit": "tons capacity",
        "unit_cost": _safe_div(hvac_cost, hvac_tons),
        "total_cost": hvac_cost,
        "division": "23_hvac",
    })

    # Electrical (Division 26)
    electrical_cost = breakdown.get("26_electrical", 0)
    electrical_circuits = round(area_sf / 100 * quality_multiplier)
    quantities.append({
        "item": "Electrical circuits",
        "quantity": electrical_circuits,
        "unit": "circuits",
        "unit_cost": _safe_div(electrical_cost * 0.5, electrical_circuits),
        "total_cost": round(electrical_cost * 0.5, 2),
        "division": "26_electrical",
    })

    # Light fixtures (Division 26)
    light_count = round(area_sf / 80 * quality_multiplier)
    quantities.append({
        "item": "Light fixtures",
        "quantity": light_count,
        "unit": "fixtures",
        "unit_cost": _safe_div(electrical_cost * 0.3, light_count),
        "total_cost": round(electrical_cost * 0.3, 2),
        "division": "26_electrical",
    })

    return quantities

