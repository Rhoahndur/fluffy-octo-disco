"""
Claude Vision API Client

Direct port of web/src/lib/llm/claude.ts
Calls Anthropic's Claude API for construction image analysis.
"""

import os
import re
import json
from typing import Optional

from openai import OpenAI

from llm_prompts import ANALYSIS_SYSTEM_PROMPT, build_analysis_user_prompt


def analyze_with_claude(
    images: list[str],
    description: str,
    context: Optional[dict] = None,
) -> dict:
    """
    Analyze construction images/description using Claude via OpenRouter.
    """
    try:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            return {
                "success": False,
                "error": {"provider": "claude", "error": "OPENROUTER_API_KEY not configured"},
            }

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

        content = []

        # Add images
        for image_base64 in images:
            # Ensure proper URL format for OpenAI schema
            data_url = image_base64
            if not data_url.startswith("data:"):
                 data_url = f"data:image/jpeg;base64,{image_base64}"

            content.append({
                "type": "image_url",
                "image_url": {
                    "url": data_url
                },
            })

        # Add text prompt
        content.append({
            "type": "text",
            "text": build_analysis_user_prompt(description, len(images) > 0, context),
        })

        # OpenRouter supports specifying system message as a role
        messages = [
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]

        response = client.chat.completions.create(
            model="anthropic/claude-3.5-sonnet",
            messages=messages,
            max_tokens=1024,
        )

        text_content = response.choices[0].message.content

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
