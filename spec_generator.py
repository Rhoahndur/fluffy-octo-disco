"""
CSI Specification Text Generator

Template-based generator that produces CSI-formatted multi-section
specification text for each project in the eval dataset. Parameter banks
vary by building type and quality level.
"""

from typing import Dict, Optional
import random

# ─── PARAMETER BANKS ──────────────────────────────────────────────────
# Organized by CSI division, building category, and quality level

STRUCTURAL_SYSTEMS = {
    "residential": {
        "low":  "Wood frame construction with 2x4 studs at 16\" o.c., engineered wood trusses, slab-on-grade foundation.",
        "mid":  "Wood frame construction with 2x6 studs at 16\" o.c., engineered floor joists, poured concrete foundation walls.",
        "high": "Hybrid wood frame and structural steel, engineered glulam beams, full basement with reinforced concrete walls.",
    },
    "commercial": {
        "low":  "Steel frame with open-web joists and metal deck, spread footings, slab-on-grade.",
        "mid":  "Structural steel frame with composite metal deck, reinforced concrete foundations, moment frames for lateral resistance.",
        "high": "Reinforced concrete frame with post-tensioned slabs, drilled pier foundations, dual lateral force-resisting system.",
    },
    "industrial": {
        "low":  "Pre-engineered metal building system with rigid frames, slab-on-grade with vapor barrier.",
        "mid":  "Structural steel frame with bar joists and metal roof deck, thickened edge slab, crane-rated columns.",
        "high": "Heavy structural steel with moment connections, reinforced concrete mat foundation, 50-ton crane capacity.",
    },
    "institutional": {
        "low":  "Load-bearing masonry walls with steel bar joists, spread footings.",
        "mid":  "Structural steel frame with composite deck, reinforced concrete foundations, seismic design category D.",
        "high": "Reinforced concrete frame with flat plate slabs, deep foundations with grade beams, progressive collapse resistance.",
    },
    "infrastructure": {
        "low":  "Cast-in-place concrete with standard reinforcement, shallow foundations.",
        "mid":  "Reinforced concrete structure with post-tensioned elements, drilled shaft foundations.",
        "high": "High-performance concrete with corrosion-resistant reinforcement, deep foundation system with seismic isolation.",
    },
}

EXTERIOR_ENCLOSURE = {
    "residential": {
        "low":  "Vinyl siding over housewrap, vinyl double-hung windows, asphalt shingle roofing, pre-hung steel entry doors.",
        "mid":  "Brick veneer with fiber cement accents, vinyl-clad casement windows (Low-E), architectural shingle roof, fiberglass entry doors.",
        "high": "Natural stone and stucco exterior, wood-clad aluminum windows (triple-pane), standing seam metal roof, custom mahogany entry system.",
    },
    "commercial": {
        "low":  "Metal wall panels with rigid insulation, storefront aluminum framing, single-ply TPO roof membrane.",
        "mid":  "Curtain wall glazing system with insulated spandrel panels, aluminum-framed ribbon windows, fully-adhered EPDM roof.",
        "high": "Unitized curtain wall with high-performance Low-E glazing, architectural precast concrete panels, vegetated green roof system.",
    },
    "industrial": {
        "low":  "Pre-finished metal wall panels, minimal glazing, standing seam metal roof, insulated overhead doors.",
        "mid":  "Insulated metal panels (R-25), strip windows with polycarbonate, single-ply PVC roof, high-speed roll-up doors.",
        "high": "Architectural insulated metal panels (R-38), aluminum curtain wall at office areas, ballasted EPDM roof with skylights.",
    },
    "institutional": {
        "low":  "Brick masonry with CMU backup, aluminum windows, built-up roofing system.",
        "mid":  "Brick and precast concrete panels, aluminum-clad wood windows, modified bitumen roof with tapered insulation.",
        "high": "Architectural precast with integral color, thermally-broken aluminum curtain wall, vegetated roof with photovoltaic array.",
    },
    "infrastructure": {
        "low":  "CMU walls with elastomeric coating, hollow metal doors and frames, built-up roof.",
        "mid":  "Split-face CMU with brick accents, impact-resistant glazing, single-ply membrane roof.",
        "high": "Cast-in-place concrete with architectural form liner, blast-resistant glazing, protected membrane roof system.",
    },
}

INTERIOR_FINISHES = {
    "residential": {
        "low":  "Painted drywall throughout, VCT flooring, hollow-core interior doors, laminate countertops, basic cabinetry.",
        "mid":  "Textured drywall with crown molding, carpet and ceramic tile, solid-core doors, granite countertops, semi-custom cabinetry.",
        "high": "Venetian plaster and wainscoting, hardwood and natural stone flooring, custom millwork, quartzite countertops, custom cabinetry.",
    },
    "commercial": {
        "low":  "Painted drywall, VCT and commercial carpet tile, suspended acoustical ceiling, plastic laminate casework.",
        "mid":  "Level 4 drywall finish, porcelain tile and broadloom carpet, suspended acoustical ceiling with recessed grid, solid surface counters.",
        "high": "Custom wall coverings, terrazzo and premium carpet, custom ceiling system with integrated lighting, natural stone and custom millwork.",
    },
    "industrial": {
        "low":  "Exposed structure, sealed concrete floor, painted CMU walls in office areas.",
        "mid":  "Epoxy-coated concrete floors, painted drywall in office areas, suspended ceiling in offices, FRP wall panels in wet areas.",
        "high": "Resinous flooring system, full drywall office build-out, cleanroom partitions, stainless steel wall panels in process areas.",
    },
    "institutional": {
        "low":  "Painted CMU walls, VCT flooring, suspended acoustical ceiling, plastic laminate casework.",
        "mid":  "Painted drywall with ceramic wainscot, terrazzo and carpet, acoustical ceiling, solid surface countertops.",
        "high": "Custom wall panels, terrazzo with brass inlays, specialty acoustical ceiling, natural stone and custom millwork throughout.",
    },
    "infrastructure": {
        "low":  "Painted CMU, sealed concrete floors, exposed ceiling with painted deck.",
        "mid":  "Painted drywall, quarry tile and VCT, suspended acoustical ceiling, stainless steel countertops.",
        "high": "Ceramic tile and epoxy flooring, custom wall protection, acoustical metal ceiling panels.",
    },
}

HVAC_SYSTEMS = {
    "residential": {
        "low":  "Split system heat pump, 14 SEER, programmable thermostat, standard ductwork.",
        "mid":  "High-efficiency split system (16 SEER), zoned ductwork, smart thermostat, HRV ventilation.",
        "high": "Geothermal heat pump system, radiant floor heating, dedicated outdoor air system (DOAS), whole-house energy management.",
    },
    "commercial": {
        "low":  "Packaged rooftop units, constant volume, basic exhaust fans, manual controls.",
        "mid":  "VAV system with central chiller and boiler plant, economizer, DDC building automation system.",
        "high": "Variable refrigerant flow (VRF) system with DOAS, chilled beams, full BAS with analytics, LEED-compliant.",
    },
    "industrial": {
        "low":  "Gas-fired unit heaters, roof-mounted exhaust fans, make-up air unit.",
        "mid":  "Rooftop units with economizers for office areas, process exhaust with make-up air, spot cooling at workstations.",
        "high": "100% outside air AHUs with energy recovery, precision cooling (CRAC/CRAH units), hot/cold aisle containment.",
    },
    "institutional": {
        "low":  "Packaged rooftop units, unit ventilators in classrooms, basic exhaust.",
        "mid":  "Central chilled water plant with AHUs, DDC controls, demand-controlled ventilation, energy recovery.",
        "high": "Central plant with thermal energy storage, displacement ventilation, full BAS, net-zero energy capable.",
    },
    "infrastructure": {
        "low":  "Split systems and exhaust fans, minimal HVAC in equipment spaces.",
        "mid":  "Packaged units with redundancy, ventilation per code, emergency generator-backed HVAC.",
        "high": "N+1 redundant cooling systems, pressurization systems, chemical filtration, full standby power.",
    },
}

ELECTRICAL_SYSTEMS = {
    "residential": {
        "low":  "200A single-phase service, standard lighting package, smoke detectors, basic wiring.",
        "mid":  "400A service, LED lighting with dimmers, structured wiring, GFCI/AFCI protection, 50A EV charging rough-in.",
        "high": "600A service with whole-house generator, architectural LED lighting, smart home automation, integrated AV systems, solar-ready.",
    },
    "commercial": {
        "low":  "480/277V 3-phase service, fluorescent lighting, basic fire alarm, minimal data infrastructure.",
        "mid":  "480/277V 3-phase with 800A switchgear, LED lighting with daylight harvesting, addressable fire alarm, structured cabling.",
        "high": "Dual-fed 480V service with ATS, tunable LED lighting, networked fire alarm/mass notification, enterprise data infrastructure.",
    },
    "industrial": {
        "low":  "480V 3-phase service, high-bay fluorescent, basic motor starters, minimal convenience power.",
        "mid":  "480V with motor control centers, LED high-bay lighting, VFDs for major motors, process control wiring.",
        "high": "N+1 redundant power distribution, 2N UPS system, LED lighting with emergency circuit, SCADA integration.",
    },
    "institutional": {
        "low":  "480/277V service, standard fluorescent, manual fire alarm, clock/intercom system.",
        "mid":  "480/277V with emergency generator, LED lighting, addressable fire alarm, PA/intercom, access control.",
        "high": "Dual utility feeds with generator, LED with tunable white, integrated security/fire/AV systems, photovoltaic array.",
    },
    "infrastructure": {
        "low":  "480V service, industrial fixtures, basic alarm systems.",
        "mid":  "480V with standby generator, LED site and building lighting, fire alarm, CCTV.",
        "high": "Dual utility with automatic transfer, N+1 standby power, explosion-proof fixtures, integrated command/control systems.",
    },
}

PLUMBING_SYSTEMS = {
    "residential": {
        "low":  "PEX water distribution, PVC DWV, standard fixtures, 40-gallon electric water heater.",
        "mid":  "PEX with manifold system, PVC DWV, mid-grade fixtures, tankless gas water heater, water softener.",
        "high": "Copper water distribution, cast iron DWV, premium designer fixtures, recirculating hot water, point-of-use filtration.",
    },
    "commercial": {
        "low":  "Copper domestic water, cast iron DWV, standard commercial fixtures, gas water heater.",
        "mid":  "Copper with PEX branches, cast iron DWV, sensor-operated fixtures, high-efficiency condensing water heaters, grease interceptor.",
        "high": "Copper distribution with recirculation, cast iron DWV, premium low-flow fixtures, solar-assisted water heating, rainwater harvesting.",
    },
    "industrial": {
        "low":  "Copper domestic, PVC DWV, industrial floor drains, gas water heater for restrooms.",
        "mid":  "Copper with backflow preventers, process piping systems, acid-resistant DWV, emergency shower/eyewash stations.",
        "high": "Stainless steel process piping, double-contained waste, DI water system, medical gas systems, compressed air distribution.",
    },
    "institutional": {
        "low":  "Copper domestic, cast iron DWV, standard flush valves, central water heater.",
        "mid":  "Copper with recirculation, cast iron DWV, sensor fixtures, high-efficiency water heating, lab waste system.",
        "high": "Copper with dedicated systems, special waste and vent, medical gas, pure water distribution, central vacuum.",
    },
    "infrastructure": {
        "low":  "Copper domestic, cast iron DWV, service sinks, electric water heater.",
        "mid":  "Copper with backflow, floor drains, decontamination fixtures, gas water heater.",
        "high": "Stainless steel in process areas, chemical-resistant piping, emergency decon showers, redundant water supply.",
    },
}

FIRE_PROTECTION = {
    "residential": {
        "low":  "Residential sprinkler system per NFPA 13D (where required), portable fire extinguishers.",
        "mid":  "NFPA 13D residential sprinkler system throughout, hardwired interconnected smoke/CO detectors.",
        "high": "NFPA 13 sprinkler system with flow switch, monitored fire alarm, residential suppression in kitchen.",
    },
    "commercial": {
        "low":  "Wet sprinkler system per NFPA 13, manual fire alarm with horn/strobes.",
        "mid":  "Wet sprinkler system with quick-response heads, addressable fire alarm, emergency voice/alarm communication.",
        "high": "Wet/dry sprinkler system, pre-action in sensitive areas, addressable fire alarm with mass notification, clean agent suppression for IT.",
    },
    "industrial": {
        "low":  "Wet sprinkler system, manual pull stations, portable extinguishers at rated intervals.",
        "mid":  "ESFR sprinkler system for high-piled storage, in-rack sprinklers, addressable fire alarm with detection.",
        "high": "Deluge and pre-action systems, foam suppression, very early smoke detection (VESDA), fire pump with diesel backup.",
    },
    "institutional": {
        "low":  "Wet sprinkler system, manual fire alarm with annunciator.",
        "mid":  "Wet sprinkler with quick-response heads, addressable fire alarm, area of refuge communication.",
        "high": "Wet/dry system, clean agent in data areas, addressable fire alarm/mass notification, smoke control system.",
    },
    "infrastructure": {
        "low":  "Wet sprinkler system, basic fire alarm.",
        "mid":  "Wet sprinkler, foam systems in vehicle bays, addressable fire alarm.",
        "high": "Specialized suppression (clean agent, foam, deluge), VESDA, integrated fire command center.",
    },
}


def _format_section(division_number: str, division_name: str, content: str) -> str:
    """Format a single CSI specification section."""
    return (
        f"SECTION {division_number} - {division_name.upper()}\n"
        f"{'=' * 60}\n\n"
        f"PART 1 - GENERAL\n"
        f"1.1 SUMMARY\n"
        f"    {content}\n\n"
        f"1.2 QUALITY ASSURANCE\n"
        f"    All work shall comply with applicable codes and standards.\n"
        f"    Materials and workmanship shall meet or exceed specified requirements.\n\n"
    )


def generate(
    sub_type: str,
    quality: str,
    area_sf: float,
    stories: int = 1,
    building_name: str = "Project",
    location: str = "national",
    seed: Optional[int] = None,
) -> str:
    """
    Generate CSI-formatted specification text for a building project.

    Args:
        sub_type: Building sub-type key
        quality: Quality level ('low', 'mid', 'high')
        area_sf: Building area in square feet
        stories: Number of stories
        building_name: Project name for header
        location: City name for header
        seed: Random seed for minor template variation

    Returns:
        Multi-section CSI specification text string
    """
    # Determine building category
    category = _get_category(sub_type)

    if seed is not None:
        rng = random.Random(seed)
    else:
        rng = random.Random()

    # Header
    spec = (
        f"{'#' * 70}\n"
        f"# PROJECT SPECIFICATIONS\n"
        f"# {building_name}\n"
        f"# Location: {location.replace('_', ' ').title()}\n"
        f"# Building Type: {sub_type.replace('_', ' ').title()}\n"
        f"# Quality Level: {quality.upper()}\n"
        f"# Gross Area: {area_sf:,.0f} SF\n"
        f"# Stories: {stories}\n"
        f"{'#' * 70}\n\n"
    )

    # Division 01 - General Requirements
    gc_pct = rng.choice(["5-8%", "6-10%", "8-12%"])
    spec += _format_section("01 00 00", "General Requirements",
        f"General conditions, overhead, and profit typically represent {gc_pct} of "
        f"construction cost. Includes project management, temporary facilities, "
        f"site security, project closeout, and commissioning requirements."
    )

    # Division 02 - Existing Conditions
    spec += _format_section("02 00 00", "Existing Conditions",
        f"Site preparation including demolition of existing improvements (if any), "
        f"environmental remediation as required, geotechnical investigation, and "
        f"subsurface utility exploration. Phase I ESA completed."
    )

    # Division 03 - Concrete
    concrete_detail = _get_concrete_detail(category, quality)
    spec += _format_section("03 00 00", "Concrete", concrete_detail)

    # Division 04 - Masonry
    masonry_detail = _get_masonry_detail(category, quality)
    spec += _format_section("04 00 00", "Masonry", masonry_detail)

    # Division 05 - Metals / Division 06 - Wood/Plastics (Structural)
    structural = STRUCTURAL_SYSTEMS.get(category, STRUCTURAL_SYSTEMS["commercial"])
    spec += _format_section("05 00 00", "Metals / Structural",
        structural.get(quality, structural["mid"])
    )

    # Division 07 - Thermal & Moisture Protection
    exterior = EXTERIOR_ENCLOSURE.get(category, EXTERIOR_ENCLOSURE["commercial"])
    spec += _format_section("07 00 00", "Thermal and Moisture Protection",
        exterior.get(quality, exterior["mid"])
    )

    # Division 08 - Openings
    openings_detail = _get_openings_detail(category, quality)
    spec += _format_section("08 00 00", "Openings", openings_detail)

    # Division 09 - Finishes
    finishes = INTERIOR_FINISHES.get(category, INTERIOR_FINISHES["commercial"])
    spec += _format_section("09 00 00", "Finishes",
        finishes.get(quality, finishes["mid"])
    )

    # Division 10 - Specialties
    specialties_detail = _get_specialties_detail(category, quality)
    spec += _format_section("10 00 00", "Specialties", specialties_detail)

    # Division 11 - Equipment
    equipment_detail = _get_equipment_detail(sub_type, quality)
    spec += _format_section("11 00 00", "Equipment", equipment_detail)

    # Division 12 - Furnishings
    furnishings_detail = _get_furnishings_detail(category, quality)
    spec += _format_section("12 00 00", "Furnishings", furnishings_detail)

    # Division 14 - Conveying Equipment
    if stories > 1 and category not in ("residential",):
        elevator_detail = _get_elevator_detail(category, quality, stories)
        spec += _format_section("14 00 00", "Conveying Equipment", elevator_detail)

    # Division 21 - Fire Suppression
    fire = FIRE_PROTECTION.get(category, FIRE_PROTECTION["commercial"])
    spec += _format_section("21 00 00", "Fire Suppression",
        fire.get(quality, fire["mid"])
    )

    # Division 22 - Plumbing
    plumbing = PLUMBING_SYSTEMS.get(category, PLUMBING_SYSTEMS["commercial"])
    spec += _format_section("22 00 00", "Plumbing",
        plumbing.get(quality, plumbing["mid"])
    )

    # Division 23 - HVAC
    hvac = HVAC_SYSTEMS.get(category, HVAC_SYSTEMS["commercial"])
    spec += _format_section("23 00 00", "HVAC",
        hvac.get(quality, hvac["mid"])
    )

    # Division 26 - Electrical
    electrical = ELECTRICAL_SYSTEMS.get(category, ELECTRICAL_SYSTEMS["commercial"])
    spec += _format_section("26 00 00", "Electrical",
        electrical.get(quality, electrical["mid"])
    )

    return spec


def _get_category(sub_type: str) -> str:
    """Map sub-type to broad category."""
    from cost_model import SUBTYPE_TO_CATEGORY
    return SUBTYPE_TO_CATEGORY.get(sub_type, "commercial")


def _get_concrete_detail(category: str, quality: str) -> str:
    details = {
        "residential": {
            "low":  "3000 PSI concrete for footings and slab-on-grade (4\" min.), #4 rebar at 18\" o.c.",
            "mid":  "4000 PSI concrete for foundations, 4\" slab with welded wire fabric, formed foundation walls.",
            "high": "5000 PSI concrete for all structural elements, post-tensioned slab, architectural exposed concrete at select locations.",
        },
        "commercial": {
            "low":  "3500 PSI concrete for footings and slab, standard reinforcement per structural drawings.",
            "mid":  "4000 PSI concrete, formed and placed foundations, elevated composite deck with lightweight concrete topping.",
            "high": "5000+ PSI concrete, post-tensioned flat plates, architectural concrete with integral color at ground level.",
        },
        "industrial": {
            "low":  "3500 PSI concrete, 6\" slab with fiber reinforcement, thickened at equipment pads.",
            "mid":  "4000 PSI concrete, 8\" slab with heavy reinforcement, superflat floor finish (FF50/FL35).",
            "high": "5000 PSI concrete, 12\" slab with post-tensioning, chemical-resistant topping at process areas.",
        },
        "institutional": {
            "low":  "3500 PSI concrete for foundations and structural slabs.",
            "mid":  "4000 PSI concrete, CIP columns and beams, elevated slabs with welded wire fabric.",
            "high": "5000 PSI high-performance concrete, exposed aggregate finish, fiber-reinforced at high-traffic areas.",
        },
        "infrastructure": {
            "low":  "4000 PSI concrete, standard reinforcement, spread footings.",
            "mid":  "4500 PSI concrete with corrosion inhibitor, epoxy-coated rebar, drilled shaft foundations.",
            "high": "6000 PSI concrete, stainless steel reinforcement in critical areas, mass concrete placements with thermal control.",
        },
    }
    return details.get(category, details["commercial"]).get(quality, details["commercial"]["mid"])


def _get_masonry_detail(category: str, quality: str) -> str:
    details = {
        "residential": {
            "low":  "CMU foundation walls, brick veneer at front elevation only (where applicable).",
            "mid":  "Full-perimeter brick veneer with flashing and weeps, stone accents at entry.",
            "high": "Natural stone veneer, custom brick patterns, reinforced CMU at below-grade walls.",
        },
        "commercial": {
            "low":  "CMU backup walls with brick veneer, standard mortar joints.",
            "mid":  "Reinforced CMU with architectural brick veneer, stone base course.",
            "high": "Custom-blend face brick, natural stone panels, reinforced and grouted CMU cores.",
        },
        "industrial": {
            "low":  "Painted CMU at office and restroom areas, minimal masonry overall.",
            "mid":  "Split-face CMU accent walls, glazed CMU at wet areas.",
            "high": "Architectural CMU with integral color, brick veneer at office/visitor areas.",
        },
        "institutional": {
            "low":  "Load-bearing and veneer CMU, standard brick.",
            "mid":  "Architectural brick with limestone accents, reinforced CMU.",
            "high": "Custom face brick with decorative patterns, natural stone, glazed block interior accents.",
        },
        "infrastructure": {
            "low":  "Standard CMU with block fill at reinforced cells.",
            "mid":  "Split-face CMU exterior, glazed CMU interior at wet areas.",
            "high": "Blast-resistant CMU, architectural precast masonry units.",
        },
    }
    return details.get(category, details["commercial"]).get(quality, details["commercial"]["mid"])


def _get_openings_detail(category: str, quality: str) -> str:
    details = {
        "residential": {
            "low":  "Vinyl double-hung windows, pre-hung hollow-core interior doors, insulated steel entry door.",
            "mid":  "Vinyl-clad wood casement windows (Low-E/argon), solid-core interior doors, fiberglass entry with sidelights.",
            "high": "Wood-clad aluminum windows (triple-pane), custom interior doors with hardware, custom entry door system.",
        },
        "commercial": {
            "low":  "Aluminum storefront system, hollow metal doors and frames, standard hardware.",
            "mid":  "Aluminum curtain wall, wood doors with commercial hardware, automatic entrance.",
            "high": "Unitized curtain wall, architectural wood/glass doors, revolving entrance, integrated access control.",
        },
        "industrial": {
            "low":  "Hollow metal doors, minimal windows, insulated overhead doors.",
            "mid":  "Hollow metal and aluminum doors, strip windows, high-speed roll-up doors.",
            "high": "Blast-rated doors and frames, impact-resistant glazing, aircraft hangar doors or equivalent.",
        },
        "institutional": {
            "low":  "Aluminum windows, hollow metal doors, manual hardware.",
            "mid":  "Aluminum-clad wood windows, solid wood doors, panic hardware, access control.",
            "high": "High-performance aluminum windows, custom wood doors, integrated security hardware throughout.",
        },
        "infrastructure": {
            "low":  "Hollow metal doors, fixed aluminum windows, overhead coiling doors.",
            "mid":  "Impact-rated windows, heavy-duty hollow metal doors, sectional overhead doors.",
            "high": "Blast-resistant doors and frames, ballistic-rated glazing, high-security hardware.",
        },
    }
    return details.get(category, details["commercial"]).get(quality, details["commercial"]["mid"])


def _get_specialties_detail(category: str, quality: str) -> str:
    details = {
        "residential": {
            "low":  "Bath accessories, closet shelving, house numbers.",
            "mid":  "Bath accessories, closet systems, fireplace, built-in shelving.",
            "high": "Designer bath accessories, custom closet systems, fireplace with stone surround, wine storage.",
        },
        "commercial": {
            "low":  "Toilet partitions, fire extinguishers, building signage.",
            "mid":  "Toilet partitions and accessories, dimensional signage, visual display boards, corner guards.",
            "high": "Custom toilet compartments, wayfinding signage system, display cases, operable partitions.",
        },
        "industrial": {
            "low":  "Toilet accessories, safety equipment, minimal signage.",
            "mid":  "Toilet accessories, lockers, safety showers/eyewash, industrial shelving.",
            "high": "Complete locker room, clean room accessories, specialized safety equipment, directional signage.",
        },
        "institutional": {
            "low":  "Toilet partitions, fire extinguishers, marker boards.",
            "mid":  "Toilet accessories, signage system, display cases, projection screens, flagpoles.",
            "high": "Custom toilet compartments, donor recognition displays, trophy cases, operable walls, stage equipment.",
        },
        "infrastructure": {
            "low":  "Toilet accessories, signage, flagpole.",
            "mid":  "Toilet partitions, lockers, turnstiles, bulletin boards.",
            "high": "Custom lockers, evidence storage, security screening equipment, memorial/dedication plaques.",
        },
    }
    return details.get(category, details["commercial"]).get(quality, details["commercial"]["mid"])


def _get_equipment_detail(sub_type: str, quality: str) -> str:
    """Equipment varies significantly by sub-type."""
    equipment_map = {
        "restaurant_casual": {
            "low":  "Basic commercial kitchen: range, oven, fryer, reach-in cooler/freezer, 3-comp sink, hood system.",
            "mid":  "Full commercial kitchen: range, convection oven, charbroiler, walk-in cooler/freezer, Type I hood, dishwasher.",
            "high": "Premium kitchen: combi oven, induction cooking, walk-in cooler/freezer/prep, custom hood, flight dishwasher.",
        },
        "restaurant_fine": {
            "low":  "Commercial kitchen with range, oven, walk-in, hood system, 3-compartment sink.",
            "mid":  "Full commercial kitchen: exhibition cooking line, walk-ins, pastry station, bar equipment, Type I/II hoods.",
            "high": "Showcase kitchen: custom fabricated stations, sous vide, blast chiller, wine cellar, artisan bread oven.",
        },
        "data_center": {
            "low":  "Server racks (20), basic UPS, PDUs, cable management, monitoring sensors.",
            "mid":  "Server cabinets (50+), modular UPS system, intelligent PDUs, DCIM software, containment system.",
            "high": "High-density racks (100+), 2N UPS with rotary flywheel, busway power distribution, full DCIM, fuel cells.",
        },
        "hospital_acute": {
            "low":  "Basic medical equipment allowance, nurse call system, patient lifts.",
            "mid":  "Medical equipment package: imaging suite, surgical lighting, central monitoring, pneumatic tube system.",
            "high": "Complete medical equipment: MRI/CT suite, robotic surgery, RTLS, automated pharmacy, linear accelerator.",
        },
        "research_lab": {
            "low":  "Fume hoods, lab benches, basic analytical instruments, safety equipment.",
            "mid":  "Fume hoods, flexible casework, BSL-2 cabinets, autoclaves, DI water system.",
            "high": "Walk-in environmental chambers, BSL-3 containment, clean rooms, specialized research instruments.",
        },
    }
    # Default equipment description
    category = _get_category(sub_type)
    default = {
        "residential": {
            "low": "Standard appliance package: range, refrigerator, dishwasher, microwave.",
            "mid": "Mid-grade appliance package: stainless steel range, refrigerator, dishwasher, microwave, disposal.",
            "high": "Premium appliance suite: professional range, built-in refrigerator, panel-ready dishwasher, wine cooler.",
        },
        "commercial": {
            "low": "Building-specific equipment as required, minimal owner-furnished equipment.",
            "mid": "Building equipment per program requirements, loading dock equipment, trash compactor.",
            "high": "Full equipment complement per program, automated systems, specialty equipment as required.",
        },
        "industrial": {
            "low": "Dock levelers, loading equipment, basic material handling.",
            "mid": "Dock levelers, bridge crane (5-ton), material handling systems, process equipment pads.",
            "high": "Overhead cranes (25-50 ton), automated material handling, process-specific equipment, robotic systems.",
        },
        "institutional": {
            "low": "Program-specific equipment per owner requirements.",
            "mid": "Institutional equipment package, AV equipment, food service (if applicable).",
            "high": "Complete equipment package, specialized program equipment, technology integration.",
        },
        "infrastructure": {
            "low": "Basic operational equipment per facility type.",
            "mid": "Operational equipment, communication systems, specialized vehicle equipment.",
            "high": "Complete operational fit-out, command center equipment, emergency management systems.",
        },
    }
    if sub_type in equipment_map:
        return equipment_map[sub_type].get(quality, equipment_map[sub_type]["mid"])
    cat = category if category in default else "commercial"
    return default[cat].get(quality, default[cat]["mid"])


def _get_furnishings_detail(category: str, quality: str) -> str:
    details = {
        "residential": {
            "low":  "Window blinds, basic closet shelving, standard bath mirrors.",
            "mid":  "Window treatments (blinds and drapes), custom closet organizers, decorative mirrors, area rugs.",
            "high": "Motorized window treatments, custom built-in furniture, designer light fixtures, curated artwork.",
        },
        "commercial": {
            "low":  "Horizontal blinds, minimal fixed furnishings.",
            "mid":  "Window treatments, reception desk, conference table, task and guest seating (owner allowance).",
            "high": "Motorized shading, custom reception millwork, designer furniture package, artwork program.",
        },
        "industrial": {
            "low":  "Minimal — break room table and chairs.",
            "mid":  "Office furniture systems, break room furnishings, entrance mat system.",
            "high": "Open office workstations, collaboration areas, executive offices, full cafeteria fit-out.",
        },
        "institutional": {
            "low":  "Window blinds, minimal fixed seating.",
            "mid":  "Window treatments, fixed and movable seating, display furnishings, entrance mats.",
            "high": "Custom window treatments, auditorium seating, custom display cases, donor walls, entrance vestibule.",
        },
        "infrastructure": {
            "low":  "Window blinds, bunk furniture (if applicable).",
            "mid":  "Window treatments, fixed seating, console furniture, dormitory furnishings (if applicable).",
            "high": "Custom console workstations, ergonomic seating, sleeping quarters furnishings, kitchen fit-out.",
        },
    }
    return details.get(category, details["commercial"]).get(quality, details["commercial"]["mid"])


def _get_elevator_detail(category: str, quality: str, stories: int) -> str:
    if stories <= 3:
        elevator = "Hydraulic passenger elevator"
    elif stories <= 8:
        elevator = "Geared traction passenger elevator"
    else:
        elevator = "Gearless traction high-speed passenger elevator"

    details = {
        "low":  f"{elevator}, {stories}-stop, 2500 lb capacity, standard cab finish.",
        "mid":  f"{elevator}, {stories}-stop, 3500 lb capacity, stainless steel cab, destination dispatch.",
        "high": f"{elevator}s (2), {stories}-stop, 4000 lb capacity, custom cab interiors, destination dispatch with hall lanterns.",
    }
    if category in ("institutional", "commercial") and quality in ("mid", "high"):
        details["mid"] += " Service elevator with 4500 lb capacity."
        details["high"] += " Dedicated service elevator with 5000 lb capacity."

    return details.get(quality, details["mid"])


if __name__ == "__main__":
    spec = generate(
        sub_type="office_midrise",
        quality="mid",
        area_sf=45000,
        stories=5,
        building_name="Example Office Building",
        location="chicago",
        seed=42,
    )
    print(spec[:2000])
    print(f"\n... ({len(spec)} total characters)")
