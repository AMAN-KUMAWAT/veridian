"""Veridian v6 upgrade tests:
- per-address live seismic/wind differ (SF vs Miami) + data_sources tags
- security_features wiring (lower security_risk) and basement flood +15
- receipt.pdf public/no-scores; report.pdf and policies.csv auth-only
- portfolio_avg_natcat on detail; empty address rejected 4xx
"""
import json
import os
import re
import subprocess
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break
WHITELIST_EMAIL = "amanbaba.kumawat@gmail.com"  # use different email to avoid RL clash
BACKEND_LOG = "/var/log/supervisor/backend.err.log"


def _find_otp(email, timeout=10):
    pat = re.compile(rf"\[OTP\] Generated code for {re.escape(email.lower())}: (\d{{6}})")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            out = subprocess.check_output(["tail", "-n", "800", BACKEND_LOG], text=True, stderr=subprocess.DEVNULL)
            m = pat.findall(out)
            if m:
                return m[-1]
        except Exception:
            pass
        time.sleep(0.5)
    return None


def _run_pipeline(payload, timeout=200):
    r = requests.post(f"{BASE_URL}/api/submissions/process", json=payload, stream=True, timeout=timeout)
    assert r.status_code == 200, r.text
    sid = None
    final_record = None
    for raw in r.iter_lines():
        if not raw:
            continue
        line = raw.decode()
        if not line.startswith("data: "):
            continue
        evt = json.loads(line[6:])
        if evt["step_name"] == "start":
            sid = evt["data"].get("submission_id")
        if evt["step_name"] == "complete":
            final_record = evt["data"].get("record") or evt["data"]
            break
    assert sid
    return sid, final_record


def _basic_policy(**over):
    p = {
        "address": "1 Main St, Springfield, IL",
        "property_type": "residential",
        "construction_type": "wood",
        "year_built": 2000,
        "sum_insured": 250000,
    }
    p.update(over)
    return p


# ---------------- Live data (SF vs Miami) differ ----------------
@pytest.fixture(scope="module")
def sf_miami_submission():
    payload = {
        "submitter_name": "TEST_SFMiami",
        "submitter_email": "TEST_sfmiami@example.com",
        "policies": [
            _basic_policy(address="500 Terry A Francois Blvd, San Francisco, CA", peril_focus="earthquake",
                          construction_type="concrete"),
            _basic_policy(address="1000 Ocean Dr, Miami Beach, FL", peril_focus="wind",
                          construction_type="concrete"),
        ],
    }
    sid, _ = _run_pipeline(payload)
    # fetch via public detail is auth-only; use raw JSON store lookup via public receipt is not enough.
    # We must authenticate to read scores. Do it lazily in the test using auth session.
    return sid


def test_seismic_wind_differ_and_live_tags(sf_miami_submission, auth_session):
    r = auth_session.get(f"{BASE_URL}/api/submissions/{sf_miami_submission}", timeout=30)
    assert r.status_code == 200
    rec = r.json()
    pols = rec["policies"]
    sf_p = next(p for p in pols if "San Francisco" in p["address"])
    mi_p = next(p for p in pols if "Miami" in p["address"])
    # seismic and wind differ (live data)
    assert sf_p["risk_scores"]["seismic_risk"] != mi_p["risk_scores"]["seismic_risk"], \
        f"Seismic identical: SF={sf_p['risk_scores']['seismic_risk']} Miami={mi_p['risk_scores']['seismic_risk']}"
    assert sf_p["risk_scores"]["wind_storm_risk"] != mi_p["risk_scores"]["wind_storm_risk"], \
        f"Wind identical: SF={sf_p['risk_scores']['wind_storm_risk']} Miami={mi_p['risk_scores']['wind_storm_risk']}"
    # data_sources tags
    for p in pols:
        ds = p["data_sources"]
        assert ds["seismic_risk"] == "live", f"seismic not live: {ds}"
        assert ds["wind_storm_risk"] == "live", f"wind not live: {ds}"
        for modeled_key in ("flood_risk", "wildfire_risk", "theft_risk", "security_risk", "property_condition"):
            assert ds[modeled_key] == "modeled"


def test_portfolio_avg_natcat_present(sf_miami_submission, auth_session):
    r = auth_session.get(f"{BASE_URL}/api/submissions/{sf_miami_submission}", timeout=15)
    assert r.status_code == 200
    assert "portfolio_avg_natcat" in r.json()


# ---------------- Security features + basement ----------------
def test_security_features_reduces_security_risk(auth_session):
    all_true = {k: True for k in ["alarm_system", "security_cameras", "smart_home_security",
                                    "fire_sprinklers", "fire_extinguishers", "smoke_detectors", "gated_access"]}
    payload = {
        "submitter_name": "TEST_sec",
        "submitter_email": "TEST_sec@example.com",
        "policies": [
            _basic_policy(address="10 Elm St, Boise, ID", security_features=all_true),
            _basic_policy(address="10 Elm St, Boise, ID", security_features={}),
        ],
    }
    sid, _ = _run_pipeline(payload)
    rec = auth_session.get(f"{BASE_URL}/api/submissions/{sid}", timeout=15).json()
    p_secured = rec["policies"][0]["risk_scores"]["security_risk"]
    p_bare = rec["policies"][1]["risk_scores"]["security_risk"]
    assert p_secured < p_bare, f"Secured({p_secured}) should be < Bare({p_bare})"
    assert p_secured == 0.0
    assert p_bare == 100.0


def test_basement_raises_flood_by_15(auth_session):
    addr = "20 Oak Ave, Dallas, TX"
    payload = {
        "submitter_name": "TEST_base",
        "submitter_email": "TEST_base@example.com",
        "policies": [
            _basic_policy(address=addr, security_features={"basement_present": True}),
            _basic_policy(address=addr, security_features={"basement_present": False}),
        ],
    }
    sid, _ = _run_pipeline(payload)
    rec = auth_session.get(f"{BASE_URL}/api/submissions/{sid}", timeout=15).json()
    with_base = rec["policies"][0]["risk_scores"]["flood_risk"]
    without = rec["policies"][1]["risk_scores"]["flood_risk"]
    # basement adds +15 (or capped at 100)
    expected = min(100.0, round(without + 15.0, 1))
    assert with_base == expected, f"basement flood: got {with_base}, expected {expected} (base {without})"


# ---------------- Validation: empty address ----------------
def test_empty_address_422():
    payload = {
        "submitter_name": "x", "submitter_email": "TEST_e@e.com",
        "policies": [_basic_policy(address="")],
    }
    r = requests.post(f"{BASE_URL}/api/submissions/process", json=payload, timeout=15)
    assert r.status_code == 422


# ---------------- Receipt PDF public + no scores ----------------
def test_receipt_pdf_public_no_scores(sf_miami_submission):
    r = requests.get(f"{BASE_URL}/api/submissions/{sf_miami_submission}/receipt.pdf", timeout=30)
    assert r.status_code == 200, r.text[:200]
    assert r.headers["content-type"].startswith("application/pdf")
    body = r.content
    assert body[:4] == b"%PDF"
    # Assert no risk score keywords bleeding into PDF text (best-effort scan of raw bytes)
    lower = body.lower()
    for banned in (b"seismic_risk", b"natcat", b"policy_composite", b"expected_loss"):
        assert banned not in lower, f"Receipt leaks {banned!r}"


# ---------------- Report PDF & CSV auth-gated ----------------
def test_report_pdf_requires_auth(sf_miami_submission):
    r = requests.get(f"{BASE_URL}/api/submissions/{sf_miami_submission}/report.pdf", timeout=15)
    assert r.status_code == 401


def test_policies_csv_requires_auth(sf_miami_submission):
    r = requests.get(f"{BASE_URL}/api/submissions/{sf_miami_submission}/policies.csv", timeout=15)
    assert r.status_code == 401


def test_report_pdf_auth_ok(sf_miami_submission, auth_session):
    r = auth_session.get(f"{BASE_URL}/api/submissions/{sf_miami_submission}/report.pdf", timeout=60)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:4] == b"%PDF"


def test_policies_csv_auth_ok(sf_miami_submission, auth_session):
    r = auth_session.get(f"{BASE_URL}/api/submissions/{sf_miami_submission}/policies.csv", timeout=30)
    assert r.status_code == 200
    ctype = r.headers["content-type"]
    assert "text/csv" in ctype, ctype
    text = r.text
    # header contains risk fields
    assert "seismic_risk" in text and "wind_storm_risk" in text and "policy_composite" in text


# ---------------- Auth session fixture (shared with backend_test) ----------------
@pytest.fixture(scope="session")
def auth_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/request-otp", json={"email": WHITELIST_EMAIL}, timeout=30)
    if r.status_code == 429:
        # fall back to another whitelisted email
        alt = "amankunawat4u@gmail.com"
        r = s.post(f"{BASE_URL}/api/auth/request-otp", json={"email": alt}, timeout=30)
        if r.status_code != 200:
            pytest.skip(f"OTP request failed for both emails: {r.status_code}")
        otp = _find_otp(alt)
        email_used = alt
    else:
        assert r.status_code == 200, r.text
        otp = _find_otp(WHITELIST_EMAIL)
        email_used = WHITELIST_EMAIL
    if not otp:
        pytest.skip("Could not read OTP from backend log")
    v = s.post(f"{BASE_URL}/api/auth/verify-otp", json={"email": email_used, "otp": otp}, timeout=15)
    assert v.status_code == 200, v.text
    return s
