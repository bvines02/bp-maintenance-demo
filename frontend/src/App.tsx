import { useState } from "react";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import Dashboard from "./components/Dashboard";
import AssetRegister from "./components/AssetRegister";
import CorrectiveMaintenance from "./components/CorrectiveMaintenance";
import HypothesisTesting from "./components/HypothesisTesting";
import StrategyProposals from "./components/StrategyProposals";
import WeibullAnalysis from "./components/WeibullAnalysis";
import SCERegister from "./components/SCERegister";
import { PlatformProvider, usePlatforms } from "./context/PlatformContext";
import { getStrategyProposals } from "./api";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5 * 60 * 1000, retry: 1 } },
});

type Tab = "dashboard" | "hypotheses" | "proposals" | "weibull" | "sce" | "corrective" | "assets";

const TABS: { id: Tab; label: string }[] = [
  { id: "dashboard", label: "Overview" },
  { id: "hypotheses", label: "Hypothesis Testing" },
  { id: "proposals", label: "Strategy Proposals" },
  { id: "weibull", label: "Weibull Analysis" },
  { id: "sce", label: "SCE Register" },
  { id: "corrective", label: "Corrective Maintenance" },
  { id: "assets", label: "Asset Register" },
];

const TAB_DESCRIPTIONS: Record<Tab, string> = {
  dashboard: "Multi-platform maintenance performance overview — 2019 to 2024",
  hypotheses: "Structured data-driven testing of maintenance optimisation hypotheses",
  proposals: "Data-driven strategy change proposals with 5×5 risk assessment and MoC readiness",
  weibull: "Weibull β analysis per equipment class — failure mode classification and PM strategy implications",
  sce: "Safety Critical Elements and statutory inspection register — excluded from all optimisation scope",
  corrective: "Breakdown and unplanned maintenance history — failure modes and downtime by equipment class",
  assets: "Full asset register with duty/standby pairing and criticality classifications",
};

const PLATFORM_COLORS: Record<string, string> = {
  Alpha: "#3b82f6",
  Bravo: "#10b981",
  Charlie: "#f59e0b",
  Delta: "#8b5cf6",
  Echo: "#ef4444",
};

function NavIcon({ id, active }: { id: Tab; active: boolean }) {
  const color = active ? "#3b82f6" : "#475569";
  const paths: Record<Tab, string | string[]> = {
    dashboard: "M3 3h8v8H3V3zm10 0h8v8h-8V3zM3 13h8v8H3v-8zm10 0h8v8h-8v-8z",
    hypotheses: ["M9 3v8L5 18c-.6 1 .2 2 1.5 2h11c1.3 0 2.1-1 1.5-2L15 11V3", "M9 3h6", "M8 7h8"],
    proposals: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z",
    weibull: ["M3 20l5-10 4 6 3-4 6 8", "M3 20h18"],
    sce: ["M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"],
    corrective: ["M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"],
    assets: ["M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7", "M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4", "M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"],
  };
  const d = paths[id];
  const pathArray = Array.isArray(d) ? d : [d];
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke={color}
      strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
      {pathArray.map((p, i) => <path key={i} d={p} />)}
    </svg>
  );
}

function Sidebar({ tab, setTab, mocReadyCount }: { tab: Tab; setTab: (t: Tab) => void; mocReadyCount: number }) {
  const { platforms, selected, toggle, selectAll } = usePlatforms();
  const allSelected = selected.length === platforms.length;

  return (
    <aside style={{
      position: "fixed", left: 0, top: 0, bottom: 0, width: 240,
      background: "#080f1e",
      borderRight: "1px solid #0f1f35",
      display: "flex", flexDirection: "column",
      zIndex: 100,
    }}>
      {/* Logo */}
      <div style={{ padding: "18px 16px 14px", borderBottom: "1px solid #0f1f35" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 36, height: 36, background: "linear-gradient(135deg, #3b82f6, #1d4ed8)",
            borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 18, flexShrink: 0, boxShadow: "0 2px 8px #3b82f644",
          }}>⚙</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 13, lineHeight: 1.3, color: "#e2e8f0" }}>Maintenance</div>
            <div style={{ fontWeight: 700, fontSize: 13, lineHeight: 1.3, color: "#e2e8f0" }}>Optimiser</div>
            <div style={{ fontSize: 10, color: "#334155", marginTop: 1 }}>Reliability Analytics</div>
          </div>
        </div>
      </div>

      {/* Platform selector */}
      <div style={{ padding: "12px 14px", borderBottom: "1px solid #0f1f35" }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: "#334155", letterSpacing: "0.08em", marginBottom: 8 }}>
          PLATFORMS
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          <button onClick={selectAll} style={{
            padding: "3px 9px", borderRadius: 4, fontSize: 11, fontWeight: 500,
            border: `1px solid ${allSelected ? "#1e3a5f" : "#0f1f35"}`,
            background: allSelected ? "#0f2744" : "transparent",
            color: allSelected ? "#93c5fd" : "#334155",
            cursor: "pointer", transition: "all 0.15s",
          }}>All</button>
          {platforms.map(p => {
            const isSelected = selected.includes(p.name);
            const color = PLATFORM_COLORS[p.name] || "#64748b";
            return (
              <button key={p.name} onClick={() => toggle(p.name)} title={p.description} style={{
                padding: "3px 9px", borderRadius: 4, fontSize: 11,
                fontWeight: isSelected ? 600 : 400,
                border: `1px solid ${isSelected ? color + "44" : "#0f1f35"}`,
                background: isSelected ? color + "18" : "transparent",
                color: isSelected ? color : "#334155",
                cursor: "pointer", transition: "all 0.15s",
                display: "flex", alignItems: "center", gap: 4,
              }}>
                <span style={{
                  width: 5, height: 5, borderRadius: "50%",
                  background: isSelected ? color : "#1e293b", display: "inline-block", flexShrink: 0,
                }} />
                {p.name}
              </button>
            );
          })}
        </div>
        {!allSelected && (
          <div style={{ fontSize: 10, color: "#334155", marginTop: 6 }}>
            {selected.length} of {platforms.length} shown
          </div>
        )}
      </div>

      {/* Nav items */}
      <nav style={{ flex: 1, padding: "8px 8px", overflowY: "auto" }}>
        {TABS.map(t => {
          const isActive = tab === t.id;
          const badge = t.id === "proposals" && mocReadyCount > 0 ? mocReadyCount : null;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                width: "100%", textAlign: "left",
                padding: "8px 10px", borderRadius: 6, marginBottom: 1,
                background: isActive ? "#0f2744" : "transparent",
                color: isActive ? "#3b82f6" : "#475569",
                fontWeight: isActive ? 600 : 400,
                border: `1px solid ${isActive ? "#1e3a5f" : "transparent"}`,
                fontSize: 13, cursor: "pointer",
                display: "flex", alignItems: "center", gap: 9,
                transition: "all 0.15s",
              }}
            >
              <NavIcon id={t.id} active={isActive} />
              <span style={{ flex: 1 }}>{t.label}</span>
              {badge !== null && (
                <span style={{
                  background: "#10b981", color: "white",
                  fontSize: 10, fontWeight: 700,
                  padding: "1px 6px", borderRadius: 10,
                  minWidth: 18, textAlign: "center", lineHeight: "16px",
                }}>{badge}</span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Data provenance footer */}
      <div style={{ padding: "12px 14px", borderTop: "1px solid #0f1f35" }}>
        <div style={{ fontSize: 10, color: "#1e3a5f", lineHeight: 1.8 }}>
          <div style={{ color: "#334155", fontWeight: 600, letterSpacing: "0.06em", marginBottom: 2 }}>DATASET</div>
          OREDA-calibrated synthetic data<br />
          2019–2024 · 5 platforms<br />
          848 assets · 38,447 work orders
        </div>
      </div>
    </aside>
  );
}

function AppInner() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const { platformsParam } = usePlatforms();

  const { data: proposals } = useQuery({
    queryKey: ["strategy-proposals-badge", platformsParam],
    queryFn: () => getStrategyProposals(platformsParam),
    staleTime: 10 * 60 * 1000,
  });
  const mocReadyCount = proposals?.ready_for_moc ?? 0;

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <Sidebar tab={tab} setTab={setTab} mocReadyCount={mocReadyCount} />

      <div style={{ flex: 1, marginLeft: 240, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* Page header */}
        <div style={{
          padding: "24px 32px 16px",
          borderBottom: "1px solid var(--border)",
          background: "var(--surface)",
        }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0, marginBottom: 4 }}>
            {TABS.find(t => t.id === tab)?.label}
          </h1>
          <p style={{ color: "var(--muted)", fontSize: 13, margin: 0 }}>
            {TAB_DESCRIPTIONS[tab]}
          </p>
        </div>

        {/* Content */}
        <main style={{ flex: 1, padding: "24px 32px" }}>
          {tab === "dashboard" && <Dashboard />}
          {tab === "hypotheses" && <HypothesisTesting onNavigate={(t) => setTab(t as Tab)} />}
          {tab === "proposals" && <StrategyProposals />}
          {tab === "weibull" && <WeibullAnalysis />}
          {tab === "sce" && <SCERegister />}
          {tab === "corrective" && <CorrectiveMaintenance />}
          {tab === "assets" && <AssetRegister />}
        </main>
      </div>
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <PlatformProvider>
        <AppInner />
      </PlatformProvider>
    </QueryClientProvider>
  );
}

export default App;
