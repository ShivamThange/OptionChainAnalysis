import { fmtNum } from "../format";
import {
  useActiveSource, useConn, useCurrentSnapshot, useSelected,
  useUnderlyings, setSelected,
} from "../store";

export function Header() {
  const underlyings = useUnderlyings();
  const selected = useSelected();
  const conn = useConn();
  const source = useActiveSource();
  const snap = useCurrentSnapshot();

  return (
    <header className="header">
      <div className="brand">Option Chain <span>Dashboard</span></div>

      <div className="tabs">
        {underlyings.map((u) => (
          <button
            key={u}
            className={u === selected ? "tab active" : "tab"}
            onClick={() => setSelected(u)}
          >
            {u}
          </button>
        ))}
      </div>

      {snap && (
        <div className="spotbox">
          <span className="lbl">SPOT</span>
          <span className="spot">{fmtNum(snap.spot, 2)}</span>
          <span className="lbl">ATM</span>
          <span className="atm">{snap.atm}</span>
        </div>
      )}

      <div className="status">
        <span className={`badge src-${source}`}>{source ? source.toUpperCase() : "—"}</span>
        {snap?.stale && <span className="badge stale">STALE</span>}
        <span className={`dot ${conn}`} title={conn} />
      </div>
    </header>
  );
}
