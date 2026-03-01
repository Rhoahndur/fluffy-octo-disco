# Construction Cost Estimation — Eval Dataset

Ground truth evaluation dataset for software that estimates construction costs
from drawings, specifications, and project documents. Contains two datasets:

- **`eval_dataset.json`** — 53 synthetic cases (single drawing + generated spec)
- **`rich_eval_dataset.json`** — 25 real-project cases (6 drawings + real PDFs)

---

## File Structure

```
Eval_estimation/
├── README.md
├── requirements.txt
├── eval_config.yaml               # Configuration and thresholds
│
├── cost_model.py                  # RSMeans-based cost engine
├── spec_generator.py              # CSI specification text generator
│
├── setup_dataset.py               # Builds eval_dataset.json (53-case dataset)
├── build_rich_dataset.py          # Builds rich_eval_dataset.json (25-case rich dataset)
├── rich_dataset_sources.py        # Curated project catalog + LOC drawing URLs
├── evaluate.py                    # Evaluation framework (MAPE, MAE, RMSE, R²)
│
├── eval_dataset.json              # [GENERATED] 53-case synthetic dataset
├── rich_eval_dataset.json         # [GENERATED] 25-case rich real-project dataset
│
├── floor_plans/                   # [GENERATED] Images for eval_dataset.json
│   ├── residential/               # 15 real LOC HABS drawings
│   ├── commercial/                # 12 real LOC HABS drawings
│   ├── industrial/                # 8 real LOC HABS drawings
│   ├── institutional/             # 10 real LOC HABS drawings
│   └── infrastructure/            # 8 real LOC HABS drawings
│
├── rich_floor_plans/              # [GENERATED] Assets for rich_eval_dataset.json
│   └── PRJ-{001..025}/
│       ├── specs/                 # Downloaded real spec PDFs (where available)
│       │   ├── spec_book_1.pdf
│       │   └── spec_book_2.pdf    # (PRJ-001 has 3 books)
│       ├── prj-NNN_sheet_g001.png # Cover sheet / project info drawing
│       ├── prj-NNN_sheet_a001.png # Site plan drawing
│       ├── prj-NNN_sheet_a101.png # Floor plan level 1
│       ├── prj-NNN_sheet_a102.png # Floor plan level 2
│       ├── prj-NNN_sheet_a201.png # Building elevations
│       └── prj-NNN_sheet_a301.png # Building sections
│
└── results/                       # Evaluation outputs (JSON + Markdown)
    ├── dummy_predictions.json     # Sample predictions for eval_dataset
    ├── rich_dummy_predictions.json
    └── eval_report_YYYYMMDD_HHMMSS.md
```

---

## Datasets

### Dataset 1: `eval_dataset.json` — 53 Synthetic Cases

Generated from RSMeans cost data with LOC HABS floor plan images. Good for
quick iteration when you don't need multi-document inputs.

| Category | Count | Sub-types |
|---|---|---|
| Residential | 15 | single-family, multi-family, apartment, townhouse, luxury |
| Commercial | 12 | office, retail, restaurant, hotel, medical, mixed-use |
| Industrial | 8 | warehouse, manufacturing, data center, lab |
| Institutional | 10 | school, university, hospital, clinic, church, library |
| Infrastructure | 8 | parking, fire station, police, transit, utility |

**Per case:** 1 floor plan image + CSI spec text (~20 pages) + cost breakdown

**Build:**
```bash
python setup_dataset.py
```

---

### Dataset 2: `rich_eval_dataset.json` — 25 Real-Project Cases

Real government procurement projects with actual drawings and spec PDFs.
Designed for testing systems that consume rich multi-document inputs.

| Metric | Value |
|---|---|
| Projects | 25 |
| Drawings per project | 6 real LOC HABS architectural drawings |
| Avg spec text | 211 pages |
| Real PDF specs | 11 / 25 projects (100–1,352 pages each) |
| Real bid award costs | 6 / 25 projects (from public bid tabulations) |
| Cost range | $139,000 – $23,520,000 |
| Total spec text | ~3.1M characters |

**Per case:** 6 drawings + up to 1,352 pages of real specification text + cost

**Project sources:**
- **California DGS OBAS** (PRJ-001 to PRJ-008) — State building project manuals
  downloaded directly from `dgs.ca.gov/OBAS`
- **Michigan DTMB** (PRJ-009 to PRJ-011) — Actual low-bid award amounts from
  public bid tabulations (Cadence Construction, RAS Contracting, Genoa Contracting)
- **Pennsylvania DGS** (PRJ-012) — $23,520,000 actual award to Rycon Construction
- **Idaho DPW** (PRJ-014 to PRJ-015) — Actual bids ($1.28M Germer Construction)
- **City of Page AZ / Indiana DNR / GSU** (PRJ-016 to PRJ-018) — Real spec PDFs
- **New construction** (PRJ-019 to PRJ-025) — RSMeans-calibrated estimates

**Build:**
```bash
python build_rich_dataset.py
# --skip-download   Use proxy specs + placeholder drawings (faster, offline)
# --output PATH     Custom output JSON path
```

---

## Evaluation

Your system should produce a JSON file with predictions:

```json
[
  {
    "project_id": "PRJ-001",
    "predicted_total": 8500000,
    "predicted_divisions": {
      "03_concrete": 400000,
      "05_metals": 250000,
      "...": "..."
    }
  }
]
```

Run evaluation:
```bash
# Against rich dataset (default)
python evaluate.py --predictions results/YOUR_PREDICTIONS.json --dataset rich_eval_dataset.json

# Against synthetic dataset
python evaluate.py --predictions results/YOUR_PREDICTIONS.json --dataset eval_dataset.json
```

**Metrics computed:**
- MAPE, MAE, RMSE, R² (overall)
- % within 10% / 20% / 30% of actual
- Per-building-type MAPE breakdown
- Per-CSI-division MAPE breakdown

**Thresholds (from `eval_config.yaml`):**
- Overall MAPE: 15% acceptable
- Per-division MAPE: 25% acceptable
- Within 20%: 65% target

Output: JSON results + Markdown report saved to `results/`.

---

## Setup

```bash
pip install -r requirements.txt
```

**Requirements:** numpy, pandas, scikit-learn, Pillow, pyyaml, shapely,
requests, tqdm, pymupdf, pdf2image

**Windows note:** Run scripts with `python -X utf8` to avoid cp1252 encoding
errors when spec text contains special characters:
```bash
python -X utf8 build_rich_dataset.py
```

---

## Cost Model (`cost_model.py`)

RSMeans 2024–2025 national average data:

- **48 building sub-types** × 3 quality levels (low / mid / high)
- **10 CSI division profiles** (residential, commercial office, industrial,
  healthcare, education, etc.) — each 18 divisions summing to 100%
- **27 US city location factors** (New York 1.30 → Memphis 0.82)
- Story premium: +2.5% per floor above 3 stories
- ±3% seeded random variance for realism

---

## Drawing Sources

All drawings are from the **Library of Congress HABS/HAER** (Historic American
Buildings Survey / Historic American Engineering Record) collection —
public domain, free to use.

Source: `https://tile.loc.gov/storage-services/service/pnp/habshaer/`

For the rich dataset, 40+ verified LOC URLs are cataloged in
`rich_dataset_sources.py` organized by building type (residential,
commercial, industrial, institutional, infrastructure).

---

## Quick Test

```bash
# Run both datasets with sample predictions
python -X utf8 evaluate.py --predictions results/dummy_predictions.json --dataset eval_dataset.json
python -X utf8 evaluate.py --predictions results/rich_dummy_predictions.json --dataset rich_eval_dataset.json
```

Expected results (±noise):
- `eval_dataset.json`: MAPE ~7%, R² ~0.998
- `rich_eval_dataset.json`: MAPE ~9%, R² ~0.95
