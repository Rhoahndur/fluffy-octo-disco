// Geographic location cost multipliers
// Relative to national average (1.00)

export const LOCATION_FACTORS: Record<string, number> = {
  new_york:       1.30,
  san_francisco:  1.27,
  boston:         1.24,
  los_angeles:    1.18,
  chicago:        1.15,
  seattle:        1.13,
  washington_dc:  1.10,
  denver:         1.08,
  minneapolis:    1.06,
  philadelphia:   1.05,
  portland:       1.04,
  detroit:        1.02,
  national:       1.00,
  miami:          0.98,
  baltimore:      0.97,
  las_vegas:      0.96,
  pittsburgh:     0.95,
  tampa:          0.93,
  atlanta:        0.92,
  phoenix:        0.91,
  nashville:      0.90,
  dallas:         0.88,
  charlotte:      0.87,
  houston:        0.86,
  san_antonio:    0.85,
  indianapolis:   0.84,
  memphis:        0.82,
};

export const ALL_LOCATIONS = Object.keys(LOCATION_FACTORS);

// Helper to find best matching location from free-form text
export function findLocationFactor(locationText: string): { location: string; factor: number } {
  const normalized = locationText.toLowerCase().replace(/[^a-z]/g, '_');

  // Direct match
  if (LOCATION_FACTORS[normalized]) {
    return { location: normalized, factor: LOCATION_FACTORS[normalized] };
  }

  // Partial match
  for (const [loc, factor] of Object.entries(LOCATION_FACTORS)) {
    if (normalized.includes(loc.replace('_', '')) || loc.includes(normalized.replace('_', ''))) {
      return { location: loc, factor };
    }
  }

  // State-based approximations
  const stateMap: Record<string, string> = {
    'california': 'los_angeles',
    'ca': 'los_angeles',
    'texas': 'dallas',
    'tx': 'dallas',
    'florida': 'miami',
    'fl': 'miami',
    'illinois': 'chicago',
    'il': 'chicago',
    'pennsylvania': 'philadelphia',
    'pa': 'philadelphia',
    'ohio': 'detroit',
    'georgia': 'atlanta',
    'ga': 'atlanta',
    'arizona': 'phoenix',
    'az': 'phoenix',
    'colorado': 'denver',
    'co': 'denver',
    'washington': 'seattle',
    'wa': 'seattle',
    'oregon': 'portland',
    'or': 'portland',
    'massachusetts': 'boston',
    'ma': 'boston',
    'tennessee': 'nashville',
    'tn': 'nashville',
    'north_carolina': 'charlotte',
    'nc': 'charlotte',
    'nevada': 'las_vegas',
    'nv': 'las_vegas',
    'minnesota': 'minneapolis',
    'mn': 'minneapolis',
    'maryland': 'baltimore',
    'md': 'baltimore',
    'indiana': 'indianapolis',
  };

  for (const [state, city] of Object.entries(stateMap)) {
    if (normalized.includes(state)) {
      return { location: city, factor: LOCATION_FACTORS[city] };
    }
  }

  // Default to national average
  return { location: 'national', factor: 1.0 };
}
