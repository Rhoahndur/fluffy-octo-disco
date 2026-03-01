"""
Gemini Vision API Client

Direct port of web/src/lib/llm/gemini.ts
Calls Google's Gemini API for construction image analysis.
"""

import os
import re
import json
from typing import Optional

import google.generativeai as genai

from llm_prompts import ANALYSIS_SYSTEM_PROMPT, build_analysis_user_prompt


def analyze_with_gemini(
    images: list[str],
    description: str,
    context: Optional[dict] = None,
) -> dict:
    """
    Analyze construction images/description using Gemini.
    Direct port of analyzeWithGemini from gemini.ts.

    Args:
        images: List of base64-encoded image strings (with or without data URI prefix)
        description: Project description text
        context: Optional analysis context with cv_analysis and/or pdf_extraction

    Returns:
        dict with either:
          {"success": True, "data": <LLMAnalysisResponse>, "provider": "gemini"}
          {"success": False, "error": {"provider": "gemini", "error": <message>}}
    """
    try:
        api_key = os.environ.get("GOOGLE_AI_API_KEY")
        if not api_key:
            return {
                "success": False,
                "error": {"provider": "gemini", "error": "GOOGLE_AI_API_KEY not configured"},
            }

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        # Build parts array
        parts = []

        # Add system prompt + user prompt as first text part (matches TS implementation)
        user_prompt = build_analysis_user_prompt(description, len(images) > 0, context)
        parts.append(ANALYSIS_SYSTEM_PROMPT + "\n\n" + user_prompt)

        # Add images
        for image_base64 in images:
            mime_type = "image/png"
            data = image_base64

            if image_base64.startswith("data:"):
                match = re.match(r"^data:([^;]+);base64,(.+)$", image_base64)
                if match:
                    mime_type = match.group(1)
                    data = match.group(2)

            import base64
            image_bytes = base64.b64decode(data)
            parts.append({
                "mime_type": mime_type,
                "data": image_bytes,
            })

        result = model.generate_content(parts)
        text = result.text

        # Parse JSON from response
        json_match = re.search(r"\{[\s\S]*\}", text)
        if not json_match:
            return {
                "success": False,
                "error": {"provider": "gemini", "error": "Could not extract JSON from Gemini response"},
            }

        analysis = json.loads(json_match.group(0))

        return {
            "success": True,
            "data": analysis,
            "provider": "gemini",
        }

    except Exception as e:
        error_message = str(e)
        return {
            "success": False,
            "error": {
                "provider": "gemini",
                "error": error_message,
            },
        }
