import { fmtCompact } from "../format";
import type { Snapshot } from "../types";

// Diverging horizontal bars: CE OI (left, red) vs PE OI (right, green) per strike.
export function OIProfileChart({ snap }: { snap: Snapshot }) {
  const rows = snap.chain;
  const max = Math.max(1, ...rows.map((r) => Math.max(r.ce.oi, r.pe.oi)));
  const H = Math.max(160, rows.length * 12);
  const W = 320;
  const mid = W / 2;
  const bh = H / rows.length;

  return (
    <div className="panel">
      <h3>OI Profile <span className="muted">CE / PE</span></h3>
      <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="none">
        <line x1={mid} y1={0} x2={mid} y2={H} className="axis" />
        {rows.map((r, i) => {
          const y = i * bh;
          const cw = (r.ce.oi / max) * (mid - 30);
          const pw = (r.pe.oi / max) * (mid - 30);
          const atm = Math.abs(r.strike - snap.atm) < 1e-6;
          return (
            <g key={r.strike}>
              <rect x={mid - cw} y={y + 1} width={cw} height={bh - 2} className="bar-ce" />
              <rect x={mid} y={y + 1} width={pw} height={bh - 2} className="bar-pe" />
              {atm && <text x={mid} y={y + bh - 2} className="atm-lbl" textAnchor="middle">{r.strike}</text>}
            </g>
          );
        })}
      </svg>
      <div className="chart-foot">
        <span className="neg">CE {fmtCompact(snap.totals.ce_oi)}</span>
        <span className="pos">PE {fmtCompact(snap.totals.pe_oi)}</span>
      </div>
    </div>
  );
}
