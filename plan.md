# AI-CLAIMS-Orchestrator-Azure — MVP Plan

## Context

The parent project [`AI-CLAIMS-Orchestrator/`](../) is a multi-agent insurance-claims app using **Google Gemini** (LLM + vision), **Qdrant** (vector DB), and **Opus workflow YAML** for orchestration. It runs 9 agents through a 5-stage pipeline (validate → fraud → policy → docs → decide).

This new MVP — **`AI-CLAIMS-Orchestrator-Azure/`** — re-implements a focused subset of that functionality on the **Microsoft Azure AI stack** to demonstrate real-world **industrial computer-vision** use cases for an Amity University lecture: *Industrial Image Processing / Machine Vision / APIs & Platforms for CV applications.*

The flagship demo is **car-damage assessment from photos** using **Azure Computer Vision**, with a **Claude Sonnet 4.6 (Microsoft Foundry)** LLM orchestrating the downstream insurance reasoning. OCR/Read for repair bills and brand/logo detection on vehicles add breadth to the CV showcase. Past-claims/policy data is mocked locally (JSON + in-memory cosine search) — no external vector DB, no Opus workflow, no Gemini.

The parent project is **read-only reference** — nothing in it will be modified.

---

## Goals

1. Showcase Azure Computer Vision (Image Analysis 4.0 + Read OCR + v3.2 Brands) on a real insurance use case.
2. Demonstrate end-to-end orchestration: CV outputs → LLM reasoning (Claude via Foundry) → decision.
3. **Runs entirely on a laptop, localhost only** — both backend (`uvicorn` on `:8000`) and frontend (`vite` on `:3000`). No cloud hosting, no Docker required (other than the already-cloud Azure services).
4. Preserve the UX feel of the parent project (React + Vite) so students can compare architectures.
5. Include a **lightweight human-in-the-loop path** inside the Dashboard for complicated cases (claims the Decision Maker marks as `NEEDS_REVIEW`) — without adding a third tab.

---

## Tech Stack

| Layer | Parent project | This MVP (Azure) |
|---|---|---|
| LLM | Google Gemini 2.5 Flash | **Claude Sonnet 4.6** via Microsoft AI Foundry (`/anthropic/v1/messages`) |
| Vision / OCR | Gemini Vision | **Azure Computer Vision** (Image Analysis 4.0 + Read + v3.2 Brands) |
| RAG | Qdrant Cloud (768-d) | **JSON files + in-memory cosine** (`sentence-transformers/all-MiniLM-L6-v2`, local CPU) |
| Orchestration | Opus YAML executor | **Plain async Python** pipeline in `orchestrator.py` |
| Backend | FastAPI | FastAPI (same) |
| Frontend | React + Vite (3 tabs) | React + Vite, **2 tabs only**: Submit Claim, Dashboard |

---

## Azure Resources

| Resource | Status | Notes |
|---|---|---|
| Azure Computer Vision (`computer-vision-service-swap`) | ✅ Provided | Used for image analysis, OCR, brand detection |
| Microsoft AI Foundry — Claude Sonnet 4.6 (`worksense-ai-project-resource`) | ✅ Provided | Anthropic-compatible endpoint, no separate Azure OpenAI needed |
| Azure AI Document Intelligence | ❌ Not required | Read API on Computer Vision is sufficient for invoices/bills in this MVP. *(If we later want field-extraction tables/key-value pairs on complex forms, Document Intelligence would help — flag for follow-up.)* |
| Azure AI Search | ❌ Not required | Replaced with local JSON + in-memory cosine for MVP simplicity |
| Hosting | Optional | Local dev for the lecture demo; Azure App Service or Container Apps only if remote hosting needed later |

---

## Folder Layout (new subfolder under parent)

```
AI-CLAIMS-Orchestrator-Azure/
├── plan.md                          ← this file
├── README.md                        ← setup + demo instructions
├── .env.example                     ← Azure CV + Foundry keys (placeholders)
├── .gitignore
├── backend/
│   ├── main.py                      ← FastAPI app, endpoints
│   ├── config.py                    ← pydantic-settings, loads .env
│   ├── orchestrator.py              ← 6-step async pipeline (no Opus)
│   ├── requirements.txt
│   ├── agents/
│   │   ├── validator.py             ← Claude-based completeness check
│   │   ├── car_damage_analyzer.py   ← NEW: Azure CV 4.0 + v3.2 Brands on car photos
│   │   ├── document_analyzer.py     ← Azure CV Read OCR on bills/invoices/reports
│   │   ├── fraud_detector.py        ← Claude + RAG over past_claims.json
│   │   ├── policy_checker.py        ← Claude + RAG over policies.json
│   │   └── decision_maker.py        ← Claude — final APPROVED / REJECTED / NEEDS_REVIEW
│   ├── services/
│   │   ├── azure_vision.py          ← Wrapper for all CV features (single client, multiple verbs)
│   │   ├── claude_client.py         ← anthropic SDK with base_url override → Foundry
│   │   └── rag_service.py           ← load JSON, embed once at startup, cosine top-k
│   ├── models/
│   │   └── schemas.py               ← Pydantic ClaimSubmission, AgentResult, ClaimAnalysis
│   ├── data/
│   │   ├── policies.json            ← ~8 sample auto policies (id, holder, coverage, limits, status)
│   │   ├── past_claims.json         ← ~15 historical claims (approved + 2-3 fraud examples)
│   │   └── fraud_patterns.json      ← known red flags for prompt-context
│   ├── utils/
│   │   └── file_storage.py          ← saves uploads under uploads/{claim_id}/
│   └── uploads/                     ← gitignored
├── frontend/
│   ├── package.json                 ← vite, react, axios, lucide-react (lean)
│   ├── vite.config.js               ← proxy /api → :8000
│   ├── index.html
│   ├── styles.css                   ← reuse colour vars from parent for visual continuity
│   └── src/
│       ├── App.jsx                  ← 2 tabs only
│       ├── main.jsx
│       ├── services/api.js          ← axios client
│       └── components/
│           ├── ClaimSubmissionForm.jsx   ← form + car-photo + supporting-docs upload
│           ├── Dashboard.jsx             ← list of claims with status
│           ├── ClaimDetail.jsx           ← per-claim drill-in: agent results + decision
│           └── DamageVisualization.jsx   ← canvas overlay: bounding boxes on uploaded photo
└── sample_documents/                ← copied as-is from parent ../sample_documents/ (car-damage photos + mock bills/reports). Build step: `cp -r ../sample_documents ./sample_documents` (or Windows equivalent) — referenced read-only from the README's demo walkthrough.
```

---

## Orchestration Flow (no Opus)

`backend/orchestrator.py` runs **sequentially** for a clear, narratable demo (students can watch each stage announce itself in the UI/logs):

```
submit(claim + images)
  │
  ├─ 1. Validator              (Claude) ─ completeness, schema, plausible amounts
  ├─ 2. Car Damage Analyzer    (Azure CV 4.0: Objects, Tags, Caption, DenseCaptions)
  │                            + (Azure CV v3.2: Brands)  ← demo flourish
  ├─ 3. Document Analyzer      (Azure CV Read API) ─ OCR on bills/receipts/reports
  ├─ 4. Fraud Detector         (Claude + RAG/past_claims.json + Steps 2-3 evidence)
  ├─ 5. Policy Checker         (Claude + RAG/policies.json)
  └─ 6. Decision Maker         (Claude) ─ aggregates all AgentResults → final verdict
                                          + adjuster-style summary blurb
```

A `status_update_callback` after each step writes the in-progress stage to the in-memory claims store so the frontend polling endpoint (`GET /api/claims/{id}`) can reflect live progress. (Mirrors the parent project's UX pattern without the Opus state machine.)

---

## Key Implementations

### `services/claude_client.py` — Claude via Foundry

Use the official **`anthropic`** Python SDK with `base_url` override — the Foundry endpoint speaks the native Anthropic Messages API.

```python
from anthropic import AsyncAnthropic

client = AsyncAnthropic(
    base_url="https://worksense-ai-project-resource.services.ai.azure.com/anthropic/",
    api_key=settings.foundry_api_key,
)

resp = await client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": prompt}],
)
```

Wrapped in a small helper `complete(system, user) -> str` reused by all Claude-based agents (validator, fraud, policy, decision). Each agent retains the parent project's `STATUS / CONFIDENCE / FINDINGS / RECOMMENDATIONS` text protocol so the response-parsing in [`fraud_detector.py:56-69`](../backend/agents/fraud_detector.py#L56-L69) etc. can be ported nearly verbatim.

### `services/azure_vision.py` — three CV demos in one wrapper

```python
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential
import httpx  # for v3.2 Brands fallback

class AzureVisionService:
    def __init__(self, endpoint, key):
        self.v4 = ImageAnalysisClient(endpoint, AzureKeyCredential(key))
        self.v32_url = f"{endpoint.rstrip('/')}/vision/v3.2/analyze"
        self.key = key

    def analyze_damage(self, image_bytes):       # Image Analysis 4.0
        return self.v4.analyze(image_data=image_bytes, visual_features=[
            VisualFeatures.OBJECTS, VisualFeatures.TAGS,
            VisualFeatures.CAPTION, VisualFeatures.DENSE_CAPTIONS,
        ])

    def ocr_document(self, image_bytes):         # Read OCR (v4.0)
        return self.v4.analyze(image_data=image_bytes,
                               visual_features=[VisualFeatures.READ])

    def detect_brands(self, image_bytes):        # v3.2 (Brands not in v4.0)
        r = httpx.post(self.v32_url,
                       params={"visualFeatures": "Brands"},
                       headers={"Ocp-Apim-Subscription-Key": self.key,
                                "Content-Type": "application/octet-stream"},
                       content=image_bytes, timeout=30)
        return r.json()
```

> **Why v3.2 Brands separately?** The newer Image Analysis 4.0 (Florence model) merges brand info into general tags/objects and no longer exposes a dedicated `Brands` feature. To honour the explicit student-facing demo of brand/logo detection, we make a small parallel v3.2 REST call. This is itself a useful teaching point: how Azure CV API versions evolved.

### `services/rag_service.py` — in-memory cosine RAG

At startup: load `data/policies.json` + `data/past_claims.json` → embed text fields with `sentence-transformers/all-MiniLM-L6-v2` (384-d, ~80MB, CPU-only, no API cost) → keep vectors in numpy arrays. `search(query, k=3)` returns top-k records by cosine similarity.

Used by the fraud detector (find similar past claims) and policy checker (find matching policy).

### `agents/car_damage_analyzer.py` — NEW

1. Call `azure_vision.analyze_damage(image)` for each uploaded image.
2. Call `azure_vision.detect_brands(image)` in parallel.
3. Filter `objects`/`denseCaptions` for damage-relevant terms (dent, scratch, broken, shattered, bumper, fender, headlight, …).
4. Optionally pass the structured findings + caption to Claude for a damage-severity opinion (`MINOR / MODERATE / SEVERE`) and a rough cost-band estimate — gives the LLM something concrete to reason on.
5. Return `AgentResult` with `metadata = {"detected_objects": [...], "damage_regions": [...], "brand": "...", "severity": "MODERATE", "ocr": null}` and `confidence` from CV.

The frontend uses `damage_regions` (bounding boxes) to overlay rectangles on the original photo in `DamageVisualization.jsx`.

### `agents/document_analyzer.py` — Azure CV Read

Replaces parent's Gemini Vision OCR ([`document_analyzer.py:23-28`](../backend/agents/document_analyzer.py#L23-L28)) with `azure_vision.ocr_document()`. Resulting text is passed to Claude with the same cross-verification prompt structure (dates/amounts/names match the claim form) — prompt template ported from the parent.

### `agents/fraud_detector.py` — Claude + JSON RAG

Port of [parent fraud_detector.py](../backend/agents/fraud_detector.py). Replace the Qdrant call with `rag_service.search(claim_description, k=3)` against `past_claims.json`. Same `STATUS / CONFIDENCE / FINDINGS / RECOMMENDATIONS` output format — keep the regex parser intact.

### API Endpoints (`backend/main.py`)

Trimmed from the parent's set ([api-reference.md](../docs/api-reference.md)) to what the 2-tab UI actually needs:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/claims/submit` | multipart: form fields + 1..N images |
| `GET`  | `/api/claims` | list all (Dashboard) |
| `GET`  | `/api/claims/{id}` | full claim + agent results (ClaimDetail polls this) |
| `GET`  | `/api/claims/{id}/image/{filename}` | serve uploaded image to the canvas overlay |
| `POST` | `/api/claims/{id}/review` | human-in-the-loop decision (`approve` / `reject` / `request_info` / `escalate` + reviewer note) |
| `GET`  | `/api/health` | sanity check |

In-memory dict for claims store — acceptable for a single-session demo. (No DB.)

---

## Frontend (2-tab) — UI parity with parent

**Hard requirement: visual look-and-feel must match the parent project.** Students seeing both side-by-side should recognise it as the same product family — only the agent stack underneath differs.

Concretely, we **copy and reuse, not redesign**:

| Element | Source in parent | Reuse strategy |
|---|---|---|
| Global CSS (colour tokens, typography, spacing, shadows) | [`frontend/src/styles.css`](../frontend/src/styles.css) — `:root` vars `--primary-color: #3b82f6`, `--success-color: #10b981`, `--warning-color: #f59e0b`, `--error-color: #ef4444`, etc. | **Copy `styles.css` verbatim** into the new project, then extend only with any new classes the damage-visualisation overlay needs. |
| Header (blue gradient banner + Bot icon + title + subtitle) | [`App.jsx:11-22`](../frontend/src/App.jsx#L11-L22) — `lucide-react`'s `Bot` icon, `.header` gradient class | **Copy structure 1:1**; change only the subtitle to *"Azure-Powered Insurance Claims Processing with Computer Vision"*. |
| Tab navigation pattern | [`App.jsx:25-46`](../frontend/src/App.jsx#L25-L46) — `.tabs` / `.tab-button` / `active` modifier, emoji+label tabs | **Same component pattern**, two buttons: `📝 Submit Claim` and `📊 Claims Dashboard`. (Drop `💬 Chat` and `🔍 Review Queue` tabs from parent.) |
| Claim card grid | [`Dashboard.jsx`](../frontend/src/components/Dashboard.jsx) — card layout, status badges, progress bars | Reuse the JSX shape and CSS classes; just point at the new API. |
| Per-agent result cards (status / confidence / findings) | [`ClaimStatus.jsx`](../frontend/src/components/ClaimStatus.jsx) — `passed` / `failed` / `warning` colour coding, confidence pill | Reuse class names and JSX shape; render the 6 Azure agents through the same component. |
| Human-in-loop review controls | [`ReviewDetail.jsx`](../frontend/src/components/ReviewDetail.jsx) — Approve / Reject / Request Info / Escalate buttons, reviewer-note textarea | Inline a trimmed version into `ClaimDetail.jsx`; reuse the button/input styles. |
| Icons | `lucide-react` (already used in parent) | Same library, same icon vocabulary. |

**What's new (Azure-specific UI):**
- `DamageVisualization.jsx` — canvas overlay drawing bounding boxes on the uploaded car photo. New component, but styled with the existing `--primary-color` / `--warning-color` tokens so it feels native.
- A "Powered by Microsoft Azure AI" sub-line in the header footer and small Azure / Foundry / Computer Vision logo chips on `ClaimDetail.jsx` — purely to reinforce the lecture's Azure-stack theme. Uses parent CSS classes.

**Side-by-side comparison test:** During build, place the parent's UI and the new MVP's UI in two browser windows. The header, fonts, colour palette, card shadows, badge styles, and tab bar should be visually indistinguishable. The only obvious differences should be: (1) two tabs instead of three, (2) the new bounding-box overlay on the claim detail view.

---



**Tab 1 — Submit Claim** (`ClaimSubmissionForm.jsx`)
- Fields: policy_number, claimant_name, claimant_email, incident_date, claim_type (default: `auto_collision`), claim_amount, description.
- File inputs: **car damage photos** (multi, image/*) + **supporting docs** (multi, image/pdf — bills, police reports).
- On submit → POST `/api/claims/submit` → redirect into Dashboard, highlight the new claim.

**Tab 2 — Dashboard** (`Dashboard.jsx` + `ClaimDetail.jsx`) — *also hosts the human-in-the-loop review for complicated cases*
- List view: claim_id, claimant, type, amount, current stage, final status. Polls every 3s while any claim is in-progress.
- Filter chips at top: **All / Approved / Rejected / Needs Review**. Claims with `NEEDS_REVIEW` are visually highlighted (amber border) — they form the implicit "review queue" without needing a separate tab.
- Click row → `ClaimDetail.jsx`:
  - Top: original car photo with **`DamageVisualization.jsx`** overlay of bounding boxes + labels (canvas, drawn from `damage_regions` returned by CV).
  - Per-agent cards (6) with status / confidence / findings — same visual language as parent [`ClaimStatus.jsx`](../frontend/src/components/ClaimStatus.jsx).
  - **CV showcase ribbon**: side strip showing the raw CV outputs (tags, dense captions, OCR text, detected brand) — explicit teaching panel for the lecture.
  - Final decision card (APPROVED / REJECTED / NEEDS_REVIEW) with the adjuster-style summary.
  - **Human-in-the-loop panel** — appears only when status is `NEEDS_REVIEW`. Shows AI recommendation, fraud/policy flags, then four action buttons: **Approve / Reject / Request More Info / Escalate**, plus a free-text reviewer note. Submitting calls `POST /api/claims/{id}/review` which writes the human decision into the claim record (overrides the AI verdict and appends an audit entry).
  - Drawn from the patterns in parent [`ReviewDetail.jsx`](../frontend/src/components/ReviewDetail.jsx), but inlined into ClaimDetail rather than a separate page.

No chat tab — would add UX complexity that doesn't serve the CV-demo objective.

---

## Critical Files

| File | Status | Notes |
|---|---|---|
| `AI-CLAIMS-Orchestrator-Azure/backend/services/azure_vision.py` | **new** | Single source of truth for all CV calls |
| `AI-CLAIMS-Orchestrator-Azure/backend/services/claude_client.py` | **new** | Anthropic SDK pointed at Foundry |
| `AI-CLAIMS-Orchestrator-Azure/backend/services/rag_service.py` | **new** | sentence-transformers + numpy cosine |
| `AI-CLAIMS-Orchestrator-Azure/backend/agents/car_damage_analyzer.py` | **new** | The headline agent for the demo |
| `AI-CLAIMS-Orchestrator-Azure/backend/agents/document_analyzer.py` | port + rewrite | Azure Read replaces Gemini Vision |
| `AI-CLAIMS-Orchestrator-Azure/backend/agents/fraud_detector.py` | port | Reuse parent logic; swap Qdrant for `rag_service` |
| `AI-CLAIMS-Orchestrator-Azure/backend/agents/{validator,policy_checker,decision_maker}.py` | port | Swap `ChatGoogleGenerativeAI` → `claude_client.complete()` |
| `AI-CLAIMS-Orchestrator-Azure/backend/orchestrator.py` | **new** (simpler) | Plain async pipeline, no Opus |
| `AI-CLAIMS-Orchestrator-Azure/backend/main.py` | **new** (trimmed) | 5 endpoints only |
| `AI-CLAIMS-Orchestrator-Azure/backend/data/*.json` | **new** | Dummy RAG dataset |
| `AI-CLAIMS-Orchestrator-Azure/frontend/src/components/DamageVisualization.jsx` | **new** | Canvas bounding-box overlay |
| `AI-CLAIMS-Orchestrator-Azure/frontend/src/components/ClaimDetail.jsx` | **new** | Shows raw CV outputs prominently for lecture; embeds the Human-in-Loop review panel when `status == NEEDS_REVIEW` |
| `AI-CLAIMS-Orchestrator-Azure/.env.example` | **new** | `AZURE_CV_ENDPOINT`, `AZURE_CV_KEY`, `FOUNDRY_ENDPOINT`, `FOUNDRY_API_KEY` |

---

## Reused Patterns from Parent

- **Pydantic schemas** for `ClaimSubmission`, `AgentResult`, `ClaimAnalysis` — copy from [`backend/models/schemas.py`](../backend/models/schemas.py) (only field renames if any).
- **Regex response parsing** (`STATUS:`, `CONFIDENCE:`, etc.) from [`fraud_detector.py:56-69`](../backend/agents/fraud_detector.py#L56-L69) — works for any LLM that follows the format.
- **In-memory claims dict + status callback** orchestration pattern from [`orchestrator.py:92-120`](../backend/orchestrator.py#L92-L120).
- **Vite proxy + axios pattern + colour vars** from [`frontend/vite.config.js`](../frontend/vite.config.js) and [`frontend/styles.css`](../frontend/styles.css).

---

## Dependencies

**Backend (`requirements.txt`):**
```
fastapi
uvicorn[standard]
pydantic
pydantic-settings
python-multipart
anthropic                          # talks to Foundry via base_url
azure-ai-vision-imageanalysis      # v4.0 SDK
httpx                              # v3.2 Brands REST call + general
sentence-transformers              # local embeddings for RAG
numpy
Pillow
```

**Frontend (`package.json`):** `react`, `react-dom`, `vite`, `@vitejs/plugin-react`, `axios`, `lucide-react`, `uuid`. (Lean — no UI library.)

---

## Verification Plan

End-to-end smoke test for the demo:

1. **Backend boot** — `uvicorn main:app --reload --port 8000` from `backend/`. Verify `/api/health` returns 200. Confirm startup logs show: Azure CV client OK, Claude/Foundry reachable, RAG service loaded N policies + M past claims with embeddings.
2. **Frontend boot** — `npm run dev` from `frontend/`. Visit `http://localhost:3000`, see two tabs.
3. **Happy path** — submit a sample claim with `sample_documents/car_damage_*.jpg`:
   - Dashboard shows claim with progressing stage labels (Validating → Damage Analysis → OCR → Fraud → Policy → Decision).
   - ClaimDetail renders bounding boxes on the photo over the detected damage regions.
   - CV showcase ribbon shows tags (`car`, `vehicle`, `damaged`, …), dense captions, OCR text from any supporting bill, detected brand.
   - Each agent card shows STATUS / CONFIDENCE / FINDINGS populated.
   - Final decision card visible.
4. **Failure-mode demos** — submit a claim with (a) a non-car photo (CV correctly tags as `non-car`, decision = NEEDS_REVIEW), (b) a claim amount > $50k with minor damage (fraud agent flags inconsistency).
5. **Standalone CV demo (lecture aid)** — `curl` the `/api/cv/demo` debug endpoint with a sample image to dump raw Azure CV JSON for the slide.
6. **Manual checks per agent** — confirm Claude responses parse correctly into `AgentResult` (regex match for STATUS / CONFIDENCE).

---

## Out of Scope (intentional)

- Opus workflow YAML (dropped — replaced by plain async pipeline).
- Qdrant or any external vector DB (replaced with local JSON + cosine).
- Chat / guided-submission agents (parent's ChatAgent, GuidedChatAgent) — not core to the CV demo.
- Separate human-review-queue tab — replaced by an inline review panel inside Dashboard → ClaimDetail (still serves the human-in-loop story without a third tab).
- Adjuster-brief, audit-log, workflow-state endpoints — parent has them; not needed for the lecture (a minimal in-memory audit list is kept on each claim record for review traceability).
- Production hardening: auth, persistent DB, multi-tenancy, observability — explicitly an MVP demo.
- Remote deployment — explicitly localhost-only for this MVP.

---

## Confirmed Decisions

1. **Localhost-only** — runs entirely on the lecture laptop (backend `:8000`, frontend `:3000`). No cloud deploy.
2. **Two tabs only** — Submit Claim + Dashboard; the human-in-loop review for complicated cases lives **inside Dashboard → ClaimDetail** for `NEEDS_REVIEW` claims (no third tab).
3. **Sample documents** — copy directly from parent [`sample_documents/`](../sample_documents/) into the new project's `sample_documents/` folder during setup. No new images need to be sourced.
4. **No Document Intelligence resource** — Azure CV Read API on the existing Computer Vision resource is sufficient for the MVP's invoice/bill OCR. Can be added later if structured field extraction is needed.
