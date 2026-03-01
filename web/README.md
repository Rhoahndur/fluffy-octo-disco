# Construction Cost Estimation MVP

AI-powered construction cost estimation using LLMs, computer vision, and RSMeans cost data.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Input                                   │
│         (Floor plans, photos, descriptions, PDF specs)               │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│    OpenCV     │   │      PDF      │   │  Description  │
│  (Modal.com)  │   │   Extraction  │   │    Parsing    │
│               │   │               │   │               │
│ Deterministic │   │ • Schedules   │   │ • Keywords    │
│ measurements  │   │ • Specs       │   │ • Sqft regex  │
│ from drawings │   │ • Project info│   │ • Location    │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │      Context Assembly                  │
        │                                        │
        │  CV + PDF data packaged as context     │
        │  for LLM interpretation                │
        └───────────────────┬───────────────────┘
                            │
            ┌───────────────┴───────────────┐
            │                               │
            ▼                               ▼
    ┌───────────────┐               ┌───────────────┐
    │    Claude     │               │    Gemini     │
    │               │               │               │
    │ Receives:     │               │ Receives:     │
    │ • Images      │               │ • Images      │
    │ • Description │               │ • Description │
    │ • CV takeoff  │               │ • CV takeoff  │
    │ • PDF specs   │               │ • PDF specs   │
    │               │               │               │
    │ Returns:      │               │ Returns:      │
    │ • Building    │               │ • Building    │
    │   classification│             │   classification│
    │ • Quality     │               │ • Quality     │
    │ • Materials   │               │ • Materials   │
    └───────┬───────┘               └───────┬───────┘
            │                               │
            └───────────────┬───────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │           Reconciliation              │
        │                                       │
        │  • LLM consensus increases confidence │
        │  • CV data validates LLM sqft         │
        │  • PDF specs confirm materials        │
        │  • Conflicts flagged for review       │
        └───────────────────┬───────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     RSMeans Cost Model                               │
│                                                                      │
│  • 40+ building sub-types with cost/SF data                         │
│  • CSI MasterFormat division breakdown                               │
│  • Location factors (60+ US cities)                                  │
│  • Quality multipliers (low/mid/high)                                │
│  • Story premium calculations                                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Step 1: Deterministic Extraction** - OpenCV and PDF parsers run first to extract ground-truth measurements
2. **Step 2: Context Assembly** - CV takeoff and PDF specs packaged as structured context
3. **Step 3: LLM Interpretation** - Claude and Gemini receive images + context, classify building type and quality
4. **Step 4: Reconciliation** - LLM outputs merged with CV guardrails
5. **Step 5: Cost Calculation** - Final parameters fed to RSMeans model

## Key Features

### Multi-Model Analysis
- **Claude & Gemini** analyze images/descriptions for probabilistic interpretation
- **OpenCV** provides deterministic measurements (counts, areas, dimensions)
- Consensus reconciliation with CV guardrails constraining LLM outputs

### OpenCV Analysis (Modal.com Worker)
The CV worker extracts quantitative takeoff data from construction drawings:

| Output | Unit | CSI Division | Use |
|--------|------|--------------|-----|
| `gross_floor_area` | SF | 01_general | Base for overhead calculations |
| `concrete_slab_volume` | CY | 03_concrete | Slab-on-grade estimate |
| `foundation_volume` | CY | 03_concrete | Foundation wall estimate |
| `excavation_volume` | CY | 02_sitework | Site prep estimate |
| `interior_wall_length` | LF | 06/09 | Framing, drywall, trim |
| `door_count` | EA | 08_openings | Door assemblies |
| `window_count` | EA | 08_openings | Window assemblies |
| `room_count` | EA | - | HVAC zoning, fixtures |

**Scale Detection Priority:**
1. Dimension-based calibration (matches "25'-0"" text to nearby lines)
2. OCR scale notation (e.g., "1/4" = 1'-0"")
3. Scale bar detection + assumption
4. Default estimate (lowest confidence)

### RSMeans Cost Model
- 40+ building sub-types across 5 categories
- CSI MasterFormat 18-division breakdown
- Location adjustment factors for 60+ US cities
- Story premium: +2.5% per floor above 3
- Quality multipliers for low/mid/high finishes

## Project Structure

```
web/
├── src/
│   ├── app/
│   │   ├── api/
│   │   │   ├── estimate/route.ts    # Main estimation endpoint
│   │   │   └── similar/route.ts     # Similar projects lookup
│   │   └── page.tsx                 # Frontend UI
│   ├── components/                   # React components
│   ├── lib/
│   │   ├── llm/
│   │   │   ├── claude.ts            # Claude client (accepts CV/PDF context)
│   │   │   ├── gemini.ts            # Gemini client (accepts CV/PDF context)
│   │   │   ├── reconcile.ts         # LLM + CV reconciliation
│   │   │   └── prompts.ts           # System prompts with context injection
│   │   ├── cv/
│   │   │   └── modal-client.ts      # Modal.com CV client
│   │   ├── pdf/
│   │   │   └── pdf-client.ts        # PDF extraction client
│   │   ├── cost/
│   │   │   ├── rsmeans.ts           # Cost calculation engine
│   │   │   └── data/                # Cost/SF, CSI profiles, location factors
│   │   ├── similar/
│   │   │   └── matcher.ts           # Similar project matching
│   │   └── db/
│   │       └── supabase.ts          # Database client
│   └── types/
│       └── index.ts                 # TypeScript types
├── modal/
│   ├── cv_worker.py                 # OpenCV worker for Modal.com
│   └── test_cv_local.py             # Local testing script
└── package.json
```

## API Reference

### POST /api/estimate

Generate a cost estimate from images and/or description.

**Request:**
```json
{
  "images": ["data:image/png;base64,..."],
  "description": "2-story single family home, 2500 SF, wood frame",
  "location": "Boston, MA",
  "pdfExtraction": {
    "source": "pdf_extraction",
    "project_info": {
      "name": "Smith Residence",
      "location": "Boston, MA",
      "total_area": 2500
    },
    "schedules": {
      "door_schedule": [{"mark": "D1", "type": "Solid Core"}],
      "window_schedule": [{"mark": "W1", "type": "Double Hung"}]
    }
  }
}
```

**Response:**
```json
{
  "id": "uuid",
  "status": "complete",
  "estimate": {
    "total_cost": 625000,
    "cost_per_sf": 250,
    "area_sf": 2500,
    "stories": 2,
    "quality": "mid",
    "location": "boston",
    "location_factor": 1.12,
    "division_breakdown": {
      "03_concrete": 31250,
      "06_wood_plastics_composites": 62500,
      ...
    },
    "item_quantities": [
      {"item": "Concrete", "quantity": 62.5, "unit": "CY", "total_cost": 31250}
    ]
  },
  "analysis": {
    "merged": {
      "building_type": "residential",
      "sub_type": "single_family_standard",
      "quality": "mid",
      "estimated_sqft": 2500,
      ...
    },
    "conflicts": [],
    "confidence": 0.85
  },
  "similar_projects": []
}
```

## Environment Variables

```bash
# Required for LLM analysis
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_AI_API_KEY=AI...

# Optional: OpenCV analysis (Modal.com)
MODAL_ENDPOINT_URL=https://your-workspace--construction-cv-worker-analyze.modal.run

# Optional: PDF extraction (external service)
PDF_ENDPOINT_URL=https://your-pdf-service/extract

# Optional: Database persistence
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
```

## Getting Started

### 1. Install dependencies
```bash
npm install
```

### 2. Set environment variables
```bash
cp .env.example .env.local
# Edit .env.local with your API keys
```

### 3. Run development server
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

### 4. Deploy OpenCV Worker (Optional)

```bash
# Install Modal CLI
pip install modal

# Authenticate
modal token new

# Deploy the worker
cd modal
modal deploy cv_worker.py
```

The endpoint URL will be displayed after deployment.

## Reconciliation Philosophy

The system uses a hybrid approach:

**OpenCV (Deterministic)**
- Provides hard measurements: counts, areas, dimensions
- High confidence when scale is calibrated
- Acts as guardrails for LLM outputs

**LLMs (Probabilistic)**
- Interprets building type, quality, construction method
- Fills in semantic context
- Consensus between Claude and Gemini increases confidence

**Reconciliation Rules:**
1. OCR-extracted sqft overrides LLM estimates (ground truth)
2. CV-measured areas with scale detection weight 70/30 vs LLM
3. CV counts (doors, windows, rooms) inform quality validation
4. LLM consensus on classification boosts confidence
5. Conflicts between sources reduce overall confidence

## Building Types Supported

### Residential
- `single_family_economy` / `standard` / `premium` / `custom`
- `multi_family_duplex` / `triplex` / `fourplex`
- `apartment_lowrise` / `midrise` / `garden`
- `townhouse_standard` / `luxury`
- `luxury_estate`, `custom_architectural`

### Commercial
- `office_lowrise` / `midrise` / `highrise`
- `retail_strip` / `bigbox`
- `restaurant_casual` / `fine`
- `hotel_limited` / `full_service`
- `bank_branch`, `medical_office`, `mixed_use`

### Industrial
- `warehouse_light` / `heavy`
- `manufacturing_light` / `heavy`
- `data_center`, `research_lab`, `cold_storage`, `food_processing`

### Institutional
- `school_elementary` / `high`
- `university_classroom` / `science`
- `hospital_acute`, `clinic_outpatient`
- `church_standard` / `cathedral`
- `library_public`, `community_center`

### Infrastructure
- `parking_surface` / `structured`
- `fire_station`, `police_station`
- `transit_station`, `bus_maintenance`
- `water_treatment`, `electrical_substation`

## Tech Stack

- **Frontend:** Next.js 16, React 19, Tailwind CSS, shadcn/ui
- **LLMs:** Anthropic Claude, Google Gemini
- **Computer Vision:** OpenCV (via Modal.com serverless)
- **OCR:** Tesseract
- **Database:** Supabase (optional)
- **Deployment:** Vercel (web), Modal.com (CV worker)
