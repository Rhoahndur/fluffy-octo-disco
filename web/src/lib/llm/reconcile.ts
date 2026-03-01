// Reconciliation logic for merging LLM outputs with OpenCV guardrails
//
// Philosophy:
// - OpenCV provides DETERMINISTIC measurements (counts, areas, dimensions)
// - LLMs provide PROBABILISTIC interpretation (building type, quality, semantics)
// - Reconciliation uses CV to constrain/validate LLM outputs
// - When CV and LLM disagree on measurables, CV wins (with confidence weighting)

import type { LLMAnalysis, CVAnalysis, ReconciliationResult, Quality } from '@/types';
import type { LLMAnalysisResponse } from './types';
import { ALL_SUBTYPES } from '@/lib/cost/data/cost-per-sf';

interface ReconcileInput {
  claude?: LLMAnalysisResponse;
  gemini?: LLMAnalysisResponse;
  opencv?: CVAnalysis;
}

interface ReconciliationDetails {
  sqft_source: 'cv_ocr' | 'cv_measured' | 'llm_consensus' | 'llm_primary' | 'default';
  cv_overrides: string[];
  llm_consensus: string[];
  warnings: string[];
}

export function reconcileAnalyses(input: ReconcileInput): ReconciliationResult {
  const { claude, gemini, opencv } = input;
  const conflicts: string[] = [];
  const details: ReconciliationDetails = {
    sqft_source: 'default',
    cv_overrides: [],
    llm_consensus: [],
    warnings: [],
  };

  // If we have no LLM results, try to build from CV alone
  if (!claude && !gemini) {
    return buildFromCVOnly(opencv, conflicts);
  }

  // Determine primary and secondary LLM sources
  const { primary, secondary } = selectPrimaryLLM(claude, gemini);

  // Start with LLM-based merged analysis
  const merged: LLMAnalysis = {
    building_type: primary.building_type,
    sub_type: primary.sub_type,
    quality: primary.quality,
    estimated_sqft: primary.estimated_sqft,
    stories: primary.stories,
    materials_detected: [...primary.materials_detected],
    construction_type: primary.construction_type,
    location: primary.location,
    confidence: primary.confidence,
    notes: primary.notes,
  };

  // Step 1: Reconcile between LLMs (semantic/classification tasks)
  if (secondary) {
    reconcileLLMs(merged, primary, secondary, conflicts, details);
  }

  // Step 2: Apply CV guardrails (deterministic measurements override probabilistic)
  if (opencv) {
    applyCVGuardrails(merged, opencv, conflicts, details);
  }

  // Step 3: Validate and finalize
  validateSubType(merged, conflicts);
  const finalConfidence = calculateFinalConfidence(merged, conflicts, details, opencv);

  return {
    merged,
    conflicts,
    confidence: Math.round(finalConfidence * 100) / 100,
    sources: {
      claude: claude as LLMAnalysis | undefined,
      gemini: gemini as LLMAnalysis | undefined,
      opencv,
    },
  };
}

function selectPrimaryLLM(
  claude?: LLMAnalysisResponse,
  gemini?: LLMAnalysisResponse
): { primary: LLMAnalysisResponse; secondary?: LLMAnalysisResponse } {
  if (claude && gemini) {
    // Prefer higher confidence, but weight Claude slightly for construction
    const claudeScore = claude.confidence + 0.05;
    const geminiScore = gemini.confidence;

    if (claudeScore >= geminiScore) {
      return { primary: claude, secondary: gemini };
    } else {
      return { primary: gemini, secondary: claude };
    }
  }

  return { primary: (claude || gemini)! };
}

function reconcileLLMs(
  merged: LLMAnalysis,
  primary: LLMAnalysisResponse,
  secondary: LLMAnalysisResponse,
  conflicts: string[],
  details: ReconciliationDetails
): void {
  // Building type - semantic, trust LLM consensus
  if (primary.building_type === secondary.building_type) {
    details.llm_consensus.push('building_type');
  } else {
    conflicts.push(`Building type: ${primary.building_type} vs ${secondary.building_type}`);
  }

  // Sub-type consensus
  if (primary.sub_type === secondary.sub_type) {
    details.llm_consensus.push('sub_type');
  } else {
    conflicts.push(`Sub-type: ${primary.sub_type} vs ${secondary.sub_type}`);
  }

  // Quality - semantic assessment, average if adjacent
  if (primary.quality === secondary.quality) {
    details.llm_consensus.push('quality');
  } else {
    conflicts.push(`Quality: ${primary.quality} vs ${secondary.quality}`);
    const qualities: Quality[] = ['low', 'mid', 'high'];
    const pIdx = qualities.indexOf(primary.quality);
    const sIdx = qualities.indexOf(secondary.quality);
    if (Math.abs(pIdx - sIdx) === 1) {
      merged.quality = 'mid'; // Split the difference
    }
  }

  // Square footage - average if significant difference (CV will override later if available)
  const sqftDiff = Math.abs(primary.estimated_sqft - secondary.estimated_sqft) /
                   Math.max(primary.estimated_sqft, secondary.estimated_sqft);
  if (sqftDiff > 0.2) {
    conflicts.push(`LLM sqft: ${primary.estimated_sqft} vs ${secondary.estimated_sqft} (${Math.round(sqftDiff * 100)}% diff)`);
    merged.estimated_sqft = Math.round((primary.estimated_sqft + secondary.estimated_sqft) / 2);
    details.sqft_source = 'llm_consensus';
  } else {
    details.sqft_source = 'llm_primary';
  }

  // Stories - use lower (more conservative)
  if (primary.stories !== secondary.stories) {
    conflicts.push(`Stories: ${primary.stories} vs ${secondary.stories}`);
    merged.stories = Math.min(primary.stories, secondary.stories);
  }

  // Merge materials (union of both)
  const allMaterials = new Set([...primary.materials_detected, ...secondary.materials_detected]);
  merged.materials_detected = Array.from(allMaterials);
}

function applyCVGuardrails(
  merged: LLMAnalysis,
  cv: CVAnalysis,
  conflicts: string[],
  details: ReconciliationDetails
): void {
  // RULE 1: If CV extracted sqft from OCR text, that's ground truth
  if (cv.text_extraction?.sqft_from_text && cv.text_extraction.sqft_from_text.length > 0) {
    const cvSqft = Math.max(...cv.text_extraction.sqft_from_text);
    const llmSqft = merged.estimated_sqft;
    const diff = Math.abs(cvSqft - llmSqft) / Math.max(cvSqft, llmSqft);

    if (diff > 0.1) {
      conflicts.push(`CV OCR sqft (${cvSqft}) vs LLM estimate (${llmSqft}) - using OCR value`);
      details.cv_overrides.push('sqft_from_ocr');
    }
    merged.estimated_sqft = cvSqft;
    details.sqft_source = 'cv_ocr';
  }
  // RULE 2: If CV measured area with scale, use weighted average
  else if (cv.measurements?.total_area?.value && cv.scale?.detected) {
    const cvSqft = cv.measurements.total_area.value;
    const llmSqft = merged.estimated_sqft;
    const diff = Math.abs(cvSqft - llmSqft) / Math.max(cvSqft, llmSqft);

    if (diff > 0.25) {
      conflicts.push(`CV measured sqft (${cvSqft}) vs LLM estimate (${llmSqft})`);
      // Weight CV more heavily when scale is detected
      merged.estimated_sqft = Math.round(cvSqft * 0.7 + llmSqft * 0.3);
      details.cv_overrides.push('sqft_from_measurement');
      details.sqft_source = 'cv_measured';
    }
  }

  // RULE 3: Room count sanity check
  const cvRooms = cv.counts?.rooms || cv.room_count || 0;
  if (cvRooms > 0) {
    // Typical room sizes: 100-400 SF per room
    const expectedMinSqft = cvRooms * 100;
    const expectedMaxSqft = cvRooms * 500;

    if (merged.estimated_sqft < expectedMinSqft) {
      details.warnings.push(`Sqft (${merged.estimated_sqft}) seems low for ${cvRooms} rooms`);
    }
    if (merged.estimated_sqft > expectedMaxSqft && merged.stories === 1) {
      details.warnings.push(`Sqft (${merged.estimated_sqft}) seems high for ${cvRooms} rooms on 1 story`);
    }

    // If many rooms but single story, might be multi-story
    if (cvRooms > 8 && merged.stories === 1 && merged.building_type === 'residential') {
      details.warnings.push(`${cvRooms} rooms detected but only 1 story - verify floor count`);
    }
  }

  // RULE 4: Door/window counts for quality validation
  const doors = cv.counts?.doors || 0;
  const windows = cv.counts?.windows || 0;

  if (doors > 0 || windows > 0) {
    // High-end homes typically have more windows per sqft
    const windowDensity = windows / (merged.estimated_sqft / 1000);

    if (windowDensity > 15 && merged.quality === 'low') {
      details.warnings.push(`High window density (${windowDensity.toFixed(1)}/1000sf) suggests higher quality`);
    }
    if (windowDensity < 5 && merged.quality === 'high') {
      details.warnings.push(`Low window density (${windowDensity.toFixed(1)}/1000sf) - verify quality level`);
    }
  }

  // RULE 5: Drawing type validation
  if (cv.drawing_type === 'photo' && merged.construction_type === 'unknown') {
    merged.construction_type = 'existing_structure';
  }

  // RULE 6: Merge CV-detected materials with LLM materials
  if (cv.materials && Object.keys(cv.materials).length > 0) {
    const cvMaterials = Object.keys(cv.materials).filter(k => cv.materials[k]);
    const newMaterials = cvMaterials.filter(m => !merged.materials_detected.includes(m));
    if (newMaterials.length > 0) {
      merged.materials_detected = [...merged.materials_detected, ...newMaterials];
      details.cv_overrides.push(`materials: +${newMaterials.join(', ')}`);
    }
  }

  // RULE 7: Add CV-extracted specs/grades to notes
  if (cv.text_extraction?.grades_specs && cv.text_extraction.grades_specs.length > 0) {
    const specs = cv.text_extraction.grades_specs.slice(0, 5).join(', ');
    merged.notes = merged.notes
      ? `${merged.notes} | CV specs: ${specs}`
      : `CV specs: ${specs}`;
  }

  // RULE 8: Use CV dimensions in notes if available
  if (cv.text_extraction?.dimensions_found && cv.text_extraction.dimensions_found.length > 0) {
    const dims = cv.text_extraction.dimensions_found.slice(0, 5).join(', ');
    merged.notes = merged.notes
      ? `${merged.notes} | Dimensions: ${dims}`
      : `Dimensions: ${dims}`;
  }
}

function validateSubType(merged: LLMAnalysis, conflicts: string[]): void {
  if (!ALL_SUBTYPES.includes(merged.sub_type)) {
    const original = merged.sub_type;

    // Try to find a close match
    const normalized = merged.sub_type.toLowerCase().replace(/[-\s]/g, '_');
    const match = ALL_SUBTYPES.find(st =>
      st.toLowerCase().includes(normalized) ||
      normalized.includes(st.toLowerCase().replace(/_/g, ''))
    );

    if (match) {
      merged.sub_type = match;
      conflicts.push(`Normalized sub_type: ${original} → ${match}`);
    } else {
      // Default based on building type
      const defaults: Record<string, string> = {
        residential: 'single_family_standard',
        commercial: 'office_standard',
        industrial: 'warehouse_standard',
        institutional: 'school_standard',
        infrastructure: 'road_local',
      };
      merged.sub_type = defaults[merged.building_type] || 'single_family_standard';
      conflicts.push(`Unknown sub_type: ${original}, defaulted to ${merged.sub_type}`);
    }
  }
}

function calculateFinalConfidence(
  merged: LLMAnalysis,
  conflicts: string[],
  details: ReconciliationDetails,
  opencv?: CVAnalysis
): number {
  let confidence = merged.confidence;

  // Boost for CV validation
  if (details.sqft_source === 'cv_ocr') {
    confidence += 0.15; // High confidence in OCR-extracted sqft
  } else if (details.sqft_source === 'cv_measured') {
    confidence += 0.10;
  }

  // Boost for LLM consensus
  if (details.llm_consensus.length >= 3) {
    confidence += 0.10;
  }

  // Penalty for conflicts
  confidence -= conflicts.length * 0.03;

  // Penalty for warnings
  confidence -= details.warnings.length * 0.02;

  // Boost if CV has high confidence
  if (opencv && opencv.confidence > 0.7) {
    confidence += 0.05;
  }

  // Ensure valid range
  return Math.max(0.1, Math.min(1.0, confidence));
}

function buildFromCVOnly(
  opencv: CVAnalysis | undefined,
  conflicts: string[]
): ReconciliationResult {
  conflicts.push('No LLM analysis available - using CV data only');

  const merged: LLMAnalysis = {
    building_type: 'residential',
    sub_type: 'single_family_standard',
    quality: 'mid',
    estimated_sqft: 2000,
    stories: 1,
    materials_detected: [],
    construction_type: 'unknown',
    confidence: 0.2,
    notes: 'Built from CV analysis only',
  };

  if (opencv) {
    // Use CV sqft if available
    if (opencv.text_extraction?.sqft_from_text?.length) {
      merged.estimated_sqft = Math.max(...opencv.text_extraction.sqft_from_text);
      merged.confidence += 0.2;
    } else if (opencv.measurements?.total_area?.value) {
      merged.estimated_sqft = opencv.measurements.total_area.value;
      merged.confidence += 0.1;
    }

    // Use CV materials
    if (opencv.materials) {
      merged.materials_detected = Object.keys(opencv.materials).filter(k => opencv.materials[k]);
    }

    // Infer building type from room count and drawing type
    const rooms = opencv.counts?.rooms || opencv.room_count || 0;
    if (opencv.drawing_type === 'floor_plan') {
      if (rooms > 20) {
        merged.building_type = 'commercial';
        merged.sub_type = 'office_standard';
      } else if (rooms > 10) {
        merged.building_type = 'residential';
        merged.sub_type = 'multi_family_standard';
      }
    }
  }

  return {
    merged,
    conflicts,
    confidence: Math.round(merged.confidence * 100) / 100,
    sources: { opencv },
  };
}
