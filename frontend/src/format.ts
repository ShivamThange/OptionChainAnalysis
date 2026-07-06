export function fmtNum(v: number | null | undefined, d = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return v.toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
}

export function fmtCompact(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  const abs = Math.abs(v);
  if (abs >= 1e7) return (v / 1e7).toFixed(2) + "Cr";
  if (abs >= 1e5) return (v / 1e5).toFixed(2) + "L";
  if (abs >= 1e3) return (v / 1e3).toFixed(1) + "K";
  return v.toFixed(0);
}

export function fmtSigned(v: number | null | undefined, d = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return (v > 0 ? "+" : "") + fmtCompact(v * (d === 0 ? 1 : 1));
}

// buildup label -> css class
export function buildupClass(b: string): string {
  switch (b) {
    case "Long Buildup": return "bu-long";
    case "Short Buildup": return "bu-short";
    case "Short Covering": return "bu-cover";
    case "Long Unwinding": return "bu-unwind";
    default: return "bu-neutral";
  }
}

export function biasClass(b: string): string {
  if (b.includes("BULL") || b === "PE ACTIVE" || b === "OPTION BUY" || b === "PUT WRITER STRONG")
    return "pos";
  if (b.includes("BEAR") || b === "CE ACTIVE" || b === "OPTION SELL" || b === "CALL WRITER STRONG")
    return "neg";
  return "neutral";
}
