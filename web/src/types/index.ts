// Core types for the construction cost estimation system

export type Quality = 'low' | 'mid' | 'high';

export type BuildingCategory = 'residential' | 'commercial' | 'industrial' | 'institutional' | 'infrastructure';

export interface LLMAnalysis {
  building_type: BuildingCategory;
  sub_type: string;
  quality: Quality;
  estimated_sqft: number;
  stories: number;
  materials_detected: string[];
  construction_type: string;
  location?: string;
  confidence: number;
  notes: string;
}

export interface CVAnalysis {
  dimensions: {
    estimated_sqft?: number;
    rooms?: Array<{ width: number; height: number }>;
    scale_detected: boolean;
  };
  room_count: number;
  drawing_type: 'floor_plan' | 'elevation' | 'site_plan' | 'photo' | 'unknown';
  confidence: number;
}

export interface ReconciliationResult {
  merged: LLMAnalysis;
  conflicts: string[];
  confidence: number;
  sources: {
    claude?: LLMAnalysis;
    gemini?: LLMAnalysis;
    opencv?: CVAnalysis;
  };
}

export interface DivisionBreakdown {
  '01_general_requirements': number;
  '02_existing_conditions': number;
  '03_concrete': number;
  '04_masonry': number;
  '05_metals': number;
  '06_wood_plastics_composites': number;
  '07_thermal_moisture': number;
  '08_openings': number;
  '09_finishes': number;
  '10_specialties': number;
  '11_equipment': number;
  '12_furnishings': number;
  '13_special_construction': number;
  '14_conveying_equipment': number;
  '21_fire_suppression': number;
  '22_plumbing': number;
  '23_hvac': number;
  '26_electrical': number;
}

export interface ItemQuantity {
  item: string;
  quantity: number;
  unit: string;
  unit_cost: number;
  total_cost: number;
  division: string;
}

export interface CostEstimate {
  total_cost: number;
  cost_per_sf: number;
  area_sf: number;
  stories: number;
  quality: Quality;
  location: string;
  location_factor: number;
  story_premium: number;
  base_cost_sf: number;
  csi_profile: string;
  division_breakdown: DivisionBreakdown;
  item_quantities?: ItemQuantity[];
}

export interface SimilarProject {
  project_id: string;
  name: string;
  building_type: BuildingCategory | string;
  sub_type: string;
  quality: Quality | string;
  area_sf: number;
  total_cost: number;
  cost_per_sf: number;
  similarity_score: number;
}

export interface EstimateRequest {
  images: string[]; // Base64 encoded images
  description: string;
  location?: string;
}

export interface EstimateResponse {
  id: string;
  status: 'complete' | 'needs_followup' | 'error';
  estimate?: CostEstimate;
  analysis?: ReconciliationResult;
  similar_projects?: SimilarProject[];
  error?: string;
  created_at: string;
}

export interface EstimateRecord {
  id: string;
  session_id?: string;
  created_at: string;
  description: string;
  image_urls: string[];
  claude_response?: LLMAnalysis;
  gemini_response?: LLMAnalysis;
  opencv_response?: CVAnalysis;
  reconciled?: ReconciliationResult;
  building_type?: string;
  sub_type?: string;
  quality?: Quality;
  area_sf?: number;
  stories?: number;
  location?: string;
  location_factor?: number;
  total_cost?: number;
  cost_per_sf?: number;
  division_breakdown?: DivisionBreakdown;
  item_quantities?: ItemQuantity[];
  similar_projects?: SimilarProject[];
  confidence_score?: number;
}

// Eval dataset types (for similar project matching)
export interface EvalProject {
  project_id: string;
  name: string;
  building_type: BuildingCategory | string;
  sub_type: string;
  quality: Quality | string;
  area_sf: number;
  stories?: number;
  location?: string;
  location_factor?: number;
  floor_plan_path?: string;
  specification_text?: string;
  ground_truth: {
    total_cost: number;
    cost_per_sf: number;
    csi_profile?: string;
    division_breakdown?: DivisionBreakdown;
  };
}
