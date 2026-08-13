import os
import io
import csv
import json
import hmac
import base64
import asyncio
import random
import logging
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal

import jwt
import httpx
from fpdf import FPDF
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, Header
from fastapi.responses import StreamingResponse
from starlette.responses import Response as FileResponse
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
PUBLIC_APP_URL = os.environ.get("PUBLIC_APP_URL", "").rstrip("/")
LOGO_URL = os.environ.get("VERIDIAN_LOGO_URL", "")
WEBHOOK_CRON_SECRET = os.environ.get("WEBHOOK_CRON_SECRET", "")
RECEIPT_TTL = 24 * 3600  # signed receipt links valid 24h (prevents id enumeration)

app = FastAPI()
api = APIRouter(prefix="/api")

_file_lock = asyncio.Lock()
OTP_STORE: dict = {}

# security_risk added (Section 1) + rebalanced so weights sum to 1.0
RISK_WEIGHTS = {
    "flood_risk": 0.18,
    "seismic_risk": 0.22,
    "wildfire_risk": 0.13,
    "wind_storm_risk": 0.18,
    "theft_risk": 0.04,
    "property_condition": 0.13,
    "security_risk": 0.12,
}
# Perils genuinely computed from live external APIs (rest are documented modeled estimates)
LIVE_PERILS = {"seismic_risk", "wind_storm_risk"}
SECURITY_BOOLS = ["alarm_system", "security_cameras", "smart_home_security",
                  "fire_sprinklers", "fire_extinguishers", "smoke_detectors", "gated_access"]


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
class SecurityFeatures(BaseModel):
    alarm_system: bool = False
    security_cameras: bool = False
    smart_home_security: bool = False
    fire_sprinklers: bool = False
    fire_extinguishers: bool = False
    smoke_detectors: bool = False
    gated_access: bool = False
    basement_present: bool = False


class PolicyRecord(BaseModel):
    address: str = Field(min_length=3)
    region: Optional[str] = ""
    property_type: Literal["residential", "commercial", "industrial", "mixed-use"]
    construction_type: str = Field(min_length=1)
    year_built: int
    sum_insured: float
    peril_focus: Optional[str] = ""
    security_features: SecurityFeatures = Field(default_factory=SecurityFeatures)

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
    submitter_name: str = Field(min_length=1)
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


class ClaimUpdate(BaseModel):
    action: Literal["claim", "release"]


# ----------------------------- Risk scoring (real APIs + documented stubs) -----------------------------
async def geocode(client: httpx.AsyncClient, address: str):
    """Real geocoding via Nominatim (OSM), with Open-Meteo fallback. Returns (lat, lon, ok)."""
    try:
        r = await client.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": "VeridianCATAnalytics/1.0"},
            timeout=15,
        )
        if r.status_code == 200 and r.json():
            j = r.json()[0]
            logger.info(f"[GEOCODE] '{address[:40]}' -> {j['lat']},{j['lon']} (nominatim)")
            return float(j["lat"]), float(j["lon"]), True
    except Exception as e:
        logger.warning(f"Nominatim failed: {e}")
    try:
        name = address.split(",")[0]
        r = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": name, "count": 1}, timeout=15,
        )
        res = r.json().get("results")
        if res:
            logger.info(f"[GEOCODE] '{address[:40]}' -> {res[0]['latitude']},{res[0]['longitude']} (open-meteo fallback)")
            return float(res[0]["latitude"]), float(res[0]["longitude"]), True
    except Exception as e:
        logger.warning(f"Open-Meteo geocode fallback failed: {e}")
    return None, None, False


async def seismic_risk(client: httpx.AsyncClient, lat, lon):
    """Real USGS earthquake density -> (score 0-100, ok)."""
    try:
        r = await client.get(
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            params={"format": "geojson", "latitude": lat, "longitude": lon,
                    "maxradiuskm": 100, "minmagnitude": 3, "starttime": "2015-01-01"},
            timeout=20,
        )
        count = r.json().get("metadata", {}).get("count", 0)
        logger.info(f"[USGS] lat={lat} lon={lon} quake_count={count}")
        return round(min(100.0, count * 1.2), 1), True
    except Exception as e:
        logger.warning(f"USGS failed (fallback to modeled): {e}")
        return 25.0, False


async def wind_storm_risk(client: httpx.AsyncClient, lat, lon):
    """Real Open-Meteo archive max wind speed -> (score 0-100, ok)."""
    try:
        r = await client.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params={"latitude": lat, "longitude": lon, "start_date": "2023-01-01",
                    "end_date": "2023-12-31", "daily": "windspeed_10m_max"},
            timeout=20,
        )
        winds = [w for w in r.json().get("daily", {}).get("windspeed_10m_max", []) if w is not None]
        if not winds:
            return 30.0, False
        peak = max(winds)
        logger.info(f"[OPEN-METEO] lat={lat} lon={lon} peak_wind_kmh={peak}")
        return round(min(100.0, peak / 1.2), 1), True
    except Exception as e:
        logger.warning(f"Open-Meteo archive failed (fallback to modeled): {e}")
        return 30.0, False


def _stub(seed: str, lo=30, hi=50) -> float:
    """Documented modeled estimate for flood/wildfire/theft (no free real-time API). Deterministic 30-50."""
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    return float(lo + (h % (hi - lo + 1)))


def property_condition_score(year_built: int, construction_type: str) -> float:
    age = datetime.now().year - year_built
    base = min(100.0, age * 0.9)
    if construction_type.lower() in ("wood", "timber", "frame"):
        base = min(100.0, base + 12)
    return round(base, 1)


def security_risk_score(sf: dict) -> float:
    """Inverse of how many of the 7 security features (excluding basement) are present."""
    present = sum(1 for k in SECURITY_BOOLS if sf.get(k))
    return round(100.0 * (1 - present / len(SECURITY_BOOLS)), 1)


async def score_policy(client, policy, idx, geo_cache, seis_cache, wind_cache):
    addr = policy["address"]
    if addr in geo_cache:
        lat, lon, geo_ok = geo_cache[addr]
    else:
        lat, lon, geo_ok = await geocode(client, addr)
        geo_cache[addr] = (lat, lon, geo_ok)
    if lat is None:
        lat, lon = 39.5, -98.35  # US centroid fallback (coords not real -> live scores tagged modeled)

    ckey = (round(lat, 3), round(lon, 3))
    if ckey in seis_cache:
        seismic, seis_ok = seis_cache[ckey]
    else:
        seismic, seis_ok = await seismic_risk(client, lat, lon)
        seis_cache[ckey] = (seismic, seis_ok)
    if ckey in wind_cache:
        wind, wind_ok = wind_cache[ckey]
    else:
        wind, wind_ok = await wind_storm_risk(client, lat, lon)
        wind_cache[ckey] = (wind, wind_ok)

    sf = policy.get("security_features") or {}
    # Documented modeled estimates (30-50) — no free real-time API for these perils
    flood = _stub(f"flood{addr}")
    if sf.get("basement_present"):
        flood = min(100.0, flood + 15.0)  # underwriting logic: basements raise water-damage exposure
    wildfire = _stub(f"wildfire{addr}")
    theft = _stub(f"theft{addr}")
    prop_cond = property_condition_score(policy["year_built"], policy["construction_type"])
    security = security_risk_score(sf)

    scores = {
        "flood_risk": flood, "seismic_risk": seismic, "wildfire_risk": wildfire,
        "wind_storm_risk": wind, "theft_risk": theft,
        "property_condition": prop_cond, "security_risk": security,
    }
    live_ok = {"seismic_risk": geo_ok and seis_ok, "wind_storm_risk": geo_ok and wind_ok}
    data_sources = {k: ("live" if (k in LIVE_PERILS and live_ok.get(k)) else "modeled") for k in scores}

    composite = round(sum(scores[k] * w for k, w in RISK_WEIGHTS.items()), 1)
    expected_loss = round(policy["sum_insured"] * composite / 100.0, 2)
    return {
        "policy_id": f"POL-{idx+1:03d}",
        "address": addr,
        "region": policy.get("region") or _derive_region(addr),
        "property_type": policy["property_type"],
        "construction_type": policy["construction_type"],
        "year_built": policy["year_built"],
        "sum_insured": policy["sum_insured"],
        "peril_focus": policy.get("peril_focus") or "",
        "security_features": sf,
        "lat": lat, "lon": lon,
        "risk_scores": scores,
        "data_sources": data_sources,
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


# ----------------------------- PDF / CSV builders -----------------------------
def _clean(t: str) -> str:
    repl = {"—": "-", "–": "-", "·": "-", "’": "'", "“": '"', "”": '"', "→": "->", "×": "x", "≥": ">=", "…": "..."}
    for k, v in repl.items():
        t = str(t).replace(k, v)
    return t.encode("latin-1", "replace").decode("latin-1")


def _pdf_header(pdf, subtitle):
    pdf.set_fill_color(15, 44, 76)
    pdf.rect(0, 0, 210, 30, style="F")
    pdf.set_xy(12, 8)
    pdf.set_font("Helvetica", "B", 18); pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, "Veridian", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(12); pdf.set_font("Helvetica", "", 9); pdf.set_text_color(230, 247, 245)
    pdf.cell(0, 6, _clean(subtitle))
    pdf.ln(22); pdf.set_text_color(31, 41, 55)


def build_receipt_pdf(rec: dict) -> bytes:
    """Submitter-facing receipt: NO risk scores / analytics (reviewer-only by design)."""
    pdf = FPDF(); pdf.add_page(); pdf.set_auto_page_break(True, 15)
    _pdf_header(pdf, "Submission Receipt - Real-Time Risk Intelligence for Smarter Reinsurance")
    pdf.set_font("Helvetica", "B", 13); pdf.cell(0, 8, "Submission Confirmation", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for label, val in [
        ("Reference ID", rec["submission_id"]),
        ("Submitted", rec["created_at"][:19].replace("T", " ") + " UTC"),
        ("Submitter", rec["submitter_name"]),
        ("Email", rec["submitter_email"]),
        ("Organization", rec.get("submitter_organization") or "-"),
        ("Policies submitted", str(len(rec["policies"]))),
    ]:
        pdf.set_font("Helvetica", "B", 10); pdf.cell(45, 6, _clean(label + ":"))
        pdf.set_font("Helvetica", "", 10); pdf.cell(0, 6, _clean(val), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11); pdf.cell(0, 8, "Submitted Policies", new_x="LMARGIN", new_y="NEXT")
    pdf.set_fill_color(230, 247, 245); pdf.set_font("Helvetica", "B", 9)
    pdf.cell(95, 7, "Address", border=1, fill=True)
    pdf.cell(40, 7, "Property Type", border=1, fill=True)
    pdf.cell(50, 7, "Sum Insured (USD)", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for p in rec["policies"]:
        addr = _clean(p["address"]); addr = addr[:60] + "..." if len(addr) > 60 else addr
        pdf.cell(95, 7, addr, border=1)
        pdf.cell(40, 7, _clean(p["property_type"]), border=1)
        pdf.cell(50, 7, f"{p['sum_insured']:,.0f}", border=1, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6); pdf.set_font("Helvetica", "I", 8); pdf.set_text_color(110, 120, 130)
    pdf.multi_cell(0, 4.5, _clean("This receipt confirms what was submitted. Risk scoring and analytics are "
                                  "assessed privately by an authorized reviewer and are not included here."))
    return bytes(pdf.output())


def build_report_pdf(rec: dict, cession: float, attachment: float, reserve: float) -> bytes:
    """Reviewer-facing full report: includes risk scores, treaty simulation and AI insight."""
    pdf = FPDF(); pdf.add_page(); pdf.set_auto_page_break(True, 15)
    _pdf_header(pdf, "Confidential Reviewer Report")
    loss = rec["aggregate_expected_loss"]
    ceded = max(0.0, loss - attachment) * (cession / 100.0)
    retained = loss - ceded
    ceded_prem = ceded * 1.2

    pdf.set_font("Helvetica", "B", 13); pdf.cell(0, 8, _clean(f"{rec['submission_id']} - {rec.get('submitter_organization') or rec['submitter_name']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for label, val in [
        ("Total Sum Insured", f"${rec['total_sum_insured']:,.0f}"),
        ("Aggregate Expected CAT Loss", f"${loss:,.0f}"),
        ("NatCat Composite Score", f"{rec['natcat_composite_score']} / 100"),
        ("Status", rec.get("submission_status", "Received")),
    ]:
        pdf.set_font("Helvetica", "B", 10); pdf.cell(60, 6, _clean(label + ":"))
        pdf.set_font("Helvetica", "", 10); pdf.cell(0, 6, _clean(val), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(3); pdf.set_font("Helvetica", "B", 11); pdf.cell(0, 7, "Treaty Simulation (Quota Share)", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for label, val in [("Cession %", f"{cession}%"), ("Attachment Point", f"${attachment:,.0f}"),
                       ("Retained Loss", f"${retained:,.0f}"), ("Ceded Loss", f"${ceded:,.0f}"),
                       ("Ceded Premium (est.)", f"${ceded_prem:,.0f}"), ("Capital Reserve Threshold", f"${reserve:,.0f}"),
                       ("Reserve Status", "BREACHED" if retained > reserve and reserve > 0 else "Within reserve")]:
        pdf.set_font("Helvetica", "B", 10); pdf.cell(60, 6, _clean(label + ":"))
        pdf.set_font("Helvetica", "", 10); pdf.cell(0, 6, _clean(val), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(3); pdf.set_font("Helvetica", "B", 11); pdf.cell(0, 7, "Per-Policy Risk Scores", new_x="LMARGIN", new_y="NEXT")
    pdf.set_fill_color(230, 247, 245); pdf.set_font("Helvetica", "B", 8)
    heads = [("Policy", 18), ("Flood", 16), ("Seismic", 18), ("Wildfire", 18), ("Wind", 15), ("Theft", 15), ("Cond.", 15), ("Sec.", 14), ("Comp.", 16)]
    for h, w in heads:
        pdf.cell(w, 7, h, border=1, fill=True)
    pdf.ln(); pdf.set_font("Helvetica", "", 8)
    for p in rec["policies"]:
        rs = p["risk_scores"]
        row = [p["policy_id"], rs["flood_risk"], rs["seismic_risk"], rs["wildfire_risk"], rs["wind_storm_risk"],
               rs["theft_risk"], rs["property_condition"], rs["security_risk"], p["policy_composite"]]
        for (h, w), val in zip(heads, row):
            pdf.cell(w, 6, _clean(str(val)), border=1)
        pdf.ln()

    if rec.get("ai_insight"):
        pdf.ln(3); pdf.set_font("Helvetica", "B", 11); pdf.cell(0, 7, "AI Underwriting Insight (Claude)", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 4.8, _clean(rec["ai_insight"]))
    return bytes(pdf.output())


def build_policies_csv(rec: dict) -> str:
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(["policy_id", "address", "region", "property_type", "construction_type", "year_built", "sum_insured",
                "flood_risk", "seismic_risk", "wildfire_risk", "wind_storm_risk", "theft_risk",
                "property_condition", "security_risk", "policy_composite", "expected_loss",
                "seismic_source", "wind_source"])
    for p in rec["policies"]:
        rs = p["risk_scores"]; ds = p.get("data_sources", {})
        w.writerow([p["policy_id"], p["address"], p["region"], p["property_type"], p["construction_type"],
                    p["year_built"], p["sum_insured"], rs["flood_risk"], rs["seismic_risk"], rs["wildfire_risk"],
                    rs["wind_storm_risk"], rs["theft_risk"], rs["property_condition"], rs["security_risk"],
                    p["policy_composite"], p["expected_loss"], ds.get("seismic_risk", ""), ds.get("wind_storm_risk", "")])
    return out.getvalue()


# ----------------------------- Email + signed receipt links -----------------------------
def make_receipt_token(submission_id: str) -> str:
    exp = int(datetime.now(timezone.utc).timestamp()) + RECEIPT_TTL
    sig = hmac.new(JWT_SECRET.encode(), f"{submission_id}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    return base64.urlsafe_b64encode(f"{exp}:{sig}".encode()).decode()


def verify_receipt_token(submission_id: str, token: str) -> bool:
    try:
        exp_s, sig = base64.urlsafe_b64decode(token.encode()).decode().split(":")
        exp = int(exp_s)
    except Exception:
        return False
    if datetime.now(timezone.utc).timestamp() > exp:
        return False
    good = hmac.new(JWT_SECRET.encode(), f"{submission_id}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(sig, good)


def receipt_url(submission_id: str) -> str:
    return f"{PUBLIC_APP_URL}/api/submissions/{submission_id}/receipt.pdf?token={make_receipt_token(submission_id)}"


def _email_shell(inner: str) -> str:
    logo = (f'<img src="{LOGO_URL}" alt="Veridian" width="34" height="34" '
            f'style="display:inline-block;vertical-align:middle;border:0">') if LOGO_URL else ""
    return f"""
    <div style="margin:0;background:#F8FAFB;padding:32px 0;font-family:Arial,Helvetica,sans-serif">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
        <table role="presentation" width="520" cellpadding="0" cellspacing="0"
               style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:14px;overflow:hidden">
          <tr><td style="background:#0F2C4C;padding:20px 28px">
            <table role="presentation" cellpadding="0" cellspacing="0"><tr>
              <td style="padding-right:10px">{logo}</td>
              <td style="color:#FFFFFF;font-size:20px;font-weight:bold;letter-spacing:.5px">Veridian</td>
            </tr></table>
            <div style="color:#0EA5A0;font-size:11px;letter-spacing:2px;text-transform:uppercase;margin-top:8px">Real-Time Risk Intelligence</div>
          </td></tr>
          <tr><td style="padding:28px">{inner}</td></tr>
          <tr><td style="background:#F8FAFB;padding:16px 28px;color:#9AA3AF;font-size:11px;border-top:1px solid #EEF1F4">
            (c) 2026 Veridian - Real-Time Risk Intelligence for Smarter Reinsurance
          </td></tr>
        </table>
      </td></tr></table>
    </div>"""


async def _post_email(payload: dict):
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{EMAIL_BASE_URL}/api/v1/email/send",
                                 headers={"X-Email-Key": EMAIL_KEY}, json=payload)
        resp.raise_for_status()


async def send_otp_email(recipient: str, otp: str):
    inner = f"""
      <h2 style="color:#0F2C4C;margin:0 0 6px;font-size:19px">Verify your sign-in</h2>
      <p style="color:#1F2937;font-size:14px;margin:0 0 20px">Use this one-time code to access the Insights Dashboard.</p>
      <div style="background:#E6F7F5;color:#0F2C4C;font-size:34px;font-weight:bold;letter-spacing:12px;text-align:center;padding:18px;border-radius:10px">{otp}</div>
      <p style="color:#6B7280;font-size:12px;margin-top:18px">This code expires in 5 minutes. If you didn't request it, you can ignore this email.</p>
    """
    await _post_email({"to": [recipient], "subject": f"Your Veridian code: {otp}",
                       "html": _email_shell(inner), "from_name": EMAIL_FROM_NAME})


async def send_receipt_email(rec: dict, pdf_bytes: bytes):
    rows = "".join(
        f"<tr><td style='padding:7px 6px;border-bottom:1px solid #EEF1F4;font-size:13px'>{p['address']}</td>"
        f"<td style='padding:7px 6px;border-bottom:1px solid #EEF1F4;font-size:13px;text-transform:capitalize'>{p['property_type']}</td>"
        f"<td style='padding:7px 6px;border-bottom:1px solid #EEF1F4;font-size:13px;text-align:right'>${p['sum_insured']:,.0f}</td></tr>"
        for p in rec["policies"])
    link = receipt_url(rec["submission_id"])
    inner = f"""
      <h2 style="color:#0F2C4C;margin:0 0 6px;font-size:19px">Submission received</h2>
      <p style="color:#1F2937;font-size:14px;margin:0 0 8px">Thank you, {rec['submitter_name']}. Your portfolio has been received and will be assessed by an authorized reviewer.</p>
      <p style="font-size:15px;margin:0 0 16px">Reference ID: <b style="color:#0EA5A0">{rec['submission_id']}</b></p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:1px solid #EEF1F4;border-radius:8px;overflow:hidden">
        <tr style="background:#E6F7F5;color:#0F2C4C"><th style="text-align:left;padding:8px 6px;font-size:12px">Address</th><th style="text-align:left;padding:8px 6px;font-size:12px">Type</th><th style="text-align:right;padding:8px 6px;font-size:12px">Sum Insured</th></tr>
        {rows}
      </table>
      <div style="text-align:center;margin-top:24px">
        <a href="{link}" style="background:#0EA5A0;color:#FFFFFF;text-decoration:none;padding:12px 24px;border-radius:999px;font-weight:bold;font-size:14px;display:inline-block">Download Receipt (PDF)</a>
        <div style="color:#9AA3AF;font-size:11px;margin-top:10px">Secure link - expires in 24 hours. A copy is also attached.</div>
      </div>
      <p style="color:#6B7280;font-size:12px;margin-top:18px">Risk analytics remain reviewer-only by design and are not included in this receipt.</p>
    """
    b64 = base64.b64encode(pdf_bytes).decode()
    payload = {"to": [rec["submitter_email"]], "subject": f"Veridian - Submission Receipt {rec['submission_id']}",
               "html": _email_shell(inner), "from_name": EMAIL_FROM_NAME,
               "attachments": [{"filename": f"{rec['submission_id']}_receipt.pdf", "content": b64}]}
    try:
        await _post_email(payload)
        logger.info(f"[EMAIL] Receipt (with PDF) sent to {rec['submitter_email']}")
    except Exception as e:
        logger.warning(f"[EMAIL] attachment send failed ({e}); retrying without attachment")
        payload.pop("attachments", None)
        await _post_email(payload)


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
        geo_cache, seis_cache, wind_cache = {}, {}, {}
        async with httpx.AsyncClient() as client:
            yield sse("geocoding", "running", "Geocoding policy addresses via OpenStreetMap...")
            for i, p in enumerate(policies_in):
                yield sse("risk_scoring", "running",
                          f"Scoring policy {i+1}/{len(policies_in)}: {p['address'][:40]}")
                res = await score_policy(client, p, i, geo_cache, seis_cache, wind_cache)
                scored.append(res)
                live = ", ".join(k.replace('_risk', '') for k, v in res["data_sources"].items() if v == "live") or "none"
                yield sse("risk_scoring", "running",
                          f"Policy {res['policy_id']} composite {res['policy_composite']} (live: {live})",
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
            "assigned_to": "",
            "activity": [],
            "ai_insight": "",
        }
        await write_submission(record)
        yield sse("persist", "done", "Submission stored successfully.", {"submission_id": submission_id})

        yield sse("email", "running", f"Emailing receipt to {record['submitter_email']}...")
        try:
            await send_receipt_email(record, build_receipt_pdf(record))
            yield sse("email", "done", f"Receipt emailed to {record['submitter_email']}.")
        except Exception as e:
            logger.error(f"Receipt email failed: {e}")
            yield sse("email", "done", "Submission stored (receipt email could not be sent).")

        yield sse("complete", "complete", "Analysis complete.",
                  {"submission_id": submission_id, "submitter_email": record["submitter_email"],
                   "receipt_url": receipt_url(submission_id)})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ----------------------------- Public receipt download (signed, submitter-safe) -----------------------------
@api.get("/submissions/{submission_id}/receipt.pdf")
async def receipt_pdf(submission_id: str, token: str = ""):
    # Signed short-lived token required — prevents enumeration of submissions by guessing IDs.
    if not verify_receipt_token(submission_id, token):
        raise HTTPException(status_code=403, detail="Invalid or expired download link")
    data = await read_submissions()
    rec = next((r for r in data if r["submission_id"] == submission_id), None)
    if not rec:
        raise HTTPException(status_code=404, detail="Submission not found")
    pdf = build_receipt_pdf(rec)
    return FileResponse(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{submission_id}_receipt.pdf"'})


# ----------------------------- Auth (real OTP) -----------------------------
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
    logger.info(f"[OTP] Generated code for {email}: {otp}")
    try:
        await send_otp_email(email, otp)
    except httpx.HTTPStatusError as e:
        # OTP is already stored; if the email provider is merely rate-limiting (429),
        # don't block login — let the user proceed and retry delivery.
        if e.response is not None and e.response.status_code == 429:
            logger.warning(f"OTP email rate-limited (429) for {email}; code still valid")
            return {"status": "sent", "warning": "delivery_delayed",
                    "message": f"Code generated for {email}. Email delivery may be delayed — you can still enter your code."}
        logger.error(f"OTP email failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to send verification email")
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
        "submitter_email": r.get("submitter_email", ""),
        "submitter_organization": r.get("submitter_organization", ""),
        "created_at": r["created_at"], "total_sum_insured": r["total_sum_insured"],
        "natcat_composite_score": r["natcat_composite_score"],
        "submission_status": r["submission_status"], "policy_count": len(r["policies"]),
        "assigned_to": r.get("assigned_to", ""),
    } for r in data]


@api.get("/submissions/{submission_id}")
async def get_submission(submission_id: str, email: str = Depends(require_auth)):
    data = await read_submissions()
    rec = next((r for r in data if r["submission_id"] == submission_id), None)
    if not rec:
        raise HTTPException(status_code=404, detail="Submission not found")
    scores = [r["natcat_composite_score"] for r in data]
    rec = {**rec, "portfolio_avg_natcat": round(sum(scores) / len(scores), 1) if scores else 0}
    return rec


@api.post("/submissions/{submission_id}/review")
async def review_submission(submission_id: str, body: ReviewUpdate, email: str = Depends(require_auth)):
    data = await read_submissions()
    rec = next((r for r in data if r["submission_id"] == submission_id), None)
    if not rec:
        raise HTTPException(status_code=404, detail="Submission not found")
    activity = rec.get("activity", [])
    activity.append({"action": body.status.lower(), "label": body.status, "by": email,
                     "at": datetime.now(timezone.utc).isoformat(), "note": body.note or ""})
    await update_submission(submission_id, {"submission_status": body.status,
                                            "review_note": body.note or "", "activity": activity})
    return {"status": "updated", "submission_status": body.status}


@api.post("/submissions/{submission_id}/claim")
async def claim_submission(submission_id: str, body: ClaimUpdate, email: str = Depends(require_auth)):
    data = await read_submissions()
    rec = next((r for r in data if r["submission_id"] == submission_id), None)
    if not rec:
        raise HTTPException(status_code=404, detail="Submission not found")
    current = rec.get("assigned_to", "")
    activity = rec.get("activity", [])
    if body.action == "release":
        if current and current != email:
            raise HTTPException(status_code=403, detail="Assigned to another reviewer")
        activity.append({"action": "released", "label": "Released", "by": email,
                         "at": datetime.now(timezone.utc).isoformat()})
        await update_submission(submission_id, {"assigned_to": "", "activity": activity})
        return {"assigned_to": ""}
    if current and current != email:
        raise HTTPException(status_code=409, detail=f"Already claimed by {current}")
    activity.append({"action": "claimed", "label": "Claimed", "by": email,
                     "at": datetime.now(timezone.utc).isoformat()})
    await update_submission(submission_id, {"assigned_to": email, "activity": activity})
    return {"assigned_to": email}


@api.get("/portfolio/map")
async def portfolio_map(email: str = Depends(require_auth)):
    data = await read_submissions()
    points = []
    for r in data:
        for p in r["policies"]:
            if p.get("lat") is not None and p.get("lon") is not None:
                points.append({
                    "submission_id": r["submission_id"], "policy_id": p["policy_id"],
                    "address": p["address"], "lat": p["lat"], "lon": p["lon"],
                    "composite": p["policy_composite"], "sum_insured": p["sum_insured"],
                    "submitter_name": r["submitter_name"],
                })
    return {"points": points}


@api.get("/submissions/{submission_id}/report.pdf")
async def report_pdf(submission_id: str, cession: float = 40, attachment: float = 0,
                     reserve: float = 0, email: str = Depends(require_auth)):
    data = await read_submissions()
    rec = next((r for r in data if r["submission_id"] == submission_id), None)
    if not rec:
        raise HTTPException(status_code=404, detail="Submission not found")
    pdf = build_report_pdf(rec, cession, attachment, reserve)
    return FileResponse(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{submission_id}_report.pdf"'})


@api.get("/submissions/{submission_id}/policies.csv")
async def policies_csv(submission_id: str, email: str = Depends(require_auth)):
    data = await read_submissions()
    rec = next((r for r in data if r["submission_id"] == submission_id), None)
    if not rec:
        raise HTTPException(status_code=404, detail="Submission not found")
    csv_str = build_policies_csv(rec)
    return FileResponse(content=csv_str, media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{submission_id}_policies.csv"'})


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
    breaches = sum(1 for r in data if r["aggregate_expected_loss"] > 0.15 * r["total_sum_insured"])
    return {
        "total_submissions": len(data),
        "total_exposure": round(total_exposure, 2),
        "average_natcat_score": avg_natcat,
        "capital_reserve_breaches": breaches,
    }


async def _send_digest():
    try:
        data = await read_submissions()
        pending = [r for r in data if r.get("submission_status") == "Received"]
        pending.sort(key=lambda r: r["created_at"], reverse=True)
        if pending:
            rows = "".join(
                f"<tr><td style='padding:7px 6px;border-bottom:1px solid #EEF1F4;font-size:13px'><b>{r['submission_id']}</b></td>"
                f"<td style='padding:7px 6px;border-bottom:1px solid #EEF1F4;font-size:13px'>{r['submitter_name']}</td>"
                f"<td style='padding:7px 6px;border-bottom:1px solid #EEF1F4;font-size:13px;text-align:right'>${r['total_sum_insured']:,.0f}</td>"
                f"<td style='padding:7px 6px;border-bottom:1px solid #EEF1F4;font-size:13px;text-align:center'>{r['natcat_composite_score']}</td></tr>"
                for r in pending[:50])
            table = (f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse;border:1px solid #EEF1F4;border-radius:8px;overflow:hidden;margin-top:12px'>"
                     f"<tr style='background:#E6F7F5;color:#0F2C4C'><th style='text-align:left;padding:8px 6px;font-size:12px'>Reference</th><th style='text-align:left;padding:8px 6px;font-size:12px'>Submitter</th><th style='text-align:right;padding:8px 6px;font-size:12px'>Sum Insured</th><th style='text-align:center;padding:8px 6px;font-size:12px'>NatCat</th></tr>{rows}</table>")
        else:
            table = "<p style='color:#6B7280;font-size:13px'>No submissions are awaiting review. You're all caught up.</p>"
        inner = (f"<h2 style='color:#0F2C4C;margin:0 0 6px;font-size:19px'>Daily review digest</h2>"
                 f"<p style='color:#1F2937;font-size:14px;margin:0 0 4px'><b style='color:#0EA5A0'>{len(pending)}</b> submission(s) awaiting review.</p>{table}"
                 f"<div style='text-align:center;margin-top:22px'><a href='{PUBLIC_APP_URL}/insights' style='background:#0EA5A0;color:#FFFFFF;text-decoration:none;padding:12px 24px;border-radius:999px;font-weight:bold;font-size:14px;display:inline-block'>Open Insights Dashboard</a></div>")
        for reviewer in WHITELIST:
            try:
                await _post_email({"to": [reviewer],
                                   "subject": f"Veridian - {len(pending)} submission(s) awaiting review",
                                   "html": _email_shell(inner), "from_name": EMAIL_FROM_NAME})
            except Exception as e:
                logger.warning(f"[DIGEST] send to {reviewer} failed: {e}")
        logger.info(f"[DIGEST] dispatched to {len(WHITELIST)} reviewers; {len(pending)} pending")
    except Exception as e:
        logger.error(f"[DIGEST] failed: {e}")


@api.post("/cron/digest")
async def cron_digest(authorization: str = Header(default="")):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    expected = f"Bearer {WEBHOOK_CRON_SECRET}"
    if not WEBHOOK_CRON_SECRET or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")
    asyncio.create_task(_send_digest())
    return {"status": "accepted"}


@api.get("/")
async def root():
    return {"message": "Veridian CAT Analytics API", "whitelist_count": len(WHITELIST)}


app.include_router(api)
app.add_middleware(
    CORSMiddleware, allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"], allow_headers=["*"],
)
