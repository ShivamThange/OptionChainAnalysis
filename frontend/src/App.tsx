import { useEffect } from "react";
import { Header } from "./components/Header";
import { IVSkewChart } from "./components/IVSkewChart";
import { OIProfileChart } from "./components/OIProfileChart";
import { OptionChainGrid } from "./components/OptionChainGrid";
import { PainCurveChart } from "./components/PainCurveChart";
import { SignalsPanel } from "./components/SignalsPanel";
import { StatsPanel } from "./components/StatsPanel";
import { useConn, useCurrentSnapshot } from "./store";
import { connectWS } from "./ws";

export default function App() {
  const snap = useCurrentSnapshot();
  const conn = useConn();

  useEffect(() => { connectWS(); }, []);

  return (
    <div className="app">
      <Header />
      {!snap ? (
        <div className="waiting">
          {conn === "open"
            ? "Connected — waiting for the first market snapshot…"
            : "Connecting to backend…"}
          <div className="hint">
            Ensure the backend is running (uvicorn app.main:app --port 8000).
            Live data flows during NSE market hours.
          </div>
        </div>
      ) : (
        <main className="layout">
          <section className="col-left">
            <SignalsPanel snap={snap} />
            <StatsPanel snap={snap} />
          </section>
          <section className="col-mid">
            <OptionChainGrid snap={snap} />
          </section>
          <section className="col-right">
            <OIProfileChart snap={snap} />
            <PainCurveChart snap={snap} />
            <IVSkewChart snap={snap} />
          </section>
        </main>
      )}
    </div>
  );
}
