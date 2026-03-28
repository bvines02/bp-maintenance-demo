import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSCERegister } from "../api";
import { usePlatforms } from "../context/PlatformContext";
import { SkeletonCard } from "./Skeleton";

function ShieldIcon() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

const SCE_TYPE_COLORS: Record<string, string> = {
  "Fire & Gas Detection": "#ef4444",
  "Overpressure Protection": "#f59e0b",
  "Pressure Containment": "#3b82f6",
  "Emergency Shutdown": "#8b5cf6",
  "General": "#64748b",
};

export default function SCERegister() {
  const { platformsParam } = usePlatforms();
  const [activeClass, setActiveClass] = useState<string>("All");

  const { data, isLoading } = useQuery({
    queryKey: ["sce-register", platformsParam],
    queryFn: () => getSCERegister(platformsParam),
  });

  if (isLoading || !data) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          <SkeletonCard /><SkeletonCard /><SkeletonCard /><SkeletonCard />
        </div>
        <SkeletonCard lines={10} height={400} />
      </div>
    );
  }

  const classes = ["All", ...Object.keys(data.sce_assets_by_class as Record<string, number>).sort()];
  const filteredAssets = activeClass === "All"
    ? data.sce_asset_list
    : data.sce_asset_list.filter((a: { equipment_class: string }) => a.equipment_class === activeClass);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Scope exclusion alert */}
      <div style={{
        background: "#1a0a0a",
        border: "1px solid #7f1d1d",
        borderLeft: "4px solid #ef4444",
        borderRadius: "var(--radius)",
        padding: "14px 20px",
        display: "flex", alignItems: "flex-start", gap: 12,
      }}>
        <div style={{ color: "#ef4444", marginTop: 1, flexShrink: 0 }}><ShieldIcon /></div>
        <div>
          <div style={{ color: "#fca5a5", fontWeight: 700, fontSize: 13, marginBottom: 4 }}>
            Safety Critical Elements — Excluded from Optimisation Scope
          </div>
          <div style={{ color: "#ef4444", fontSize: 12, lineHeight: 1.7 }}>
            {data.scope_note}
          </div>
        </div>
      </div>

      {/* KPI row */}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        {[
          { label: "SCE Assets", value: data.total_sce_assets, sub: "safety-critical elements", color: "#ef4444" },
          { label: "Statutory Inspections", value: data.total_statutory_wos, sub: "2019–2024 total", color: "#f59e0b" },
          { label: "Statutory Cost", value: `£${(data.total_statutory_cost / 1000).toFixed(0)}k`, sub: "ring-fenced spend", color: "#3b82f6" },
          { label: "SCE Cost Share", value: `${data.sce_cost_pct_of_total.toFixed(1)}%`, sub: "of total maintenance cost", color: "#8b5cf6" },
        ].map(k => (
          <div key={k.label} style={{
            flex: 1, minWidth: 180,
            background: "var(--surface)", border: "1px solid var(--border)",
            borderRadius: "var(--radius)", padding: "16px 20px",
          }}>
            <div style={{ color: "var(--muted)", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6 }}>
              {k.label}
            </div>
            <div style={{ fontSize: 26, fontWeight: 700, color: k.color }}>{k.value}</div>
            <div style={{ color: "var(--muted)", fontSize: 11, marginTop: 3 }}>{k.sub}</div>
          </div>
        ))}
      </div>

      {/* Statutory inspection schedule */}
      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 20 }}>
        <h3 style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>Statutory Inspection Schedule</h3>
        <p style={{ color: "var(--muted)", fontSize: 12, marginBottom: 16 }}>
          Mandatory inspection tasks governed by PSSR 2000, PFEER, IEC 61511, and Written Schemes of Examination
        </p>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Task Code", "Description", "SCE Type", "Regulation", "Interval", "WOs (6yr)", "Avg Hours", "Notes"].map(h => (
                  <th key={h} style={{ textAlign: "left", padding: "8px 12px", color: "var(--muted)", fontWeight: 600, fontSize: 11, whiteSpace: "nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.statutory_inspection_schedule.map((row: {
                task_code: string;
                task_description: string;
                sce_type: string;
                regulation: string;
                interval_days: number | null;
                wo_count: number;
                avg_hours: number;
                notes: string;
              }) => {
                const typeColor = SCE_TYPE_COLORS[row.sce_type] || "#64748b";
                return (
                  <tr key={row.task_code} style={{ borderBottom: "1px solid #0f1f35" }}>
                    <td style={{ padding: "10px 12px", fontFamily: "monospace", color: "#e2e8f0", fontWeight: 600, fontSize: 11 }}>{row.task_code}</td>
                    <td style={{ padding: "10px 12px", color: "#94a3b8" }}>{row.task_description}</td>
                    <td style={{ padding: "10px 12px" }}>
                      <span style={{
                        background: typeColor + "22", color: typeColor,
                        border: `1px solid ${typeColor}44`,
                        borderRadius: 4, padding: "2px 7px", fontSize: 10, fontWeight: 600, whiteSpace: "nowrap",
                      }}>{row.sce_type}</span>
                    </td>
                    <td style={{ padding: "10px 12px", color: "#64748b", fontSize: 11 }}>{row.regulation}</td>
                    <td style={{ padding: "10px 12px", color: "#94a3b8", textAlign: "center" }}>
                      {row.interval_days ? `${row.interval_days}d` : "—"}
                    </td>
                    <td style={{ padding: "10px 12px", color: "#94a3b8", textAlign: "center" }}>{row.wo_count}</td>
                    <td style={{ padding: "10px 12px", color: "#94a3b8", textAlign: "center" }}>{row.avg_hours}h</td>
                    <td style={{ padding: "10px 12px", color: "#475569", fontSize: 11, maxWidth: 280, lineHeight: 1.5 }}>{row.notes}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* SCE Asset register */}
      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 20 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
          <h3 style={{ fontWeight: 600, fontSize: 14, margin: 0 }}>SCE Asset Register ({filteredAssets.length})</h3>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {classes.map(c => (
              <button key={c} onClick={() => setActiveClass(c)} style={{
                padding: "3px 10px", borderRadius: 4, fontSize: 11,
                border: `1px solid ${activeClass === c ? "#3b82f6" : "#1e3a5f"}`,
                background: activeClass === c ? "#0f2744" : "transparent",
                color: activeClass === c ? "#3b82f6" : "#475569",
                cursor: "pointer",
              }}>{c}{c !== "All" ? ` (${(data.sce_assets_by_class as Record<string, number>)[c]})` : ` (${data.total_sce_assets})`}</button>
            ))}
          </div>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Tag", "Description", "Class", "Platform", "Criticality", "Status", "System", "SCE Reason", "Regulation"].map(h => (
                  <th key={h} style={{ textAlign: "left", padding: "8px 12px", color: "var(--muted)", fontWeight: 600, fontSize: 11, whiteSpace: "nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredAssets.map((a: {
                tag: string;
                description: string;
                equipment_class: string;
                platform: string;
                criticality: string;
                operating_status: string;
                system: string;
                sce_reason: string;
                regulation_basis: string;
              }) => (
                <tr key={a.tag} style={{ borderBottom: "1px solid #0f1f35" }}>
                  <td style={{ padding: "9px 12px", fontFamily: "monospace", color: "#e2e8f0", fontSize: 11 }}>{a.tag}</td>
                  <td style={{ padding: "9px 12px", color: "#94a3b8", maxWidth: 200 }}>{a.description}</td>
                  <td style={{ padding: "9px 12px", color: "#94a3b8" }}>{a.equipment_class}</td>
                  <td style={{ padding: "9px 12px", color: "#94a3b8" }}>{a.platform}</td>
                  <td style={{ padding: "9px 12px", textAlign: "center" }}>
                    <span style={{
                      background: a.criticality === "1" ? "#ef444422" : a.criticality === "2" ? "#f59e0b22" : "#10b98122",
                      color: a.criticality === "1" ? "#ef4444" : a.criticality === "2" ? "#f59e0b" : "#10b981",
                      padding: "1px 7px", borderRadius: 3, fontSize: 11, fontWeight: 700,
                    }}>{a.criticality}</span>
                  </td>
                  <td style={{ padding: "9px 12px", color: "#64748b", fontSize: 11 }}>{a.operating_status}</td>
                  <td style={{ padding: "9px 12px", color: "#64748b" }}>{a.system}</td>
                  <td style={{ padding: "9px 12px" }}>
                    <span style={{
                      background: a.sce_reason === "SCE Equipment Class" ? "#ef444418" : "#3b82f618",
                      color: a.sce_reason === "SCE Equipment Class" ? "#ef4444" : "#3b82f6",
                      fontSize: 10, fontWeight: 600, padding: "2px 6px", borderRadius: 3,
                    }}>{a.sce_reason}</span>
                  </td>
                  <td style={{ padding: "9px 12px", color: "#475569", fontSize: 11 }}>{a.regulation_basis}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
