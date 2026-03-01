"""
Dataset Setup — Floor Plan Acquisition & Eval Dataset Assembly

Downloads real floor plan images from public sources and assembles
eval_dataset.json with all 53 evaluation cases.

Sources:
  - CubiCasa5K (Zenodo / Kaggle): Residential floor plans
  - FloorPlanCAD (HuggingFace): Commercial / Industrial / Institutional
  - Library of Congress (LOC): Public domain architectural plans
  - FEMA / Government: Infrastructure plans

Usage:
    python setup_dataset.py [--skip-download] [--output eval_dataset.json]
"""

import argparse
import json
import os
import random
import sys
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import requests
    from tqdm import tqdm
    from PIL import Image
    import yaml
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Run: pip install -r requirements.txt")
    sys.exit(1)

from cost_model import (
    calculate_ground_truth_cost,
    COST_PER_SF,
    LOCATION_FACTORS,
    SUBTYPE_TO_CATEGORY,
    get_all_locations,
)
import spec_generator

# ─── 53 EVAL CASES DEFINITION ────────────────────────────────────────
# Each case: (project_id, sub_type, quality, area_sf, stories, location, name)

EVAL_CASES: List[Dict] = [
    # ── Residential (15) ──────────────────────────────────────────────
    {"id": "RES-001", "sub_type": "single_family_economy",  "quality": "low",  "area_sf": 1100, "stories": 1, "location": "memphis",        "name": "Starter Home — Memphis"},
    {"id": "RES-002", "sub_type": "single_family_standard", "quality": "mid",  "area_sf": 2200, "stories": 2, "location": "chicago",        "name": "Family Home — Chicago"},
    {"id": "RES-003", "sub_type": "single_family_premium",  "quality": "high", "area_sf": 3500, "stories": 2, "location": "san_francisco",  "name": "Premium Home — San Francisco"},
    {"id": "RES-004", "sub_type": "single_family_custom",   "quality": "high", "area_sf": 5200, "stories": 2, "location": "boston",          "name": "Custom Estate — Boston"},
    {"id": "RES-005", "sub_type": "multi_family_duplex",    "quality": "mid",  "area_sf": 2800, "stories": 2, "location": "dallas",          "name": "Duplex — Dallas"},
    {"id": "RES-006", "sub_type": "multi_family_triplex",   "quality": "mid",  "area_sf": 3600, "stories": 3, "location": "portland",        "name": "Triplex — Portland"},
    {"id": "RES-007", "sub_type": "multi_family_fourplex",  "quality": "low",  "area_sf": 4000, "stories": 2, "location": "indianapolis",    "name": "Fourplex — Indianapolis"},
    {"id": "RES-008", "sub_type": "apartment_lowrise",      "quality": "mid",  "area_sf": 24000, "stories": 3, "location": "atlanta",        "name": "Garden Apartments — Atlanta"},
    {"id": "RES-009", "sub_type": "apartment_midrise",      "quality": "high", "area_sf": 85000, "stories": 6, "location": "new_york",       "name": "Midrise Apartments — NYC"},
    {"id": "RES-010", "sub_type": "apartment_garden",       "quality": "mid",  "area_sf": 18000, "stories": 2, "location": "tampa",           "name": "Garden Walk-ups — Tampa"},
    {"id": "RES-011", "sub_type": "townhouse_standard",     "quality": "mid",  "area_sf": 1800, "stories": 3, "location": "charlotte",       "name": "Townhouse — Charlotte"},
    {"id": "RES-012", "sub_type": "townhouse_luxury",       "quality": "high", "area_sf": 3200, "stories": 3, "location": "washington_dc",   "name": "Luxury Townhouse — DC"},
    {"id": "RES-013", "sub_type": "condo_midrise",          "quality": "mid",  "area_sf": 62000, "stories": 8, "location": "miami",          "name": "Condo Tower — Miami"},
    {"id": "RES-014", "sub_type": "luxury_estate",          "quality": "high", "area_sf": 8500, "stories": 2, "location": "los_angeles",     "name": "Luxury Estate — Los Angeles"},
    {"id": "RES-015", "sub_type": "custom_architectural",   "quality": "high", "area_sf": 6000, "stories": 2, "location": "seattle",         "name": "Architectural Home — Seattle"},

    # ── Commercial (12) ───────────────────────────────────────────────
    {"id": "COM-001", "sub_type": "office_lowrise",         "quality": "mid",  "area_sf": 15000, "stories": 2, "location": "denver",         "name": "Suburban Office — Denver"},
    {"id": "COM-002", "sub_type": "office_midrise",         "quality": "mid",  "area_sf": 45000, "stories": 5, "location": "chicago",        "name": "Office Tower — Chicago"},
    {"id": "COM-003", "sub_type": "office_highrise",        "quality": "high", "area_sf": 320000, "stories": 25, "location": "new_york",     "name": "Class A Office Tower — NYC"},
    {"id": "COM-004", "sub_type": "retail_strip",           "quality": "low",  "area_sf": 8000, "stories": 1, "location": "houston",         "name": "Strip Mall — Houston"},
    {"id": "COM-005", "sub_type": "retail_bigbox",          "quality": "low",  "area_sf": 120000, "stories": 1, "location": "phoenix",       "name": "Big Box Retail — Phoenix"},
    {"id": "COM-006", "sub_type": "restaurant_casual",      "quality": "mid",  "area_sf": 4500, "stories": 1, "location": "nashville",       "name": "Casual Restaurant — Nashville"},
    {"id": "COM-007", "sub_type": "restaurant_fine",        "quality": "high", "area_sf": 6200, "stories": 1, "location": "san_francisco",   "name": "Fine Dining — San Francisco"},
    {"id": "COM-008", "sub_type": "hotel_limited",          "quality": "mid",  "area_sf": 52000, "stories": 4, "location": "las_vegas",      "name": "Select Service Hotel — Vegas"},
    {"id": "COM-009", "sub_type": "hotel_full_service",     "quality": "high", "area_sf": 180000, "stories": 12, "location": "miami",        "name": "Full Service Hotel — Miami"},
    {"id": "COM-010", "sub_type": "bank_branch",            "quality": "mid",  "area_sf": 4200, "stories": 1, "location": "pittsburgh",      "name": "Bank Branch — Pittsburgh"},
    {"id": "COM-011", "sub_type": "medical_office",         "quality": "mid",  "area_sf": 12000, "stories": 2, "location": "minneapolis",    "name": "Medical Office — Minneapolis"},
    {"id": "COM-012", "sub_type": "mixed_use",              "quality": "mid",  "area_sf": 38000, "stories": 5, "location": "portland",       "name": "Mixed-Use Development — Portland"},

    # ── Industrial (8) ────────────────────────────────────────────────
    {"id": "IND-001", "sub_type": "warehouse_light",        "quality": "low",  "area_sf": 50000, "stories": 1, "location": "dallas",         "name": "Distribution Warehouse — Dallas"},
    {"id": "IND-002", "sub_type": "warehouse_heavy",        "quality": "mid",  "area_sf": 80000, "stories": 1, "location": "detroit",        "name": "Heavy Warehouse — Detroit"},
    {"id": "IND-003", "sub_type": "manufacturing_light",    "quality": "mid",  "area_sf": 35000, "stories": 1, "location": "charlotte",      "name": "Light Manufacturing — Charlotte"},
    {"id": "IND-004", "sub_type": "manufacturing_heavy",    "quality": "mid",  "area_sf": 65000, "stories": 1, "location": "houston",        "name": "Heavy Manufacturing — Houston"},
    {"id": "IND-005", "sub_type": "data_center",            "quality": "high", "area_sf": 40000, "stories": 2, "location": "washington_dc",  "name": "Data Center — Northern Virginia"},
    {"id": "IND-006", "sub_type": "research_lab",           "quality": "high", "area_sf": 28000, "stories": 3, "location": "boston",          "name": "Research Lab — Boston"},
    {"id": "IND-007", "sub_type": "cold_storage",           "quality": "mid",  "area_sf": 25000, "stories": 1, "location": "atlanta",        "name": "Cold Storage Facility — Atlanta"},
    {"id": "IND-008", "sub_type": "food_processing",        "quality": "mid",  "area_sf": 30000, "stories": 1, "location": "san_antonio",    "name": "Food Processing Plant — San Antonio"},

    # ── Institutional (10) ────────────────────────────────────────────
    {"id": "INS-001", "sub_type": "school_elementary",      "quality": "mid",  "area_sf": 65000, "stories": 2, "location": "baltimore",      "name": "Elementary School — Baltimore"},
    {"id": "INS-002", "sub_type": "school_high",            "quality": "mid",  "area_sf": 150000, "stories": 3, "location": "denver",        "name": "High School — Denver"},
    {"id": "INS-003", "sub_type": "university_classroom",   "quality": "mid",  "area_sf": 42000, "stories": 3, "location": "philadelphia",   "name": "University Hall — Philadelphia"},
    {"id": "INS-004", "sub_type": "university_science",     "quality": "high", "area_sf": 55000, "stories": 4, "location": "boston",          "name": "Science Building — Boston"},
    {"id": "INS-005", "sub_type": "hospital_acute",         "quality": "high", "area_sf": 250000, "stories": 6, "location": "los_angeles",   "name": "Acute Care Hospital — LA"},
    {"id": "INS-006", "sub_type": "clinic_outpatient",      "quality": "mid",  "area_sf": 18000, "stories": 2, "location": "tampa",           "name": "Outpatient Clinic — Tampa"},
    {"id": "INS-007", "sub_type": "church_standard",        "quality": "mid",  "area_sf": 12000, "stories": 1, "location": "nashville",       "name": "Community Church — Nashville"},
    {"id": "INS-008", "sub_type": "church_cathedral",       "quality": "high", "area_sf": 35000, "stories": 2, "location": "washington_dc",   "name": "Cathedral — Washington DC"},
    {"id": "INS-009", "sub_type": "library_public",         "quality": "mid",  "area_sf": 22000, "stories": 2, "location": "seattle",         "name": "Public Library — Seattle"},
    {"id": "INS-010", "sub_type": "community_center",       "quality": "mid",  "area_sf": 15000, "stories": 1, "location": "phoenix",         "name": "Community Center — Phoenix"},

    # ── Infrastructure (8) ────────────────────────────────────────────
    {"id": "INF-001", "sub_type": "parking_surface",        "quality": "mid",  "area_sf": 45000, "stories": 1, "location": "national",       "name": "Surface Parking Lot"},
    {"id": "INF-002", "sub_type": "parking_structured",     "quality": "mid",  "area_sf": 180000, "stories": 5, "location": "chicago",       "name": "Parking Garage — Chicago"},
    {"id": "INF-003", "sub_type": "fire_station",           "quality": "mid",  "area_sf": 12000, "stories": 2, "location": "san_antonio",    "name": "Fire Station — San Antonio"},
    {"id": "INF-004", "sub_type": "police_station",         "quality": "mid",  "area_sf": 25000, "stories": 2, "location": "detroit",        "name": "Police Station — Detroit"},
    {"id": "INF-005", "sub_type": "transit_station",        "quality": "high", "area_sf": 18000, "stories": 2, "location": "los_angeles",    "name": "Metro Station — Los Angeles"},
    {"id": "INF-006", "sub_type": "bus_maintenance",        "quality": "mid",  "area_sf": 35000, "stories": 1, "location": "minneapolis",    "name": "Bus Maintenance Facility — Minneapolis"},
    {"id": "INF-007", "sub_type": "water_treatment",        "quality": "mid",  "area_sf": 15000, "stories": 1, "location": "philadelphia",   "name": "Water Treatment Plant — Philadelphia"},
    {"id": "INF-008", "sub_type": "electrical_substation",  "quality": "mid",  "area_sf": 8000, "stories": 1, "location": "las_vegas",       "name": "Electrical Substation — Las Vegas"},
]

# ─── FLOOR PLAN DOWNLOAD SOURCES ─────────────────────────────────────
# Publicly accessible real floor plan image URLs

# CubiCasa5K sample images (public Zenodo thumbnails / Kaggle previews)
# FloorPlanCAD HuggingFace previews
# Library of Congress architectural drawings (public domain)

# We use a curated list of real, publicly accessible floor plan image URLs.
# These are organized by building category.

FLOOR_PLAN_SOURCES = {
    "residential": [
        # LOC — Historic American Buildings Survey residential plans (verified working)
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/dc/dc1000/dc1044/photos/362628pr.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/ms/ms0300/ms0361/sheet/00003r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/ms/ms0300/ms0362/sheet/00003r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/md/md0500/md0576/sheet/00001r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/md/md0600/md0606/sheet/00001r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/md/md0700/md0732/sheet/00001r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/va/va2400/va2443/sheet/00001r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/va/va2100/va2130/sheet/00001r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/md/md0800/md0830/sheet/00001r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/la/la0600/la0697/sheet/00005r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/ar/ar1100/ar1167/sheet/00001r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/ma/ma0000/ma0095/sheet/00001r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/ky/ky0000/ky0080/sheet/00002r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/ca/ca2900/ca2960/photos/192924pr.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/ca/ca3000/ca3027/photos/192906pr.jpg",
    ],
    "commercial": [
        # LOC commercial / public buildings (verified working)
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/ak/ak0000/ak0003/sheet/00013r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/tx/tx0600/tx0685/sheet/00002r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/tx/tx0600/tx0690/sheet/00004r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/cph/3b20000/3b27000/3b27100/3b27175r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/mi/mi0700/mi0716/photos/223299pr.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/ds/01100/01121r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/ppmsca/15500/15568r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/cph/3c10000/3c11000/3c11800/3c11809r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/cph/3b30000/3b37000/3b37300/3b37313r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/cph/3b30000/3b39000/3b39100/3b39182r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/ppmsca/15800/15823r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/cph/3b30000/3b39000/3b39100/3b39181r.jpg",
    ],
    "industrial": [
        # LOC industrial / factory plans (verified working)
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/wv/wv0300/wv0385/photos/041163pr.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/mo/mo1800/mo1801/sheet/00002r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/il/il0700/il0737/photos/048616pr.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/il/il0700/il0737/photos/048627pr.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/il/il0700/il0737/photos/048623pr.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/il/il0700/il0737/photos/048631pr.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/co/co0200/co0249/photos/021128pr.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/id/id0100/id0151/photos/184541pr.jpg",
    ],
    "institutional": [
        # LOC institutional — churches, schools, government (verified working)
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/nd/nd0100/nd0142/sheet/00001r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/pa/pa1700/pa1790/sheet/00002r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/il/il0000/il0041/sheet/00002r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/pa/pa1000/pa1064/sheet/00006r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/wi/wi0200/wi0276/photos/371675pr.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/me/me0000/me0028/photos/087880pr.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/ma/ma1600/ma1617/photos/217211pr.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/cz/cz0000/cz0033/photos/330468pr.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/oh/oh1800/oh1850/photos/353772pr.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/ca/ca3400/ca3405/photos/225191pr.jpg",
    ],
    "infrastructure": [
        # LOC infrastructure — bridges, utilities, public works (verified working)
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/ca/ca3000/ca3045/photos/192880pr.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/ca/ca3000/ca3045/photos/192881pr.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/ca/ca3400/ca3424/photos/220603pr.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/habshaer/ca/ca4100/ca4169/sheet/00003r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/ade/2a02000/2a02900/2a02952r.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/ds/14800/14821_150px.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/ds/14800/14824_150px.jpg",
        "https://tile.loc.gov/storage-services/service/pnp/ppmsca/15300/15366r.jpg",
    ],
}


def download_floor_plan(url: str, output_path: Path, timeout: int = 30) -> bool:
    """Download a single floor plan image."""
    try:
        response = requests.get(url, timeout=timeout, stream=True,
                                headers={"User-Agent": "ConstructionEvalDataset/1.0"})
        response.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"  WARNING: Failed to download {url}: {e}")
        return False


def generate_placeholder_plan(output_path: Path, case: Dict) -> None:
    """Generate a simple placeholder floor plan image when download fails."""
    try:
        img = Image.new("RGB", (800, 600), color=(255, 255, 255))
        # Draw a simple rectangle to represent a floor plan outline
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)
        # Outer walls
        draw.rectangle([50, 50, 750, 550], outline=(0, 0, 0), width=3)
        # Interior walls
        draw.line([400, 50, 400, 550], fill=(0, 0, 0), width=2)
        draw.line([50, 300, 750, 300], fill=(0, 0, 0), width=2)
        # Labels
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        draw.text((60, 10), f"{case['name']}", fill=(0, 0, 0), font=font)
        draw.text((60, 30), f"{case['area_sf']:,} SF | {case['stories']} stories", fill=(100, 100, 100), font=font)
        draw.text((100, 160), "Room A", fill=(128, 128, 128), font=font)
        draw.text((500, 160), "Room B", fill=(128, 128, 128), font=font)
        draw.text((100, 410), "Room C", fill=(128, 128, 128), font=font)
        draw.text((500, 410), "Room D", fill=(128, 128, 128), font=font)
        img.save(output_path, "PNG")
    except Exception as e:
        print(f"  WARNING: Could not generate placeholder for {case['id']}: {e}")
        # Create minimal valid PNG
        img = Image.new("RGB", (100, 100), color=(240, 240, 240))
        img.save(output_path, "PNG")


def download_all_floor_plans(base_dir: Path, skip_existing: bool = True) -> Dict[str, Path]:
    """Download floor plans for all 53 cases."""
    results = {}
    categories = ["residential", "commercial", "industrial", "institutional", "infrastructure"]

    for category in categories:
        cat_dir = base_dir / category
        cat_dir.mkdir(parents=True, exist_ok=True)
        urls = FLOOR_PLAN_SOURCES.get(category, [])
        # Get cases for this category
        cat_cases = [c for c in EVAL_CASES if SUBTYPE_TO_CATEGORY[c["sub_type"]] == category]

        print(f"\n{'='*60}")
        print(f"Processing {category} ({len(cat_cases)} cases, {len(urls)} source images)")
        print(f"{'='*60}")

        for i, case in enumerate(tqdm(cat_cases, desc=f"  {category}")):
            filename = f"{case['id'].lower().replace('-', '_')}.png"
            output_path = cat_dir / filename

            if skip_existing and output_path.exists():
                results[case["id"]] = output_path
                continue

            # Try to download from source
            downloaded = False
            if i < len(urls):
                url = urls[i]
                # First download as original format
                temp_path = cat_dir / f"{case['id'].lower().replace('-', '_')}_temp"
                if download_floor_plan(url, temp_path):
                    try:
                        # Convert to PNG for consistency
                        img = Image.open(temp_path)
                        img = img.convert("RGB")
                        # Resize very large images to reasonable size
                        max_dim = 2000
                        if max(img.size) > max_dim:
                            ratio = max_dim / max(img.size)
                            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                            img = img.resize(new_size, Image.LANCZOS)
                        img.save(output_path, "PNG")
                        downloaded = True
                    except Exception as e:
                        print(f"  WARNING: Image conversion failed for {case['id']}: {e}")
                    finally:
                        if temp_path.exists():
                            temp_path.unlink()

            if not downloaded:
                print(f"  Generating placeholder for {case['id']}...")
                generate_placeholder_plan(output_path, case)

            results[case["id"]] = output_path

    return results


def assemble_dataset(floor_plan_paths: Dict[str, Path], base_dir: Path) -> List[Dict]:
    """Assemble the complete eval dataset with ground truth costs and specs."""
    dataset = []

    for case in tqdm(EVAL_CASES, desc="Assembling dataset"):
        # Calculate ground truth cost
        seed = int(hashlib.md5(case["id"].encode()).hexdigest()[:8], 16) % (2**31)
        cost_result = calculate_ground_truth_cost(
            sub_type=case["sub_type"],
            quality=case["quality"],
            area_sf=case["area_sf"],
            stories=case["stories"],
            location=case["location"],
            seed=seed,
        )

        # Generate specification text
        spec_text = spec_generator.generate(
            sub_type=case["sub_type"],
            quality=case["quality"],
            area_sf=case["area_sf"],
            stories=case["stories"],
            building_name=case["name"],
            location=case["location"],
            seed=seed,
        )

        # Floor plan path (relative)
        category = SUBTYPE_TO_CATEGORY[case["sub_type"]]
        fp_filename = f"{case['id'].lower().replace('-', '_')}.png"
        fp_rel_path = f"floor_plans/{category}/{fp_filename}"

        entry = {
            "project_id": case["id"],
            "name": case["name"],
            "building_type": category,
            "sub_type": case["sub_type"],
            "quality": case["quality"],
            "area_sf": case["area_sf"],
            "stories": case["stories"],
            "location": case["location"],
            "location_factor": cost_result["location_factor"],
            "floor_plan_path": fp_rel_path,
            "specification_text": spec_text,
            "ground_truth": {
                "total_cost": cost_result["total_cost"],
                "cost_per_sf": cost_result["cost_per_sf"],
                "base_cost_sf": cost_result["base_cost_sf"],
                "story_premium": cost_result["story_premium"],
                "csi_profile": cost_result["csi_profile"],
                "division_breakdown": cost_result["division_breakdown"],
            },
        }
        dataset.append(entry)

    return dataset


def validate_dataset(dataset: List[Dict], base_dir: Path) -> bool:
    """Validate the assembled dataset."""
    print(f"\n{'='*60}")
    print("VALIDATION")
    print(f"{'='*60}")

    errors = []
    warnings = []

    # Check count
    if len(dataset) != 53:
        errors.append(f"Expected 53 cases, got {len(dataset)}")

    # Check each case
    for entry in dataset:
        pid = entry["project_id"]

        # Check floor plan exists
        fp_path = base_dir / entry["floor_plan_path"]
        if not fp_path.exists():
            errors.append(f"{pid}: Floor plan not found at {fp_path}")
        else:
            try:
                img = Image.open(fp_path)
                img.verify()
            except Exception as e:
                errors.append(f"{pid}: Invalid image — {e}")

        # Check CSI breakdown sums to ~100% of total
        gt = entry["ground_truth"]
        div_sum = sum(gt["division_breakdown"].values())
        pct_diff = abs(div_sum - gt["total_cost"]) / gt["total_cost"]
        if pct_diff > 0.02:  # >2% discrepancy
            warnings.append(
                f"{pid}: Division sum ${div_sum:,.0f} differs from total "
                f"${gt['total_cost']:,.0f} by {pct_diff:.1%}"
            )

        # Check cost ranges are reasonable
        cost_sf = gt["cost_per_sf"]
        if cost_sf < 20:
            warnings.append(f"{pid}: Very low $/SF: ${cost_sf:.0f}")
        if cost_sf > 3000:
            warnings.append(f"{pid}: Very high $/SF: ${cost_sf:.0f}")

        # Check spec text is non-empty
        if len(entry["specification_text"]) < 500:
            warnings.append(f"{pid}: Short specification text ({len(entry['specification_text'])} chars)")

    # Category distribution
    cat_counts = {}
    for entry in dataset:
        cat = entry["building_type"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    expected = {"residential": 15, "commercial": 12, "industrial": 8, "institutional": 10, "infrastructure": 8}
    for cat, expected_count in expected.items():
        actual = cat_counts.get(cat, 0)
        if actual != expected_count:
            errors.append(f"Category '{cat}': expected {expected_count}, got {actual}")

    # Report
    print(f"\n  Total cases: {len(dataset)}")
    print(f"  Category distribution: {cat_counts}")
    print(f"\n  Errors: {len(errors)}")
    for e in errors:
        print(f"    ERROR: {e}")
    print(f"\n  Warnings: {len(warnings)}")
    for w in warnings[:10]:
        print(f"    WARN: {w}")
    if len(warnings) > 10:
        print(f"    ... and {len(warnings) - 10} more warnings")

    # Spot-check 5 cases
    print(f"\n  Spot-check (5 cases):")
    spot_checks = [dataset[0], dataset[3], dataset[20], dataset[35], dataset[45]]
    for sc in spot_checks:
        gt = sc["ground_truth"]
        print(f"    {sc['project_id']} ({sc['sub_type']}, {sc['quality']}): "
              f"${gt['total_cost']:,.0f} total, ${gt['cost_per_sf']:,.0f}/SF, "
              f"{sc['area_sf']:,} SF × {sc['stories']} stories @ {sc['location']}")

    valid = len(errors) == 0
    print(f"\n  {'PASSED' if valid else 'FAILED'}")
    return valid


def main():
    parser = argparse.ArgumentParser(description="Set up construction cost eval dataset")
    parser.add_argument("--skip-download", action="store_true",
                        help="Skip downloading floor plans (use existing/placeholders)")
    parser.add_argument("--output", default="eval_dataset.json",
                        help="Output dataset JSON path")
    parser.add_argument("--base-dir", default=".",
                        help="Base directory for the project")
    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve()
    fp_dir = base_dir / "floor_plans"
    output_path = base_dir / args.output

    print("Construction Cost Estimation — Eval Dataset Setup")
    print(f"Base directory: {base_dir}")
    print(f"Output: {output_path}")
    print(f"Cases: {len(EVAL_CASES)}")

    # Step 1: Download floor plans
    if args.skip_download:
        print("\nSkipping downloads — generating placeholders for missing plans...")
        fp_paths = {}
        for case in EVAL_CASES:
            category = SUBTYPE_TO_CATEGORY[case["sub_type"]]
            cat_dir = fp_dir / category
            cat_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{case['id'].lower().replace('-', '_')}.png"
            fp_path = cat_dir / filename
            if not fp_path.exists():
                generate_placeholder_plan(fp_path, case)
            fp_paths[case["id"]] = fp_path
    else:
        print("\nDownloading floor plans from public sources...")
        fp_paths = download_all_floor_plans(fp_dir)

    # Step 2: Assemble dataset
    print("\nAssembling eval dataset...")
    dataset = assemble_dataset(fp_paths, base_dir)

    # Step 3: Write JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
    print(f"\nDataset written to {output_path} ({os.path.getsize(output_path) / 1024:.1f} KB)")

    # Step 4: Validate
    validate_dataset(dataset, base_dir)

    # Step 5: Generate dummy predictions for testing evaluate.py
    dummy_path = base_dir / "results" / "dummy_predictions.json"
    dummy_path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(12345)
    dummy_predictions = []
    for entry in dataset:
        gt = entry["ground_truth"]
        # Add ±15% noise to total
        noise = rng.uniform(-0.15, 0.15)
        pred_total = gt["total_cost"] * (1 + noise)
        # Add ±20% noise to each division
        pred_divs = {}
        for div, val in gt["division_breakdown"].items():
            div_noise = rng.uniform(-0.20, 0.20)
            pred_divs[div] = round(val * (1 + div_noise), 2)
        dummy_predictions.append({
            "project_id": entry["project_id"],
            "predicted_total": round(pred_total, 2),
            "predicted_divisions": pred_divs,
        })
    with open(dummy_path, "w") as f:
        json.dump(dummy_predictions, f, indent=2)
    print(f"\nDummy predictions written to {dummy_path}")

    print("\nSetup complete!")


if __name__ == "__main__":
    main()
