// Reconciliation logic for merging LLM outputs

import type { LLMAnalysis, CVAnalysis, ReconciliationResult, Quality, BuildingCategory } from '@/types';
import type { LLMAnalysisResponse } from './types';
import { ALL_SUBTYPES } from '@/lib/cost/data/cost-per-sf';

interface ReconcileInput {
  claude?: LLMAnalysisResponse;
  gemini?: LLMAnalysisResponse;
  opencv?: CVAnalysis;
}

export function reconcileAnalyses(input: ReconcileInput): ReconciliationResult {
  const { claude, gemini, opencv } = input;
  const conflicts: string[] = [];

  // If we have no LLM results, return a default
  if (!claude && !gemini) {
    return {
      merged: getDefaultAnalysis(),
      conflicts: ['No LLM analysis available'],
      confidence: 0,
      sources: { opencv },
    };
  }

  // Start with the higher-confidence result as base
  let primary: LLMAnalysisResponse;
  let secondary: LLMAnalysisResponse | undefined;

  if (claude && gemini) {
    if (claude.confidence >= gemini.confidence) {
      primary = claude;
      secondary = gemini;
    } else {
      primary = gemini;
      secondary = claude;
    }
  } else {
    primary = (claude || gemini)!;
  }

  const merged: LLMAnalysis = {
    building_type: primary.building_type,
    sub_type: primary.sub_type,
    quality: primary.quality,
    estimated_sqft: primary.estimated_sqft,
    stories: primary.stories,
    materials_detected: primary.materials_detected,
    construction_type: primary.construction_type,
    location: primary.location,
    confidence: primary.confidence,
    notes: primary.notes,
  };

  // Check for conflicts if we have both LLM results
  if (secondary) {
    // Building type conflict
    if (primary.building_type !== secondary.building_type) {
      conflicts.push(`Building type: ${primary.building_type} vs ${secondary.building_type}`);
    }

    // Sub-type conflict
    if (primary.sub_type !== secondary.sub_type) {
      conflicts.push(`Sub-type: ${primary.sub_type} vs ${secondary.sub_type}`);
    }

    // Quality conflict
    if (primary.quality !== secondary.quality) {
      conflicts.push(`Quality: ${primary.quality} vs ${secondary.quality}`);
      // Use average if adjacent quality levels
      const qualities: Quality[] = ['low', 'mid', 'high'];
      const pIdx = qualities.indexOf(primary.quality);
      const sIdx = qualities.indexOf(secondary.quality);
      if (Math.abs(pIdx - sIdx) === 1) {
        merged.quality = 'mid';
      }
    }

    // Sqft conflict (>20% difference)
    const sqftDiff = Math.abs(primary.estimated_sqft - secondary.estimated_sqft) /
                     Math.max(primary.estimated_sqft, secondary.estimated_sqft);
    if (sqftDiff > 0.2) {
      conflicts.push(`Square footage: ${primary.estimated_sqft} vs ${secondary.estimated_sqft} (${Math.round(sqftDiff * 100)}% diff)`);
      // Average them
      merged.estimated_sqft = Math.round((primary.estimated_sqft + secondary.estimated_sqft) / 2);
    }

    // Stories conflict
    if (primary.stories !== secondary.stories) {
      conflicts.push(`Stories: ${primary.stories} vs ${secondary.stories}`);
      // Use the lower (more conservative)
      merged.stories = Math.min(primary.stories, secondary.stories);
    }

    // Merge materials detected
    const allMaterials = new Set([...primary.materials_detected, ...secondary.materials_detected]);
    merged.materials_detected = Array.from(allMaterials);

    // Merge notes
    if (secondary.notes && secondary.notes !== primary.notes) {
      merged.notes = `${primary.notes} | Additional: ${secondary.notes}`;
    }
  }

  // Cross-check with OpenCV if available
  if (opencv) {
    // Check sqft estimate
    if (opencv.dimensions.estimated_sqft) {
      const cvSqft = opencv.dimensions.estimated_sqft;
      const llmSqft = merged.estimated_sqft;
      const sqftDiff = Math.abs(cvSqft - llmSqft) / Math.max(cvSqft, llmSqft);

      if (sqftDiff > 0.3) {
        conflicts.push(`CV sqft (${cvSqft}) differs significantly from LLM estimate (${llmSqft})`);
        // If CV has high confidence and scale was detected, weight it more
        if (opencv.confidence > 0.7 && opencv.dimensions.scale_detected) {
          merged.estimated_sqft = Math.round((cvSqft * 0.6 + llmSqft * 0.4));
        }
      }
    }

    // Check room count could indicate stories
    if (opencv.room_count > 10 && merged.stories === 1) {
      conflicts.push(`High room count (${opencv.room_count}) but only 1 story estimated`);
    }

    // Adjust confidence based on CV validation
    if (opencv.confidence > 0.7) {
      merged.confidence = Math.min(merged.confidence + 0.1, 1.0);
    }
  }

  // Validate sub_type exists
  if (!ALL_SUBTYPES.includes(merged.sub_type)) {
    conflicts.push(`Unknown sub_type: ${merged.sub_type}, defaulting to single_family_standard`);
    merged.sub_type = 'single_family_standard';
  }

  // Calculate final confidence
  let finalConfidence = merged.confidence;

  // Reduce confidence based on conflicts
  finalConfidence -= conflicts.length * 0.05;

  // Boost if both LLMs agree
  if (secondary && conflicts.length === 0) {
    finalConfidence = Math.min(finalConfidence + 0.15, 1.0);
  }

  // Ensure confidence is in valid range
  finalConfidence = Math.max(0.1, Math.min(1.0, finalConfidence));

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

function getDefaultAnalysis(): LLMAnalysis {
  return {
    building_type: 'residential',
    sub_type: 'single_family_standard',
    quality: 'mid',
    estimated_sqft: 2000,
    stories: 1,
    materials_detected: [],
    construction_type: 'wood_frame',
    confidence: 0.1,
    notes: 'Default values used due to analysis failure',
  };
}
