// Modal.com OpenCV worker client

import type { CVAnalysis } from '@/types';

const MODAL_ENDPOINT = process.env.MODAL_ENDPOINT_URL;

interface ModalCVResponse {
  dimensions: {
    estimated_sqft?: number;
    rooms?: Array<{ width: number; height: number }>;
    scale_detected: boolean;
    scale_factor?: number;
  };
  room_count: number;
  drawing_type: 'floor_plan' | 'elevation' | 'site_plan' | 'photo' | 'unknown';
  confidence: number;
  error?: string;
}

export async function analyzeWithOpenCV(
  imageBase64: string
): Promise<CVAnalysis | null> {
  // If Modal endpoint not configured, return null (graceful degradation)
  if (!MODAL_ENDPOINT) {
    console.log('Modal endpoint not configured, skipping OpenCV analysis');
    return null;
  }

  try {
    // Remove data URL prefix if present
    let data = imageBase64;
    if (imageBase64.startsWith('data:')) {
      const match = imageBase64.match(/^data:[^;]+;base64,(.+)$/);
      if (match) {
        data = match[1];
      }
    }

    const response = await fetch(MODAL_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ image_base64: data }),
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
      dimensions: {
        estimated_sqft: result.dimensions.estimated_sqft,
        rooms: result.dimensions.rooms,
        scale_detected: result.dimensions.scale_detected,
      },
      room_count: result.room_count,
      drawing_type: result.drawing_type,
      confidence: result.confidence,
    };
  } catch (error) {
    console.error('Failed to call Modal CV worker:', error);
    return null;
  }
}

// Fallback local analysis using basic heuristics (no OpenCV)
export function analyzeImageBasic(
  imageWidth: number,
  imageHeight: number,
  fileSize: number
): Partial<CVAnalysis> {
  // Very basic heuristics based on image properties
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
  // Photos can vary widely but often have standard camera ratios
  else if (aspectRatio >= 1.3 && aspectRatio <= 1.8) {
    drawingType = 'photo';
  }

  return {
    dimensions: {
      scale_detected: false,
    },
    room_count: 0,
    drawing_type: drawingType,
    confidence: 0.2, // Low confidence for basic analysis
  };
}
