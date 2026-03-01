import { NextRequest, NextResponse } from 'next/server';
import { v4 as uuidv4 } from 'uuid';
import { analyzeWithClaude } from '@/lib/llm/claude';
import { analyzeWithGemini } from '@/lib/llm/gemini';
import { reconcileAnalyses } from '@/lib/llm/reconcile';
import { analyzeWithOpenCV } from '@/lib/cv/modal-client';
import { calculateCost } from '@/lib/cost/rsmeans';
import { findSimilarProjects } from '@/lib/similar/matcher';
import { findLocationFactor } from '@/lib/cost/data/location-factors';
import { saveEstimate, isSupabaseConfigured } from '@/lib/db/supabase';
import type { EstimateRequest, EstimateResponse, LLMAnalysis, CVAnalysis } from '@/types';

export const maxDuration = 60; // Allow up to 60 seconds for LLM calls

export async function POST(request: NextRequest) {
  try {
    const body: EstimateRequest = await request.json();
    const { images = [], description = '', location } = body;

    // Validate input
    if (images.length === 0 && !description.trim()) {
      return NextResponse.json(
        { error: 'Please provide at least one image or a description' },
        { status: 400 }
      );
    }

    // Run analyses in parallel
    const [claudeResult, geminiResult, opencvResult] = await Promise.all([
      // Claude analysis
      analyzeWithClaude(images, description).catch(err => {
        console.error('Claude analysis failed:', err);
        return null;
      }),
      // Gemini analysis
      analyzeWithGemini(images, description).catch(err => {
        console.error('Gemini analysis failed:', err);
        return null;
      }),
      // OpenCV analysis (first image only)
      images.length > 0
        ? analyzeWithOpenCV(images[0]).catch(err => {
            console.error('OpenCV analysis failed:', err);
            return null;
          })
        : Promise.resolve(null),
    ]);

    // Extract successful results
    const claudeAnalysis = claudeResult?.success ? claudeResult.data : undefined;
    const geminiAnalysis = geminiResult?.success ? geminiResult.data : undefined;
    const opencvAnalysis = opencvResult || undefined;

    // Check if we have at least one LLM result
    if (!claudeAnalysis && !geminiAnalysis) {
      // If no LLM results, provide a basic estimate based on description parsing
      const fallbackEstimate = createFallbackEstimate(description, location);
      return NextResponse.json(fallbackEstimate);
    }

    // Reconcile analyses
    const reconciliation = reconcileAnalyses({
      claude: claudeAnalysis,
      gemini: geminiAnalysis,
      opencv: opencvAnalysis,
    });

    const { merged, conflicts, confidence } = reconciliation;

    // Determine location factor
    const locationInfo = findLocationFactor(
      location || merged.location || 'national'
    );

    // Calculate cost estimate
    const costEstimate = calculateCost({
      sub_type: merged.sub_type,
      quality: merged.quality,
      area_sf: merged.estimated_sqft,
      stories: merged.stories,
      location: locationInfo.location,
    });

    // Find similar projects
    const similarProjects = await findSimilarProjects({
      building_type: merged.building_type,
      sub_type: merged.sub_type,
      quality: merged.quality,
      area_sf: merged.estimated_sqft,
    });

    // Generate estimate ID
    const estimateId = uuidv4();

    // Build response
    const response: EstimateResponse = {
      id: estimateId,
      status: 'complete',
      estimate: costEstimate,
      analysis: reconciliation,
      similar_projects: similarProjects,
      created_at: new Date().toISOString(),
    };

    // Save to database if configured
    if (isSupabaseConfigured()) {
      try {
        await saveEstimate({
          session_id: request.headers.get('x-session-id') || undefined,
          description,
          image_urls: [], // Would upload to storage in production
          claude_response: claudeAnalysis as LLMAnalysis | undefined,
          gemini_response: geminiAnalysis as LLMAnalysis | undefined,
          opencv_response: opencvAnalysis as CVAnalysis | undefined,
          reconciled: reconciliation,
          building_type: merged.building_type,
          sub_type: merged.sub_type,
          quality: merged.quality,
          area_sf: merged.estimated_sqft,
          stories: merged.stories,
          location: locationInfo.location,
          location_factor: locationInfo.factor,
          total_cost: costEstimate.total_cost,
          cost_per_sf: costEstimate.cost_per_sf,
          division_breakdown: costEstimate.division_breakdown,
          item_quantities: costEstimate.item_quantities,
          similar_projects: similarProjects,
          confidence_score: confidence,
        });
      } catch (dbError) {
        console.error('Failed to save estimate:', dbError);
        // Continue without saving - don't fail the request
      }
    }

    return NextResponse.json(response);
  } catch (error) {
    console.error('Estimate error:', error);
    return NextResponse.json(
      { error: 'Failed to generate estimate' },
      { status: 500 }
    );
  }
}

// Fallback estimate when LLMs fail
function createFallbackEstimate(
  description: string,
  location?: string
): EstimateResponse {
  // Simple keyword-based parsing
  const desc = description.toLowerCase();

  // Detect building type
  let subType = 'single_family_standard';
  let quality: 'low' | 'mid' | 'high' = 'mid';
  let sqft = 2000;
  let stories = 1;

  // Building type detection
  if (desc.includes('warehouse') || desc.includes('industrial')) {
    subType = 'warehouse_light';
  } else if (desc.includes('office')) {
    subType = 'office_lowrise';
  } else if (desc.includes('retail') || desc.includes('store')) {
    subType = 'retail_strip';
  } else if (desc.includes('restaurant')) {
    subType = 'restaurant_casual';
  } else if (desc.includes('apartment') || desc.includes('multi-family')) {
    subType = 'apartment_lowrise';
  } else if (desc.includes('school')) {
    subType = 'school_elementary';
  } else if (desc.includes('church')) {
    subType = 'church_standard';
  } else if (desc.includes('hospital') || desc.includes('medical')) {
    subType = 'clinic_outpatient';
  }

  // Quality detection
  if (desc.includes('luxury') || desc.includes('premium') || desc.includes('high-end')) {
    quality = 'high';
  } else if (desc.includes('basic') || desc.includes('economy') || desc.includes('budget')) {
    quality = 'low';
  }

  // Square footage extraction
  const sqftMatch = desc.match(/(\d{1,3}(?:,\d{3})*|\d+)\s*(?:sq\s*ft|sqft|square\s*feet|sf)/i);
  if (sqftMatch) {
    sqft = parseInt(sqftMatch[1].replace(/,/g, ''), 10);
  }

  // Stories extraction
  const storyMatch = desc.match(/(\d+)\s*(?:story|stories|floor|floors)/i);
  if (storyMatch) {
    stories = parseInt(storyMatch[1], 10);
  }

  const locationInfo = findLocationFactor(location || 'national');

  const costEstimate = calculateCost({
    sub_type: subType,
    quality,
    area_sf: sqft,
    stories,
    location: locationInfo.location,
  });

  return {
    id: uuidv4(),
    status: 'complete',
    estimate: costEstimate,
    analysis: {
      merged: {
        building_type: 'residential',
        sub_type: subType,
        quality,
        estimated_sqft: sqft,
        stories,
        materials_detected: [],
        construction_type: 'wood_frame',
        confidence: 0.3,
        notes: 'Estimate based on description parsing only (LLM analysis unavailable)',
      },
      conflicts: ['LLM analysis unavailable - using fallback parsing'],
      confidence: 0.3,
      sources: {},
    },
    similar_projects: [],
    created_at: new Date().toISOString(),
  };
}
