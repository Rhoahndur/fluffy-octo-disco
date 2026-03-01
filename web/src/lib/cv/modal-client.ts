// Modal.com OpenCV worker client
// Calls the enhanced CV worker for deterministic takeoff data

import type { CVAnalysis } from '@/types';

const MODAL_ENDPOINT = process.env.MODAL_ENDPOINT_URL;

// Takeoff item with value, unit, confidence, and CSI mapping
interface TakeoffItem {
  value: number | null;
  unit: string;
  confidence: number;
  csi_divisions?: string[];
  use?: string;
  assumptions?: string;
}

// Full response from Modal CV worker (optimized for LLM consumption)
export interface ModalCVResponse {
  source: 'opencv_analysis';
  drawing_type: 'floor_plan' | 'elevation' | 'site_plan' | 'photo' | 'unknown';
  analysis_confidence: number;

  takeoff: {
    gross_floor_area?: TakeoffItem | null;
    concrete_slab_volume?: TakeoffItem | null;
    foundation_volume?: TakeoffItem | null;
    excavation_volume?: TakeoffItem | null;
    interior_wall_length?: TakeoffItem | null;
    door_count?: TakeoffItem | null;
    window_count?: TakeoffItem | null;
    column_count?: TakeoffItem | null;
    room_count?: TakeoffItem | null;
  };

  materials_detected: {
    [key: string]: {
      detected: boolean;
      source: string;
      use: string;
    };
  };

  text_extractions: {
    dimension_strings: string[];
    grade_specifications: string[];
    area_callouts_sf: number[];
  };

  scale_info: {
    detected: boolean;
    method?: string;
    confidence?: number;
    note?: string;
  };

  aggregation_notes: {
    priority: string;
    conflicts: string;
    missing_data: (string | null)[];
  };

  error?: string;
}

// Result includes both raw response (for LLM) and simplified analysis (for frontend)
export interface OpenCVAnalysisResult {
  // Full response with CSI mappings and aggregation hints (send to LLM)
  rawForLLM: ModalCVResponse;
  // Simplified analysis for frontend display
  analysis: CVAnalysis;
}

export async function analyzeWithOpenCV(
  imageBase64: string
): Promise<OpenCVAnalysisResult | null> {
  // If Modal endpoint not configured, return null (graceful degradation)
  if (!MODAL_ENDPOINT) {
    console.log('Modal endpoint not configured, skipping OpenCV analysis');
    return null;
  }

  try {
    // Keep data URL prefix - the CV worker handles both formats now
    const response = await fetch(MODAL_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ image_base64: imageBase64 }),
    });

    if (!response.ok) {
      console.error('Modal CV worker error:', response.status, response.statusText);
      return null;
    }

    const result: ModalCVResponse = await response.json();

    if (result.error) {
      console.error('Modal CV worker returned error:', result.error);
      return null;
    }

    return {
      rawForLLM: result,  // Full response for LLM agent
      analysis: mapModalResponseToCVAnalysis(result),  // Simplified for frontend
    };
  } catch (error) {
    console.error('Failed to call Modal CV worker:', error);
    return null;
  }
}

function mapModalResponseToCVAnalysis(result: ModalCVResponse): CVAnalysis {
  const takeoff = result.takeoff || {};

  return {
    drawing_type: result.drawing_type,

    counts: {
      doors: takeoff.door_count?.value || 0,
      windows: takeoff.window_count?.value || 0,
      columns: takeoff.column_count?.value || 0,
      fixtures: 0,
      rooms: takeoff.room_count?.value || 0,
    },

    measurements: {
      total_area: takeoff.gross_floor_area ? {
        value: takeoff.gross_floor_area.value!,
        unit: takeoff.gross_floor_area.unit,
      } : null,
      total_wall_length: takeoff.interior_wall_length ? {
        value: takeoff.interior_wall_length.value!,
        unit: takeoff.interior_wall_length.unit,
      } : null,
      concrete_slab: takeoff.concrete_slab_volume ? {
        value: takeoff.concrete_slab_volume.value!,
        unit: takeoff.concrete_slab_volume.unit,
      } : null,
      foundation: takeoff.foundation_volume ? {
        value: takeoff.foundation_volume.value!,
        unit: takeoff.foundation_volume.unit,
      } : null,
      excavation: takeoff.excavation_volume ? {
        value: takeoff.excavation_volume.value!,
        unit: takeoff.excavation_volume.unit,
      } : null,
    },

    materials: Object.fromEntries(
      Object.entries(result.materials_detected || {}).map(([k, v]) => [k, v.detected])
    ),

    scale: {
      detected: result.scale_info?.detected || false,
      source: result.scale_info?.method,
      confidence: result.scale_info?.confidence,
    },

    text_extraction: {
      dimensions_found: result.text_extractions?.dimension_strings || [],
      grades_specs: result.text_extractions?.grade_specifications || [],
      sqft_from_text: result.text_extractions?.area_callouts_sf || [],
    },

    room_count: takeoff.room_count?.value || 0,
    confidence: result.analysis_confidence,
  };
}

// Fallback local analysis using basic heuristics (no OpenCV)
// Used when Modal is not configured
export function analyzeImageBasic(
  imageWidth: number,
  imageHeight: number,
): CVAnalysis {
  const aspectRatio = imageWidth / imageHeight;

  let drawingType: CVAnalysis['drawing_type'] = 'unknown';

  // Floor plans typically have aspect ratios between 0.7 and 1.4
  if (aspectRatio >= 0.7 && aspectRatio <= 1.4) {
    drawingType = 'floor_plan';
  }
  // Elevations are often wider than tall
  else if (aspectRatio > 1.4 && aspectRatio <= 3) {
    drawingType = 'elevation';
  }
  // Very wide images might be site plans
  else if (aspectRatio > 3) {
    drawingType = 'site_plan';
  }

  return {
    drawing_type: drawingType,
    counts: {
      doors: 0,
      windows: 0,
      columns: 0,
      fixtures: 0,
      rooms: 0,
    },
    measurements: {
      total_area: null,
      total_wall_length: null,
      concrete_slab: null,
      foundation: null,
      excavation: null,
    },
    materials: {},
    scale: {
      detected: false,
    },
    text_extraction: {
      dimensions_found: [],
      grades_specs: [],
      sqft_from_text: [],
    },
    room_count: 0,
    confidence: 0.1, // Very low confidence for basic analysis
  };
}

// Helper to get just the CVAnalysis from the result
export function getAnalysisOnly(result: OpenCVAnalysisResult | null): CVAnalysis | null {
  return result?.analysis || null;
}

// Helper to get the raw LLM-ready response
export function getRawForLLM(result: OpenCVAnalysisResult | null): ModalCVResponse | null {
  return result?.rawForLLM || null;
}
