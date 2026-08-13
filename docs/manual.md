# Veridian — Owner's Manual & Access Guide

Real-Time Risk Intelligence for Smarter Reinsurance

This document explains what the app does, how to access every part of it, how the
system works under the hood, the secret keys it uses (and where to replace them),
and how to push the code to GitHub and rework it later.

---

## 1. Live URLs (open these to use the app)

- Public Submission Portal (landing + request form):
  https://veridian-submission.preview.emergentagent.com/

- Submission Form (direct link):
  https://veridian-submission.preview.emergentagent.com/submit

- Insights Dashboard Login (restricted, OTP login):
  https://veridian-submission.preview.emergentagent.com/insights/login

Note: the current address contains "emergentagent.com" because this is the
development preview URL. To use your own project name / custom domain, see
Section 8 (Changing the website address).

---

## 2. What Veridian does (in plain language)

Veridian is a Catastrophe (CAT) risk analytics platform for reinsurance decision
support. It has two clearly separated areas:

- Public Submission Portal — anyone can submit a portfolio (a "book of business"
  made of insurance policies). No login is required. They get back only a
  reference ID. They do NOT see the risk results.

- Insights Dashboard — a private area for authorized reviewers only. Access is
  protected by real email one-time-password (OTP) login, limited to a fixed
  whitelist of email addresses. Reviewers see all submissions, full analytics,
  a treaty simulator, capital-reserve checks, and an AI recommendation.

This split is intentional: submitters send data in; only underwriters see the
computed intelligence.

---

## 3. How to use the Public Submission Portal (no login)

1. Open the landing page and click "Submit a Portfolio" (or go to /submit).
2. Fill in Submitter details: full name, email (required), organization (optional).
3. Add one or more Policies (up to 20). For each policy provide:
   - Property address (used for live geocoding)
   - Property type: residential / commercial / industrial / mixed-use
   - Construction type: Concrete / Steel / Masonry / Wood / Mixed
   - Year built (1800 - current year)
   - Sum insured in USD (must be greater than 0)
   - Peril focus (optional tag, e.g. "flood-prone")
4. Click "Run Risk Analysis". A live processing view streams each pipeline step
   (geocoding, per-policy scoring, aggregation, NatCat score, storage).
5. You receive a Confirmation screen with a Reference ID (e.g. VRD-A1B2C3D4).
   Keep this ID. Results are only visible to authorized reviewers in the Dashboard.

---

## 4. How to access the Insights Dashboard (OTP login)

Access is restricted to these whitelisted email addresses ONLY:
- aman7339811186@gmail.com
- amankunawat4u@gmail.com
- amanbaba.kumawat@gmail.com

Login steps:
1. Open /insights/login.
2. Enter one of the whitelisted email addresses and click "Send code".
   - If the email is not on the whitelist, you are rejected with
     "This email is not authorized to access Insights".
3. Check that email inbox. You will receive a real 6-digit code (valid 5 minutes).
4. Enter the 6-digit code and click "Verify & enter".
5. You are now signed in (a secure httpOnly session cookie is set, valid 12 hours).

Extra rules:
- "Resend code" is available, limited to a maximum of 3 sends per 10 minutes.
- No password is ever used - this is OTP-only login by design.

---

## 5. Inside the Insights Dashboard

Submissions Inbox
- A table of every submission: reference ID, submitter, date, total sum insured,
  NatCat composite score (color-coded), and status.
- Click any row to open its detailed analytics.

Submission Detail / Analytics
- Top metrics: total sum insured, aggregate expected CAT loss, NatCat composite,
  number of regions.
- Portfolio Exposure - by Region: bar chart of sum insured per region.
- Average Peril Risk Scores: bar chart across flood, seismic, wildfire,
  wind/storm, theft, and property condition.
- Reinsurance Treaty Simulator (Quota Share):
  - Cession % slider and Attachment Point (retention floor) slider.
  - Recalculates Retained Loss, Ceded Loss and Ceded Premium estimate in real time.
- Risk Appetite / Capital Reserve Check:
  - Set a capital reserve threshold. If modeled retained loss breaches it, a clear
    red "BREACHED" flag appears; otherwise a green "Within reserve" flag.
- AI Underwriting Insight (Claude):
  - Click "Generate recommendation" to stream a real AI-authored underwriting /
    treaty-efficiency recommendation computed from the actual numbers.
- Per-Policy Risk Breakdown: full table of every policy's individual peril scores,
  composite score, and expected loss.
- Reviewer Action: add a note and mark the submission as Reviewed or Flagged.

Portfolio-Wide View (top of the Dashboard)
- Total submissions, total exposure under management, average NatCat score, and
  the count of capital-reserve breaches across all submissions.

---

## 6. How the system works (architecture)

Frontend
- React (Create React App) + Tailwind CSS. Pages: Landing, Submit, Login,
  Dashboard, Submission Detail. Charts use Recharts; animation uses Framer Motion;
  icons use lucide-react; toasts use sonner.

Backend
- Python FastAPI (async), Pydantic validation. All API routes are prefixed /api.
- Storage is local JSON files (no database), exactly as specified:
  - backend/data/submissions.json  (all submissions + computed outputs)
  - backend/data/historical_claims.json  (seed reference data)

Submission pipeline (streamed live via Server-Sent Events)
1. Geocoding - each policy address to latitude/longitude.
2. Per-policy risk scoring (0-100) for six perils.
3. Portfolio aggregation - sum insured by region and by peril; aggregate expected
   loss = sum of (sum_insured x normalized risk factor).
4. NatCat composite score - weighted portfolio-level score.
5. Persist the full submission to submissions.json.

Real external data sources (live, no key needed)
- Geocoding: Nominatim (OpenStreetMap), with Open-Meteo geocoding as fallback.
- Seismic risk: USGS Earthquake API (earthquake density near the location).
- Wind/storm risk: Open-Meteo Archive (historical max wind speed).

Documented simulated stubs (no free real-time API available) - clearly commented
in the code as returning a default 30-50 band:
- flood_risk, wildfire_risk, theft_risk.

Authentication
- Real email OTP via the managed email integration (Resend).
- On success a JWT is issued in an httpOnly cookie (12-hour expiry).

AI
- Anthropic Claude (Sonnet) generates the underwriting recommendation from the
  computed portfolio numbers - a real API call, not canned text.

---

## 7. Secret keys & environment variables (WHERE TO REPLACE THEM)

IMPORTANT: The .env files below are NOT pushed to GitHub (they are git-ignored).
Never paste these values into public code, issues, or chat.

File: backend/.env
- MONGO_URL      : Local MongoDB connection string (present by default; the core
                   data lives in JSON files, not Mongo). Leave as-is locally.
- DB_NAME        : Database name (leave as-is locally).
- CORS_ORIGINS   : Allowed origins for the API. "*" for development.
- EMERGENT_EMAIL_KEY : Key for the managed email (Resend) proxy that delivers OTP
                   emails. TO REWORK WITH YOUR OWN RESEND ACCOUNT: replace the
                   managed email call in backend/server.py (function
                   `send_otp_email`, which posts to the Emergent email proxy) with
                   a direct Resend call to https://api.resend.com/emails using your
                   own RESEND_API_KEY, and store that key here instead.
- EMAIL_FROM_NAME : The sender display name shown on OTP emails ("Veridian").
- EMERGENT_LLM_KEY : Universal key that powers the Claude AI call. TO REWORK WITH
                   YOUR OWN ANTHROPIC ACCOUNT: replace with your ANTHROPIC_API_KEY
                   and switch the AI call in backend/server.py (endpoint
                   `/api/submissions/{id}/ai-insight`) to Anthropic's SDK /
                   https://api.anthropic.com/v1/messages.
- WHITELIST_EMAILS : Comma-separated list of emails allowed to log in to Insights.
                   Edit this to add/remove authorized reviewers.
- JWT_SECRET     : Secret used to sign login session tokens. REPLACE with a long
                   random string in production.

File: frontend/.env
- REACT_APP_BACKEND_URL : The base URL the frontend uses to reach the backend API.
                   Do not hardcode API URLs anywhere else; always use this variable.

Key mapping vs. the original spec (for a standalone rework):
- Original spec wanted RESEND_API_KEY  -> currently served by EMERGENT_EMAIL_KEY.
- Original spec wanted ANTHROPIC_API_KEY -> currently served by EMERGENT_LLM_KEY.
The current keys let the app work immediately with no external signup. Swap them
for your own provider keys only when you move fully off the managed integrations.

---

## 8. Changing the website address (remove "emergent")

The current address is a development preview URL, so it contains
"emergentagent.com". To publish under your own project name / custom domain, use
the platform's Deploy flow and attach a custom domain. The exact in-app steps are
provided separately in the platform guidance (Deploy -> custom domain). After a
custom domain is attached, update frontend/.env REACT_APP_BACKEND_URL if the
backend is served from that domain.

---

## 9. Pushing the code to GitHub

- Use the platform's built-in "Save to GitHub" feature to push all folders.
- The .env files and other secrets are git-ignored and will NOT be pushed, so your
  keys stay private. Add a `.env.example` (placeholders only) for collaborators.
- A user-supplied Personal Access Token pasted into chat should be revoked/rotated
  afterward, since it was exposed. Prefer the platform's GitHub connection.

---

## 10. Reworking / running locally later

Backend (FastAPI):
- cd backend
- pip install -r requirements.txt
- create backend/.env from the values in Section 7
- the server runs on port 8001 (managed by supervisor in this environment)

Frontend (React):
- cd frontend
- yarn install
- create frontend/.env with REACT_APP_BACKEND_URL pointing at your backend
- yarn start  (development)  or  yarn build  (production bundle)

Data files (edit or reset the "database"):
- backend/data/submissions.json    -> all stored submissions
- backend/data/historical_claims.json -> seed reference data
Resetting submissions.json to `[]` clears all submissions.

---

End of guide.
