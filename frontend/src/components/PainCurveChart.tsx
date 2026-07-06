import type { Snapshot } from "../types";

// Max-pain: total writer loss vs candidate expiry price. Min = max-pain strike.
export function PainCurveChart({ snap }: { snap: Snapshot }) {
  const pts = snap.pain_curve;
  if (pts.length < 2) return null;
  const W = 320, H = 160, pad = 6;
  const xs = pts.map((p) => p.strike);
  const ys = pts.map((p) => p.pain);
  const xmin = Math.min(...xs), xmax = Math.max(...xs);
  const ymin = Math.min(...ys), ymax = Math.max(...ys);
  const sx = (x: number) => pad + ((x - xmin) / (xmax - xmin || 1)) * (W - 2 * pad);
  const sy = (y: number) => H - pad - ((y - ymin) / (ymax - ymin || 1)) * (H - 2 * pad);
  const path = pts.map((p, i) => `${i ? "L" : "M"}${sx(p.strike).toFixed(1)},${sy(p.pain).toFixed(1)}`).join(" ");
  const mp = snap.max_pain;

  return (
    <div className="panel">
      <h3>Max Pain Curve <span className="muted">min @ {mp ?? "–"}</span></h3>
      <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="none">
        <path d={path} className="line" fill="none" />
        {mp != null && <line x1={sx(mp)} y1={pad} x2={sx(mp)} y2={H - pad} className="marker" />}
        {snap.spot >= xmin && snap.spot <= xmax && (
          <line x1={sx(snap.spot)} y1={pad} x2={sx(snap.spot)} y2={H - pad} className="marker-spot" />
        )}
      </svg>
      <div className="chart-foot">
        <span><i className="sw marker" /> Max Pain</span>
        <span><i className="sw marker-spot" /> Spot</span>
      </div>
    </div>
  );
}
