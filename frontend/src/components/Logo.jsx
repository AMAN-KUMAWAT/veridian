import React from "react";

// Veridian logo: shield built from an interconnected node/circuit pattern with a "V" in negative space.
export const Logo = ({ size = 36, light = false }) => {
  const stroke = light ? "#E6F7F5" : "#0EA5A0";
  const shield = light ? "#FFFFFF" : "#0F2C4C";
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" data-testid="veridian-logo">
      <path d="M24 3L42 9V24C42 35 34 42.5 24 45C14 42.5 6 35 6 24V9L24 3Z"
        fill={shield} stroke={stroke} strokeWidth="1.5" />
      {/* circuit nodes */}
      <circle cx="14" cy="16" r="2.2" fill={stroke} />
      <circle cx="34" cy="16" r="2.2" fill={stroke} />
      <circle cx="24" cy="34" r="2.6" fill={stroke} />
      <circle cx="24" cy="14" r="1.6" fill={stroke} opacity="0.6" />
      {/* V in negative space via connecting lines */}
      <path d="M14 16L24 34L34 16" stroke={stroke} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      <path d="M14 16L24 14L34 16" stroke={stroke} strokeWidth="1.2" strokeLinecap="round" opacity="0.5" />
    </svg>
  );
};

export const Wordmark = ({ light = false, size = 36 }) => (
  <div className="flex items-center gap-2.5" data-testid="veridian-wordmark">
    <Logo size={size} light={light} />
    <span className="font-head font-bold tracking-tight text-xl" style={{ color: light ? "#fff" : "#0F2C4C" }}>
      Veridian
    </span>
  </div>
);
