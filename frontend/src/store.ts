// Minimal external store built on useSyncExternalStore — no extra deps, and it
// lets components subscribe to exactly the slice they render (per-underlying
// snapshot), so a NIFTY tick never re-renders a BANKNIFTY panel.

import { useSyncExternalStore } from "react";
import type { Snapshot, SnapshotMap } from "./types";

type ConnStatus = "connecting" | "open" | "closed";

interface State {
  snapshots: SnapshotMap;
  names: string[];        // stable array (only changes when the key set changes)
  activeSource: string;
  selected: string;
  conn: ConnStatus;
}

let state: State = {
  snapshots: {},
  names: [],
  activeSource: "",
  selected: "NIFTY",
  conn: "connecting",
};

const listeners = new Set<() => void>();
function emit() { for (const l of listeners) l(); }
function subscribe(l: () => void) { listeners.add(l); return () => listeners.delete(l); }

// --- mutations -------------------------------------------------------------
export function applySnapshots(data: SnapshotMap, activeSource: string) {
  // shallow-merge so unchanged underlyings keep referential identity
  const snapshots = { ...state.snapshots, ...data };
  const keys = Object.keys(snapshots);
  // keep the `names` array reference stable unless the key set actually changed
  const names =
    keys.length === state.names.length && keys.every((k, i) => k === state.names[i])
      ? state.names
      : keys;
  let selected = state.selected;
  if (names.length && !names.includes(selected)) selected = names[0];
  state = { ...state, snapshots, names, activeSource, selected };
  emit();
}
export function setConn(conn: ConnStatus) { state = { ...state, conn }; emit(); }
export function setSelected(u: string) { state = { ...state, selected: u }; emit(); }

// --- selectors (hooks) -----------------------------------------------------
function useStore<T>(sel: (s: State) => T): T {
  return useSyncExternalStore(subscribe, () => sel(state));
}
export const useSelected = () => useStore((s) => s.selected);
export const useConn = () => useStore((s) => s.conn);
export const useActiveSource = () => useStore((s) => s.activeSource);
export const useUnderlyings = () => useStore((s) => s.names);
export const useSnapshot = (u: string): Snapshot | undefined =>
  useStore((s) => s.snapshots[u]);
export const useCurrentSnapshot = (): Snapshot | undefined =>
  useStore((s) => s.snapshots[s.selected]);
