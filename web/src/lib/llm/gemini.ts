// Gemini Vision API client

import { GoogleGenerativeAI } from '@google/generative-ai';
import { ANALYSIS_SYSTEM_PROMPT, ANALYSIS_USER_PROMPT } from './prompts';
import type { LLMAnalysisResponse, LLMResult } from './types';

export async function analyzeWithGemini(
  images: string[], // Base64 encoded images
  description: string
): Promise<LLMResult> {
  try {
    const apiKey = process.env.GOOGLE_AI_API_KEY;
    if (!apiKey) {
      return {
        success: false,
        error: {
          provider: 'gemini',
          error: 'GOOGLE_AI_API_KEY not configured',
        },
      };
    }

    const genAI = new GoogleGenerativeAI(apiKey);
    const model = genAI.getGenerativeModel({ model: 'gemini-1.5-flash' });

    // Build parts array
    const parts: Array<{ text: string } | { inlineData: { mimeType: string; data: string } }> = [];

    // Add system prompt as first part
    parts.push({ text: ANALYSIS_SYSTEM_PROMPT + '\n\n' + ANALYSIS_USER_PROMPT(description, images.length > 0) });

    // Add images
    for (const imageBase64 of images) {
      let mimeType = 'image/png';
      let data = imageBase64;

      if (imageBase64.startsWith('data:')) {
        const match = imageBase64.match(/^data:([^;]+);base64,(.+)$/);
        if (match) {
          const [, type, base64Data] = match;
          mimeType = type;
          data = base64Data;
        }
      }

      parts.push({
        inlineData: {
          mimeType,
          data,
        },
      });
    }

    const result = await model.generateContent(parts);
    const response = result.response;
    const text = response.text();

    // Parse JSON from response
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      return {
        success: false,
        error: {
          provider: 'gemini',
          error: 'Could not extract JSON from Gemini response',
        },
      };
    }

    const analysis: LLMAnalysisResponse = JSON.parse(jsonMatch[0]);

    return {
      success: true,
      data: analysis,
      provider: 'gemini',
    };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    return {
      success: false,
      error: {
        provider: 'gemini',
        error: errorMessage,
      },
    };
  }
}
