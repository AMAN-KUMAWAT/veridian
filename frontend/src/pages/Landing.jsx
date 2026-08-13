import React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ShieldCheck, Radar, Network, ArrowRight, Lock, Activity, Globe } from "lucide-react";
import { Wordmark } from "../components/Logo";

const HERO = "https://images.unsplash.com/photo-1707365531261-f2bb8407adda?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMjh8MHwxfHNlYXJjaHwyfHxtb2Rlcm4lMjBza3lzY3JhcGVycyUyMGZvZ3xlbnwwfHx8fDE3ODY2MDM1MTd8MA&ixlib=rb-4.1.0&q=85";

const steps = [
  { icon: Network, title: "Submit a book of business", body: "Upload your portfolio of policies — addresses, property types, sums insured. No login required." },
  { icon: Radar, title: "Real-time risk scoring", body: "Every policy is geocoded and scored against live USGS seismic and Open-Meteo storm data." },
  { icon: ShieldCheck, title: "Reviewed by underwriters", body: "Authorized reinsurance analysts assess your portfolio inside the secure Insights Dashboard." },
];

export default function Landing() {
  return (
    <div className="min-h-screen bg-[#F8FAFB]">
      <header className="glass-header sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Wordmark />
          <nav className="flex items-center gap-6">
            <a href="#how" className="text-sm text-[#1F2937] hover:text-[#0EA5A0] transition-colors hidden sm:block">How it works</a>
            <Link to="/insights/login" data-testid="nav-insights-login"
              className="text-sm font-medium text-[#0F2C4C] hover:text-[#0EA5A0] transition-colors flex items-center gap-1.5">
              <Lock size={15} strokeWidth={1.5} /> Insights Login
            </Link>
            <Link to="/submit" data-testid="nav-submit"
              className="px-4 py-2 rounded-full bg-[#0EA5A0] text-white text-sm font-medium hover:-translate-y-px hover:shadow-lg transition-transform">
              Submit Portfolio
            </Link>
          </nav>
        </div>
      </header>

      {/* HERO */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0">
          <img src={HERO} alt="skyline" className="w-full h-full object-cover" />
          <div className="absolute inset-0 bg-white/55" />
        </div>
        <div className="relative max-w-7xl mx-auto px-6 py-28 lg:py-40 grid lg:grid-cols-12 gap-8">
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}
            className="lg:col-span-8">
            <div className="overline text-[#0EA5A0] mb-4">Catastrophe Risk Analytics</div>
            <h1 className="font-head font-extrabold tracking-tight text-4xl sm:text-5xl lg:text-6xl text-[#0F2C4C] leading-[1.05]">
              Real-Time Risk Intelligence<br />for Smarter Reinsurance.
            </h1>
            <p className="mt-6 text-base sm:text-lg text-[#1F2937] max-w-2xl leading-relaxed">
              Veridian scores catastrophe exposure across your portfolio using live seismic, storm and
              structural data — then hands underwriters the treaty-efficiency insight they need.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-4">
              <Link to="/submit" data-testid="hero-submit-btn"
                className="group px-6 py-3.5 rounded-full bg-[#0EA5A0] text-white font-medium flex items-center gap-2 hover:-translate-y-px hover:shadow-xl transition-transform">
                Submit a Portfolio <ArrowRight size={18} className="group-hover:translate-x-0.5 transition-transform" />
              </Link>
              <Link to="/insights/login" data-testid="hero-insights-btn"
                className="px-6 py-3.5 rounded-full border border-[#0F2C4C]/20 text-[#0F2C4C] font-medium hover:bg-white transition-colors">
                Access Insights
              </Link>
            </div>
            <div className="mt-10 inline-flex items-center gap-2.5 bg-white/80 border border-[#0EA5A0]/20 rounded-full px-4 py-2">
              <Activity size={16} className="text-[#22C55E]" strokeWidth={2} />
              <span className="text-sm font-medium text-[#0F2C4C]">Real-Time Risk Data · Secure Submission</span>
            </div>
          </motion.div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section id="how" className="max-w-7xl mx-auto px-6 py-24">
        <div className="overline text-[#0EA5A0] mb-3">How it works</div>
        <h2 className="font-head font-bold tracking-tight text-3xl text-[#0F2C4C] max-w-2xl">
          From submission to underwriting decision — in one live pipeline.
        </h2>
        <div className="mt-14 grid md:grid-cols-3 gap-6">
          {steps.map((s, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }} transition={{ delay: i * 0.12 }}
              className="bg-white border border-[#E5E7EB] rounded-2xl p-8 hover:shadow-md hover:border-[#0EA5A0]/40 transition-all">
              <div className="w-12 h-12 rounded-xl bg-[#E6F7F5] flex items-center justify-center mb-5">
                <s.icon className="text-[#0EA5A0]" size={24} strokeWidth={1.5} />
              </div>
              <div className="text-sm mono text-[#0EA5A0] mb-2">0{i + 1}</div>
              <h3 className="font-head font-semibold text-lg text-[#0F2C4C]">{s.title}</h3>
              <p className="mt-2 text-sm text-[#1F2937]/80 leading-relaxed">{s.body}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* CTA band */}
      <section className="bg-[#0F2C4C]">
        <div className="max-w-7xl mx-auto px-6 py-20 grid lg:grid-cols-12 gap-8 items-center">
          <div className="lg:col-span-8">
            <h2 className="font-head font-bold tracking-tight text-3xl text-white">Bring your book. We'll model the catastrophe risk.</h2>
            <p className="mt-3 text-[#E6F7F5]/80 max-w-2xl">Live geocoding, seismic and wind data — aggregated into portfolio exposure and expected CAT loss.</p>
          </div>
          <div className="lg:col-span-4 flex lg:justify-end">
            <Link to="/submit" data-testid="cta-submit-btn"
              className="px-7 py-4 rounded-full bg-[#0EA5A0] text-white font-medium flex items-center gap-2 hover:-translate-y-px hover:shadow-xl transition-transform">
              <Globe size={18} strokeWidth={1.5} /> Start a Submission
            </Link>
          </div>
        </div>
      </section>

      <footer className="max-w-7xl mx-auto px-6 py-10 flex items-center justify-between">
        <Wordmark />
        <span className="text-xs text-[#1F2937]/50 mono">© 2026 Veridian Risk Intelligence</span>
      </footer>
    </div>
  );
}
