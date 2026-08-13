# Veridian — CAT Portfolio & Reinsurance Analytics (PRD)

## Original Problem Statement
Full-stack CAT (catastrophe) risk analytics platform for reinsurance decision support. Two areas:
public Submission Portal (no login) + protected Insights Dashboard (real email-OTP auth, whitelist-only).
Real external APIs for geocoding/seismic/wind; documented stubs for flood/wildfire/theft; Claude AI insight;
Resend OTP email. Storage in local JSON files (no DB).

## Architecture (as built)
- Frontend: React (CRA) + Tailwind (Next.js not available in platform runtime — adapted to React, same UX).
- Backend: FastAPI async + Pydantic. Storage: /app/backend/data/submissions.json + historical_claims.json.
- Auth: passwordless OTP -> JWT in httpOnly cookie `veridian_token`. Whitelist via WHITELIST_EMAILS env.
- Integrations: Emergent-managed Resend (OTP email); Emergent LLM key -> Claude Sonnet 4.6 (AI insight).
- Real APIs verified live: Nominatim (+Open-Meteo geocode fallback), USGS earthquakes, Open-Meteo archive wind.
- Stubs (documented, deterministic 30-50): flood_risk, wildfire_risk, theft_risk. property_condition from age.

## Core Requirements (static)
- Public: landing, multi-row policy submission form, live SSE processing, confirmation with reference ID.
- Dashboard: OTP login (whitelist), submissions inbox, submission detail (exposure charts, per-policy risk),
  Quota Share treaty simulator, capital reserve breach check, AI insight panel, review/flag, portfolio-wide view.
- Validation both frontend + backend (email format, year 1800-now, sum_insured>0, >=1 policy).

## Implemented (2026-08-13)
- All 8 build stages complete and verified. 17/17 backend pytest pass; all frontend critical flows pass.
- Whitelist: aman7339811186@gmail.com, amankunawat4u@gmail.com, amanbaba.kumawat@gmail.com.
- Pipeline SSE events: start, geocoding, risk_scoring, aggregation, natcat, persist, complete.
- Treaty simulator implemented as Quota Share with attachment point; ceded premium loaded at 1.2x.

## Backlog / Remaining (P1/P2)
- P2: geographical risk map (react-globe.gl) for portfolio-wide view.
- P2: CSV upload for bulk policy import.
- P2: per-submission stored capital reserve (currently interactive-only; overview uses 15%-of-SI default model).
- P1: request.is_disconnected guard on AI stream to avoid truncated persisted insight.

## Test Credentials
See /app/memory/test_credentials.md. OTP logged to backend logs for E2E testing.
