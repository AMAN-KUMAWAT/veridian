import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { Mail, ArrowLeft, KeyRound, Loader2 } from "lucide-react";
import { Wordmark } from "../components/Logo";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const [step, setStep] = useState("email"); // email | otp
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [busy, setBusy] = useState(false);
  const { setEmail: setAuthEmail } = useAuth();
  const nav = useNavigate();

  const requestOtp = async () => {
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { toast.error("Enter a valid email"); return; }
    setBusy(true);
    try {
      await api.post("/auth/request-otp", { email });
      toast.success("Verification code sent to your inbox");
      setStep("otp");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not send code");
    } finally { setBusy(false); }
  };

  const verify = async () => {
    if (otp.length !== 6) { toast.error("Enter the 6-digit code"); return; }
    setBusy(true);
    try {
      const { data } = await api.post("/auth/verify-otp", { email, otp });
      setAuthEmail(data.email);
      toast.success("Welcome back");
      nav("/insights");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Invalid code");
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-[#0F2C4C] flex flex-col">
      <div className="max-w-6xl w-full mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/"><Wordmark light /></Link>
        <Link to="/" className="text-sm text-[#E6F7F5]/80 hover:text-white flex items-center gap-1.5 transition-colors">
          <ArrowLeft size={16} /> Home
        </Link>
      </div>

      <div className="flex-1 flex items-center justify-center px-6">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-md bg-white rounded-2xl p-8 sm:p-10" data-testid="login-card">
          <div className="overline text-[#0EA5A0] mb-2">Insights Dashboard</div>
          <h1 className="font-head font-bold tracking-tight text-2xl text-[#0F2C4C]">
            {step === "email" ? "Sign in to Insights" : "Enter your code"}
          </h1>
          <p className="mt-2 text-sm text-[#1F2937]/70">
            {step === "email"
              ? "Access is restricted to authorized reviewers. We'll email you a one-time code."
              : `We sent a 6-digit code to ${email}. It expires in 5 minutes.`}
          </p>

          {step === "email" ? (
            <div className="mt-7">
              <label className="overline text-[#1F2937]/60 block mb-1.5">Email address</label>
              <div className="relative">
                <Mail size={17} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#0EA5A0]" strokeWidth={1.5} />
                <input value={email} onChange={(e) => setEmail(e.target.value)} data-testid="login-email-input"
                  onKeyDown={(e) => e.key === "Enter" && requestOtp()} placeholder="you@company.com"
                  className="w-full pl-11 pr-4 py-3 rounded-lg border border-[#E5E7EB] text-sm focus:ring-2 focus:ring-[#0EA5A0] focus:outline-none focus:border-[#0EA5A0] transition-colors" />
              </div>
              <button onClick={requestOtp} disabled={busy} data-testid="request-otp-button"
                className="mt-6 w-full py-3 rounded-full bg-[#0EA5A0] text-white font-medium flex items-center justify-center gap-2 hover:-translate-y-px hover:shadow-lg transition-transform disabled:opacity-60">
                {busy ? <Loader2 size={18} className="animate-spin" /> : <KeyRound size={17} />} Send code
              </button>
            </div>
          ) : (
            <div className="mt-7">
              <label className="overline text-[#1F2937]/60 block mb-1.5">6-digit code</label>
              <input value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                data-testid="otp-input" onKeyDown={(e) => e.key === "Enter" && verify()}
                inputMode="numeric" placeholder="000000"
                className="w-full px-4 py-3 rounded-lg border border-[#E5E7EB] text-center mono text-2xl tracking-[0.5em] focus:ring-2 focus:ring-[#0EA5A0] focus:outline-none transition-colors" />
              <button onClick={verify} disabled={busy} data-testid="verify-otp-button"
                className="mt-6 w-full py-3 rounded-full bg-[#0EA5A0] text-white font-medium flex items-center justify-center gap-2 hover:-translate-y-px hover:shadow-lg transition-transform disabled:opacity-60">
                {busy ? <Loader2 size={18} className="animate-spin" /> : null} Verify & enter
              </button>
              <div className="mt-4 flex justify-between text-sm">
                <button onClick={() => setStep("email")} className="text-[#1F2937]/60 hover:text-[#0F2C4C] transition-colors">Change email</button>
                <button onClick={requestOtp} disabled={busy} data-testid="resend-otp-button"
                  className="text-[#0EA5A0] hover:text-[#0F2C4C] font-medium transition-colors">Resend code</button>
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
