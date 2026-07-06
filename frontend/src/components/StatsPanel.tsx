import { fmtCompact, fmtNum } from "../format";
import type { Snapshot } from "../types";

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="stat">
      <div className="stat-lbl">{label}</div>
      <div className="stat-val">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

export function StatsPanel({ snap }: { snap: Snapshot }) {
  const em = snap.expected_move;
  return (
    <div className="panel">
      <h3>Key Metrics</h3>
      <div className="stat-grid">
        <Stat label="Max Pain" value={snap.max_pain != null ? String(snap.max_pain) : "–"} />
        <Stat label="PCR (OI)" value={fmtNum(snap.pcr.pcr_oi, 2)} />
        <Stat label="PCR (Vol)" value={fmtNum(snap.pcr.pcr_volume, 2)} />
        <Stat label="ATM IV" value={fmtNum(snap.atm_iv.atm_iv, 2) + "%"}
              sub={`CE ${fmtNum(snap.atm_iv.atm_ce_iv, 1)} / PE ${fmtNum(snap.atm_iv.atm_pe_iv, 1)}`} />
        <Stat label="ATM Straddle" value={fmtNum(snap.straddle.premium, 2)}
              sub={snap.straddle.decay != null ? `Δ ${fmtNum(snap.straddle.decay, 2)}` : undefined} />
        <Stat label="Expected Move" value={`±${fmtNum(em.sigma_pct, 2)}%`}
              sub={em.lower != null ? `${fmtNum(em.lower, 0)} – ${fmtNum(em.upper, 0)}` : undefined} />
        <Stat label="Total CE OI" value={fmtCompact(snap.totals.ce_oi)}
              sub={`Δ ${fmtCompact(snap.totals.ce_oi_change)}`} />
        <Stat label="Total PE OI" value={fmtCompact(snap.totals.pe_oi)}
              sub={`Δ ${fmtCompact(snap.totals.pe_oi_change)}`} />
      </div>
      <div className="sr-row">
        <span>Support <b className="pos">{snap.support_resistance.support_1 ?? "–"}</b>
          {snap.support_resistance.support_2 != null && <em> / {snap.support_resistance.support_2}</em>}
        </span>
        <span>Resistance <b className="neg">{snap.support_resistance.resistance_1 ?? "–"}</b>
          {snap.support_resistance.resistance_2 != null && <em> / {snap.support_resistance.resistance_2}</em>}
        </span>
      </div>
    </div>
  );
}
