// Mirrors the backend snapshot payload (app/engine/pipeline.py compute_snapshot).

export interface Leg {
  ltp: number;
  oi: number;
  oi_change: number;
  volume: number;
  atp: number;
  atp_minus_ltp: number;
  bid: number;
  ask: number;
  iv: number | null;
  delta: number | null;
  gamma: number | null;
  theta: number | null;
  vega: number | null;
  buildup: string;
}

export interface StrikeRow {
  strike: number;
  ce: Leg;
  pe: Leg;
  total_oi: number;
}

export interface Snapshot {
  underlying: string;
  spot: number;
  atm: number;
  step: number;
  t_years: number;
  ts: number;
  source: string;
  stale: boolean;
  chain: StrikeRow[];
  totals: {
    ce_oi: number; pe_oi: number;
    ce_volume: number; pe_volume: number;
    ce_oi_change: number; pe_oi_change: number;
  };
  pcr: { pcr_oi: number | null; pcr_volume: number | null; pcr_oi_change: number | null };
  support_resistance: {
    resistance_1: number | null; resistance_2: number | null;
    support_1: number | null; support_2: number | null;
    resistance_fresh: number | null; support_fresh: number | null;
  };
  max_pain: number | null;
  pain_curve: { strike: number; pain: number }[];
  total_oi_curve: { strike: number; total_oi: number }[];
  atm_iv: { atm_ce_iv: number | null; atm_pe_iv: number | null; atm_iv: number | null };
  iv_signals: {
    iv_diff: number | null;
    iv_squeeze_ce: number | null;
    iv_squeeze_pe: number | null;
    iv_skew_signal: string;
  };
  iv_skew: { strike: number; offset: number; ce_iv: number | null; pe_iv: number | null }[];
  expected_move: { sigma_pct: number | null; upper: number | null; lower: number | null };
  straddle: { premium: number | null; decay: number | null };
  theta_pool: { ce: number; pe: number };
  signals: {
    ce_pe_active: string;
    option_buy_sell: string;
    writer_strength: string;
    max_pain_bias: string;
    composite_bias: string;
  };
}

export type SnapshotMap = Record<string, Snapshot>;
