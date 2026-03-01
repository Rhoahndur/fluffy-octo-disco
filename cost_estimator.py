import os
import json
import base64
import argparse
from pathlib import Path
from openai import OpenAI

def encode_image(image_path: str) -> str:
    """Encodes an image to base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def get_floor_plan_images(project_id: str, floor_plans_dir: str = "rich_floor_plans") -> list[dict]:
    """Retrieves and encodes all floor plan images for a given project."""
    project_dir = Path(floor_plans_dir) / project_id
    image_messages = []
    
    if not project_dir.exists() or not project_dir.is_dir():
        print(f"Warning: No floor plan directory found for {project_id} at {project_dir}")
        return image_messages
        
    for image_path in project_dir.glob("*.[jp][pn][g]"): # Matches .jpg, .png, .jpeg
        base64_image = encode_image(str(image_path))
        # OpenRouter vision format
        image_messages.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_image}"
            }
        })
        print(f"Loaded floor plan: {image_path.name}")
        
    return image_messages

def extract_cost(project_data: dict, floor_plan_messages: list, api_key: str) -> str:
    """Calls OpenRouter with Gemini 3 Flash to estimate the construction cost."""
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    
    # Format the project data summary as context
    project_summary = json.dumps(project_data.get("qualitative_insights", {}), indent=2)
    structured_fields = json.dumps(project_data.get("structured_fields", {}), indent=2)
    
    prompt = f"""
You are an expert construction cost estimator. Analyze the following project summary, structured fields, and the provided floor plan images (if any) to estimate the total construction cost.

Project Summary:
{project_summary}

Structured Fields:
{structured_fields}

You have agentic vision and are provided with floor plans. You are also equipped with a code execution tool to perform complex calculations if needed.

CRITICAL INSTRUCTION:
Your final output MUST be exactly ONE NUMBER representing the total estimated cost in USD. 
Do not include dollar signs, commas, text, or any explanation.
Example valid output: 15000000
Example invalid output: $15,000,000
Example invalid output: The cost is 15000000.
"""

    messages = [
        {"role": "system", "content": "You are an expert construction cost estimator. You must output ONLY a single number representing the total cost. No symbols or text."},
        {"role": "user", "content": [{"type": "text", "text": prompt}] + floor_plan_messages}
    ]

    print(f"Calling OpenRouter (google/gemini-3-flash-preview) for project {project_data.get('project_id')}...")
    
    # We pass the standard code interpreter plugin tool via OpenRouter's recommended format
    try:
        response = client.chat.completions.create(
            model="google/gemini-3-flash-preview",
            messages=messages,
            temperature=0.1
        )
        
        # OpenRouter / OpenAI standard extraction
        result = response.choices[0].message.content.strip()
        
        # Clean up any potential formatting just in case the model disobeys
        result = ''.join(c for c in result if c.isdigit() or c == '.')
        
        return result
        
    except Exception as e:
        print(f"Error calling LLM: {e}")
        if hasattr(e, 'response'):
            print(e.response.text)
        return None

def main():
    parser = argparse.ArgumentParser(description="Estimate construction costs from JSON and floor plans.")
    parser.add_argument("--input", default="results/test_extraction.json", help="Path to the input JSON file.")
    parser.add_argument("--output", default="results/test_cost_estimations.json", help="Path to save the output.")
    parser.add_argument("--floor_plans", default="rich_floor_plans", help="Directory containing floor plan subdirectories.")
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: Set OPENROUTER_API_KEY environment variable.")
        return
    
    # Load input JSON
    try:
        with open(args.input, 'r') as f:
            projects = json.load(f)
    except Exception as e:
        print(f"Failed to load input file {args.input}: {e}")
        return

    results = []

    for project in projects:
        project_id = project.get("project_id")
        if not project_id:
            print("Skipping project with no ID.")
            continue
            
        print(f"\nProcessing Project: {project_id}")
        
        # 1. Load floor plan images
        floor_plan_messages = get_floor_plan_images(project_id, args.floor_plans)
        
        # 2. Call LLM for extraction
        estimated_cost = extract_cost(project, floor_plan_messages, api_key)
        
        print(f"Estimated Cost: {estimated_cost}")
        
        # 3. Save result
        if estimated_cost:
            project_result = {
                "project_id": project_id,
                "estimated_cost": estimated_cost
            }
            results.append(project_result)

    # Output results
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"\nSaved estimations to {args.output}")

if __name__ == "__main__":
    main()
