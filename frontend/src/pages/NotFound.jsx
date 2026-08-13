import React from "react";
import { Link } from "react-router-dom";
import { Wordmark } from "../components/Logo";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-[#0F2C4C] flex flex-col items-center justify-center px-6 text-center" data-testid="not-found">
      <Wordmark light />
      <div className="mt-10 font-head font-extrabold text-7xl text-[#0EA5A0]">404</div>
      <h1 className="mt-2 font-head font-bold text-2xl text-white">Page not found</h1>
      <p className="mt-3 text-[#E6F7F5]/70 max-w-md">The page you're looking for doesn't exist or has moved.</p>
      <Link to="/" className="mt-8 px-6 py-3 rounded-full bg-[#0EA5A0] text-white font-medium hover:-translate-y-px hover:shadow-lg transition-transform">
        Back to home
      </Link>
    </div>
  );
}
