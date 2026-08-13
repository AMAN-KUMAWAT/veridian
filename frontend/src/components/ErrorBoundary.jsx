import React from "react";
import { Wordmark } from "./Logo";

export class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { hasError: false }; }
  static getDerivedStateFromError() { return { hasError: true }; }
  componentDidCatch(error, info) { console.error("Veridian crash:", error, info); }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#F8FAFB] flex flex-col items-center justify-center px-6 text-center" data-testid="error-boundary">
          <Wordmark />
          <h1 className="mt-8 font-head font-bold text-2xl text-[#0F2C4C]">Something went wrong</h1>
          <p className="mt-3 text-[#1F2937]/70 max-w-md">An unexpected error occurred. Please reload the page — your data is safe.</p>
          <button onClick={() => (window.location.href = "/")} data-testid="error-reload-button"
            className="mt-8 px-6 py-3 rounded-full bg-[#0EA5A0] text-white font-medium hover:-translate-y-px hover:shadow-lg transition-transform">
            Back to home
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
