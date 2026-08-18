# Here are your Instructions
# Veridian

## Problem Statement

Catastrophic-property reinsurance teams typically assess portfolio exposure and individual policy risk using static spreadsheets and disconnected data sources, making it slow and error-prone to answer basic questions like "how concentrated is our peril exposure," "what should this policy's premium actually be," or "is this application consistent and fairly priced." Veridian solves this by turning a property submission into a live, data-grounded risk assessment — combining real public hazard data, a transparent premium/eligibility calculation, and an AI reasoning layer — so underwriters get portfolio-level visibility and per-policy justification in one place instead of manual cross-referencing.

## What the Solution Does

Veridian is a portfolio-level CAT (catastrophe)/reinsurance analytics platform with two sides:

- **Public submission portal (no login)** — applicants (or underwriters on their behalf) submit catastrophic-property applications with property, financial, coverage, and claims data.
- **Underwriter Insights Dashboard (email-OTP authenticated)** — where the actual product lives:
  - **Submission inbox/queue** with search, filter, sort, pagination, and a claim/release/reassign review workflow
  - **Per-policy risk breakdown** — real hazard scores computed per submitted address
  - **Portfolio exposure dashboard** — regional breakdown, peril concentration, risk heatmap (clustered map)
  - **Reinsurance Treaty Simulator** — interactive cession % and attachment point sliders with live retained/ceded calculations
  - **Risk Appetite / Capital Reserve Check** — adjustable threshold slider with breach flagging
  - **AI Insight panel** — streamed narrative reasoning per submission, plus AI-suggested eligible coverage amounts per policy that the underwriter can review and manually override/save
  - **Activity/audit trail**, branded PDF reports (submitter receipt + full underwriter report), CSV export, and email digest notifications

A background pipeline runs automatically on every submission: geocode the address, pull real hazard data from public APIs, compute a composite NatCat risk score per policy, and calculate a transparent premium/eligibility figure — all before a human ever opens the record.

## Technologies Used

- **Frontend:** React (multi-page app: submission flow, underwriter dashboard, submission detail, treaty simulator, etc.), Leaflet + marker clustering for the exposure heatmap
- **Backend:** FastAPI (Python), Server-Sent Events (SSE) for streaming the AI narrative
- **Storage:** JSON file-based storage (no database) — intentionally lightweight for MVP scope
- **Auth:** Email one-time-password (OTP) for the underwriter portal
- **External risk-data APIs (all free/public tier):**
  - Nominatim / Open-Meteo — geocoding
  - USGS — earthquake and elevation data
  - NOAA/NWS — weather data
  - FEMA flood layer — flood risk
  - NASA FIRMS — wildfire data (requires free API key)
  - OpenStreetMap Overpass — infrastructure/proximity data
  - Zippopotam — location/postal lookups
- **AI/LLM:**
  - **Claude** (via Emergent's managed key) — streaming AI Insight narrative and per-policy eligible-amount reasoning
  - Groq (`llama-3.3-70b-versatile`) — primary free LLM for chat/suggestion flows
  - Google Gemini (`gemini-2.0-flash`) — automatic fallback if Groq is unavailable
  - Both providers are called through a single abstracted `call_llm()` function so the reasoning/flagging logic is provider-agnostic
- **Dev tooling:** Emergent (initial scaffold), VSCode with the Claude Code extension (iterative refinement, bug fixes, feature additions)

## Where Claude Is Used

1. **AI Insight panel** — the "Generate recommendation" flow streams a Claude-generated narrative explaining a submission's risk profile, grounded in that policy's actual computed risk scores (not generic insurance text).
2. **Per-policy eligible-amount suggestions** — Claude returns a structured JSON block (parsed after the stream completes) suggesting a per-policy eligible coverage amount with reasoning tied to the real risk data, which the underwriter can accept or manually override via the eligible-amount save endpoint.
3. **Development process** — Claude Code (VSCode extension) was used throughout to refine the Emergent-generated scaffold: fixing bugs (e.g. PDF text truncation, mislabeled sections), adding the multi-step submission form, wiring new fields into risk scoring, and extending the AI Insight prompt.

## Folder/File Structure

> ⚠️ Not fully confirmed — the tool-output blocks showing your exact repo tree didn't survive the export I have access to. Structure below reflects what's confirmed from referenced file paths (`backend/server.py`, `frontend/src/pages/Submit.jsx`, `frontend/src/pages/SubmissionDetail.jsx`). Replace with your actual tree, or send me a folder listing and I'll finalize this section.

```
veridian/
├── backend/
│   └── server.py          # FastAPI app — endpoints, risk scoring, AI insight, storage I/O
├── frontend/
│   └── src/
│       └── pages/
│           ├── Submit.jsx           # Public application submission (multi-step)
│           ├── SubmissionDetail.jsx # Underwriter detail view — risk breakdown, AI panel
│           └── ...                  # Dashboard, inbox, treaty simulator, capital check, etc.
├── data/                  # JSON file storage (submissions, activity trail)
└── README.md
```

## How to Run the Application

> ⚠️ Confirm exact commands against your repo's actual `package.json` / requirements setup — these are the standard steps for this stack.

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn server:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm start
```

The frontend expects the backend API URL configured via an environment variable (check `frontend/.env` or equivalent) — update it if your backend isn't running on the default local port.

## Credentials / API / Configuration Prerequisites

Do **not** commit real values for these — use a local `.env` file (excluded via `.gitignore`) or your platform's secrets manager.

| Variable | Purpose | Required? |
|---|---|---|
| `GROQ_API_KEY` | Primary free LLM for chat/suggestions | Yes (free signup at console.groq.com) |
| `GEMINI_API_KEY` | Fallback LLM if Groq is unavailable | Recommended |
| `NASA_FIRMS_API_KEY` | Wildfire risk data | Yes (free signup at firms.modaps.eosdis.nasa.gov) |
| `EMERGENT_LLM_KEY` | Claude access via Emergent's managed key (AI Insight narrative) | Yes, if using this integration path |
| Email/SMTP config (host, port, sender credentials) | Sends OTP codes for underwriter login | Yes |

No API key is required for Nominatim, USGS, NOAA, FEMA, Overpass, or Zippopotam — all public/free without registration. No database credentials are needed since storage is JSON-file based.

---
*This README was reconstructed from project conversation history. Sections marked ⚠️ should be verified against the current state of the repository before submission.*
