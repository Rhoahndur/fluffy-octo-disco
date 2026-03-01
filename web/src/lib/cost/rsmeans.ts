// RSMeans-based cost calculation engine
// Ported from cost_model.py

import { COST_PER_SF, ALL_SUBTYPES } from './data/cost-per-sf';
import { LOCATION_FACTORS, findLocationFactor } from './data/location-factors';
import {
  CSI_DIVISIONS,
  CSI_DIVISION_PROFILES,
  SUBTYPE_TO_PROFILE,
  SUBTYPE_TO_CATEGORY
} from './data/csi-profiles';
import type { Quality, CostEstimate, DivisionBreakdown, ItemQuantity } from '@/types';

export interface CostCalculationInput {
  sub_type: string;
  quality: Quality;
  area_sf: number;
  stories?: number;
  location?: string;
  seed?: number;
}

// Seeded random number generator
function seededRandom(seed: number): () => number {
  let state = seed;
  return () => {
    state = (state * 1103515245 + 12345) & 0x7fffffff;
    return state / 0x7fffffff;
  };
}

export function calculateCost(input: CostCalculationInput): CostEstimate {
  const {
    sub_type,
    quality,
    area_sf,
    stories = 1,
    location = 'national',
    seed,
  } = input;

  // Validate sub_type
  if (!COST_PER_SF[sub_type]) {
    throw new Error(`Unknown building sub-type: ${sub_type}. Valid types: ${ALL_SUBTYPES.join(', ')}`);
  }

  // Get base cost per SF
  const baseCostSF = COST_PER_SF[sub_type][quality];

  // Location adjustment
  const { location: resolvedLocation, factor: locationFactor } = findLocationFactor(location);
  let adjustedCostSF = baseCostSF * locationFactor;

  // Story premium: +2.5% per floor above 3
  let storyPremium = 1.0;
  if (stories > 3) {
    storyPremium = 1.0 + 0.025 * (stories - 3);
  }
  adjustedCostSF *= storyPremium;

  // Seeded random variance (±3%) for realism
  if (seed !== undefined) {
    const rng = seededRandom(seed);
    const variance = (rng() * 0.06) - 0.03; // -0.03 to +0.03
    adjustedCostSF *= (1.0 + variance);
  }

  // Total cost
  const totalCost = adjustedCostSF * area_sf;

  // CSI division breakdown
  const profileName = SUBTYPE_TO_PROFILE[sub_type] || 'commercial_office';
  const profile = CSI_DIVISION_PROFILES[profileName];

  const divisionBreakdown: DivisionBreakdown = {} as DivisionBreakdown;
  for (const division of CSI_DIVISIONS) {
    const pct = profile[division] || 0;
    divisionBreakdown[division] = Math.round(totalCost * pct * 100) / 100;
  }

  // Estimate item quantities
  const itemQuantities = estimateQuantities(sub_type, quality, area_sf, stories, divisionBreakdown);

  return {
    total_cost: Math.round(totalCost * 100) / 100,
    cost_per_sf: Math.round(adjustedCostSF * 100) / 100,
    area_sf,
    stories,
    quality,
    location: resolvedLocation,
    location_factor: locationFactor,
    story_premium: Math.round(storyPremium * 10000) / 10000,
    base_cost_sf: baseCostSF,
    csi_profile: profileName,
    division_breakdown: divisionBreakdown,
    item_quantities: itemQuantities,
  };
}

// Estimate material quantities based on building type and area
function estimateQuantities(
  subType: string,
  quality: Quality,
  areaSF: number,
  stories: number,
  breakdown: DivisionBreakdown
): ItemQuantity[] {
  const quantities: ItemQuantity[] = [];
  const category = SUBTYPE_TO_CATEGORY[subType] || 'commercial';

  // Quality multipliers for material quantities
  const qualityMultiplier = quality === 'high' ? 1.15 : quality === 'low' ? 0.85 : 1.0;

  // Concrete (Division 03)
  const concreteYards = Math.round((areaSF * 0.05 * qualityMultiplier) * 10) / 10;
  quantities.push({
    item: 'Concrete (foundation & slab)',
    quantity: concreteYards,
    unit: 'cubic yards',
    unit_cost: Math.round((breakdown['03_concrete'] / concreteYards) * 100) / 100,
    total_cost: breakdown['03_concrete'],
    division: '03_concrete',
  });

  // Lumber/Wood (Division 06) - mainly for residential
  if (category === 'residential') {
    const boardFeet = Math.round(areaSF * 12 * qualityMultiplier);
    quantities.push({
      item: 'Framing lumber',
      quantity: boardFeet,
      unit: 'board feet',
      unit_cost: Math.round((breakdown['06_wood_plastics_composites'] / boardFeet) * 100) / 100,
      total_cost: breakdown['06_wood_plastics_composites'],
      division: '06_wood_plastics_composites',
    });
  }

  // Structural steel (Division 05) - mainly for commercial/industrial
  if (category !== 'residential') {
    const steelTons = Math.round((areaSF * 0.008 * qualityMultiplier) * 10) / 10;
    quantities.push({
      item: 'Structural steel',
      quantity: steelTons,
      unit: 'tons',
      unit_cost: Math.round((breakdown['05_metals'] / steelTons) * 100) / 100,
      total_cost: breakdown['05_metals'],
      division: '05_metals',
    });
  }

  // Roofing (Division 07)
  const roofingSF = Math.round(areaSF / stories * 1.1); // Account for overhangs/slope
  quantities.push({
    item: 'Roofing materials',
    quantity: roofingSF,
    unit: 'sq ft',
    unit_cost: Math.round((breakdown['07_thermal_moisture'] * 0.4 / roofingSF) * 100) / 100,
    total_cost: Math.round(breakdown['07_thermal_moisture'] * 0.4 * 100) / 100,
    division: '07_thermal_moisture',
  });

  // Insulation (Division 07)
  const insulationSF = Math.round(areaSF * 1.5); // Walls + ceiling
  quantities.push({
    item: 'Insulation',
    quantity: insulationSF,
    unit: 'sq ft',
    unit_cost: Math.round((breakdown['07_thermal_moisture'] * 0.6 / insulationSF) * 100) / 100,
    total_cost: Math.round(breakdown['07_thermal_moisture'] * 0.6 * 100) / 100,
    division: '07_thermal_moisture',
  });

  // Windows & Doors (Division 08)
  const windowCount = Math.round(areaSF / 150 * qualityMultiplier);
  const doorCount = Math.round(areaSF / 300);
  quantities.push({
    item: 'Windows',
    quantity: windowCount,
    unit: 'units',
    unit_cost: Math.round((breakdown['08_openings'] * 0.7 / windowCount) * 100) / 100,
    total_cost: Math.round(breakdown['08_openings'] * 0.7 * 100) / 100,
    division: '08_openings',
  });
  quantities.push({
    item: 'Doors (interior & exterior)',
    quantity: doorCount,
    unit: 'units',
    unit_cost: Math.round((breakdown['08_openings'] * 0.3 / doorCount) * 100) / 100,
    total_cost: Math.round(breakdown['08_openings'] * 0.3 * 100) / 100,
    division: '08_openings',
  });

  // Drywall (Division 09)
  const drywallSF = Math.round(areaSF * 3.5); // Walls and ceiling
  quantities.push({
    item: 'Drywall',
    quantity: drywallSF,
    unit: 'sq ft',
    unit_cost: Math.round((breakdown['09_finishes'] * 0.3 / drywallSF) * 100) / 100,
    total_cost: Math.round(breakdown['09_finishes'] * 0.3 * 100) / 100,
    division: '09_finishes',
  });

  // Flooring (Division 09)
  quantities.push({
    item: 'Flooring materials',
    quantity: areaSF,
    unit: 'sq ft',
    unit_cost: Math.round((breakdown['09_finishes'] * 0.4 / areaSF) * 100) / 100,
    total_cost: Math.round(breakdown['09_finishes'] * 0.4 * 100) / 100,
    division: '09_finishes',
  });

  // Paint (Division 09)
  const paintSF = Math.round(areaSF * 4); // All surfaces
  quantities.push({
    item: 'Paint & coatings',
    quantity: paintSF,
    unit: 'sq ft',
    unit_cost: Math.round((breakdown['09_finishes'] * 0.3 / paintSF) * 100) / 100,
    total_cost: Math.round(breakdown['09_finishes'] * 0.3 * 100) / 100,
    division: '09_finishes',
  });

  // Plumbing fixtures (Division 22)
  const fixtureCount = Math.round(areaSF / 400 * qualityMultiplier);
  quantities.push({
    item: 'Plumbing fixtures',
    quantity: fixtureCount,
    unit: 'fixtures',
    unit_cost: Math.round((breakdown['22_plumbing'] * 0.6 / fixtureCount) * 100) / 100,
    total_cost: Math.round(breakdown['22_plumbing'] * 0.6 * 100) / 100,
    division: '22_plumbing',
  });

  // HVAC (Division 23)
  const hvacTons = Math.round(areaSF / 500 * qualityMultiplier * 10) / 10;
  quantities.push({
    item: 'HVAC system',
    quantity: hvacTons,
    unit: 'tons capacity',
    unit_cost: Math.round((breakdown['23_hvac'] / hvacTons) * 100) / 100,
    total_cost: breakdown['23_hvac'],
    division: '23_hvac',
  });

  // Electrical (Division 26)
  const electricalCircuits = Math.round(areaSF / 100 * qualityMultiplier);
  quantities.push({
    item: 'Electrical circuits',
    quantity: electricalCircuits,
    unit: 'circuits',
    unit_cost: Math.round((breakdown['26_electrical'] * 0.5 / electricalCircuits) * 100) / 100,
    total_cost: Math.round(breakdown['26_electrical'] * 0.5 * 100) / 100,
    division: '26_electrical',
  });

  // Light fixtures (Division 26)
  const lightCount = Math.round(areaSF / 80 * qualityMultiplier);
  quantities.push({
    item: 'Light fixtures',
    quantity: lightCount,
    unit: 'fixtures',
    unit_cost: Math.round((breakdown['26_electrical'] * 0.3 / lightCount) * 100) / 100,
    total_cost: Math.round(breakdown['26_electrical'] * 0.3 * 100) / 100,
    division: '26_electrical',
  });

  return quantities;
}

export function getAllSubtypes(): string[] {
  return ALL_SUBTYPES;
}

export function getCategory(subType: string): string {
  return SUBTYPE_TO_CATEGORY[subType] || 'unknown';
}

export function getCSIProfile(subType: string): string {
  return SUBTYPE_TO_PROFILE[subType] || 'commercial_office';
}
