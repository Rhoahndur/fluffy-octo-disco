// Claude Vision API client

import Anthropic from '@anthropic-ai/sdk';
import { ANALYSIS_SYSTEM_PROMPT, ANALYSIS_USER_PROMPT, type AnalysisContext } from './prompts';
import type { LLMAnalysisResponse, LLMResult } from './types';

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

export async function analyzeWithClaude(
  images: string[], // Base64 encoded images
  description: string,
  context?: AnalysisContext
): Promise<LLMResult> {
  try {
    // Build content array with images and text
    const content: Anthropic.MessageCreateParams['messages'][0]['content'] = [];

    // Add images
    for (const imageBase64 of images) {
      // Extract media type and data
      let mediaType: 'image/jpeg' | 'image/png' | 'image/gif' | 'image/webp' = 'image/png';
      let data = imageBase64;

      if (imageBase64.startsWith('data:')) {
        const match = imageBase64.match(/^data:([^;]+);base64,(.+)$/);
        if (match) {
          const [, type, base64Data] = match;
          if (type === 'image/jpeg' || type === 'image/png' || type === 'image/gif' || type === 'image/webp') {
            mediaType = type;
          }
          data = base64Data;
        }
      }

      content.push({
        type: 'image',
        source: {
          type: 'base64',
          media_type: mediaType,
          data,
        },
      });
    }

    // Add text prompt with context
    content.push({
      type: 'text',
      text: ANALYSIS_USER_PROMPT(description, images.length > 0, context),
    });

    const response = await anthropic.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 1024,
      system: ANALYSIS_SYSTEM_PROMPT,
      messages: [
        {
          role: 'user',
          content,
        },
      ],
    });

    // Extract text response
    const textContent = response.content.find(c => c.type === 'text');
    if (!textContent || textContent.type !== 'text') {
      return {
        success: false,
        error: {
          provider: 'claude',
          error: 'No text response from Claude',
        },
      };
    }

    // Parse JSON from response
    const jsonMatch = textContent.text.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      return {
        success: false,
        error: {
          provider: 'claude',
          error: 'Could not extract JSON from Claude response',
        },
      };
    }

    const analysis: LLMAnalysisResponse = JSON.parse(jsonMatch[0]);

    return {
      success: true,
      data: analysis,
      provider: 'claude',
    };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    return {
      success: false,
      error: {
        provider: 'claude',
        error: errorMessage,
        code: (error as { status?: number })?.status?.toString(),
      },
    };
  }
}
