import React, { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { LogOut, Inbox, TrendingUp, AlertTriangle, Layers, ChevronRight, Search, ArrowUpDown, ArrowUp, ArrowDown, ChevronLeft, MapPin, UserCheck, UserPlus } from "lucide-react";
import { Wordmark } from "../components/Logo";
import { PortfolioMap } from "../components/PortfolioMap";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";

const fmt = (n) => "$" + Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
const scoreColor = (s) => (s >= 60 ? "#EF4444" : s >= 40 ? "#F59E0B" : "#22C55E");
const statusStyle = { Received: "bg-[#E6F7F5] text-[#0EA5A0]", Reviewed: "bg-green-50 text-[#22C55E]", Flagged: "bg-red-50 text-[#EF4444]" };
const PAGE_SIZE = 15;

export default function Dashboard() {
  const { email, logout } = useAuth();
  const [subs, setSubs] = useState([]);
  const [overview, setOverview] = useState(null);
  const [mapPoints, setMapPoints] = useState([]);
  const [loading, setLoading] = useState(true);
  const nav = useNavigate();

  // filters
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("All");
  const [assignee, setAssignee] = useState("All");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [natMin, setNatMin] = useState(0);
  const [natMax, setNatMax] = useState(100);
  const [sortKey, setSortKey] = useState("created_at");
  const [sortDir, setSortDir] = useState("desc");
  const [page, setPage] = useState(1);

  useEffect(() => {
    (async () => {
      try {
        const [s, o, m] = await Promise.all([api.get("/submissions"), api.get("/portfolio/overview"), api.get("/portfolio/map")]);
        setSubs(s.data); setOverview(o.data); setMapPoints(m.data.points || []);
      } finally { setLoading(false); }
    })();
  }, []);

  const doLogout = async () => { await logout(); nav("/insights/login"); };

  const claim = async (e, s, action) => {
    e.stopPropagation();
    try {
      const { data } = await api.post(`/submissions/${s.submission_id}/claim`, { action });
      setSubs((prev) => prev.map((x) => x.submission_id === s.submission_id ? { ...x, assigned_to: data.assigned_to } : x));
      toast.success(action === "claim" ? "Submission claimed" : "Submission released");
    } catch (err) { toast.error(err.response?.data?.detail || "Action failed"); }
  };

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("asc"); }
    setPage(1);
  };

  const filtered = useMemo(() => {
    let rows = subs.filter((s) => {
      const text = `${s.submission_id} ${s.submitter_name} ${s.submitter_email}`.toLowerCase();
      if (q && !text.includes(q.toLowerCase())) return false;
      if (status !== "All" && s.submission_status !== status) return false;
      if (assignee === "Mine" && s.assigned_to !== email) return false;
      if (assignee === "Unclaimed" && s.assigned_to) return false;
      if (natMin > s.natcat_composite_score || s.natcat_composite_score > natMax) return false;
      const d = new Date(s.created_at);
      if (dateFrom && d < new Date(dateFrom)) return false;
      if (dateTo && d > new Date(dateTo + "T23:59:59")) return false;
      return true;
    });
    rows = [...rows].sort((a, b) => {
      let av = a[sortKey], bv = b[sortKey];
      if (sortKey === "created_at") { av = new Date(av); bv = new Date(bv); }
      if (typeof av === "string") { av = av.toLowerCase(); bv = (bv || "").toLowerCase(); }
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return rows;
  }, [subs, q, status, assignee, email, natMin, natMax, dateFrom, dateTo, sortKey, sortDir]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageRows = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const stats = overview ? [
    { label: "Total submissions", value: overview.total_submissions, icon: Inbox, color: "#0EA5A0" },
    { label: "Exposure under mgmt", value: fmt(overview.total_exposure), icon: Layers, color: "#0F2C4C" },
    { label: "Avg NatCat score", value: overview.average_natcat_score, icon: TrendingUp, color: "#F59E0B" },
    { label: "Capital reserve breaches", value: overview.capital_reserve_breaches, icon: AlertTriangle, color: "#EF4444" },
  ] : [];

  const SortHead = ({ label, k, align = "left" }) => (
    <th className={`px-5 py-3 cursor-pointer select-none hover:text-[#0EA5A0] transition-colors text-${align}`}
      onClick={() => toggleSort(k)} data-testid={`sort-${k}`}>
      <span className="inline-flex items-center gap-1">{label}
        {sortKey === k ? (sortDir === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />) : <ArrowUpDown size={12} className="opacity-30" />}
      </span>
    </th>
  );

  return (
    <div className="min-h-screen bg-[#F8FAFB]">
      <header className="bg-[#0F2C4C] sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Wordmark light />
          <div className="flex items-center gap-4">
            <span className="text-sm text-[#E6F7F5]/80 hidden sm:block mono">{email}</span>
            <button onClick={() => nav("/insights/settings")} data-testid="settings-link"
              className="text-sm text-[#E6F7F5]/80 hover:text-white transition-colors">Settings</button>
            <button onClick={doLogout} data-testid="logout-button"
              className="flex items-center gap-1.5 text-sm text-white hover:text-[#0EA5A0] transition-colors">
              <LogOut size={16} /> Logout
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-10">
        <div className="overline text-[#0EA5A0] mb-2">Portfolio-Wide View</div>
        <h1 className="font-head font-bold tracking-tight text-3xl text-[#0F2C4C]">Insights Dashboard</h1>

        <div className="mt-8 grid grid-cols-2 lg:grid-cols-4 gap-4">
          {loading ? [0, 1, 2, 3].map((i) => <div key={i} className="h-[110px] rounded-xl bg-white border border-[#E5E7EB] animate-pulse" />)
            : stats.map((s, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}
                className="bg-white border border-[#E5E7EB] rounded-xl p-5 hover:shadow-sm transition-shadow" data-testid={`stat-${i}`}>
                <s.icon size={20} style={{ color: s.color }} strokeWidth={1.5} />
                <div className="mt-3 mono text-2xl font-bold text-[#0F2C4C]">{s.value}</div>
                <div className="overline text-[#1F2937]/50 mt-1">{s.label}</div>
              </motion.div>
            ))}
        </div>

        <div className="mt-10 flex items-center gap-2">
          <MapPin size={20} className="text-[#0EA5A0]" strokeWidth={1.5} />
          <h2 className="font-head font-semibold text-xl text-[#0F2C4C]">Portfolio Risk Heatmap</h2>
        </div>
        <div className="mt-4 bg-white border border-[#E5E7EB] rounded-xl p-2">
          {loading ? <div className="h-[380px] rounded-lg bg-[#F1F5F9] animate-pulse" />
            : mapPoints.length ? <PortfolioMap points={mapPoints} />
            : <div className="h-[380px] flex items-center justify-center text-[#1F2937]/50">No geocoded policies to map yet</div>}
        </div>
        <div className="mt-3 flex items-center gap-5 text-xs text-[#1F2937]/60">
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full inline-block" style={{ background: "#22C55E" }} /> Low (&lt;40)</span>
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full inline-block" style={{ background: "#F59E0B" }} /> Moderate (40-59)</span>
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full inline-block" style={{ background: "#EF4444" }} /> High (60+)</span>
        </div>
        <p className="mt-2 text-xs text-[#1F2937]/50" data-testid="cluster-legend-note">Cluster color reflects the <b>average composite risk</b> of the policies grouped inside it (the small number shows that average); zoom in to see individual policies.</p>

        <div className="mt-10 flex items-center gap-2">
          <Inbox size={20} className="text-[#0EA5A0]" strokeWidth={1.5} />
          <h2 className="font-head font-semibold text-xl text-[#0F2C4C]">Submissions Inbox</h2>
        </div>

        {/* Filters */}
        <div className="mt-4 bg-white border border-[#E5E7EB] rounded-xl p-4 grid md:grid-cols-2 lg:grid-cols-5 gap-4">
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#0EA5A0]" />
            <input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} data-testid="inbox-search"
              placeholder="Search ref, name or email" className="w-full pl-9 pr-3 py-2.5 rounded-lg border border-[#E5E7EB] text-sm focus:ring-2 focus:ring-[#0EA5A0] focus:outline-none transition-colors" />
          </div>
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} data-testid="inbox-status-filter"
            className="px-3 py-2.5 rounded-lg border border-[#E5E7EB] text-sm focus:ring-2 focus:ring-[#0EA5A0] focus:outline-none transition-colors">
            {["All", "Received", "Reviewed", "Flagged"].map((s) => <option key={s}>{s}</option>)}
          </select>
          <select value={assignee} onChange={(e) => { setAssignee(e.target.value); setPage(1); }} data-testid="inbox-assignee-filter"
            className="px-3 py-2.5 rounded-lg border border-[#E5E7EB] text-sm focus:ring-2 focus:ring-[#0EA5A0] focus:outline-none transition-colors">
            <option value="All">All assignees</option>
            <option value="Mine">Assigned to me</option>
            <option value="Unclaimed">Unclaimed</option>
          </select>
          <div className="flex items-center gap-2">
            <input type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(1); }} data-testid="inbox-date-from"
              className="w-full px-2 py-2.5 rounded-lg border border-[#E5E7EB] text-xs focus:ring-2 focus:ring-[#0EA5A0] focus:outline-none" />
            <span className="text-[#1F2937]/40 text-xs">to</span>
            <input type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(1); }} data-testid="inbox-date-to"
              className="w-full px-2 py-2.5 rounded-lg border border-[#E5E7EB] text-xs focus:ring-2 focus:ring-[#0EA5A0] focus:outline-none" />
          </div>
          <div>
            <div className="flex justify-between overline text-[#1F2937]/60 mb-1"><span>NatCat range</span><span className="mono">{natMin}-{natMax}</span></div>
            <div className="flex items-center gap-2">
              <input type="range" min={0} max={100} value={natMin} data-testid="inbox-nat-min"
                onChange={(e) => { setNatMin(Math.min(Number(e.target.value), natMax)); setPage(1); }} className="w-full accent-[#0EA5A0]" />
              <input type="range" min={0} max={100} value={natMax} data-testid="inbox-nat-max"
                onChange={(e) => { setNatMax(Math.max(Number(e.target.value), natMin)); setPage(1); }} className="w-full accent-[#0EA5A0]" />
            </div>
          </div>
        </div>

        <div className="mt-4 bg-white border border-[#E5E7EB] rounded-xl overflow-hidden">
          <table className="w-full text-sm" data-testid="submissions-table">
            <thead>
              <tr className="bg-[#F8FAFB] text-left overline text-[#1F2937]/50 border-b border-[#E5E7EB]">
                <th className="px-5 py-3">Reference</th>
                <th className="px-5 py-3">Submitter</th>
                <SortHead label="Date" k="created_at" />
                <SortHead label="Sum Insured" k="total_sum_insured" />
                <SortHead label="NatCat" k="natcat_composite_score" />
                <SortHead label="Status" k="submission_status" />
                <th className="px-5 py-3">Assignee</th>
                <th className="px-5 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {loading && [...Array(5)].map((_, i) => (
                <tr key={i} className="border-b border-[#F1F5F9]"><td colSpan={8} className="px-5 py-4">
                  <div className="h-5 bg-[#F1F5F9] rounded animate-pulse" /></td></tr>
              ))}
              {!loading && pageRows.length === 0 && (
                <tr><td colSpan={8} className="px-5 py-12 text-center text-[#1F2937]/50" data-testid="inbox-empty">No submissions match your filters</td></tr>
              )}
              {!loading && pageRows.map((s, idx) => (
                <tr key={s.submission_id} onClick={() => nav(`/insights/submission/${s.submission_id}`)}
                  data-testid={`submission-row-${s.submission_id}`}
                  className={`border-b border-[#F1F5F9] hover:bg-[#E6F7F5]/50 cursor-pointer transition-colors ${idx % 2 ? "bg-[#F8FAFB]/60" : ""}`}>
                  <td className="px-5 py-4 mono font-medium text-[#0F2C4C]">{s.submission_id}</td>
                  <td className="px-5 py-4">
                    <div className="text-[#1F2937] font-medium">{s.submitter_name}</div>
                    <div className="text-xs text-[#1F2937]/50">{s.submitter_organization || `${s.policy_count} policies`}</div>
                  </td>
                  <td className="px-5 py-4 text-[#1F2937]/70 mono text-xs">{new Date(s.created_at).toLocaleDateString()}</td>
                  <td className="px-5 py-4 mono text-[#0F2C4C]">{fmt(s.total_sum_insured)}</td>
                  <td className="px-5 py-4"><span className="mono font-bold" style={{ color: scoreColor(s.natcat_composite_score) }}>{s.natcat_composite_score}</span></td>
                  <td className="px-5 py-4"><span className={`text-xs font-medium px-2.5 py-1 rounded-full ${statusStyle[s.submission_status] || ""}`}>{s.submission_status}</span></td>
                  <td className="px-5 py-4" onClick={(e) => e.stopPropagation()}>
                    {s.assigned_to ? (
                      <span className="inline-flex items-center gap-1.5 text-xs text-[#0F2C4C]" data-testid={`assignee-${s.submission_id}`}>
                        <UserCheck size={13} className="text-[#0EA5A0]" />
                        <span className="truncate max-w-[120px]">{s.assigned_to === email ? "You" : s.assigned_to}</span>
                        {s.assigned_to === email && <button onClick={(e) => claim(e, s, "release")} className="text-[#EF4444] hover:underline">release</button>}
                      </span>
                    ) : (
                      <button onClick={(e) => claim(e, s, "claim")} data-testid={`claim-${s.submission_id}`}
                        className="inline-flex items-center gap-1 text-xs text-[#0EA5A0] hover:text-[#0F2C4C] transition-colors font-medium">
                        <UserPlus size={13} /> Claim
                      </button>
                    )}
                  </td>
                  <td className="px-5 py-4 text-right"><ChevronRight size={16} className="text-[#0EA5A0]" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {!loading && filtered.length > 0 && (
          <div className="mt-4 flex items-center justify-between text-sm text-[#1F2937]/70">
            <span>Showing {(page - 1) * PAGE_SIZE + 1}-{Math.min(page * PAGE_SIZE, filtered.length)} of {filtered.length}</span>
            <div className="flex items-center gap-2">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} data-testid="page-prev"
                className="p-2 rounded-lg border border-[#E5E7EB] disabled:opacity-40 hover:bg-white transition-colors"><ChevronLeft size={16} /></button>
              <span className="mono">Page {page} / {pageCount}</span>
              <button onClick={() => setPage((p) => Math.min(pageCount, p + 1))} disabled={page === pageCount} data-testid="page-next"
                className="p-2 rounded-lg border border-[#E5E7EB] disabled:opacity-40 hover:bg-white transition-colors"><ChevronRight size={16} /></button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
