import { useMemo } from "react";
import { buildupClass, fmtCompact, fmtNum } from "../format";
import type { Leg, Snapshot } from "../types";

function OiCell({ leg, max, side }: { leg: Leg; max: number; side: "ce" | "pe" }) {
  const pct = max > 0 ? (leg.oi / max) * 100 : 0;
  return (
    <td className={`oi ${side}`}>
      <span className="oi-bar" style={{ width: `${pct}%` }} />
      <span className="oi-txt">{fmtCompact(leg.oi)}</span>
    </td>
  );
}

function chgClass(v: number) { return v > 0 ? "pos" : v < 0 ? "neg" : ""; }

export function OptionChainGrid({ snap }: { snap: Snapshot }) {
  const { maxCe, maxPe } = useMemo(() => {
    let maxCe = 0, maxPe = 0;
    for (const r of snap.chain) {
      if (r.ce.oi > maxCe) maxCe = r.ce.oi;
      if (r.pe.oi > maxPe) maxPe = r.pe.oi;
    }
    return { maxCe, maxPe };
  }, [snap.chain]);

  const sr = snap.support_resistance;

  return (
    <div className="panel grid-panel">
      <h3>Option Chain — {snap.underlying} <span className="muted">(CALLS · STRIKE · PUTS)</span></h3>
      <div className="grid-scroll">
        <table className="chain">
          <thead>
            <tr>
              <th>OI</th><th>ChgOI</th><th>Vol</th><th>IV</th><th>Δ</th><th className="ltp-h">LTP</th>
              <th className="strike-h">STRIKE</th>
              <th className="ltp-h">LTP</th><th>Δ</th><th>IV</th><th>Vol</th><th>ChgOI</th><th>OI</th>
            </tr>
          </thead>
          <tbody>
            {snap.chain.map((r) => {
              const isAtm = Math.abs(r.strike - snap.atm) < 1e-6;
              const isRes = r.strike === sr.resistance_1;
              const isSup = r.strike === sr.support_1;
              const itmCe = r.strike < snap.spot;
              const itmPe = r.strike > snap.spot;
              return (
                <tr key={r.strike} className={isAtm ? "row atm" : "row"}>
                  <OiCell leg={r.ce} max={maxCe} side="ce" />
                  <td className={chgClass(r.ce.oi_change)}>{fmtCompact(r.ce.oi_change)}</td>
                  <td className="dim">{fmtCompact(r.ce.volume)}</td>
                  <td>{fmtNum(r.ce.iv, 1)}</td>
                  <td className="dim">{fmtNum(r.ce.delta, 2)}</td>
                  <td className={`ltp ${itmCe ? "itm" : ""}`}>
                    <span className={`bu ${buildupClass(r.ce.buildup)}`} title={r.ce.buildup} />
                    {fmtNum(r.ce.ltp, 2)}
                  </td>

                  <td className="strike">
                    {r.strike}
                    {isRes && <span className="tag r">R</span>}
                    {isSup && <span className="tag s">S</span>}
                  </td>

                  <td className={`ltp ${itmPe ? "itm" : ""}`}>
                    {fmtNum(r.pe.ltp, 2)}
                    <span className={`bu ${buildupClass(r.pe.buildup)}`} title={r.pe.buildup} />
                  </td>
                  <td className="dim">{fmtNum(r.pe.delta, 2)}</td>
                  <td>{fmtNum(r.pe.iv, 1)}</td>
                  <td className="dim">{fmtCompact(r.pe.volume)}</td>
                  <td className={chgClass(r.pe.oi_change)}>{fmtCompact(r.pe.oi_change)}</td>
                  <OiCell leg={r.pe} max={maxPe} side="pe" />
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="legend">
        <span><i className="bu bu-long" /> Long Buildup</span>
        <span><i className="bu bu-short" /> Short Buildup</span>
        <span><i className="bu bu-cover" /> Short Covering</span>
        <span><i className="bu bu-unwind" /> Long Unwinding</span>
      </div>
    </div>
  );
}
