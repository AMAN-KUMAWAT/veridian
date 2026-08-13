# Veridian — Product Requirements & Progress

## Problem statement
Veridian is a Catastrophe (CAT) risk analytics platform for reinsurance decision support.
Two areas: a public Submission Portal (no login) and a protected Insights Dashboard
(real email-OTP auth, whitelist-restricted). Frontend React+Tailwind, backend FastAPI (async,
Pydantic), storage = local JSON files (no DB). Real external APIs: Nominatim/Open-Meteo geocoding,
USGS seismic, Open-Meteo wind. AI: Anthropic Claude (Emergent LLM key). Email/OTP: managed Resend.

## Architecture
- Frontend: React (CRA) + Tailwind, Recharts, Framer Motion, lucide-react, sonner. Pages: Landing,
  Submit, Login (OTP), Dashboard, SubmissionDetail, NotFound; global ErrorBoundary.
- Backend: FastAPI /api routes. Auth via OTP -> JWT in httpOnly cookie. SSE-streamed pipeline.
  PDF/CSV via fpdf2/csv. Data in backend/data/*.json.

## User personas
- Public submitter (broker/insurer): submits a book of business, gets a receipt. No results shown.
- Authorized reviewer (underwriter, whitelisted email): reviews submissions, runs treaty/capital
  analysis and AI insight, marks Reviewed/Flagged.

## Core requirements (static)
- Whitelist OTP auth; public submission portal; per-policy risk scoring (real APIs + documented
  stubs); portfolio aggregation; NatCat composite; JSON persistence; reviewer analytics.

## Implemented
- 2026-08: MVP — public portal (landing/form/SSE processing/confirmation), OTP login (real email),
  inbox + detail (exposure, loss model, treaty simulator, capital reserve, AI insight, review).
  Pushed to GitHub (AMAN-KUMAWAT/veridian). Owner guide PDF generated.
- 2026-08 (v6 upgrade):
  - Section 1: per-policy security_features (8 booleans); security_risk = inverse of 7 features;
    basement_present -> +15 flood_risk. UI 2-col checkbox grid.
  - Section 2: full frontend (inline blur errors, disabled submit) + backend Pydantic validation.
  - Section 3: submitter receipt PDF (no scores) + auto Resend email with PDF attachment.
  - Section 4: inbox search, status/date/NatCat filters, sortable columns, pagination, empty state,
    zebra rows, skeletons.
  - Section 5: benchmark badge vs portfolio avg, data provenance tags (Live vs Modeled),
    reviewer full report PDF + per-policy CSV, live retained/ceded stacked bar, action toasts.
  - Section 6: risk integrity — per-address live seismic/wind (cached, logged raw), fallback tagged
    Modeled; verified SF vs Miami differ (seismic 100 vs 0).
  - Section 7: skeletons, favicon (shield), branded 404, ErrorBoundary, hover/focus states.
  - OTP resilience: 429 from email provider no longer blocks login (code still valid).
- Testing: iteration_2 — backend 25/25, frontend 100%, no bugs.

- 2026-08 (v7 enhancements):
  - Receipt Link Security: public receipt.pdf now requires an HMAC-signed 24h token (receipt_url in
    SSE complete event + email). 403 without/tampered token.
  - Reviewer Assignment: assigned_to field; POST /submissions/{id}/claim (claim/release, 409 if taken);
    inbox Assignee column + Claim buttons; detail Claim/Release + "Handled by you" badge.
  - Portfolio Heatmap: GET /portfolio/map + Leaflet map (PortfolioMap.jsx) plotting every geocoded
    policy as a circle marker colored by composite risk, with popups + legend.
  - Email Branding: _email_shell with Veridian shield logo (VERIDIAN_LOGO_URL); branded OTP + receipt.
  - Testing: iteration_3 (backend 38/38; caught Dashboard mapPoints crash) -> fixed -> iteration_4
    frontend 100% (heatmap 33 markers, claim/release, detail flow), zero bugs.

- 2026-08 (v8 enhancements):
  - Assignment Filter: inbox dropdown (All / Assigned to me / Unclaimed), client-side.
  - Map Clustering: PortfolioMap uses leaflet.markercluster so dense pins group into clusters.
  - Reviewer Activity: submission record.activity trail (claimed/released/reviewed/flagged with by+at+note),
    appended in review/claim endpoints; shown as a timeline on detail.
  - Email Digest: .emergent/crons.yml daily 08:00 UTC -> POST /api/cron/digest (Bearer WEBHOOK_CRON_SECRET,
    401 otherwise, acks immediately + backgrounds _send_digest) emailing all reviewers the pending queue.
  - Testing: iteration_5 caught assignee useMemo missing deps -> fixed (added assignee,email to deps).

- 2026-08 (v9 enhancements):
  - Digest Preferences: per-reviewer settings (data/reviewer_prefs.json) — enable/disable + UTC hour;
    GET/PUT /api/settings; Settings screen at /insights/settings (header link). Digest cron now hourly
    and _send_digest(target_hour) emails only reviewers whose enabled hour matches.
  - Cluster Risk Color: heatmap cluster bubbles colored by AVERAGE child composite risk (green/amber/red)
    via markerClusterGroup iconCreateFunction, showing count + avg.
  - Activity Export: reviewer full-report PDF now appends a "Reviewer Activity (Audit Trail)" section.
  - Assignment Notify: claiming a submission emails the assignee (send_assignment_email, backgrounded).
  - Testing: iteration_6 both new features + regression pass (assignee-filter fix confirmed); only a
    Playwright select flake noted (backend PUT + toggle persistence proven).

- 2026-08 (v10 enhancements):
  - Digest Test Send: POST /api/settings/test-digest (_send_digest only=[caller]); "Send me a test digest now" button on Settings.
  - Cluster Legend note: dashboard heatmap note explaining cluster color = average composite risk.
  - Reassign Submission: POST /api/submissions/{id}/reassign (+ GET /api/reviewers); detail "Reassign to…" dropdown; emails new reviewer; activity trail "Reassigned to …".
  - Weekly Summary: prefs weekly_enabled/weekly_day; _send_weekly + hourly /api/cron/weekly (weekday+hour match); Settings weekly toggle + weekday select.
  - Testing: iteration_7 frontend 100% (all 3 UI features + regression), zero bugs.

## Backlog (P1/P2)
- P1: signed/expiring tokens or rate-limit on public receipt.pdf (id enumeration risk).
- P2: persist OTP store outside process memory; align route naming to plural.
- P2: real flood/wildfire/theft data source if a free API becomes available.

## Next tasks
- Optional: deploy + custom domain; push v6 to GitHub via Save to GitHub.
