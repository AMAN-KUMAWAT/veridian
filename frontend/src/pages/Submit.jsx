import React, { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { Plus, Trash2, ArrowLeft, CheckCircle2, Loader2, Building2, ShieldCheck, Download, Mail } from "lucide-react";
import { Wordmark } from "../components/Logo";
import { API } from "../lib/api";

const emptySecurity = () => ({
  alarm_system: false, security_cameras: false, smart_home_security: false,
  fire_sprinklers: false, fire_extinguishers: false, smoke_detectors: false,
  gated_access: false, basement_present: false,
});
const emptyPolicy = () => ({
  address: "", property_type: "residential", construction_type: "Concrete",
  year_built: 2005, sum_insured: 500000, region: "", peril_focus: "",
  security_features: emptySecurity(),
});

const PROP_TYPES = ["residential", "commercial", "industrial", "mixed-use"];
const CONSTRUCTION = ["Concrete", "Steel", "Masonry", "Wood", "Mixed"];
const SECURITY_FIELDS = [
  ["alarm_system", "Alarm system"], ["security_cameras", "Security cameras"],
  ["smart_home_security", "Smart home security"], ["fire_sprinklers", "Fire sprinklers"],
  ["fire_extinguishers", "Fire extinguishers"], ["smoke_detectors", "Smoke detectors"],
  ["gated_access", "Gated access"], ["basement_present", "Basement present"],
];
const YEAR_NOW = new Date().getFullYear();
const emailOk = (v) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v);

export default function Submit() {
  const [stage, setStage] = useState("form");
  const [submitter, setSubmitter] = useState({ submitter_name: "", submitter_email: "", submitter_organization: "" });
  const [policies, setPolicies] = useState([emptyPolicy()]);
  const [events, setEvents] = useState([]);
  const [refId, setRefId] = useState("");
  const [receiptUrl, setReceiptUrl] = useState("");
  const [errors, setErrors] = useState({});

  const updatePolicy = (i, field, val) => {
    const next = [...policies]; next[i][field] = val; setPolicies(next);
  };
  const toggleSecurity = (i, key) => {
    const next = [...policies]; next[i].security_features[key] = !next[i].security_features[key]; setPolicies(next);
  };
  const addPolicy = () => { if (policies.length < 20) setPolicies([...policies, emptyPolicy()]); };
  const removePolicy = (i) => setPolicies(policies.filter((_, idx) => idx !== i));

  const fieldError = (key, val, pIdx = null) => {
    if (key === "submitter_name") return !String(val).trim() ? "Name is required" : "";
    if (key === "submitter_email") return !emailOk(val) ? "Enter a valid email" : "";
    if (key === "address") return String(val).trim().length < 3 ? "Address is required" : "";
    if (key === "construction_type") return !val ? "Required" : "";
    if (key === "year_built") {
      const y = Number(val);
      if (!Number.isInteger(y) || y < 1800 || y > YEAR_NOW) return `1800-${YEAR_NOW}`;
      return "";
    }
    if (key === "sum_insured") return Number(val) > 0 ? "" : "Must be > 0";
    return "";
  };

  const blur = (key, val, pIdx = null) => {
    const ek = pIdx === null ? key : `p${pIdx}_${key}`;
    setErrors((prev) => ({ ...prev, [ek]: fieldError(key, val, pIdx) }));
  };

  const formValid = useMemo(() => {
    if (fieldError("submitter_name", submitter.submitter_name)) return false;
    if (fieldError("submitter_email", submitter.submitter_email)) return false;
    for (const p of policies) {
      if (fieldError("address", p.address)) return false;
      if (fieldError("construction_type", p.construction_type)) return false;
      if (fieldError("year_built", p.year_built)) return false;
      if (fieldError("sum_insured", p.sum_insured)) return false;
    }
    return true;
  }, [submitter, policies]);

  const submit = async () => {
    if (!formValid) { toast.error("Please fix the highlighted fields"); return; }
    setStage("processing"); setEvents([]);
    const payload = {
      ...submitter,
      policies: policies.map((p) => ({ ...p, year_built: Number(p.year_built), sum_insured: Number(p.sum_insured) })),
    };
    try {
      const res = await fetch(`${API}/submissions/process`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || "Submission failed"); }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop();
        for (const part of parts) {
          const line = part.replace(/^data:\s?/, "").trim();
          if (!line) continue;
          const evt = JSON.parse(line);
          setEvents((prev) => [...prev, evt]);
          if (evt.step_name === "complete") { setRefId(evt.data.submission_id); setReceiptUrl(evt.data.receipt_url || ""); }
        }
      }
      setStage("done");
    } catch (e) {
      toast.error(e.message || "Something went wrong");
      setStage("form");
    }
  };

  return (
    <div className="min-h-screen bg-[#F8FAFB]">
      <header className="glass-header sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/"><Wordmark /></Link>
          <Link to="/" className="text-sm text-[#0F2C4C] hover:text-[#0EA5A0] flex items-center gap-1.5 transition-colors">
            <ArrowLeft size={16} /> Back
          </Link>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-12">
        {stage === "form" && (
          <div>
            <div className="overline text-[#0EA5A0] mb-2">Public Submission Portal</div>
            <h1 className="font-head font-bold tracking-tight text-3xl sm:text-4xl text-[#0F2C4C]">Submit your portfolio</h1>
            <p className="mt-3 text-[#1F2937]/80 max-w-2xl">Add your book of business below. Every policy is scored against live catastrophe data. No login required.</p>

            <div className="mt-10 bg-white border border-[#E5E7EB] rounded-2xl p-8">
              <h2 className="font-head font-semibold text-lg text-[#0F2C4C] mb-5">Submitter details</h2>
              <div className="grid sm:grid-cols-3 gap-5">
                <Field label="Full name *" testid="submitter-name" value={submitter.submitter_name}
                  onChange={(v) => setSubmitter({ ...submitter, submitter_name: v })}
                  onBlur={(v) => blur("submitter_name", v)} error={errors.submitter_name} />
                <Field label="Email *" testid="submitter-email" type="email" value={submitter.submitter_email}
                  onChange={(v) => setSubmitter({ ...submitter, submitter_email: v })}
                  onBlur={(v) => blur("submitter_email", v)} error={errors.submitter_email} />
                <Field label="Organization" testid="submitter-org" value={submitter.submitter_organization}
                  onChange={(v) => setSubmitter({ ...submitter, submitter_organization: v })} />
              </div>
            </div>

            <div className="mt-6 flex items-center justify-between">
              <h2 className="font-head font-semibold text-lg text-[#0F2C4C] flex items-center gap-2">
                <Building2 size={20} className="text-[#0EA5A0]" strokeWidth={1.5} /> Policies ({policies.length})
              </h2>
              <button onClick={addPolicy} data-testid="add-policy-btn" disabled={policies.length >= 20}
                className="flex items-center gap-1.5 text-sm font-medium text-[#0EA5A0] hover:text-[#0F2C4C] transition-colors disabled:opacity-40">
                <Plus size={16} /> Add policy
              </button>
            </div>

            <div className="mt-4 space-y-4">
              {policies.map((p, i) => (
                <div key={i} className="bg-white border border-[#E5E7EB] rounded-xl p-6" data-testid={`policy-row-${i}`}>
                  <div className="flex items-center justify-between mb-4">
                    <span className="mono text-xs text-[#0EA5A0]">POLICY {i + 1}</span>
                    {policies.length > 1 && (
                      <button onClick={() => removePolicy(i)} data-testid={`remove-policy-${i}`}
                        className="text-[#EF4444] hover:opacity-70 transition-opacity"><Trash2 size={16} /></button>
                    )}
                  </div>
                  <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    <div className="lg:col-span-3">
                      <Field label="Property address *" testid={`policy-address-${i}`} value={p.address}
                        onChange={(v) => updatePolicy(i, "address", v)} onBlur={(v) => blur("address", v, i)}
                        error={errors[`p${i}_address`]} placeholder="e.g. 1600 Amphitheatre Pkwy, Mountain View, CA" />
                    </div>
                    <Select label="Property type *" testid={`policy-type-${i}`} options={PROP_TYPES}
                      value={p.property_type} onChange={(v) => updatePolicy(i, "property_type", v)} />
                    <Select label="Construction *" testid={`policy-construction-${i}`} options={CONSTRUCTION}
                      value={p.construction_type} onChange={(v) => updatePolicy(i, "construction_type", v)} />
                    <Field label="Year built *" testid={`policy-year-${i}`} type="number" value={p.year_built}
                      onChange={(v) => updatePolicy(i, "year_built", v)} onBlur={(v) => blur("year_built", v, i)}
                      error={errors[`p${i}_year_built`]} />
                    <Field label="Sum insured (USD) *" testid={`policy-sum-${i}`} type="number" value={p.sum_insured}
                      onChange={(v) => updatePolicy(i, "sum_insured", v)} onBlur={(v) => blur("sum_insured", v, i)}
                      error={errors[`p${i}_sum_insured`]} />
                    <Field label="Peril focus (optional)" testid={`policy-peril-${i}`} value={p.peril_focus}
                      onChange={(v) => updatePolicy(i, "peril_focus", v)} placeholder="e.g. flood-prone" />
                  </div>

                  <div className="mt-5 pt-4 border-t border-[#F1F5F9]">
                    <div className="overline text-[#1F2937]/60 flex items-center gap-1.5 mb-3">
                      <ShieldCheck size={14} className="text-[#0EA5A0]" /> Security & risk features
                    </div>
                    <div className="grid grid-cols-2 gap-x-6 gap-y-2.5">
                      {SECURITY_FIELDS.map(([key, label]) => (
                        <label key={key} className="flex items-center gap-2.5 text-sm text-[#1F2937] cursor-pointer select-none">
                          <input type="checkbox" checked={p.security_features[key]}
                            onChange={() => toggleSecurity(i, key)} data-testid={`policy-${i}-${key}`}
                            className="w-4 h-4 accent-[#0EA5A0] cursor-pointer" />
                          {label}
                        </label>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <button onClick={submit} data-testid="submit-portfolio-button" disabled={!formValid}
              className="mt-8 px-8 py-4 rounded-full bg-[#0EA5A0] text-white font-medium hover:-translate-y-px hover:shadow-xl transition-transform disabled:opacity-40 disabled:hover:translate-y-0 disabled:hover:shadow-none disabled:cursor-not-allowed">
              Run Risk Analysis
            </button>
            {!formValid && <p className="mt-3 text-sm text-[#1F2937]/50">Complete all required (*) fields to enable analysis.</p>}
          </div>
        )}

        {stage === "processing" && (
          <div className="max-w-2xl mx-auto py-10" data-testid="processing-view">
            <div className="overline text-[#0EA5A0] mb-2">Live Pipeline</div>
            <h1 className="font-head font-bold tracking-tight text-3xl text-[#0F2C4C] flex items-center gap-3">
              <Loader2 className="animate-spin text-[#0EA5A0]" /> Analyzing portfolio…
            </h1>
            <div className="mt-8 bg-[#0F2C4C] rounded-2xl p-6 max-h-[460px] overflow-auto">
              {events.map((e, i) => (
                <motion.div key={i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
                  className="flex items-start gap-3 py-1.5 mono text-[13px]">
                  <span className={`mt-0.5 ${e.status === "done" || e.status === "complete" ? "text-[#22C55E]" : "text-[#0EA5A0]"}`}>›</span>
                  <div>
                    <span className="text-[#E6F7F5]">{e.message}</span>
                    <span className="block text-[#E6F7F5]/40 text-[11px]">{e.step_name}</span>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        )}

        {stage === "done" && (
          <div className="max-w-xl mx-auto py-16 text-center" data-testid="confirmation-view">
            <div className="w-20 h-20 rounded-full bg-[#E6F7F5] flex items-center justify-center mx-auto mb-6">
              <CheckCircle2 size={44} className="text-[#22C55E]" strokeWidth={1.5} />
            </div>
            <h1 className="font-head font-bold tracking-tight text-3xl text-[#0F2C4C]">Submission received</h1>
            <p className="mt-4 text-[#1F2937]/80 flex items-center justify-center gap-1.5">
              <Mail size={16} className="text-[#0EA5A0]" /> A copy has been emailed to {submitter.submitter_email}
            </p>
            <div className="mt-6 inline-block bg-white border border-[#0EA5A0]/30 rounded-xl px-8 py-5">
              <div className="overline text-[#0EA5A0] mb-1">Reference ID</div>
              <div className="mono text-2xl font-bold text-[#0F2C4C]" data-testid="reference-id">{refId}</div>
            </div>
            <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
              <a href={receiptUrl} target="_blank" rel="noreferrer"
                data-testid="download-receipt-button"
                className="px-6 py-3 rounded-full bg-[#0EA5A0] text-white font-medium flex items-center gap-2 hover:-translate-y-px hover:shadow-lg transition-transform">
                <Download size={17} /> Download Submission Receipt
              </a>
              <Link to="/" className="px-6 py-3 rounded-full border border-[#0F2C4C]/20 text-[#0F2C4C] font-medium hover:bg-white transition-colors">
                Back to home
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const Field = ({ label, value, onChange, onBlur, error, type = "text", testid, placeholder }) => (
  <label className="block">
    <span className="overline text-[#1F2937]/60 block mb-1.5">{label}</span>
    <input type={type} value={value} placeholder={placeholder} data-testid={testid}
      onChange={(e) => onChange(e.target.value)} onBlur={onBlur ? (e) => onBlur(e.target.value) : undefined}
      className={`w-full px-3.5 py-2.5 rounded-lg border bg-white text-[#1F2937] text-sm focus:ring-2 focus:outline-none transition-colors ${error ? "border-[#EF4444] focus:ring-[#EF4444]/40" : "border-[#E5E7EB] focus:ring-[#0EA5A0] focus:border-[#0EA5A0]"}`} />
    {error && <span className="text-xs text-[#EF4444] mt-1 block" data-testid={`${testid}-error`}>{error}</span>}
  </label>
);

const Select = ({ label, value, onChange, options, testid }) => (
  <label className="block">
    <span className="overline text-[#1F2937]/60 block mb-1.5">{label}</span>
    <select value={value} data-testid={testid} onChange={(e) => onChange(e.target.value)}
      className="w-full px-3.5 py-2.5 rounded-lg border border-[#E5E7EB] bg-white text-[#1F2937] text-sm focus:ring-2 focus:ring-[#0EA5A0] focus:outline-none transition-colors capitalize">
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  </label>
);
