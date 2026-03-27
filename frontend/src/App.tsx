import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Dashboard from "./components/Dashboard";
import Opportunities from "./components/Opportunities";
import AssetRegister from "./components/AssetRegister";
import DeferralAnalysis from "./components/DeferralAnalysis";
import CorrectiveMaintenance from "./components/CorrectiveMaintenance";
import HypothesisTesting from "./components/HypothesisTesting";
import Chat from "./components/Chat";
import { PlatformProvider, usePlatforms } from "./context/PlatformContext";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5 * 60 * 1000, retry: 1 } },
});

type Tab = "dashboard" | "hypotheses" | "opportunities" | "deferral" | "corrective" | "assets" | "chat";

const TABS: { id: Tab; label: string }[] = [
  { id: "dashboard", label: "Overview" },
  { id: "hypotheses", label: "Hypothesis Testing" },
  { id: "opportunities", label: "Optimisation Opportunities" },
  { id: "deferral", label: "Deferral Analysis" },
  { id: "corrective", label: "Corrective Maintenance" },
  { id: "assets", label: "Asset Register" },
  { id: "chat", label: "Analyst Chat" },
];

const PLATFORM_COLORS: Record<string, string> = {
  Alpha: "#3b82f6",
  Bravo: "#10b981",
  Charlie: "#f59e0b",
  Delta: "#8b5cf6",
  Echo: "#ef4444",
};

function PlatformSelector() {
  const { platforms, selected, toggle, selectAll } = usePlatforms();
  const allSelected = selected.length === platforms.length;

  if (platforms.length === 0) return null;

  return (
    <div style={{
      background: "#0f172a",
      borderBottom: "1px solid var(--border)",
      padding: "8px 32px",
      display: "flex",
      alignItems: "center",
      gap: 8,
      flexWrap: "wrap",
    }}>
      <span style={{ color: "var(--muted)", fontSize: 12, fontWeight: 500, marginRight: 4 }}>
        PLATFORMS
      </span>

      <button
        onClick={selectAll}
        style={{
          padding: "3px 10px",
          borderRadius: 4,
          fontSize: 11,
          fontWeight: 500,
          border: "1px solid var(--border)",
          background: allSelected ? "#1e293b" : "transparent",
          color: allSelected ? "#94a3b8" : "var(--muted)",
          cursor: "pointer",
          transition: "all 0.15s",
        }}
      >
        All
      </button>

      {platforms.map(platform => {
        const isSelected = selected.includes(platform.name);
        const color = PLATFORM_COLORS[platform.name] || "#64748b";
        return (
          <button
            key={platform.name}
            onClick={() => toggle(platform.name)}
            title={platform.description}
            style={{
              padding: "3px 12px",
              borderRadius: 4,
              fontSize: 12,
              fontWeight: isSelected ? 600 : 400,
              border: `1px solid ${isSelected ? color + "66" : "var(--border)"}`,
              background: isSelected ? color + "22" : "transparent",
              color: isSelected ? color : "var(--muted)",
              cursor: "pointer",
              transition: "all 0.15s",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span style={{
              width: 7, height: 7, borderRadius: "50%",
              background: isSelected ? color : "#475569",
              display: "inline-block",
              flexShrink: 0,
            }} />
            {platform.name}
          </button>
        );
      })}

      {!allSelected && (
        <span style={{ color: "var(--muted)", fontSize: 11, marginLeft: 4 }}>
          · Filtered view ({selected.length} of {platforms.length} platforms)
        </span>
      )}
    </div>
  );
}

function AppInner() {
  const [tab, setTab] = useState<Tab>("dashboard");

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Header */}
      <header style={{
        background: "var(--surface)",
        borderBottom: "1px solid var(--border)",
        padding: "0 32px",
        display: "flex",
        alignItems: "center",
        gap: 32,
        height: 56,
        position: "sticky",
        top: 0,
        zIndex: 100,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 32, height: 32, background: "#3b82f6", borderRadius: 6,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 16, fontWeight: 700,
          }}>⚙</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, lineHeight: 1 }}>Maintenance Optimiser</div>
            <div style={{ color: "var(--muted)", fontSize: 11, marginTop: 2 }}>5 Platforms · Demo</div>
          </div>
        </div>

        <nav style={{ display: "flex", gap: 4, marginLeft: "auto" }}>
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                padding: "6px 14px",
                borderRadius: 6,
                background: tab === t.id ? "#3b82f622" : "transparent",
                color: tab === t.id ? "#3b82f6" : "var(--muted)",
                fontWeight: tab === t.id ? 600 : 400,
                border: tab === t.id ? "1px solid #3b82f644" : "1px solid transparent",
                fontSize: 13,
                transition: "all 0.15s",
              }}>
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      {/* Platform Selector */}
      <div style={{ position: "sticky", top: 56, zIndex: 99 }}>
        <PlatformSelector />
      </div>

      {/* Page title */}
      <div style={{
        padding: "20px 32px 0",
        borderBottom: "1px solid var(--border)",
        background: "var(--surface)",
      }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>
          {TABS.find(t => t.id === tab)?.label}
        </h1>
        {tab === "dashboard" && <p style={{ color: "var(--muted)", fontSize: 13, paddingBottom: 16 }}>Multi-platform maintenance performance overview — 2019 to 2024</p>}
        {tab === "opportunities" && <p style={{ color: "var(--muted)", fontSize: 13, paddingBottom: 16 }}>Identified PPM schedule optimisation opportunities, ranked by estimated annual saving</p>}
        {tab === "deferral" && <p style={{ color: "var(--muted)", fontSize: 13, paddingBottom: 16 }}>Tasks consistently completed late without resulting failures — candidates for interval extension</p>}
        {tab === "hypotheses" && <p style={{ color: "var(--muted)", fontSize: 13, paddingBottom: 16 }}>Structured data-driven testing of maintenance optimisation hypotheses H1.1, H1.2, and H1.3</p>}
        {tab === "corrective" && <p style={{ color: "var(--muted)", fontSize: 13, paddingBottom: 16 }}>Breakdown and unplanned maintenance history — failure modes, costs, and downtime by equipment class</p>}
        {tab === "assets" && <p style={{ color: "var(--muted)", fontSize: 13, paddingBottom: 16 }}>Full asset register with duty/standby pairing and criticality classifications</p>}
        {tab === "chat" && <p style={{ color: "var(--muted)", fontSize: 13, paddingBottom: 16 }}>Ask questions and test hypotheses against the maintenance dataset using AI analysis</p>}
      </div>

      {/* Content */}
      <main style={{ flex: 1, padding: "24px 32px", maxWidth: 1400, width: "100%", margin: "0 auto", alignSelf: "stretch" }}>
        {tab === "dashboard" && <Dashboard />}
        {tab === "opportunities" && <Opportunities />}
        {tab === "hypotheses" && <HypothesisTesting />}
        {tab === "deferral" && <DeferralAnalysis />}
        {tab === "corrective" && <CorrectiveMaintenance />}
        {tab === "assets" && <AssetRegister />}
        {tab === "chat" && <Chat />}
      </main>
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
