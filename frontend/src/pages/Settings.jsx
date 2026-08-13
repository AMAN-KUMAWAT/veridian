import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Save, Bell, BellOff, Loader2 } from "lucide-react";
import { Wordmark } from "../components/Logo";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";

export default function Settings() {
  const { email } = useAuth();
  const nav = useNavigate();
  const [enabled, setEnabled] = useState(true);
  const [hour, setHour] = useState(8);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/settings");
        setEnabled(data.digest_enabled);
        setHour(data.digest_hour);
      } catch { toast.error("Could not load settings"); }
      finally { setLoading(false); }
    })();
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/settings", { digest_enabled: enabled, digest_hour: Number(hour) });
      toast.success("Preferences saved");
    } catch { toast.error("Could not save preferences"); }
    finally { setSaving(false); }
  };

  const fmtHour = (h) => `${String(h).padStart(2, "0")}:00 UTC`;

  return (
    <div className="min-h-screen bg-[#F8FAFB]">
      <header className="bg-[#0F2C4C] sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Wordmark light />
          <button onClick={() => nav("/insights")} className="text-sm text-[#E6F7F5]/80 hover:text-white flex items-center gap-1.5 transition-colors">
            <ArrowLeft size={16} /> Dashboard
          </button>
        </div>
      </header>

      <div className="max-w-2xl mx-auto px-6 py-12">
        <div className="overline text-[#0EA5A0] mb-2">Reviewer Settings</div>
        <h1 className="font-head font-bold tracking-tight text-3xl text-[#0F2C4C]">Digest preferences</h1>
        <p className="mt-2 text-sm text-[#1F2937]/60 mono">{email}</p>

        {loading ? (
          <div className="mt-8 h-48 bg-white border border-[#E5E7EB] rounded-2xl animate-pulse" />
        ) : (
          <div className="mt-8 bg-white border border-[#E5E7EB] rounded-2xl p-8" data-testid="settings-card">
            <div className="flex items-start justify-between gap-6 pb-6 border-b border-[#F1F5F9]">
              <div>
                <div className="font-head font-semibold text-[#0F2C4C] flex items-center gap-2">
                  {enabled ? <Bell size={18} className="text-[#0EA5A0]" /> : <BellOff size={18} className="text-[#9CA3AF]" />}
                  Daily review digest
                </div>
                <p className="text-sm text-[#1F2937]/70 mt-1 max-w-sm">Receive a daily email summarizing submissions still awaiting your review.</p>
              </div>
              <button onClick={() => setEnabled(!enabled)} data-testid="settings-digest-toggle"
                className={`relative w-12 h-7 rounded-full transition-colors shrink-0 ${enabled ? "bg-[#0EA5A0]" : "bg-[#CBD5E1]"}`}>
                <span className={`absolute top-1 w-5 h-5 rounded-full bg-white transition-all ${enabled ? "left-6" : "left-1"}`} />
              </button>
            </div>

            <div className={`pt-6 transition-opacity ${enabled ? "opacity-100" : "opacity-40 pointer-events-none"}`}>
              <label className="overline text-[#1F2937]/60 block mb-2">Delivery time</label>
              <select value={hour} onChange={(e) => setHour(Number(e.target.value))} data-testid="settings-hour-select"
                className="w-full sm:w-64 px-3.5 py-2.5 rounded-lg border border-[#E5E7EB] bg-white text-[#1F2937] text-sm focus:ring-2 focus:ring-[#0EA5A0] focus:outline-none transition-colors">
                {Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{fmtHour(h)}</option>)}
              </select>
              <p className="text-xs text-[#1F2937]/50 mt-2">The digest checks hourly and sends at your chosen UTC hour.</p>
            </div>

            <button onClick={save} disabled={saving} data-testid="settings-save-button"
              className="mt-8 px-6 py-3 rounded-full bg-[#0EA5A0] text-white font-medium flex items-center gap-2 hover:-translate-y-px hover:shadow-lg transition-transform disabled:opacity-60">
              {saving ? <Loader2 size={17} className="animate-spin" /> : <Save size={17} />} Save preferences
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
