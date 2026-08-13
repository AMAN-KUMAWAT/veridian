import React, { useEffect, useMemo, useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { ArrowLeft, Sparkles, CheckCircle2, Flag, Loader2, ShieldAlert, ShieldCheck, FileDown, Table2, Radio, Cpu, UserCheck, UserPlus } from "lucide-react";
import { Wordmark } from "../components/Logo";
import { api, API } from "../lib/api";
import { useAuth } from "../context/AuthContext";

const fmt = (n) => "$" + Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
const scoreColor = (s) => (s >= 60 ? "#EF4444" : s >= 40 ? "#F59E0B" : "#22C55E");
const PERIL_LABEL = { flood_risk: "Flood", seismic_risk: "Seismic", wildfire_risk: "Wildfire", wind_storm_risk: "Wind/Storm", theft_risk: "Theft", property_condition: "Property Cond.", security_risk: "Security" };
const actColor = (a) => ({ reviewed: "#22C55E", flagged: "#EF4444", claimed: "#0EA5A0", released: "#9CA3AF" }[a] || "#0F2C4C");

export default function SubmissionDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { email } = useAuth();
  const [rec, setRec] = useState(null);
  const [note, setNote] = useState("");
  const [insight, setInsight] = useState("");
  const [aiBusy, setAiBusy] = useState(false);

  const [cession, setCession] = useState(40);
  const [attachment, setAttachment] = useState(0);
  const [reserve, setReserve] = useState(0);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get(`/submissions/${id}`);
        setRec(data);
        setNote(data.review_note || "");
        setInsight(data.ai_insight || "");
        setAttachment(Math.round(data.aggregate_expected_loss * 0.2));
        setReserve(Math.round(data.total_sum_insured * 0.12));
      } catch { toast.error("Could not load submission"); nav("/insights"); }
    })();
  }, [id]);

  const loss = rec?.aggregate_expected_loss || 0;
  const ceded = useMemo(() => Math.max(0, loss - attachment) * (cession / 100), [loss, attachment, cession]);
  const retained = loss - ceded;
  const cededPremium = ceded * 1.2;
  const breach = retained > reserve && reserve > 0;
  const cededPct = loss > 0 ? (ceded / loss) * 100 : 0;

  const benchmark = useMemo(() => {
    if (!rec) return null;
    const avg = rec.portfolio_avg_natcat || 0;
    if (!avg) return null;
    const diff = rec.natcat_composite_score - avg;
    const pct = Math.round((Math.abs(diff) / avg) * 100);
    if (Math.abs(diff) < 0.5) return { text: "At portfolio average", color: "#6B7280", bg: "#F1F5F9" };
    return diff > 0
      ? { text: `${pct}% above portfolio average`, color: "#EF4444", bg: "#FEF2F2" }
      : { text: `${pct}% below average exposure`, color: "#22C55E", bg: "#F0FDF4" };
  }, [rec]);

  const provenance = useMemo(() => {
    if (!rec) return {};
    const map = {};
    for (const k of Object.keys(PERIL_LABEL)) {
      map[k] = rec.policies.some((p) => (p.data_sources || {})[k] === "live") ? "live" : "modeled";
    }
    return map;
  }, [rec]);

  const regionData = rec ? Object.entries(rec.exposure_by_region).map(([name, v]) => ({ name, value: v })) : [];
  const perilData = rec ? Object.entries(rec.avg_scores).map(([k, v]) => ({ name: PERIL_LABEL[k], value: v })) : [];

  const setReview = async (status) => {
    try {
      await api.post(`/submissions/${id}/review`, { status, note });
      const entry = { action: status.toLowerCase(), label: status, by: email, at: new Date().toISOString(), note };
      setRec({ ...rec, submission_status: status, review_note: note, activity: [...(rec.activity || []), entry] });
      toast.success(`Submission marked as ${status}`);
    } catch { toast.error("Update failed"); }
  };

  const genInsight = async () => {
    setAiBusy(true); setInsight("");
    try {
      const res = await fetch(`${API}/submissions/${id}/ai-insight`, { method: "POST", credentials: "include" });
      if (!res.ok) throw new Error("AI request failed");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        setInsight((p) => p + decoder.decode(value, { stream: true }));
      }
      toast.success("AI recommendation generated");
    } catch { toast.error("Could not generate insight"); } finally { setAiBusy(false); }
  };

  const claim = async (action) => {
    try {
      const { data } = await api.post(`/submissions/${id}/claim`, { action });
      const entry = { action: action === "claim" ? "claimed" : "released",
                      label: action === "claim" ? "Claimed" : "Released", by: email, at: new Date().toISOString() };
      setRec({ ...rec, assigned_to: data.assigned_to, activity: [...(rec.activity || []), entry] });
      toast.success(action === "claim" ? "You claimed this submission" : "Submission released");
    } catch (e) { toast.error(e.response?.data?.detail || "Action failed"); }
  };

  const reportUrl = `${API}/submissions/${id}/report.pdf?cession=${cession}&attachment=${Math.round(attachment)}&reserve=${Math.round(reserve)}`;
  const csvUrl = `${API}/submissions/${id}/policies.csv`;

  if (!rec) return (
    <div className="min-h-screen bg-[#F8FAFB]">
      <div className="bg-[#0F2C4C] h-16" />
      <div className="max-w-7xl mx-auto px-6 py-8 space-y-4" data-testid="detail-skeleton">
        <div className="h-10 w-1/3 bg-white rounded-lg animate-pulse" />
        <div className="grid grid-cols-4 gap-4">{[0, 1, 2, 3].map((i) => <div key={i} className="h-24 bg-white rounded-xl animate-pulse" />)}</div>
        <div className="grid lg:grid-cols-2 gap-6">{[0, 1].map((i) => <div key={i} className="h-64 bg-white rounded-xl animate-pulse" />)}</div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#F8FAFB]">
      <header className="bg-[#0F2C4C] sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Wordmark light />
          <Link to="/insights" className="text-sm text-[#E6F7F5]/80 hover:text-white flex items-center gap-1.5 transition-colors">
            <ArrowLeft size={16} /> Inbox
          </Link>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="overline text-[#0EA5A0] mb-1">{rec.submission_id}</div>
            <h1 className="font-head font-bold tracking-tight text-3xl text-[#0F2C4C]">{rec.submitter_organization || rec.submitter_name}</h1>
            <p className="text-sm text-[#1F2937]/60 mt-1">{rec.submitter_name} · {rec.submitter_email} · {rec.policies.length} policies</p>
          </div>
          <div className="flex items-center gap-3">
            {rec.assigned_to ? (
              <span className="px-3 py-2 rounded-full bg-[#E6F7F5] text-[#0EA5A0] text-xs font-medium flex items-center gap-1.5" data-testid="assignee-badge">
                <UserCheck size={14} /> {rec.assigned_to === email ? "Handled by you" : `Handled by ${rec.assigned_to}`}
                {rec.assigned_to === email && <button onClick={() => claim("release")} data-testid="release-button" className="ml-1 text-[#0F2C4C]/60 hover:text-[#EF4444] underline">release</button>}
              </span>
            ) : (
              <button onClick={() => claim("claim")} data-testid="claim-button"
                className="px-4 py-2 rounded-full border border-[#0EA5A0] text-[#0EA5A0] text-sm font-medium flex items-center gap-2 hover:bg-[#E6F7F5] transition-colors">
                <UserPlus size={15} /> Claim
              </button>
            )}
            <a href={reportUrl} target="_blank" rel="noreferrer" data-testid="export-report-button"
              className="px-4 py-2 rounded-full bg-[#0F2C4C] text-white text-sm font-medium flex items-center gap-2 hover:-translate-y-px hover:shadow-lg transition-transform">
              <FileDown size={15} /> Export Full Report (PDF)
            </a>
            <a href={csvUrl} target="_blank" rel="noreferrer" data-testid="export-csv-button"
              className="px-4 py-2 rounded-full border border-[#0F2C4C]/20 text-[#0F2C4C] text-sm font-medium flex items-center gap-2 hover:bg-white transition-colors">
              <Table2 size={15} /> Per-Policy CSV
            </a>
          </div>
        </div>

        {/* Top metrics */}
        <div className="mt-6 grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Metric label="Total Sum Insured" value={fmt(rec.total_sum_insured)} />
          <Metric label="Aggregate Expected CAT Loss" value={fmt(rec.aggregate_expected_loss)} accent="#EF4444" />
          <div className="bg-white border border-[#E5E7EB] rounded-xl p-5">
            <div className="mono text-2xl font-bold" style={{ color: scoreColor(rec.natcat_composite_score) }}>{rec.natcat_composite_score}</div>
            <div className="overline text-[#1F2937]/50 mt-1">NatCat Composite</div>
            {benchmark && (
              <span className="inline-block mt-2 text-xs font-medium px-2 py-1 rounded-full" style={{ color: benchmark.color, background: benchmark.bg }} data-testid="benchmark-badge">
                {benchmark.text}
              </span>
            )}
          </div>
          <Metric label="Regions" value={Object.keys(rec.exposure_by_region).length} />
        </div>

        <div className="mt-6 grid lg:grid-cols-2 gap-6">
          <Panel title="Portfolio Exposure — by Region">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={regionData} layout="vertical" margin={{ left: 10 }}>
                <XAxis type="number" tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="name" width={90} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => fmt(v)} />
                <Bar dataKey="value" radius={[0, 4, 4, 0]} fill="#0EA5A0" />
              </BarChart>
            </ResponsiveContainer>
          </Panel>

          <Panel title="Average Peril Risk Scores">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={perilData} margin={{ top: 10 }}>
                <XAxis dataKey="name" tick={{ fontSize: 9 }} interval={0} angle={-20} textAnchor="end" height={54} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {perilData.map((d, i) => <Cell key={i} fill={scoreColor(d.value)} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div className="mt-3 flex flex-wrap gap-2" data-testid="provenance-tags">
              {Object.entries(PERIL_LABEL).map(([k, label]) => (
                <span key={k} className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full ${provenance[k] === "live" ? "bg-[#E6F7F5] text-[#0EA5A0]" : "bg-[#F1F5F9] text-[#6B7280]"}`}>
                  {provenance[k] === "live" ? <Radio size={10} /> : <Cpu size={10} />}
                  {label}: {provenance[k] === "live" ? "Live data" : "Modeled estimate"}
                </span>
              ))}
            </div>
          </Panel>
        </div>

        {/* Treaty simulator + capital reserve */}
        <div className="mt-6 grid lg:grid-cols-2 gap-6">
          <Panel title="Reinsurance Treaty Simulator (Quota Share)">
            <div className="space-y-5">
              <Slider label="Cession %" value={cession} min={0} max={100} step={5} onChange={setCession} display={`${cession}%`} testid="cession-slider" />
              <Slider label="Attachment Point (retention floor)" value={attachment} min={0} max={Math.max(1, Math.round(loss))} step={1000} onChange={setAttachment} display={fmt(attachment)} testid="attachment-slider" />
              {/* live stacked bar */}
              <div>
                <div className="flex justify-between overline text-[#1F2937]/60 mb-1"><span>Retained vs Ceded</span></div>
                <div className="h-7 w-full rounded-lg overflow-hidden flex bg-[#F1F5F9]" data-testid="treaty-bar">
                  <div className="h-full flex items-center justify-center text-[10px] font-bold text-white transition-all duration-300" style={{ width: `${100 - cededPct}%`, background: "#0F2C4C" }}>
                    {100 - cededPct > 12 ? "Retained" : ""}
                  </div>
                  <div className="h-full flex items-center justify-center text-[10px] font-bold text-white transition-all duration-300" style={{ width: `${cededPct}%`, background: "#0EA5A0" }}>
                    {cededPct > 12 ? "Ceded" : ""}
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 pt-1">
                <MiniStat label="Retained Loss" value={fmt(retained)} color="#0F2C4C" testid="retained-loss" />
                <MiniStat label="Ceded Loss" value={fmt(ceded)} color="#0EA5A0" testid="ceded-loss" />
                <MiniStat label="Ceded Premium (est.)" value={fmt(cededPremium)} color="#F59E0B" testid="ceded-premium" />
              </div>
            </div>
          </Panel>

          <Panel title="Risk Appetite / Capital Reserve Check">
            <Slider label="Capital Reserve Threshold" value={reserve} min={0} max={Math.max(1, Math.round(rec.total_sum_insured * 0.3))} step={5000} onChange={setReserve} display={fmt(reserve)} testid="reserve-slider" />
            <div className={`mt-5 rounded-xl p-5 border flex items-start gap-3 ${breach ? "bg-red-50 border-[#EF4444]/40" : "bg-green-50 border-[#22C55E]/40"}`} data-testid="reserve-flag">
              {breach ? <ShieldAlert className="text-[#EF4444] mt-0.5" strokeWidth={1.5} /> : <ShieldCheck className="text-[#22C55E] mt-0.5" strokeWidth={1.5} />}
              <div>
                <div className="font-head font-semibold" style={{ color: breach ? "#EF4444" : "#22C55E" }}>
                  {breach ? "Capital reserve BREACHED" : "Within capital reserve"}
                </div>
                <p className="text-sm text-[#1F2937]/70 mt-1">
                  Modeled retained loss of <span className="mono font-medium">{fmt(retained)}</span> {breach ? "exceeds" : "is within"} the reserve threshold of <span className="mono font-medium">{fmt(reserve)}</span>.
                </p>
              </div>
            </div>
          </Panel>
        </div>

        {/* AI Insight */}
        <div className="mt-6">
          <Panel title="AI Underwriting Insight (Claude)">
            <button onClick={genInsight} disabled={aiBusy} data-testid="generate-insight-button"
              className="px-5 py-2.5 rounded-full bg-[#0F2C4C] text-white text-sm font-medium flex items-center gap-2 hover:-translate-y-px hover:shadow-lg transition-transform disabled:opacity-60">
              {aiBusy ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />} Generate recommendation
            </button>
            {insight && (
              <div className="mt-4 bg-[#E6F7F5]/50 border border-[#0EA5A0]/20 rounded-xl p-5 text-sm text-[#1F2937] leading-relaxed whitespace-pre-wrap" data-testid="ai-insight-text">
                {insight}
              </div>
            )}
          </Panel>
        </div>

        {/* Per-policy breakdown */}
        <div className="mt-6">
          <Panel title="Per-Policy Risk Breakdown">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="policy-breakdown-table">
                <thead>
                  <tr className="text-left overline text-[#1F2937]/50 border-b border-[#E5E7EB]">
                    <th className="px-3 py-2">Policy</th><th className="px-3 py-2">Address</th>
                    <th className="px-3 py-2 text-right">Sum Insured</th>
                    {Object.values(PERIL_LABEL).map((l) => <th key={l} className="px-3 py-2 text-center">{l}</th>)}
                    <th className="px-3 py-2 text-center">Composite</th><th className="px-3 py-2 text-right">Exp. Loss</th>
                  </tr>
                </thead>
                <tbody>
                  {rec.policies.map((p, idx) => (
                    <tr key={p.policy_id} className={`border-b border-[#F1F5F9] hover:bg-[#E6F7F5]/40 transition-colors ${idx % 2 ? "bg-[#F8FAFB]/60" : ""}`}>
                      <td className="px-3 py-2.5 mono text-[#0F2C4C]">{p.policy_id}</td>
                      <td className="px-3 py-2.5 text-[#1F2937]/70 max-w-[180px] truncate">{p.address}</td>
                      <td className="px-3 py-2.5 text-right mono">{fmt(p.sum_insured)}</td>
                      {Object.keys(PERIL_LABEL).map((k) => (
                        <td key={k} className="px-3 py-2.5 text-center mono" style={{ color: scoreColor(p.risk_scores[k]) }}>{p.risk_scores[k]}</td>
                      ))}
                      <td className="px-3 py-2.5 text-center mono font-bold" style={{ color: scoreColor(p.policy_composite) }}>{p.policy_composite}</td>
                      <td className="px-3 py-2.5 text-right mono text-[#EF4444]">{fmt(p.expected_loss)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>

        {/* Reviewer activity trail */}
        <div className="mt-6">
          <Panel title="Reviewer Activity">
            {rec.activity && rec.activity.length ? (
              <ol className="relative border-l border-[#E5E7EB] ml-2" data-testid="activity-trail">
                {rec.activity.slice().reverse().map((a, i) => (
                  <li key={i} className="ml-5 pb-4 last:pb-0 relative">
                    <span className="absolute -left-[26px] top-1 w-3 h-3 rounded-full ring-4 ring-white" style={{ background: actColor(a.action) }} />
                    <div className="text-sm text-[#1F2937]"><b className="capitalize">{a.label || a.action}</b> by {a.by === email ? "you" : a.by}</div>
                    <div className="text-xs text-[#1F2937]/50 mono">{new Date(a.at).toLocaleString()}</div>
                    {a.note && <div className="text-xs text-[#1F2937]/70 mt-1 italic">"{a.note}"</div>}
                  </li>
                ))}
              </ol>
            ) : <p className="text-sm text-[#1F2937]/50">No activity yet. Claim, review or flag this submission to start the trail.</p>}
          </Panel>
        </div>

        {/* Review action */}
        <div className="mt-6">
          <Panel title="Reviewer Action">
            <textarea value={note} onChange={(e) => setNote(e.target.value)} data-testid="review-note"
              placeholder="Add a review note…" rows={3}
              className="w-full px-3.5 py-2.5 rounded-lg border border-[#E5E7EB] text-sm focus:ring-2 focus:ring-[#0EA5A0] focus:outline-none transition-colors" />
            <div className="mt-4 flex gap-3">
              <button onClick={() => setReview("Reviewed")} data-testid="mark-reviewed-button"
                className="px-5 py-2.5 rounded-full bg-[#22C55E] text-white text-sm font-medium flex items-center gap-2 hover:-translate-y-px hover:shadow-lg transition-transform">
                <CheckCircle2 size={16} /> Mark Reviewed
              </button>
              <button onClick={() => setReview("Flagged")} data-testid="mark-flagged-button"
                className="px-5 py-2.5 rounded-full bg-[#EF4444] text-white text-sm font-medium flex items-center gap-2 hover:-translate-y-px hover:shadow-lg transition-transform">
                <Flag size={16} /> Flag
              </button>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

const Metric = ({ label, value, accent = "#0F2C4C" }) => (
  <div className="bg-white border border-[#E5E7EB] rounded-xl p-5">
    <div className="mono text-2xl font-bold" style={{ color: accent }}>{value}</div>
    <div className="overline text-[#1F2937]/50 mt-1">{label}</div>
  </div>
);

const Panel = ({ title, children }) => (
  <div className="bg-white border border-[#E5E7EB] rounded-xl p-6">
    <h3 className="font-head font-semibold text-[#0F2C4C] mb-4">{title}</h3>
    {children}
  </div>
);

const Slider = ({ label, value, min, max, step, onChange, display, testid }) => (
  <div>
    <div className="flex justify-between items-center mb-2">
      <span className="overline text-[#1F2937]/60">{label}</span>
      <span className="mono text-sm font-bold text-[#0F2C4C]">{display}</span>
    </div>
    <input type="range" min={min} max={max} step={step} value={value} data-testid={testid}
      onChange={(e) => onChange(Number(e.target.value))} className="w-full accent-[#0EA5A0] cursor-pointer" />
  </div>
);

const MiniStat = ({ label, value, color, testid }) => (
  <div className="bg-[#F8FAFB] rounded-lg p-3 border border-[#E5E7EB]">
    <div className="mono text-base font-bold" style={{ color }} data-testid={testid}>{value}</div>
    <div className="overline text-[#1F2937]/50 mt-1 text-[0.6rem]">{label}</div>
  </div>
);
