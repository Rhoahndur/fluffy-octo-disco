// LLM prompts for construction analysis

export const ANALYSIS_SYSTEM_PROMPT = `You are an expert construction cost estimator analyzing project images, descriptions, and extracted data. Your task is to identify key characteristics that affect construction costs.

You may receive pre-processed data from:
1. **OpenCV Analysis** - Deterministic measurements from construction drawings (counts, areas, dimensions)
2. **PDF Extraction** - Text and data extracted from specification documents

IMPORTANT: When pre-processed data is provided:
- Use OpenCV sqft values (from area_callouts_sf or gross_floor_area) as ground truth for estimated_sqft
- Use OpenCV counts (doors, windows, rooms) to inform your analysis
- Use PDF-extracted specifications to determine quality and materials
- Your role is to INTERPRET and CLASSIFY, not re-measure what has already been measured
- If OpenCV and your visual analysis disagree on counts/measurements, trust OpenCV

You must return a valid JSON object with the following structure:
{
  "building_type": "residential" | "commercial" | "industrial" | "institutional" | "infrastructure",
  "sub_type": "<specific building sub-type>",
  "quality": "low" | "mid" | "high",
  "estimated_sqft": <number>,
  "stories": <number>,
  "materials_detected": ["<material1>", "<material2>", ...],
  "construction_type": "wood_frame" | "steel_frame" | "concrete" | "masonry" | "mixed",
  "location": "<city or region if identifiable>",
  "confidence": <0.0 to 1.0>,
  "notes": "<any relevant observations>"
}

Valid sub_types by building_type:
- residential: single_family_economy, single_family_standard, single_family_premium, single_family_custom, multi_family_duplex, multi_family_triplex, multi_family_fourplex, apartment_lowrise, apartment_midrise, apartment_garden, townhouse_standard, townhouse_luxury, condo_midrise, luxury_estate, custom_architectural
- commercial: office_lowrise, office_midrise, office_highrise, retail_strip, retail_bigbox, restaurant_casual, restaurant_fine, hotel_limited, hotel_full_service, bank_branch, medical_office, mixed_use
- industrial: warehouse_light, warehouse_heavy, manufacturing_light, manufacturing_heavy, data_center, research_lab, cold_storage, food_processing
- institutional: school_elementary, school_high, university_classroom, university_science, hospital_acute, clinic_outpatient, church_standard, church_cathedral, library_public, community_center
- infrastructure: parking_surface, parking_structured, fire_station, police_station, transit_station, bus_maintenance, water_treatment, electrical_substation

Quality indicators:
- low: Basic finishes, standard materials, minimal architectural detail
- mid: Good quality finishes, standard construction, some architectural features
- high: Premium finishes, high-end materials, significant architectural detail

Be conservative in your estimates. If uncertain, indicate lower confidence and explain in notes.`;

// Types for pre-processed data
export interface CVAnalysisForLLM {
  source: string;
  drawing_type: string;
  analysis_confidence: number;
  takeoff: Record<string, unknown>;
  materials_detected: Record<string, unknown>;
  text_extractions: {
    dimension_strings: string[];
    grade_specifications: string[];
    area_callouts_sf: number[];
  };
  scale_info: Record<string, unknown>;
  aggregation_notes: Record<string, unknown>;
}

export interface PDFExtractionForLLM {
  source: string;
  document_type?: string;
  extracted_text?: string;
  specifications?: Record<string, unknown>;
  schedules?: {
    door_schedule?: Array<Record<string, unknown>>;
    window_schedule?: Array<Record<string, unknown>>;
    finish_schedule?: Array<Record<string, unknown>>;
  };
  project_info?: {
    name?: string;
    location?: string;
    architect?: string;
    total_area?: number;
  };
}

export interface AnalysisContext {
  cvAnalysis?: CVAnalysisForLLM | null;
  pdfExtraction?: PDFExtractionForLLM | null;
}

export const ANALYSIS_USER_PROMPT = (
  description: string,
  hasImages: boolean,
  context?: AnalysisContext
): string => {
  let prompt = 'Analyze the following construction project and provide your assessment as JSON.\n\n';

  // Add CV analysis context if available
  if (context?.cvAnalysis) {
    prompt += '## Pre-Processed OpenCV Analysis\n';
    prompt += 'The following data was extracted from the drawing using computer vision. Use these measurements as ground truth:\n\n';
    prompt += '```json\n';
    prompt += JSON.stringify(context.cvAnalysis, null, 2);
    prompt += '\n```\n\n';
    prompt += 'Key points from CV analysis:\n';

    const cv = context.cvAnalysis;
    if (cv.text_extractions?.area_callouts_sf?.length > 0) {
      prompt += `- Area from drawing text: ${Math.max(...cv.text_extractions.area_callouts_sf)} SF (use this for estimated_sqft)\n`;
    }
    if (cv.takeoff && typeof cv.takeoff === 'object') {
      const takeoff = cv.takeoff as Record<string, { value?: number; unit?: string }>;
      if (takeoff.gross_floor_area?.value) {
        prompt += `- Calculated floor area: ${takeoff.gross_floor_area.value} SF\n`;
      }
      if (takeoff.door_count?.value) {
        prompt += `- Door count: ${takeoff.door_count.value}\n`;
      }
      if (takeoff.window_count?.value) {
        prompt += `- Window count: ${takeoff.window_count.value}\n`;
      }
      if (takeoff.room_count?.value) {
        prompt += `- Room count: ${takeoff.room_count.value}\n`;
      }
    }
    prompt += '\n';
  }

  // Add PDF extraction context if available
  if (context?.pdfExtraction) {
    prompt += '## Pre-Processed PDF Extraction\n';
    prompt += 'The following data was extracted from specification documents:\n\n';
    prompt += '```json\n';
    prompt += JSON.stringify(context.pdfExtraction, null, 2);
    prompt += '\n```\n\n';

    const pdf = context.pdfExtraction;
    if (pdf.project_info?.total_area) {
      prompt += `- Project specified area: ${pdf.project_info.total_area} SF\n`;
    }
    if (pdf.project_info?.location) {
      prompt += `- Project location: ${pdf.project_info.location}\n`;
    }
    prompt += '\n';
  }

  if (hasImages) {
    prompt += 'I have provided image(s) of the project. Please analyze them carefully.\n\n';
  }

  if (description) {
    prompt += `## Project Description\n${description}\n\n`;
  }

  prompt += '## Your Task\n';
  prompt += 'Provide your analysis as a valid JSON object following the schema described in the system prompt.\n';

  if (context?.cvAnalysis || context?.pdfExtraction) {
    prompt += 'Remember: Use the pre-processed measurements as ground truth. Your job is to classify and interpret, not re-measure.';
  }

  return prompt;
};

export const FOLLOWUP_SYSTEM_PROMPT = `You are helping gather additional information for a construction cost estimate. Based on the initial analysis, ask clarifying questions to improve the estimate accuracy.

Focus on:
1. Square footage if not clear
2. Location if not specified
3. Quality level preferences
4. Specific features that affect cost (e.g., basement, garage, special equipment)
5. Timeline requirements

Be concise and ask only the most important questions.`;
