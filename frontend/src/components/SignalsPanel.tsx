import { biasClass } from "../format";
import type { Snapshot } from "../types";

function Sig({ label, value }: { label: string; value: string }) {
  return (
    <div className="sig">
      <span className="sig-lbl">{label}</span>
      <span className={`sig-val ${biasClass(value)}`}>{value || "—"}</span>
    </div>
  );
}

export function SignalsPanel({ snap }: { snap: Snapshot }) {
  const s = snap.signals;
  return (
    <div className="panel">
      <h3>Signals</h3>
      <div className="composite">
        <span className="sig-lbl">Composite Bias</span>
        <span className={`composite-val ${biasClass(s.composite_bias)}`}>
          {s.composite_bias}
        </span>
      </div>
      <Sig label="CE / PE Active" value={s.ce_pe_active} />
      <Sig label="Option Buy/Sell" value={s.option_buy_sell} />
      <Sig label="Writer Strength" value={s.writer_strength} />
      <Sig label="Max Pain Bias" value={s.max_pain_bias} />
      <Sig label="IV Skew" value={snap.iv_signals.iv_skew_signal} />
    </div>
  );
}
