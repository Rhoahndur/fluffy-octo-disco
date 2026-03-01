"""Quick smoke test: verify the pipeline module loads and can extract PDF text."""
import pdf_pipeline

print("Module loaded OK")
print(f"Fields: {len(pdf_pipeline.CONFIG['fields'])}")
print(f"Insight categories: {len(pdf_pipeline.CONFIG['insight_categories'])}")
print(f"Model: {pdf_pipeline.CONFIG['llm']['model']}")

# Test PDF extraction on PRJ-001
from pathlib import Path
project_dir = Path("rich_floor_plans/PRJ-001")
text, pages, files = pdf_pipeline.extract_text_from_pdfs(project_dir)
print(f"\nPRJ-001 extraction:")
print(f"  PDFs: {files}")
print(f"  Pages: {pages}")
print(f"  Text length: {len(text):,} chars")
print(f"  First 300 chars: {text[:300]}")
print("\nSmoke test PASSED")
