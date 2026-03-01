"""
Claude Vision API Client

Direct port of web/src/lib/llm/claude.ts
Calls Anthropic's Claude API for construction image analysis.
"""

import os
import re
import json
from typing import Optional

import anthropic

from llm_prompts import ANALYSIS_SYSTEM_PROMPT, build_analysis_user_prompt


def analyze_with_claude(
    images: list[str],
    description: str,
    context: Optional[dict] = None,
) -> dict:
    """
    Analyze construction images/description using Claude.
    Direct port of analyzeWithClaude from claude.ts.

    Args:
        images: List of base64-encoded image strings (with or without data URI prefix)
        description: Project description text
        context: Optional analysis context with cv_analysis and/or pdf_extraction

    Returns:
        dict with either:
          {"success": True, "data": <LLMAnalysisResponse>, "provider": "claude"}
          {"success": False, "error": {"provider": "claude", "error": <message>}}
    """
    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return {
                "success": False,
                "error": {"provider": "claude", "error": "ANTHROPIC_API_KEY not configured"},
            }

        client = anthropic.Anthropic(api_key=api_key)

        # Build content array with images and text
        content = []

        # Add images
        for image_base64 in images:
            media_type = "image/png"
            data = image_base64

            if image_base64.startswith("data:"):
                match = re.match(r"^data:([^;]+);base64,(.+)$", image_base64)
                if match:
                    detected_type = match.group(1)
                    if detected_type in ("image/jpeg", "image/png", "image/gif", "image/webp"):
                        media_type = detected_type
                    data = match.group(2)

            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": data,
                },
            })

        # Add text prompt with context
        content.append({
            "type": "text",
            "text": build_analysis_user_prompt(description, len(images) > 0, context),
        })

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=ANALYSIS_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": content,
                },
            ],
        )

        # Extract text response
        text_content = None
        for block in response.content:
            if block.type == "text":
                text_content = block.text
                break

        if not text_content:
            return {
                "success": False,
                "error": {"provider": "claude", "error": "No text response from Claude"},
            }

        # Parse JSON from response
        json_match = re.search(r"\{[\s\S]*\}", text_content)
        if not json_match:
            return {
                "success": False,
                "error": {"provider": "claude", "error": "Could not extract JSON from Claude response"},
            }

        analysis = json.loads(json_match.group(0))

        return {
            "success": True,
            "data": analysis,
            "provider": "claude",
        }

    except Exception as e:
        error_message = str(e)
        return {
            "success": False,
            "error": {
                "provider": "claude",
                "error": error_message,
            },
        }
