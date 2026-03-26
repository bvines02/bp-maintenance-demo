import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Dashboard from "./components/Dashboard";
import Opportunities from "./components/Opportunities";
import AssetRegister from "./components/AssetRegister";
import DeferralAnalysis from "./components/DeferralAnalysis";
import CorrectiveMaintenance from "./components/CorrectiveMaintenance";
import HypothesisTesting from "./components/HypothesisTesting";
import Chat from "./components/Chat";

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

function App() {
  const [tab, setTab] = useState<Tab>("dashboard");

  return (
    <QueryClientProvider client={queryClient}>
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
              <div style={{ color: "var(--muted)", fontSize: 11, marginTop: 2 }}>Alpha Platform · Demo</div>
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

        {/* Page title */}
        <div style={{
          padding: "20px 32px 0",
          borderBottom: "1px solid var(--border)",
          background: "var(--surface)",
        }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>
            {TABS.find(t => t.id === tab)?.label}
          </h1>
          {tab === "dashboard" && <p style={{ color: "var(--muted)", fontSize: 13, paddingBottom: 16 }}>Alpha Platform maintenance performance overview — 2019 to 2024</p>}
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
    </QueryClientProvider>
  );
}

export default App;
