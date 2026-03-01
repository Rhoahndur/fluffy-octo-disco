"""Debug: run a single agent call on a small chunk to see what happens."""
import os
import json
os.environ["GOOGLE_API_KEY"] = "AIzaSyDHhZf5OiHZIL9Jr2IIWidHjF_Gpfwef4s"

import google.generativeai as genai
import pdf_pipeline
from pathlib import Path

# Init model
model = pdf_pipeline.init_gemini()

# Extract text (just first 50 pages worth)
project_dir = Path("rich_floor_plans/PRJ-001")
text, pages, files = pdf_pipeline.extract_text_from_pdfs(project_dir)

# Take only first 100k chars for a quick test
short_text = text[:100000]
print(f"Using {len(short_text):,} chars out of {len(text):,}")

# Test field extraction agent directly
print("\n--- Testing Field Extraction Agent ---")
prompt = pdf_pipeline.build_field_extraction_prompt(short_text)
print(f"Prompt length: {len(prompt):,} chars")

try:
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.1,
            max_output_tokens=8192,
            response_mime_type="application/json",
        ),
    )
    print(f"Response received!")
    print(f"Response text length: {len(response.text)}")
    parsed = json.loads(response.text)
    print(f"Parsed fields: {list(parsed.keys())}")
    for k, v in parsed.items():
        if v is not None and v != "" and v != []:
            print(f"  {k}: {v}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# Test insights agent directly
print("\n--- Testing Qualitative Insights Agent ---")
prompt2 = pdf_pipeline.build_insights_prompt(short_text)
print(f"Prompt length: {len(prompt2):,} chars")

try:
    response2 = model.generate_content(
        prompt2,
        generation_config=genai.types.GenerationConfig(
            temperature=0.1,
            max_output_tokens=8192,
            response_mime_type="application/json",
        ),
    )
    print(f"Response received!")
    print(f"Response text length: {len(response2.text)}")
    parsed2 = json.loads(response2.text)
    print(f"Insight categories: {list(parsed2.keys())}")
    for k, v in parsed2.items():
        if v is not None:
            preview = str(v)[:100]
            print(f"  {k}: {preview}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
