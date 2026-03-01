// PDF extraction client
// Parses construction specification PDFs for cost estimation context
//
// This module defines the interface for PDF extraction. The actual extraction
// can be performed by:
// 1. A Modal.com worker (similar to OpenCV)
// 2. An external PDF parsing API
// 3. Client-side PDF.js + LLM extraction
//
// The extracted data is fed to LLMs alongside OpenCV analysis for
// comprehensive cost estimation.

import type { PDFExtractionForLLM } from '@/lib/llm/prompts';

const PDF_ENDPOINT = process.env.PDF_ENDPOINT_URL;

// Door schedule entry from PDF
export interface DoorScheduleEntry {
  mark: string;           // e.g., "D1", "D2"
  size: string;           // e.g., "3'-0\" x 7'-0\""
  type: string;           // e.g., "Solid Core", "Hollow Metal"
  material: string;       // e.g., "Wood", "Steel"
  fire_rating?: string;   // e.g., "20 min", "90 min"
  hardware_set?: string;  // e.g., "HS-1"
}

// Window schedule entry from PDF
export interface WindowScheduleEntry {
  mark: string;           // e.g., "W1", "W2"
  size: string;           // e.g., "4'-0\" x 5'-0\""
  type: string;           // e.g., "Double Hung", "Fixed"
  glazing: string;        // e.g., "Double Pane", "Low-E"
  frame: string;          // e.g., "Aluminum", "Vinyl"
}

// Finish schedule entry from PDF
export interface FinishScheduleEntry {
  room: string;           // e.g., "Living Room", "101"
  floor: string;          // e.g., "Hardwood", "Carpet"
  base: string;           // e.g., "Wood", "Rubber"
  walls: string;          // e.g., "Paint", "Wallpaper"
  ceiling: string;        // e.g., "Drywall", "ACT"
}

// Full PDF extraction result
export interface PDFExtractionResult {
  success: boolean;
  data?: PDFExtractionForLLM;
  error?: string;
}

// Project information extracted from cover sheet
export interface ProjectInfo {
  name?: string;
  address?: string;
  city?: string;
  state?: string;
  zip?: string;
  architect?: string;
  engineer?: string;
  owner?: string;
  project_number?: string;
  date?: string;
  total_area?: number;
  building_type?: string;
}

// Specification section
export interface SpecificationSection {
  division: string;       // e.g., "03", "06", "09"
  section: string;        // e.g., "03 30 00"
  title: string;          // e.g., "Cast-in-Place Concrete"
  content: string;        // Full text content
  products?: string[];    // Product names/manufacturers
  requirements?: string[];// Key requirements
}

/**
 * Extract data from a construction specification PDF
 *
 * @param pdfBase64 - Base64 encoded PDF file
 * @returns Extracted project information, schedules, and specifications
 */
export async function extractFromPDF(
  pdfBase64: string
): Promise<PDFExtractionResult> {
  // If PDF endpoint not configured, return null (graceful degradation)
  if (!PDF_ENDPOINT) {
    console.log('PDF endpoint not configured, skipping PDF extraction');
    return {
      success: false,
      error: 'PDF_ENDPOINT_URL not configured',
    };
  }

  try {
    // Strip data URI prefix if present
    let data = pdfBase64;
    if (pdfBase64.startsWith('data:')) {
      data = pdfBase64.split(',', 2)[1];
    }

    const response = await fetch(PDF_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ pdf_base64: data }),
    });

    if (!response.ok) {
      console.error('PDF extraction error:', response.status, response.statusText);
      return {
        success: false,
        error: `PDF extraction failed: ${response.status}`,
      };
    }

    const result = await response.json();

    if (result.error) {
      return {
        success: false,
        error: result.error,
      };
    }

    return {
      success: true,
      data: formatForLLM(result),
    };
  } catch (error) {
    console.error('Failed to extract PDF:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * Format raw PDF extraction into LLM-friendly structure
 */
function formatForLLM(rawResult: Record<string, unknown>): PDFExtractionForLLM {
  return {
    source: 'pdf_extraction',
    document_type: rawResult.document_type as string | undefined,
    extracted_text: rawResult.text_preview as string | undefined,
    specifications: rawResult.specifications as Record<string, unknown> | undefined,
    schedules: {
      door_schedule: rawResult.door_schedule as Array<Record<string, unknown>> | undefined,
      window_schedule: rawResult.window_schedule as Array<Record<string, unknown>> | undefined,
      finish_schedule: rawResult.finish_schedule as Array<Record<string, unknown>> | undefined,
    },
    project_info: {
      name: (rawResult.project_info as Record<string, unknown>)?.name as string | undefined,
      location: (rawResult.project_info as Record<string, unknown>)?.location as string | undefined,
      architect: (rawResult.project_info as Record<string, unknown>)?.architect as string | undefined,
      total_area: (rawResult.project_info as Record<string, unknown>)?.total_area as number | undefined,
    },
  };
}

/**
 * Parse a PDF locally using basic text extraction
 * Fallback when external endpoint is not available
 *
 * Note: This requires pdf-parse or similar library to be installed
 * Currently returns placeholder - implement with actual PDF library
 */
export async function parseLocalPDF(
  _pdfBuffer: ArrayBuffer
): Promise<PDFExtractionResult> {
  // TODO: Implement with pdf-parse or pdfjs-dist
  // This is a placeholder for local PDF parsing

  console.log('Local PDF parsing not yet implemented');
  return {
    success: false,
    error: 'Local PDF parsing not implemented - configure PDF_ENDPOINT_URL',
  };
}

/**
 * Merge multiple PDF extractions into a single context
 * Useful when project has multiple specification documents
 */
export function mergePDFExtractions(
  extractions: PDFExtractionForLLM[]
): PDFExtractionForLLM {
  const merged: PDFExtractionForLLM = {
    source: 'pdf_extraction_merged',
    schedules: {
      door_schedule: [],
      window_schedule: [],
      finish_schedule: [],
    },
  };

  for (const extraction of extractions) {
    // Merge project info (prefer first non-empty value)
    if (extraction.project_info) {
      merged.project_info = merged.project_info || {};
      for (const [key, value] of Object.entries(extraction.project_info)) {
        if (value && !(merged.project_info as Record<string, unknown>)[key]) {
          (merged.project_info as Record<string, unknown>)[key] = value;
        }
      }
    }

    // Merge schedules
    if (extraction.schedules) {
      if (extraction.schedules.door_schedule) {
        merged.schedules!.door_schedule!.push(...extraction.schedules.door_schedule);
      }
      if (extraction.schedules.window_schedule) {
        merged.schedules!.window_schedule!.push(...extraction.schedules.window_schedule);
      }
      if (extraction.schedules.finish_schedule) {
        merged.schedules!.finish_schedule!.push(...extraction.schedules.finish_schedule);
      }
    }

    // Merge specifications
    if (extraction.specifications) {
      merged.specifications = {
        ...merged.specifications,
        ...extraction.specifications,
      };
    }
  }

  return merged;
}
