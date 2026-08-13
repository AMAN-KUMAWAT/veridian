import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { LogOut, Inbox, TrendingUp, AlertTriangle, Layers, ChevronRight } from "lucide-react";
import { Wordmark } from "../components/Logo";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";

const fmt = (n) => "$" + Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
const scoreColor = (s) => (s >= 60 ? "#EF4444" : s >= 40 ? "#F59E0B" : "#22C55E");
const statusStyle = { Received: "bg-[#E6F7F5] text-[#0EA5A0]", Reviewed: "bg-green-50 text-[#22C55E]", Flagged: "bg-red-50 text-[#EF4444]" };

export default function Dashboard() {
  const { email, logout } = useAuth();
  const [subs, setSubs] = useState([]);
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const nav = useNavigate();

  useEffect(() => {
    (async () => {
      try {
        const [s, o] = await Promise.all([api.get("/submissions"), api.get("/portfolio/overview")]);
        setSubs(s.data); setOverview(o.data);
      } finally { setLoading(false); }
    })();
  }, []);

  const doLogout = async () => { await logout(); nav("/insights/login"); };

  const stats = overview ? [
    { label: "Total submissions", value: overview.total_submissions, icon: Inbox, color: "#0EA5A0" },
    { label: "Exposure under mgmt", value: fmt(overview.total_exposure), icon: Layers, color: "#0F2C4C" },
    { label: "Avg NatCat score", value: overview.average_natcat_score, icon: TrendingUp, color: "#F59E0B" },
    { label: "Capital reserve breaches", value: overview.capital_reserve_breaches, icon: AlertTriangle, color: "#EF4444" },
  ] : [];

  return (
    <div className="min-h-screen bg-[#F8FAFB]">
      <header className="bg-[#0F2C4C] sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Wordmark light />
          <div className="flex items-center gap-4">
            <span className="text-sm text-[#E6F7F5]/80 hidden sm:block mono">{email}</span>
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
          {stats.map((s, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}
              className="bg-white border border-[#E5E7EB] rounded-xl p-5 hover:shadow-sm transition-shadow" data-testid={`stat-${i}`}>
              <s.icon size={20} style={{ color: s.color }} strokeWidth={1.5} />
              <div className="mt-3 mono text-2xl font-bold text-[#0F2C4C]">{s.value}</div>
              <div className="overline text-[#1F2937]/50 mt-1">{s.label}</div>
            </motion.div>
          ))}
        </div>

        <div className="mt-10 flex items-center gap-2">
          <Inbox size={20} className="text-[#0EA5A0]" strokeWidth={1.5} />
          <h2 className="font-head font-semibold text-xl text-[#0F2C4C]">Submissions Inbox</h2>
        </div>

        <div className="mt-4 bg-white border border-[#E5E7EB] rounded-xl overflow-hidden">
          <table className="w-full text-sm" data-testid="submissions-table">
            <thead>
              <tr className="bg-[#F8FAFB] text-left overline text-[#1F2937]/50 border-b border-[#E5E7EB]">
                <th className="px-5 py-3">Reference</th>
                <th className="px-5 py-3">Submitter</th>
                <th className="px-5 py-3 hidden md:table-cell">Date</th>
                <th className="px-5 py-3 text-right">Sum Insured</th>
                <th className="px-5 py-3 text-center">NatCat</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {loading && <tr><td colSpan={7} className="px-5 py-10 text-center text-[#1F2937]/50">Loading…</td></tr>}
              {!loading && subs.length === 0 && (
                <tr><td colSpan={7} className="px-5 py-12 text-center text-[#1F2937]/50">No submissions yet.</td></tr>
              )}
              {subs.map((s) => (
                <tr key={s.submission_id} onClick={() => nav(`/insights/submission/${s.submission_id}`)}
                  data-testid={`submission-row-${s.submission_id}`}
                  className="border-b border-[#F1F5F9] hover:bg-[#E6F7F5]/40 cursor-pointer transition-colors">
                  <td className="px-5 py-4 mono font-medium text-[#0F2C4C]">{s.submission_id}</td>
                  <td className="px-5 py-4">
                    <div className="text-[#1F2937] font-medium">{s.submitter_name}</div>
                    <div className="text-xs text-[#1F2937]/50">{s.submitter_organization || `${s.policy_count} policies`}</div>
                  </td>
                  <td className="px-5 py-4 hidden md:table-cell text-[#1F2937]/70 mono text-xs">{new Date(s.created_at).toLocaleDateString()}</td>
                  <td className="px-5 py-4 text-right mono text-[#0F2C4C]">{fmt(s.total_sum_insured)}</td>
                  <td className="px-5 py-4 text-center">
                    <span className="mono font-bold" style={{ color: scoreColor(s.natcat_composite_score) }}>{s.natcat_composite_score}</span>
                  </td>
                  <td className="px-5 py-4">
                    <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${statusStyle[s.submission_status] || ""}`}>{s.submission_status}</span>
                  </td>
                  <td className="px-5 py-4 text-right"><ChevronRight size={16} className="text-[#0EA5A0]" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
