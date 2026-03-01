// RSMeans-based cost per square foot data
// Derived from RSMeans 2024-2025 national averages

export const COST_PER_SF: Record<string, Record<'low' | 'mid' | 'high', number>> = {
  // Residential
  single_family_economy:    { low: 120, mid: 162, high: 195 },
  single_family_standard:   { low: 145, mid: 195, high: 260 },
  single_family_premium:    { low: 195, mid: 275, high: 370 },
  single_family_custom:     { low: 275, mid: 385, high: 525 },
  multi_family_duplex:      { low: 130, mid: 178, high: 235 },
  multi_family_triplex:     { low: 125, mid: 172, high: 225 },
  multi_family_fourplex:    { low: 118, mid: 165, high: 218 },
  apartment_lowrise:        { low: 140, mid: 195, high: 275 },
  apartment_midrise:        { low: 175, mid: 248, high: 340 },
  apartment_garden:         { low: 128, mid: 178, high: 245 },
  townhouse_standard:       { low: 135, mid: 185, high: 250 },
  townhouse_luxury:         { low: 210, mid: 305, high: 425 },
  condo_midrise:            { low: 185, mid: 265, high: 380 },
  luxury_estate:            { low: 350, mid: 525, high: 750 },
  custom_architectural:     { low: 400, mid: 600, high: 900 },

  // Commercial
  office_lowrise:           { low: 225, mid: 362, high: 530 },
  office_midrise:           { low: 330, mid: 562, high: 870 },
  office_highrise:          { low: 420, mid: 685, high: 1050 },
  retail_strip:             { low: 145, mid: 248, high: 385 },
  retail_bigbox:            { low: 110, mid: 185, high: 290 },
  restaurant_casual:        { low: 250, mid: 395, high: 580 },
  restaurant_fine:          { low: 380, mid: 575, high: 850 },
  hotel_limited:            { low: 210, mid: 342, high: 495 },
  hotel_full_service:       { low: 340, mid: 548, high: 820 },
  bank_branch:              { low: 280, mid: 425, high: 620 },
  medical_office:           { low: 290, mid: 448, high: 650 },
  mixed_use:                { low: 260, mid: 420, high: 640 },

  // Industrial
  warehouse_light:          { low:  90, mid: 238, high: 350 },
  warehouse_heavy:          { low: 120, mid: 285, high: 420 },
  manufacturing_light:      { low: 110, mid: 268, high: 395 },
  manufacturing_heavy:      { low: 145, mid: 325, high: 490 },
  data_center:              { low: 750, mid: 1250, high: 1950 },
  research_lab:             { low: 480, mid: 788, high: 1150 },
  cold_storage:             { low: 175, mid: 348, high: 520 },
  food_processing:          { low: 220, mid: 385, high: 575 },

  // Institutional
  school_elementary:        { low: 225, mid: 365, high: 520 },
  school_high:              { low: 275, mid: 432, high: 620 },
  university_classroom:     { low: 310, mid: 488, high: 700 },
  university_science:       { low: 450, mid: 725, high: 1050 },
  hospital_acute:           { low: 600, mid: 888, high: 1020 },
  clinic_outpatient:        { low: 320, mid: 498, high: 700 },
  church_standard:          { low: 180, mid: 295, high: 440 },
  church_cathedral:         { low: 350, mid: 575, high: 880 },
  library_public:           { low: 290, mid: 452, high: 650 },
  community_center:         { low: 220, mid: 358, high: 520 },

  // Infrastructure
  parking_surface:          { low:  25, mid:  45, high:  72 },
  parking_structured:       { low:  65, mid: 105, high: 165 },
  fire_station:             { low: 280, mid: 432, high: 620 },
  police_station:           { low: 310, mid: 475, high: 680 },
  transit_station:          { low: 350, mid: 548, high: 790 },
  bus_maintenance:          { low: 195, mid: 325, high: 480 },
  water_treatment:          { low: 420, mid: 688, high: 1020 },
  electrical_substation:    { low: 380, mid: 625, high: 940 },
};

export const ALL_SUBTYPES = Object.keys(COST_PER_SF);
