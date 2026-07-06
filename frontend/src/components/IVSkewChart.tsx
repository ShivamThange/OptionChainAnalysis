import { fmtNum } from "../format";
import type { Snapshot } from "../types";

// IV skew: CE vs PE IV across ATM±offset strikes.
export function IVSkewChart({ snap }: { snap: Snapshot }) {
  const pts = snap.iv_skew.filter((p) => p.ce_iv != null || p.pe_iv != null);
  if (!pts.length) return (
    <div className="panel"><h3>IV Skew</h3><div className="empty">no IV yet</div></div>
  );
  const W = 320, H = 160, pad = 20;
  const ivs = pts.flatMap((p) => [p.ce_iv, p.pe_iv].filter((v): v is number => v != null));
  const ymin = Math.min(...ivs), ymax = Math.max(...ivs);
  const sx = (i: number) => pad + (i / (pts.length - 1 || 1)) * (W - 2 * pad);
  const sy = (y: number) => H - pad - ((y - ymin) / (ymax - ymin || 1)) * (H - 2 * pad);
  const line = (key: "ce_iv" | "pe_iv") => {
    let d = "";
    pts.forEach((p, i) => {
      const v = p[key];
      if (v == null) return;
      d += `${d ? "L" : "M"}${sx(i).toFixed(1)},${sy(v).toFixed(1)}`;
    });
    return d;
  };

  return (
    <div className="panel">
      <h3>IV Skew <span className="muted">
        diff {fmtNum(snap.iv_signals.iv_diff, 2)}</span></h3>
      <svg viewBox={`0 0 ${W} ${H}`} className="chart">
        <path d={line("ce_iv")} className="line-ce" fill="none" />
        <path d={line("pe_iv")} className="line-pe" fill="none" />
        {pts.map((p, i) => (
          <text key={i} x={sx(i)} y={H - 4} className="tick">{p.offset > 0 ? `+${p.offset}` : p.offset}</text>
        ))}
      </svg>
      <div className="chart-foot">
        <span className="neg">CE IV</span><span className="pos">PE IV</span>
      </div>
    </div>
  );
}
