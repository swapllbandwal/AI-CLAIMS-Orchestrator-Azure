# AI Claims Orchestrator — Azure MVP

An insurance-claims processing demo built on the **Microsoft Azure AI stack** —
**Azure Computer Vision** for car-damage image analysis & OCR, and **Claude
Sonnet 4.6** served via **Microsoft AI Foundry** for the orchestration LLM.

> Built for a guest lecture at **Amity University** — *Industrial Image
> Processing / Machine Vision / APIs & Platforms for CV applications*.
> The companion (parent) project [`../`](../) implements the same domain on
> Google Gemini + Qdrant; this Azure MVP is the side-by-side comparison.

---

## What this MVP demonstrates

| # | Capability | Azure service |
|---|---|---|
| 1 | Car damage detection, captioning, dense regions, tags, object boxes | **Azure Computer Vision — Image Analysis 4.0** |
| 2 | OCR on repair invoices / police reports / receipts | **Azure Computer Vision — Read API** |
| 3 | Vehicle brand / logo detection | **Azure Computer Vision — v3.2 Brands** |
| 4 | LLM reasoning / decisioning / adjuster brief | **Claude Sonnet 4.6** on **Microsoft AI Foundry** |
| 5 | RAG over past claims and policies | **Local JSON + sentence-transformers** (no external DB) |
| 6 | Human-in-the-loop for borderline cases | Inline review panel in the dashboard |

---

## Architecture

```
┌─────────────────────┐         ┌─────────────────────────────────────────┐
│  React + Vite UI    │  HTTP   │   FastAPI Backend                       │
│  (2 tabs)           │ ──────► │                                         │
│  • Submit Claim     │         │   ┌──────────────────────────────────┐  │
│  • Dashboard +      │         │   │  6-step async orchestrator       │  │
│    Human-in-loop    │         │   │                                  │  │
└─────────────────────┘         │   │  1. Validator        (Claude)    │  │
                                │   │  2. Car Damage CV    (Azure CV)──┼──┼──► Azure Computer Vision
                                │   │  3. Document OCR     (Azure CV)──┼──┼──►  (Image Analysis 4.0
                                │   │  4. Fraud Detector   (Claude+RAG)│  │      + Read + v3.2 Brands)
                                │   │  5. Policy Checker   (Claude+RAG)│  │
                                │   │  6. Decision Maker   (Claude)────┼──┼──► MS Foundry / Claude
                                │   └──────────────────────────────────┘  │
                                │   ┌──────────────────────────────────┐  │
                                │   │  RAG (in-memory cosine)          │  │
                                │   │  data/policies.json              │  │
                                │   │  data/past_claims.json           │  │
                                │   │  data/fraud_patterns.json        │  │
                                │   └──────────────────────────────────┘  │
                                └─────────────────────────────────────────┘
```

---

## Prerequisites

- **Python 3.10+**
- **Node.js 18+** with `npm`
- An **Azure Computer Vision** resource (endpoint + key)
- A **Microsoft AI Foundry** Claude deployment (endpoint + key)
- ~80 MB free disk space (for the sentence-transformers embedding model, downloaded once on first run)

> ⚠️ Default ports: backend **8005**, frontend **3000**. The parent project
> uses **8000** for its backend, so the two can run side-by-side if you wish.

---

## Setup

### 1. Environment

From the project root (`AI-CLAIMS-Orchestrator-Azure/`):

```bash
cp .env.example .env
```

Open `.env` and replace `REPLACE_WITH_...` with your real keys.

### 2. Backend

```bash
cd backend

# Create + activate venv
python -m venv venv
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# macOS/Linux:
# source venv/bin/activate

pip install -r requirements.txt

# Start the API (loads RAG embeddings on first call, ~10s on first boot)
uvicorn main:app --reload --host 0.0.0.0 --port 8005
```

Verify: open <http://localhost:8005/api/health> — should return `status: ok`
with the count of policies and past claims loaded.

### 3. Frontend

In a **separate terminal**, from `AI-CLAIMS-Orchestrator-Azure/frontend/`:

```bash
npm install
npm run dev
```

Open <http://localhost:3000>.

---

## Demo walkthrough (lecture script)

The folder [`sample_documents/`](./sample_documents/) was copied from the parent
project — use the **Genhine case approval/** subfolder for the happy-path demo
(`Car Damage photo.png`, `repair_estimate.jpg`, `police_report.pdf`).

1. **Open the Submit Claim tab.**
2. Fill the form. Use **`POL-AUTO-1001`** (an active policy in the dummy data),
   claimant *Rajesh Kumar*, amount *$2,400*, claim type *Auto Collision*, and a
   plausible description. Set vehicle to *Maruti Suzuki Swift 2022*.
3. **Upload `Car Damage photo.png`** under "Car damage photos" and the
   `repair_estimate.jpg` + `police_report.pdf` under "Supporting documents".
4. Click **Submit Claim & Run AI Analysis**. You land on the dashboard.
5. Click into the new claim. Watch the progress bar advance through the 6
   stages (≈ 30-60 s end-to-end depending on Azure latency):
   - *Validating* → *Damage Analysis* → *Document Analysis* → *Fraud Check*
     → *Policy Check* → *Decision Pending* → final status.
6. **Talking points to highlight to students:**
   - The **bounding-box overlay** is the Azure CV `Objects` + filtered
     `DenseCaptions` output drawn on a `<canvas>` — pure CV, no LLM.
   - The **CV Showcase ribbon** on the right shows raw Azure CV outputs
     (caption, tags, dense captions, brand, OCR text). Useful for explaining
     what each Vision feature returns.
   - The **agent cards** below show how the LLM (Claude) reasons over the CV
     evidence + RAG context to produce a final decision.
   - For a borderline case (try claim amount *$24,000* with a minor-damage
     photo), the Decision Maker returns **Needs Review** → the inline
     human-in-loop panel appears. Approve / reject / request info / escalate.

### Comparing with the parent project

Open the parent project's UI side-by-side. Note that **header, tabs, cards,
status badges, progress bar, and agent-result panels are visually identical**.
The differences students will see are:
- Only 2 tabs (vs. 3 in parent — chat tab dropped).
- The "Microsoft Azure AI" chip in the header.
- The bounding-box overlay + CV Showcase panel (Azure-specific UX).

The underlying stack is **completely different**: this MVP is Azure CV +
Foundry/Claude + local RAG; the parent is Gemini + Qdrant + Opus workflow.

---

## Project structure

```
AI-CLAIMS-Orchestrator-Azure/
├── README.md
├── plan.md
├── .env.example
├── .gitignore
├── backend/
│   ├── main.py                      FastAPI app, 5 endpoints
│   ├── orchestrator.py              6-step async pipeline
│   ├── config.py                    pydantic-settings → .env
│   ├── requirements.txt
│   ├── agents/
│   │   ├── _common.py               Shared STATUS/CONFIDENCE response parser
│   │   ├── validator.py
│   │   ├── car_damage_analyzer.py   ★ Azure CV 4.0 + v3.2 Brands
│   │   ├── document_analyzer.py     ★ Azure CV Read OCR
│   │   ├── fraud_detector.py        Claude + RAG over past_claims.json
│   │   ├── policy_checker.py        Claude + RAG over policies.json
│   │   └── decision_maker.py        Final verdict
│   ├── services/
│   │   ├── azure_vision.py          ★ Three CV verbs in one wrapper
│   │   ├── claude_client.py         Anthropic SDK pointed at Foundry
│   │   └── rag_service.py           sentence-transformers + numpy cosine
│   ├── models/schemas.py            Pydantic types
│   ├── utils/file_storage.py        Per-claim upload folders
│   └── data/                        Dummy RAG dataset
│       ├── policies.json
│       ├── past_claims.json
│       └── fraud_patterns.json
├── frontend/
│   ├── package.json                 Lean: react, vite, axios, lucide-react
│   ├── vite.config.js               Proxy /api → :8005
│   ├── index.html
│   └── src/
│       ├── App.jsx                  2 tabs (Submit Claim, Dashboard)
│       ├── main.jsx
│       ├── styles.css               Copied verbatim from parent + Azure additions
│       ├── services/api.js          Axios client
│       └── components/
│           ├── ClaimSubmissionForm.jsx
│           ├── Dashboard.jsx
│           ├── ClaimDetail.jsx
│           └── DamageVisualization.jsx   ★ Canvas bbox overlay
└── sample_documents/                Copied from parent project for the demo
```

---

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/claims/submit` | multipart: form fields + images + documents |
| `GET`  | `/api/claims` | List all claims (Dashboard) |
| `GET`  | `/api/claims/{id}` | Full claim record + agent results |
| `GET`  | `/api/claims/{id}/image/{filename}` | Serve uploaded image |
| `POST` | `/api/claims/{id}/review` | Human-in-loop decision |
| `GET`  | `/api/health` | Sanity check |

---

## Out of scope (intentional)

- Authentication, persistent database, multi-tenancy — single-process
  in-memory store is fine for the lecture demo.
- Opus workflow YAML (parent project) — replaced by plain async orchestration.
- External vector DB (Qdrant in parent) — replaced by local JSON + cosine.
- Chat / guided-submission agents from the parent — not needed for the CV demo.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `/api/health` shows `degraded` | Backend booted but orchestrator init failed (e.g. invalid Azure CV endpoint) | Check backend logs; verify keys in `.env` |
| Submit hangs at "Damage Analysis" | Azure CV throttle or credentials wrong | Inspect backend log; the request times out at 30s per call |
| `port 8005 already in use` | Parent project still running | Stop the parent backend first |
| `port 3000 already in use` | Parent frontend still running | Stop it, or change Vite port |
| First request is very slow | sentence-transformers is downloading the embedding model | Wait — only happens once |

---

## Credits

Built on top of the parent project's architecture and visual design — see
[`../`](../) for the original Gemini + Qdrant implementation.
