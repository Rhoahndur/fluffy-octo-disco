// LLM analysis types and shared interfaces

import type { Quality, BuildingCategory } from '@/types';

export interface LLMAnalysisResponse {
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

export interface LLMError {
  provider: 'claude' | 'gemini';
  error: string;
  code?: string;
}

export type LLMResult =
  | { success: true; data: LLMAnalysisResponse; provider: 'claude' | 'gemini' }
  | { success: false; error: LLMError };
