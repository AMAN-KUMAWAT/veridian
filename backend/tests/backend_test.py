"""Veridian backend tests - SSE pipeline, auth (OTP), protected routes, AI insight."""
import json
import os
import re
import subprocess
import time

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # Fallback to reading frontend .env directly
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

WHITELIST_EMAIL = "amankunawat4u@gmail.com"
NON_WHITELIST_EMAIL = "nope@example.com"
BACKEND_LOG = "/var/log/supervisor/backend.err.log"


def _find_otp_for(email: str, since_ts: float, timeout: float = 8.0) -> str | None:
    """Read latest OTP for email from backend log written after since_ts (best effort)."""
    pat = re.compile(rf"\[OTP\] Generated code for {re.escape(email.lower())}: (\d{{6}})")
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            out = subprocess.check_output(["tail", "-n", "500", BACKEND_LOG], text=True, stderr=subprocess.DEVNULL)
            matches = pat.findall(out)
            if matches:
                last = matches[-1]
                return last
        except Exception:
            pass
        time.sleep(0.5)
    return last


# ----------------------------- Root -----------------------------
def test_root_ok():
    r = requests.get(f"{BASE_URL}/api/", timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert "Veridian" in j.get("message", "")
    assert j.get("whitelist_count", 0) >= 1


# ----------------------------- Submission SSE pipeline -----------------------------
VALID_SUBMISSION = {
    "submitter_name": "Test User",
    "submitter_email": "TEST_user@example.com",
    "submitter_organization": "TEST Org",
    "policies": [
        {
            "address": "1600 Amphitheatre Parkway, Mountain View, CA",
            "property_type": "commercial",
            "construction_type": "concrete",
            "year_built": 2005,
            "sum_insured": 5000000,
            "peril_focus": "earthquake",
        },
        {
            "address": "350 5th Ave, New York, NY",
            "property_type": "commercial",
            "construction_type": "steel",
            "year_built": 1931,
            "sum_insured": 12000000,
            "peril_focus": "wind",
        },
    ],
}


@pytest.fixture(scope="session")
def submission_id():
    """Run SSE pipeline once, capture submission id and events."""
    r = requests.post(f"{BASE_URL}/api/submissions/process", json=VALID_SUBMISSION,
                      stream=True, timeout=180)
    assert r.status_code == 200, r.text
    events = []
    sid = None
    for raw in r.iter_lines():
        if not raw:
            continue
        line = raw.decode()
        if line.startswith("data: "):
            evt = json.loads(line[6:])
            events.append(evt)
            if evt["step_name"] == "start":
                sid = evt["data"].get("submission_id")
            if evt["step_name"] == "complete":
                break
    assert sid and sid.startswith("VRD-")
    steps = {e["step_name"] for e in events}
    for expected in ("start", "geocoding", "risk_scoring", "aggregation", "natcat", "persist", "complete"):
        assert expected in steps, f"Missing SSE step: {expected}; got {steps}"
    return sid


def test_sse_pipeline_creates_submission(submission_id):
    assert submission_id.startswith("VRD-")


# ----------------------------- Validation -----------------------------
def _base_policy(**over):
    p = {
        "address": "1 Main St, Springfield",
        "property_type": "residential",
        "construction_type": "wood",
        "year_built": 2000,
        "sum_insured": 100000,
    }
    p.update(over)
    return p


@pytest.mark.parametrize("payload,desc", [
    ({"submitter_name": "x", "submitter_email": "TEST_a@b.com", "policies": [_base_policy(year_built=1500)]}, "year_built<1800"),
    ({"submitter_name": "x", "submitter_email": "TEST_a@b.com", "policies": [_base_policy(year_built=3000)]}, "year_built>current"),
    ({"submitter_name": "x", "submitter_email": "TEST_a@b.com", "policies": [_base_policy(sum_insured=0)]}, "sum_insured=0"),
    ({"submitter_name": "x", "submitter_email": "TEST_a@b.com", "policies": [_base_policy(sum_insured=-1)]}, "sum_insured<0"),
    ({"submitter_name": "x", "submitter_email": "TEST_a@b.com", "policies": []}, "empty policies"),
    ({"submitter_name": "x", "submitter_email": "not-an-email", "policies": [_base_policy()]}, "invalid email"),
])
def test_submission_validation_422(payload, desc):
    r = requests.post(f"{BASE_URL}/api/submissions/process", json=payload, timeout=30)
    assert r.status_code == 422, f"{desc}: expected 422, got {r.status_code} {r.text[:200]}"


# ----------------------------- Auth whitelist -----------------------------
def test_request_otp_non_whitelisted_403():
    r = requests.post(f"{BASE_URL}/api/auth/request-otp", json={"email": NON_WHITELIST_EMAIL}, timeout=15)
    assert r.status_code == 403
    assert "not authorized" in r.text.lower()


def test_verify_otp_wrong_code_401():
    # ensure an entry exists first
    requests.post(f"{BASE_URL}/api/auth/request-otp", json={"email": WHITELIST_EMAIL}, timeout=30)
    r = requests.post(f"{BASE_URL}/api/auth/verify-otp",
                      json={"email": WHITELIST_EMAIL, "otp": "000000"}, timeout=15)
    assert r.status_code == 401


@pytest.fixture(scope="session")
def auth_session():
    """Login via OTP flow using log-scraped code, return authenticated requests.Session."""
    s = requests.Session()
    since = time.time()
    r = s.post(f"{BASE_URL}/api/auth/request-otp", json={"email": WHITELIST_EMAIL}, timeout=30)
    if r.status_code == 429:
        pytest.skip("Rate limited on OTP; skipping auth-dependent tests")
    assert r.status_code == 200, r.text
    otp = _find_otp_for(WHITELIST_EMAIL, since_ts=since, timeout=10)
    if not otp:
        pytest.skip("Could not read OTP from backend log")
    v = s.post(f"{BASE_URL}/api/auth/verify-otp", json={"email": WHITELIST_EMAIL, "otp": otp}, timeout=15)
    assert v.status_code == 200, v.text
    assert v.json().get("status") == "authenticated"
    # cookie should be set
    assert "veridian_token" in s.cookies.get_dict(), f"Cookie missing: {s.cookies.get_dict()}"
    return s


# ----------------------------- Protected routes -----------------------------
def test_protected_requires_auth():
    for path in ["/api/submissions", "/api/portfolio/overview"]:
        r = requests.get(f"{BASE_URL}{path}", timeout=15)
        assert r.status_code == 401, f"{path} expected 401 unauth, got {r.status_code}"


def test_list_submissions_authed(auth_session, submission_id):
    r = auth_session.get(f"{BASE_URL}/api/submissions", timeout=30)
    assert r.status_code == 200
    ids = [x["submission_id"] for x in r.json()]
    assert submission_id in ids


def test_get_submission_detail(auth_session, submission_id):
    r = auth_session.get(f"{BASE_URL}/api/submissions/{submission_id}", timeout=30)
    assert r.status_code == 200
    rec = r.json()
    assert rec["submission_id"] == submission_id
    assert len(rec["policies"]) == 2
    for p in rec["policies"]:
        for k in ("flood_risk", "seismic_risk", "wildfire_risk", "wind_storm_risk", "theft_risk", "property_condition"):
            assert k in p["risk_scores"]
        assert "policy_composite" in p
        assert "expected_loss" in p
    for k in ("total_sum_insured", "aggregate_expected_loss", "exposure_by_region",
              "exposure_by_peril", "avg_scores", "natcat_composite_score"):
        assert k in rec


def test_portfolio_overview(auth_session):
    r = auth_session.get(f"{BASE_URL}/api/portfolio/overview", timeout=30)
    assert r.status_code == 200
    j = r.json()
    for k in ("total_submissions", "total_exposure", "average_natcat_score", "capital_reserve_breaches"):
        assert k in j


def test_review_submission(auth_session, submission_id):
    r = auth_session.post(f"{BASE_URL}/api/submissions/{submission_id}/review",
                          json={"status": "Reviewed", "note": "TEST review"}, timeout=15)
    assert r.status_code == 200
    assert r.json().get("submission_status") == "Reviewed"
    g = auth_session.get(f"{BASE_URL}/api/submissions/{submission_id}", timeout=15)
    assert g.json()["submission_status"] == "Reviewed"

    r2 = auth_session.post(f"{BASE_URL}/api/submissions/{submission_id}/review",
                           json={"status": "Flagged", "note": "TEST flag"}, timeout=15)
    assert r2.status_code == 200
    g2 = auth_session.get(f"{BASE_URL}/api/submissions/{submission_id}", timeout=15)
    assert g2.json()["submission_status"] == "Flagged"


def test_ai_insight_stream(auth_session, submission_id):
    r = auth_session.post(f"{BASE_URL}/api/submissions/{submission_id}/ai-insight",
                          stream=True, timeout=120)
    assert r.status_code == 200
    text = ""
    for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
        if chunk:
            text += chunk
        if len(text) > 200:
            # early exit - we have proof of streamed content
            pass
    r.close()
    assert len(text.strip()) > 50, f"AI insight text too short: {text!r}"


# ----------------------------- Rate limit -----------------------------
def test_otp_rate_limit_429():
    # Use a different whitelisted email to avoid interfering with auth_session
    email = "aman7339811186@gmail.com"
    statuses = []
    for _ in range(4):
        r = requests.post(f"{BASE_URL}/api/auth/request-otp", json={"email": email}, timeout=30)
        statuses.append(r.status_code)
    assert 429 in statuses, f"Expected 429 in {statuses}"
