"""
PDF Parsing & Summarizing Agentic Pipeline

Two-agent pipeline for construction project cost estimation:
  Agent 1: Extracts structured fields (area, building type, systems, etc.)
  Agent 2: Summarizes qualitative insights (cost drivers, risks, complexity)

Uses OpenRouter API (OpenAI-compatible) for LLM calls.

Usage:
  python -X utf8 pdf_pipeline.py --project-dir rich_floor_plans/PRJ-001
  python -X utf8 pdf_pipeline.py --all
  python -X utf8 pdf_pipeline.py --project-dir rich_floor_plans/PRJ-001 --output results/test.json
"""

MAX_TEXT_CHARS = 500000  # ~125k tokens — fits well within Gemini 2.5 Flash's 1M context

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF not installed. Run: pip install pymupdf")
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    print("ERROR: openai not installed. Run: pip install openai")
    sys.exit(1)


# ─── CONFIGURATION ────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).parent
CONFIG_PATH = ROOT_DIR / "pdf_pipeline_config.yaml"


def load_config() -> Dict:
    """Load pipeline configuration from YAML."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


CONFIG = load_config()


def init_client() -> OpenAI:
    """Initialize OpenRouter client via OpenAI-compatible API."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: Set OPENROUTER_API_KEY environment variable.")
        sys.exit(1)
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


# ─── LLM CALL WITH RETRY ─────────────────────────────────────────────

def call_llm_with_retry(
    client: OpenAI,
    prompt: str,
    max_retries: int = 5,
    initial_wait: float = 5.0,
) -> Optional[str]:
    """
    Call LLM via OpenRouter with exponential backoff on errors.
    Returns the response text, or None if all retries fail.
    """
    model = CONFIG["llm"]["model"]
    wait = initial_wait

    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=CONFIG["llm"]["temperature"],
                max_tokens=CONFIG["llm"]["max_output_tokens"],
            )
            content = response.choices[0].message.content
            if content:
                return content.strip()
            print(f"      Empty response on attempt {attempt}")
        except Exception as e:
            err_str = str(e)
            is_retryable = any(k in err_str.lower() for k in ["429", "rate", "quota", "timeout", "502", "503"])
            if is_retryable and attempt < max_retries:
                print(f"      Retryable error (attempt {attempt}/{max_retries}), waiting {wait:.0f}s...")
                time.sleep(wait)
                wait = min(wait * 2, 120)
            else:
                print(f"      API error (attempt {attempt}): {err_str[:300]}")
                if attempt < max_retries:
                    time.sleep(wait)
                    wait = min(wait * 2, 120)
                else:
                    return None
    return None


def extract_json_from_response(raw: str) -> dict:
    """Extract JSON from LLM response, handling markdown code fences."""
    import re
    # Strip markdown code fences if present
    cleaned = raw.strip()
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', cleaned, re.DOTALL)
    if match:
        cleaned = match.group(1).strip()
    return json.loads(cleaned)


# ─── PDF TEXT EXTRACTION ──────────────────────────────────────────────

def extract_text_from_pdfs(
    project_dir: Path,
    max_chars: int = MAX_TEXT_CHARS,
) -> Tuple[str, int, List[str]]:
    """
    Extract text from all PDFs in a project's specs/ folder.
    Applies smart truncation to stay within max_chars: keeps the first ~80%
    and last ~15% of text so we capture project info, TOC,
    scope of work, AND a sampling of later technical divisions.
    Returns (combined_text, total_pages, list_of_pdf_filenames).
    """
    specs_dir = project_dir / "specs"
    if not specs_dir.exists():
        print(f"  WARNING: No specs/ directory found in {project_dir}")
        return "", 0, []

    pdf_files = sorted(specs_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"  WARNING: No PDF files found in {specs_dir}")
        return "", 0, []

    all_text = []
    total_pages = 0
    filenames = []

    for pdf_path in pdf_files:
        filenames.append(pdf_path.name)
        try:
            doc = fitz.open(str(pdf_path))
            page_count = len(doc)
            total_pages += page_count
            print(f"  Extracting: {pdf_path.name} ({page_count} pages)")

            for page_num in range(page_count):
                page = doc[page_num]
                text = page.get_text("text")
                if text.strip():
                    all_text.append(f"\n--- PAGE {page_num + 1} ({pdf_path.name}) ---\n{text}")
            doc.close()
        except Exception as e:
            print(f"  ERROR extracting {pdf_path.name}: {e}")

    combined = "\n".join(all_text)
    full_len = len(combined)
    print(f"  Total: {total_pages} pages, {full_len:,} characters from {len(filenames)} PDFs")

    # Smart truncation: keep first 80% budget + last 15% budget
    if full_len > max_chars:
        head_budget = int(max_chars * 0.80)
        tail_budget = int(max_chars * 0.15)
        separator = f"\n\n--- [TRUNCATED: {full_len - head_budget - tail_budget:,} characters omitted] ---\n\n"
        combined = combined[:head_budget] + separator + combined[-tail_budget:]
        print(f"  Truncated: {full_len:,} -> {len(combined):,} chars (kept first 80% + last 15% of budget)")

    return combined, total_pages, filenames


def chunk_text(text: str, max_chars: int, overlap: int) -> List[str]:
    """Split text into chunks respecting page boundaries where possible."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars

        # Try to break at a page boundary
        if end < len(text):
            page_break = text.rfind("\n--- PAGE ", start + max_chars - overlap, end)
            if page_break > start:
                end = page_break

        chunks.append(text[start:end])
        start = end - overlap if end < len(text) else end

    return chunks


# ─── AGENT 1: STRUCTURED FIELD EXTRACTION ─────────────────────────────

def build_field_extraction_prompt(text_chunk: str, is_continuation: bool = False) -> str:
    """Build the prompt for structured field extraction."""
    fields = CONFIG["fields"]
    field_descriptions = "\n".join(
        f"  - **{f['name']}**: {f['description']}"
        for f in fields
    )

    continuation_note = ""
    if is_continuation:
        continuation_note = (
            "\nThis is a CONTINUATION of the same document. "
            "Extract any NEW information found in this chunk. "
            "For fields already extracted, only update if you find MORE SPECIFIC information.\n"
        )

    return f"""You are a construction document analysis expert. Extract structured fields from this construction project specification document.
{continuation_note}
**Fields to extract:**
{field_descriptions}

**Instructions:**
1. Extract each field from the document text below.
2. Use `null` for fields where information is not found.
3. For `csi_divisions_present`, list only the 2-digit division numbers found (e.g., ["01", "02", "03"]).
4. For `building_type`, choose from: residential, commercial, industrial, institutional, infrastructure.
5. For `quality_level`, infer from specification detail: economy (basic), standard (mid-grade), premium (luxury/high-end).
6. For numeric fields (`area_sf`, `stories`, `estimated_budget`, `contract_duration_days`), return integers/numbers only, not strings.
7. Be precise — only extract information explicitly stated or strongly implied in the document.

**Return ONLY valid JSON** with the field names as keys. No markdown, no explanation, just the JSON object.

---

**DOCUMENT TEXT:**

{text_chunk}
"""


def run_field_extraction(client: OpenAI, text: str) -> Dict[str, Any]:
    """Run Agent 1: Extract structured fields from PDF text."""
    max_chars = CONFIG["chunking"]["max_chars_per_chunk"]
    overlap = CONFIG["chunking"]["overlap_chars"]
    chunks = chunk_text(text, max_chars, overlap)

    print(f"  [Agent 1 — Field Extraction] Processing {len(chunks)} chunk(s)...")

    merged_fields: Dict[str, Any] = {}

    for i, chunk in enumerate(chunks):
        is_continuation = i > 0
        prompt = build_field_extraction_prompt(chunk, is_continuation)

        raw = call_llm_with_retry(client, prompt)
        if raw is None:
            print(f"    Chunk {i+1}/{len(chunks)}: FAILED after retries")
            continue

        try:
            chunk_fields = extract_json_from_response(raw)

            # Merge: prefer non-null, more specific values
            for key, value in chunk_fields.items():
                if value is not None and value != "" and value != []:
                    existing = merged_fields.get(key)
                    if existing is None or existing == "" or existing == []:
                        merged_fields[key] = value
                    elif key == "csi_divisions_present" and isinstance(value, list):
                        # Merge lists
                        existing_set = set(existing) if isinstance(existing, list) else set()
                        merged_fields[key] = sorted(existing_set | set(value))

            n_extracted = sum(1 for v in chunk_fields.values() if v is not None)
            print(f"    Chunk {i+1}/{len(chunks)}: extracted {n_extracted} fields")

        except json.JSONDecodeError as e:
            print(f"    Chunk {i+1}: JSON parse error — {e}")
            print(f"    Raw response (first 300 chars): {raw[:300]}")

        # Rate limit courtesy delay between chunks
        if i < len(chunks) - 1:
            time.sleep(2)

    return merged_fields


# ─── AGENT 2: QUALITATIVE INSIGHTS ───────────────────────────────────

def build_insights_prompt(text_chunk: str, is_continuation: bool = False) -> str:
    """Build the prompt for qualitative insight extraction."""
    categories = CONFIG["insight_categories"]
    cat_list = "\n".join(f"  - **{c}**" for c in categories)

    continuation_note = ""
    if is_continuation:
        continuation_note = (
            "\nThis is a CONTINUATION of the same document. "
            "Add any NEW qualitative insights found in this chunk.\n"
        )

    return f"""You are a senior construction cost estimator reviewing project specification documents. Your goal is to extract qualitative insights that are critical for accurately estimating the cost of this project.
{continuation_note}
**Insight categories to populate:**
{cat_list}

**For each category, provide:**
- **scope_summary**: A 2-4 sentence summary of the overall project scope, type of work, and key deliverables.
- **complexity_factors**: List specific factors that increase project complexity (e.g., phased construction, occupied building, hazmat, seismic requirements, historic preservation).
- **cost_drivers**: List the primary cost drivers identified in the specs (e.g., specialized equipment, premium materials, unique structural requirements).
- **risk_factors**: List risks that could impact cost (e.g., contamination, difficult site access, regulatory hurdles, weather-sensitive work).
- **schedule_constraints**: Any timeline pressures, phasing requirements, or deadlines that could affect cost.
- **material_quality_signals**: Indicators of material quality level — are specs calling for premium/high-end or economy materials?
- **regulatory_notes**: Permits, compliance requirements, prevailing wage, environmental, OSHA, or code-specific notes.
- **mep_complexity**: Complexity level of mechanical, electrical, and plumbing systems (simple, moderate, complex, highly complex) with brief justification.
- **site_conditions**: Relevant site conditions (soil, seismic zone, flood zone, urban vs rural, existing utilities).
- **phasing_requirements**: How work must be sequenced or phased, and any operational constraints.

**Instructions:**
1. Be specific and cite details from the document.
2. For list fields, provide 2-6 concise bullet points.
3. For text fields, keep responses to 2-4 sentences.
4. Focus on information that would impact a cost estimate.

**Return ONLY valid JSON** with the category names as keys. No markdown, no explanation, just the JSON object.

---

**DOCUMENT TEXT:**

{text_chunk}
"""


def run_insights_extraction(client: OpenAI, text: str) -> Dict[str, Any]:
    """Run Agent 2: Extract qualitative insights from PDF text."""
    max_chars = CONFIG["chunking"]["max_chars_per_chunk"]
    overlap = CONFIG["chunking"]["overlap_chars"]
    chunks = chunk_text(text, max_chars, overlap)

    print(f"  [Agent 2 — Qualitative Insights] Processing {len(chunks)} chunk(s)...")

    merged_insights: Dict[str, Any] = {}

    for i, chunk in enumerate(chunks):
        is_continuation = i > 0
        prompt = build_insights_prompt(chunk, is_continuation)

        raw = call_llm_with_retry(client, prompt)
        if raw is None:
            print(f"    Chunk {i+1}/{len(chunks)}: FAILED after retries")
            continue

        try:
            chunk_insights = extract_json_from_response(raw)

            # Merge: concatenate lists, prefer longer text fields
            for key, value in chunk_insights.items():
                if value is None or value == "" or value == []:
                    continue
                existing = merged_insights.get(key)
                if existing is None:
                    merged_insights[key] = value
                elif isinstance(value, list) and isinstance(existing, list):
                    # Merge and deduplicate lists
                    seen = set(str(x) for x in existing)
                    for item in value:
                        if str(item) not in seen:
                            existing.append(item)
                            seen.add(str(item))
                elif isinstance(value, str) and isinstance(existing, str):
                    # Keep the longer/more detailed text
                    if len(value) > len(existing):
                        merged_insights[key] = value

            print(f"    Chunk {i+1}/{len(chunks)}: extracted {len(chunk_insights)} categories")

        except json.JSONDecodeError as e:
            print(f"    Chunk {i+1}: JSON parse error — {e}")
            print(f"    Raw response (first 300 chars): {raw[:300]}")

        # Rate limit courtesy delay between chunks
        if i < len(chunks) - 1:
            time.sleep(2)

    return merged_insights


# ─── ORCHESTRATOR ─────────────────────────────────────────────────────

def enforce_json_length_limit(result: Dict, max_length: int = 20000) -> Dict:
    """Ensure the JSON string representation of the result does not exceed max_length."""
    import copy
    
    json_str = json.dumps(result)
    if len(json_str) <= max_length:
        return result
    
    print(f"  WARNING: JSON size ({len(json_str):,}) exceeds limit ({max_length:,}). Truncating...")
    truncated = copy.deepcopy(result)
    
    # Priority 1: Truncate long strings in qualitative_insights
    if "qualitative_insights" in truncated:
        insights = truncated["qualitative_insights"]
        
        # Keep trimming the longest string or list until we fit
        while len(json.dumps(truncated)) > max_length:
            longest_key = None
            max_len = 0
            is_list = False
            
            for k, v in insights.items():
                if isinstance(v, list) and len(v) > 0:
                    current_len = sum(len(str(item)) for item in v)
                    if current_len > max_len:
                        max_len = current_len
                        longest_key = k
                        is_list = True
                elif isinstance(v, str) and len(v) > 50:
                    if len(v) > max_len:
                        max_len = len(v)
                        longest_key = k
                        is_list = False
            
            if longest_key is None:
                break
                
            if is_list:
                insights[longest_key].pop()
            else:
                val = insights[longest_key]
                insights[longest_key] = val[:int(len(val) * 0.8)] + "..."
                
    # If still too long, emergency truncation of the whole qualitative insights dict
    if len(json.dumps(truncated)) > max_length:
        truncated["qualitative_insights"] = {"error": "Truncated to fit length limits."}

    # If STILL too long, truncate structured fields
    if len(json.dumps(truncated)) > max_length:
         truncated["structured_fields"] = {"error": "Truncated to fit length limits."}

    final_len = len(json.dumps(truncated))
    print(f"  Truncated JSON size down to {final_len:,} characters.")
    return truncated


def process_project(project_dir: Path, client: OpenAI) -> Optional[Dict]:
    """Process a single project: extract text, run both agents sequentially."""
    project_id = project_dir.name.upper()
    print(f"\n{'='*60}")
    print(f"Processing {project_id} — {project_dir}")
    print(f"{'='*60}")

    # Step 1: Extract text from PDFs
    text, total_pages, pdf_files = extract_text_from_pdfs(project_dir)
    if not text:
        print(f"  SKIPPING {project_id}: no text extracted")
        return None

    # Step 2: Run both agents sequentially
    result = {
        "project_id": project_id,
        "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
        "pdf_sources": pdf_files,
        "total_pages_processed": total_pages,
        "total_chars_extracted": len(text),
        "structured_fields": {},
        "qualitative_insights": {},
    }

    # Agent 1: Structured fields
    try:
        result["structured_fields"] = run_field_extraction(client, text)
    except Exception as e:
        print(f"  Field extraction failed: {e}")
        result["structured_fields"] = {"error": str(e)}

    # Brief pause between agents
    time.sleep(1)

    # Agent 2: Qualitative insights
    try:
        result["qualitative_insights"] = run_insights_extraction(client, text)
    except Exception as e:
        print(f"  Insights extraction failed: {e}")
        result["qualitative_insights"] = {"error": str(e)}

    # Summary
    n_fields = sum(
        1 for v in result["structured_fields"].values()
        if v is not None and v != "" and v != [] and not isinstance(v, dict)
    )
    n_insights = len(result["qualitative_insights"])
    print(f"\n  ✓ {project_id}: {n_fields} fields extracted, {n_insights} insight categories")

    return enforce_json_length_limit(result, max_length=20000)


def find_projects_with_specs(base_dir: Path) -> List[Path]:
    """Find all project directories that have a specs/ subfolder with PDFs."""
    projects = []
    for d in sorted(base_dir.iterdir()):
        if d.is_dir() and d.name.startswith("PRJ-"):
            specs = d / "specs"
            if specs.exists() and any(specs.glob("*.pdf")):
                projects.append(d)
    return projects


def run_pipeline(
    project_dirs: List[Path],
    output_path: Path,
    client: OpenAI,
) -> None:
    """Run the full pipeline on a list of projects."""
    print(f"\n{'#'*60}")
    print(f"  PDF Parsing & Summarizing Pipeline")
    print(f"  Projects: {len(project_dirs)}")
    print(f"  Output:   {output_path}")
    print(f"  Model:    {CONFIG['llm']['model']}")
    print(f"  Provider: OpenRouter")
    print(f"{'#'*60}")

    results = []
    for project_dir in project_dirs:
        result = process_project(project_dir, client)
        if result:
            results.append(result)

    # Save results
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'#'*60}")
    print(f"  Pipeline complete!")
    print(f"  Processed: {len(results)} / {len(project_dirs)} projects")
    print(f"  Saved to:  {output_path}")
    print(f"{'#'*60}")


# ─── CLI ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="PDF Parsing & Summarizing Pipeline for Construction Cost Estimation"
    )
    parser.add_argument(
        "--project-dir",
        type=str,
        help="Path to a single project directory (e.g., rich_floor_plans/PRJ-001)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all projects with spec PDFs in rich_floor_plans/",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON path (default: from config)",
    )
    args = parser.parse_args()

    if not args.project_dir and not args.all:
        parser.error("Specify --project-dir or --all")

    # Resolve paths
    output_path = Path(args.output) if args.output else Path(CONFIG["output"]["default_path"])

    if args.project_dir:
        project_dirs = [Path(args.project_dir)]
        if not project_dirs[0].exists():
            # Try relative to script dir
            project_dirs = [ROOT_DIR / args.project_dir]
        if not project_dirs[0].exists():
            print(f"ERROR: Project directory not found: {args.project_dir}")
            sys.exit(1)
    else:
        base = ROOT_DIR / "rich_floor_plans"
        project_dirs = find_projects_with_specs(base)
        if not project_dirs:
            print("ERROR: No projects with spec PDFs found in rich_floor_plans/")
            sys.exit(1)
        print(f"Found {len(project_dirs)} projects with spec PDFs")

    # Init client
    client = init_client()

    # Run
    start_time = time.time()
    run_pipeline(project_dirs, output_path, client)
    elapsed = time.time() - start_time
    print(f"\nTotal time: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
