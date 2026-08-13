import os
import json
import asyncio
import random
import logging
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal

import jwt
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr, field_validator
import uuid

from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("veridian")

DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
SUBMISSIONS_FILE = DATA_DIR / "submissions.json"
CLAIMS_FILE = DATA_DIR / "historical_claims.json"

EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ["EMERGENT_EMAIL_KEY"]
EMAIL_FROM_NAME = os.environ["EMAIL_FROM_NAME"]
EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]
JWT_SECRET = os.environ["JWT_SECRET"]
WHITELIST = [e.strip().lower() for e in os.environ["WHITELIST_EMAILS"].split(",") if e.strip()]

app = FastAPI()
api = APIRouter(prefix="/api")

_file_lock = asyncio.Lock()
# In-memory OTP store: {email: {"otp": str, "expires": datetime, "sends": [datetime,...]}}
OTP_STORE: dict = {}

RISK_WEIGHTS = {
    "flood_risk": 0.20,
    "seismic_risk": 0.25,
    "wildfire_risk": 0.15,
    "wind_storm_risk": 0.20,
    "theft_risk": 0.05,
    "property_condition": 0.15,
}


# ----------------------------- Storage helpers -----------------------------
def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text() or "null") or default
    except Exception:
        return default


async def read_submissions() -> List[dict]:
    async with _file_lock:
        return _read_json(SUBMISSIONS_FILE, [])


async def write_submission(record: dict):
    async with _file_lock:
        data = _read_json(SUBMISSIONS_FILE, [])
        data.append(record)
        SUBMISSIONS_FILE.write_text(json.dumps(data, indent=2))


async def update_submission(submission_id: str, patch: dict):
    async with _file_lock:
        data = _read_json(SUBMISSIONS_FILE, [])
        for rec in data:
            if rec["submission_id"] == submission_id:
                rec.update(patch)
                break
        SUBMISSIONS_FILE.write_text(json.dumps(data, indent=2))


# ----------------------------- Models -----------------------------
class PolicyRecord(BaseModel):
    address: str
    region: Optional[str] = ""
    property_type: Literal["residential", "commercial", "industrial", "mixed-use"]
    construction_type: str
    year_built: int
    sum_insured: float
    peril_focus: Optional[str] = ""

    @field_validator("year_built")
    @classmethod
    def _year(cls, v):
        if v < 1800 or v > datetime.now().year:
            raise ValueError("year_built must be between 1800 and current year")
        return v

    @field_validator("sum_insured")
    @classmethod
    def _sum(cls, v):
        if v <= 0:
            raise ValueError("sum_insured must be greater than 0")
        return v


class SubmissionCreate(BaseModel):
    submitter_name: str
    submitter_email: EmailStr
    submitter_organization: Optional[str] = ""
    policies: List[PolicyRecord]

    @field_validator("policies")
    @classmethod
    def _policies(cls, v):
        if not v:
            raise ValueError("At least one policy is required")
        return v


class OTPRequest(BaseModel):
    email: EmailStr


class OTPVerify(BaseModel):
    email: EmailStr
    otp: str


class ReviewUpdate(BaseModel):
    status: Literal["Reviewed", "Flagged"]
    note: Optional[str] = ""


# ----------------------------- Risk scoring (real APIs + documented stubs) -----------------------------
async def geocode(client: httpx.AsyncClient, address: str):
    """Real geocoding via Nominatim (OSM), with Open-Meteo fallback if rate-limited/empty."""
    try:
        r = await client.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": "VeridianCATAnalytics/1.0"},
            timeout=15,
        )
        if r.status_code == 200 and r.json():
            j = r.json()[0]
            return float(j["lat"]), float(j["lon"])
    except Exception as e:
        logger.warning(f"Nominatim failed: {e}")
    # Fallback: Open-Meteo geocoding (uses first token of address)
    try:
        name = address.split(",")[0]
        r = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": name, "count": 1}, timeout=15,
        )
        res = r.json().get("results")
        if res:
            return float(res[0]["latitude"]), float(res[0]["longitude"])
    except Exception as e:
        logger.warning(f"Open-Meteo geocode fallback failed: {e}")
    return None, None


async def seismic_risk(client: httpx.AsyncClient, lat, lon) -> float:
    """Real USGS earthquake density -> 0-100 score."""
    try:
        r = await client.get(
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            params={"format": "geojson", "latitude": lat, "longitude": lon,
                    "maxradiuskm": 100, "minmagnitude": 3, "starttime": "2015-01-01"},
            timeout=20,
        )
        count = r.json().get("metadata", {}).get("count", 0)
        return round(min(100.0, count * 1.2), 1)
    except Exception as e:
        logger.warning(f"USGS failed: {e}")
        return 25.0


async def wind_storm_risk(client: httpx.AsyncClient, lat, lon) -> float:
    """Real Open-Meteo archive max wind speed -> 0-100 score."""
    try:
        r = await client.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params={"latitude": lat, "longitude": lon, "start_date": "2023-01-01",
                    "end_date": "2023-12-31", "daily": "windspeed_10m_max"},
            timeout=20,
        )
        winds = [w for w in r.json().get("daily", {}).get("windspeed_10m_max", []) if w is not None]
        if not winds:
            return 30.0
        peak = max(winds)  # km/h
        return round(min(100.0, peak / 1.2), 1)  # ~120km/h -> 100
    except Exception as e:
        logger.warning(f"Open-Meteo archive failed: {e}")
        return 30.0


def _stub(seed: str, lo=30, hi=50) -> float:
    """Documented stub for flood/wildfire/theft (no free real-time API). Deterministic 30-50."""
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    return float(lo + (h % (hi - lo + 1)))


def property_condition_score(year_built: int, construction_type: str) -> float:
    """Higher score = worse condition/higher risk. Based on building age."""
    age = datetime.now().year - year_built
    base = min(100.0, age * 0.9)
    if construction_type.lower() in ("wood", "timber", "frame"):
        base = min(100.0, base + 12)
    return round(base, 1)


async def score_policy(client: httpx.AsyncClient, policy: dict, idx: int) -> dict:
    lat, lon = await geocode(client, policy["address"])
    if lat is None:
        lat, lon = 39.5, -98.35  # US centroid fallback
    seismic = await seismic_risk(client, lat, lon)
    wind = await wind_storm_risk(client, lat, lon)
    # Documented stubs (30-50) — no free real-time API for these perils
    flood = _stub(f"flood{policy['address']}")
    wildfire = _stub(f"wildfire{policy['address']}")
    theft = _stub(f"theft{policy['address']}")
    prop_cond = property_condition_score(policy["year_built"], policy["construction_type"])

    scores = {
        "flood_risk": flood,
        "seismic_risk": seismic,
        "wildfire_risk": wildfire,
        "wind_storm_risk": wind,
        "theft_risk": theft,
        "property_condition": prop_cond,
    }
    composite = round(sum(scores[k] * w for k, w in RISK_WEIGHTS.items()), 1)
    expected_loss = round(policy["sum_insured"] * composite / 100.0, 2)
    return {
        "policy_id": f"POL-{idx+1:03d}",
        "address": policy["address"],
        "region": policy.get("region") or _derive_region(policy["address"]),
        "property_type": policy["property_type"],
        "construction_type": policy["construction_type"],
        "year_built": policy["year_built"],
        "sum_insured": policy["sum_insured"],
        "peril_focus": policy.get("peril_focus") or "",
        "lat": lat, "lon": lon,
        "risk_scores": scores,
        "policy_composite": composite,
        "expected_loss": expected_loss,
    }


def _derive_region(address: str) -> str:
    parts = [p.strip() for p in address.split(",")]
    return parts[-2] if len(parts) >= 2 else (parts[-1] if parts else "Unknown")


def aggregate(policies: List[dict]) -> dict:
    total_si = sum(p["sum_insured"] for p in policies)
    total_loss = round(sum(p["expected_loss"] for p in policies), 2)
    by_region: dict = {}
    by_peril: dict = {k: 0.0 for k in RISK_WEIGHTS}
    for p in policies:
        by_region[p["region"]] = round(by_region.get(p["region"], 0) + p["sum_insured"], 2)
        for k in RISK_WEIGHTS:
            by_peril[k] += p["risk_scores"][k] * p["sum_insured"]
    # peril exposure weighted by sum insured -> normalized score
    exposure_by_peril = {k: round(v / total_si, 1) if total_si else 0 for k, v in by_peril.items()}
    avg_scores = {k: round(sum(p["risk_scores"][k] for p in policies) / len(policies), 1) for k in RISK_WEIGHTS}
    natcat = round(sum(avg_scores[k] * w for k, w in RISK_WEIGHTS.items()), 1)
    return {
        "total_sum_insured": round(total_si, 2),
        "aggregate_expected_loss": total_loss,
        "exposure_by_region": by_region,
        "exposure_by_peril": exposure_by_peril,
        "avg_scores": avg_scores,
        "natcat_composite_score": natcat,
    }


# ----------------------------- Submission pipeline (SSE) -----------------------------
def sse(step, status, message, data=None):
    payload = {"step_name": step, "status": status, "message": message,
               "data": data or {}, "timestamp": datetime.now(timezone.utc).isoformat()}
    return f"data: {json.dumps(payload)}\n\n"


@api.post("/submissions/process")
async def process_submission(submission: SubmissionCreate):
    async def gen():
        submission_id = "VRD-" + uuid.uuid4().hex[:8].upper()
        policies_in = [p.model_dump() for p in submission.policies]
        yield sse("start", "running", f"Submission {submission_id} received. Beginning analysis.",
                  {"submission_id": submission_id, "policy_count": len(policies_in)})
        await asyncio.sleep(0.2)

        scored = []
        async with httpx.AsyncClient() as client:
            yield sse("geocoding", "running", "Geocoding policy addresses via OpenStreetMap...")
            for i, p in enumerate(policies_in):
                yield sse("risk_scoring", "running",
                          f"Scoring policy {i+1}/{len(policies_in)}: {p['address'][:40]}")
                res = await score_policy(client, p, i)
                scored.append(res)
                yield sse("risk_scoring", "running",
                          f"Policy {res['policy_id']} composite risk {res['policy_composite']}",
                          {"policy": res})
            yield sse("geocoding", "done", "All addresses geocoded.")

        yield sse("aggregation", "running", "Aggregating portfolio exposure & expected loss...")
        agg = aggregate(scored)
        await asyncio.sleep(0.2)
        yield sse("aggregation", "done", "Portfolio aggregates computed.", agg)

        yield sse("natcat", "running", "Computing NatCat composite score...")
        await asyncio.sleep(0.2)
        yield sse("natcat", "done", f"NatCat composite score: {agg['natcat_composite_score']}",
                  {"natcat_composite_score": agg["natcat_composite_score"]})

        record = {
            "submission_id": submission_id,
            "submitter_name": submission.submitter_name,
            "submitter_email": submission.submitter_email,
            "submitter_organization": submission.submitter_organization or "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "policies": scored,
            **agg,
            "submission_status": "Received",
            "review_note": "",
            "ai_insight": "",
        }
        await write_submission(record)
        yield sse("persist", "done", "Submission stored successfully.",
                  {"submission_id": submission_id})
        yield sse("complete", "complete", "Analysis complete.",
                  {"submission_id": submission_id})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ----------------------------- Auth (real OTP via Resend) -----------------------------
async def send_otp_email(recipient: str, otp: str):
    html = f"""
    <table width="100%" style="background:#F8FAFB;padding:32px 0;font-family:Arial,sans-serif">
      <tr><td align="center">
        <table width="480" style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:12px;padding:32px">
          <tr><td style="color:#0F2C4C;font-size:22px;font-weight:bold;padding-bottom:8px">Veridian</td></tr>
          <tr><td style="color:#1F2937;font-size:14px;padding-bottom:24px">Real-Time Risk Intelligence for Smarter Reinsurance</td></tr>
          <tr><td style="color:#1F2937;font-size:15px;padding-bottom:12px">Your Insights Dashboard verification code is:</td></tr>
          <tr><td style="background:#E6F7F5;color:#0F2C4C;font-size:34px;font-weight:bold;letter-spacing:10px;text-align:center;padding:18px;border-radius:8px">{otp}</td></tr>
          <tr><td style="color:#6B7280;font-size:13px;padding-top:16px">This code expires in 5 minutes. If you did not request it, ignore this email.</td></tr>
        </table>
      </td></tr>
    </table>
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{EMAIL_BASE_URL}/api/v1/email/send",
            headers={"X-Email-Key": EMAIL_KEY},
            json={"to": [recipient], "subject": f"Your Veridian code: {otp}",
                  "html": html, "from_name": EMAIL_FROM_NAME},
        )
        resp.raise_for_status()


@api.post("/auth/request-otp")
async def request_otp(body: OTPRequest):
    email = body.email.lower()
    if email not in WHITELIST:
        raise HTTPException(status_code=403, detail="This email is not authorized to access Insights")
    now = datetime.now(timezone.utc)
    entry = OTP_STORE.get(email, {"sends": []})
    recent = [t for t in entry.get("sends", []) if now - t < timedelta(minutes=10)]
    if len(recent) >= 3:
        raise HTTPException(status_code=429, detail="Too many requests. Try again in a few minutes.")
    otp = f"{random.randint(0, 999999):06d}"
    recent.append(now)
    OTP_STORE[email] = {"otp": otp, "expires": now + timedelta(minutes=5), "sends": recent}
    logger.info(f"[OTP] Generated code for {email}: {otp}")  # demo/testing visibility
    try:
        await send_otp_email(email, otp)
    except Exception as e:
        logger.error(f"OTP email failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to send verification email")
    return {"status": "sent", "message": f"A verification code was sent to {email}"}


@api.post("/auth/verify-otp")
async def verify_otp(body: OTPVerify, response: Response):
    email = body.email.lower()
    entry = OTP_STORE.get(email)
    if not entry or entry.get("otp") != body.otp:
        raise HTTPException(status_code=401, detail="Invalid verification code")
    if datetime.now(timezone.utc) > entry["expires"]:
        raise HTTPException(status_code=401, detail="Verification code expired. Request a new one.")
    OTP_STORE.pop(email, None)
    token = jwt.encode({"email": email, "exp": datetime.now(timezone.utc) + timedelta(hours=12)},
                       JWT_SECRET, algorithm="HS256")
    response.set_cookie("veridian_token", token, httponly=True, secure=True,
                        samesite="none", max_age=43200, path="/")
    return {"status": "authenticated", "email": email}


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("veridian_token", path="/", samesite="none", secure=True)
    return {"status": "logged_out"}


async def require_auth(request: Request) -> str:
    token = request.cookies.get("veridian_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["email"]
    except Exception:
        raise HTTPException(status_code=401, detail="Session expired")


@api.get("/auth/me")
async def me(email: str = Depends(require_auth)):
    return {"email": email}


# ----------------------------- Dashboard endpoints (protected) -----------------------------
@api.get("/submissions")
async def list_submissions(email: str = Depends(require_auth)):
    data = await read_submissions()
    data.sort(key=lambda r: r["created_at"], reverse=True)
    return [{
        "submission_id": r["submission_id"], "submitter_name": r["submitter_name"],
        "submitter_organization": r.get("submitter_organization", ""),
        "created_at": r["created_at"], "total_sum_insured": r["total_sum_insured"],
        "natcat_composite_score": r["natcat_composite_score"],
        "submission_status": r["submission_status"], "policy_count": len(r["policies"]),
    } for r in data]


@api.get("/submissions/{submission_id}")
async def get_submission(submission_id: str, email: str = Depends(require_auth)):
    data = await read_submissions()
    for r in data:
        if r["submission_id"] == submission_id:
            return r
    raise HTTPException(status_code=404, detail="Submission not found")


@api.post("/submissions/{submission_id}/review")
async def review_submission(submission_id: str, body: ReviewUpdate, email: str = Depends(require_auth)):
    await update_submission(submission_id, {"submission_status": body.status, "review_note": body.note or ""})
    return {"status": "updated", "submission_status": body.status}


@api.post("/submissions/{submission_id}/ai-insight")
async def ai_insight(submission_id: str, email: str = Depends(require_auth)):
    data = await read_submissions()
    rec = next((r for r in data if r["submission_id"] == submission_id), None)
    if not rec:
        raise HTTPException(status_code=404, detail="Submission not found")

    prompt = f"""You are a senior reinsurance underwriter. Analyze this CAT portfolio and give a concise
underwriting & treaty-efficiency recommendation (max 220 words). Use the numbers directly.

Portfolio: {rec['submitter_organization'] or rec['submitter_name']}
Policies: {len(rec['policies'])}
Total Sum Insured: ${rec['total_sum_insured']:,.0f}
Aggregate Expected CAT Loss: ${rec['aggregate_expected_loss']:,.0f}
NatCat Composite Score: {rec['natcat_composite_score']}/100
Average peril scores: {json.dumps(rec['avg_scores'])}
Exposure by region: {json.dumps(rec['exposure_by_region'])}

Cover: (1) dominant perils driving loss, (2) recommended treaty structure (quota share vs XoL) with a
suggested cession range, (3) one capital-adequacy caution. Be specific and decisive."""

    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"insight-{submission_id}",
                   system_message="You are a precise, decisive reinsurance underwriting analyst.").with_model(
        "anthropic", "claude-sonnet-4-6")

    async def gen():
        full = ""
        async for ev in chat.stream_message(UserMessage(text=prompt)):
            if isinstance(ev, TextDelta):
                full += ev.content
                yield ev.content
            elif isinstance(ev, StreamDone):
                break
        await update_submission(submission_id, {"ai_insight": full})

    return StreamingResponse(gen(), media_type="text/plain",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@api.get("/portfolio/overview")
async def portfolio_overview(email: str = Depends(require_auth)):
    data = await read_submissions()
    total_exposure = sum(r["total_sum_insured"] for r in data)
    avg_natcat = round(sum(r["natcat_composite_score"] for r in data) / len(data), 1) if data else 0
    # capital reserve breach: aggregate expected loss > 15% of sum insured (default reserve model)
    breaches = sum(1 for r in data if r["aggregate_expected_loss"] > 0.15 * r["total_sum_insured"])
    return {
        "total_submissions": len(data),
        "total_exposure": round(total_exposure, 2),
        "average_natcat_score": avg_natcat,
        "capital_reserve_breaches": breaches,
    }


@api.get("/")
async def root():
    return {"message": "Veridian CAT Analytics API", "whitelist_count": len(WHITELIST)}


app.include_router(api)
app.add_middleware(
    CORSMiddleware, allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"], allow_headers=["*"],
)
