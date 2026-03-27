import { useQuery } from "@tanstack/react-query";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, Legend,
} from "recharts";
import { getCorrectiveSummary, getWorkOrders } from "../api";
import { usePlatforms } from "../context/PlatformContext";

const COLORS = ["#ef4444", "#f59e0b", "#3b82f6", "#8b5cf6", "#10b981", "#ec4899", "#06b6d4"];
const fmt = (v: number) => `£${(v / 1000).toFixed(0)}k`;

export default function CorrectiveMaintenance() {
  const { platformsParam } = usePlatforms();
  const { data: summary, isLoading } = useQuery({
    queryKey: ["corrective-summary", platformsParam],
    queryFn: () => getCorrectiveSummary(platformsParam),
  });
  const { data: recentWOs } = useQuery({
    queryKey: ["corrective-wos", platformsParam],
    queryFn: () => getWorkOrders({ wo_type: "Corrective", limit: "100" }, platformsParam),
  });

  if (isLoading) return <div style={{ color: "var(--muted)", padding: 40 }}>Loading corrective data...</div>;
  if (!summary) return null;

  const byClassData = Object.entries(summary.by_equipment_class as Record<string, { count: number; cost: number }>)
    .map(([name, v]) => ({ name: name.replace(" / ", "/"), count: v.count, cost: v.cost }))
    .sort((a, b) => b.cost - a.cost)
    .slice(0, 10);

  const byDisciplineData = Object.entries(summary.by_discipline as Record<string, number>)
    .map(([name, value]) => ({ name, value: Math.round(value as number) }));

  const topFailures: { failure_mode: string; count: number; cost: number }[] = summary.top_failures_by_cost;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* KPI row */}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        {[
          { label: "Total Breakdowns", value: summary.total_corrective_wos.toLocaleString(), color: "var(--danger)" },
          { label: "Total Corrective Cost", value: `£${(summary.total_corrective_cost / 1000).toFixed(0)}k`, color: "var(--warn)" },
          { label: "Total Downtime (days)", value: summary.total_downtime_days.toLocaleString(), color: "#8b5cf6" },
          { label: "Avg Cost per Breakdown", value: `£${(summary.total_corrective_cost / summary.total_corrective_wos).toFixed(0)}`, color: "var(--accent)" },
        ].map(kpi => (
          <div key={kpi.label} style={{
            flex: 1, minWidth: 160,
            background: "var(--surface)", border: "1px solid var(--border)",
            borderRadius: "var(--radius)", padding: "16px 20px",
          }}>
            <div style={{ color: "var(--muted)", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>{kpi.label}</div>
            <div style={{ fontSize: 26, fontWeight: 700, color: kpi.color }}>{kpi.value}</div>
          </div>
        ))}
      </div>

      {/* Charts row */}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <div style={{ flex: 2, minWidth: 320, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 20 }}>
          <h3 style={{ marginBottom: 16, fontWeight: 600, fontSize: 14 }}>Corrective Cost by Equipment Class</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={byClassData} layout="vertical" margin={{ left: 120 }}>
              <XAxis type="number" tickFormatter={fmt} tick={{ fontSize: 11, fill: "#94a3b8" }} />
              <YAxis dataKey="name" type="category" width={120} tick={{ fontSize: 10, fill: "#94a3b8" }} />
              <Tooltip
                formatter={(v: number) => [`£${v.toLocaleString()}`, "Cost"]}
                contentStyle={{ background: "#1a1d27", border: "1px solid #2e3347", borderRadius: 6 }}
              />
              <Bar dataKey="cost" radius={[0, 3, 3, 0]}>
                {byClassData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div style={{ flex: 1, minWidth: 220, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 20 }}>
          <h3 style={{ marginBottom: 16, fontWeight: 600, fontSize: 14 }}>By Discipline</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={byDisciplineData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={75}>
                {byDisciplineData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Tooltip
                formatter={(v: number) => [`£${v.toLocaleString()}`]}
                contentStyle={{ background: "#1a1d27", border: "1px solid #2e3347", borderRadius: 6 }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Top failures table */}
      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 20 }}>
        <h3 style={{ marginBottom: 14, fontWeight: 600, fontSize: 14 }}>Top Failure Modes by Cost</h3>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "var(--surface2)", borderBottom: "1px solid var(--border)" }}>
              {["#", "Failure Mode", "Occurrences", "Total Cost", "Avg Cost"].map(h => (
                <th key={h} style={{ padding: "9px 12px", textAlign: "left", color: "var(--muted)", fontWeight: 600, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.04em" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {topFailures.map((f, i) => (
              <tr key={f.failure_mode} style={{ borderBottom: "1px solid var(--border)" }}
                onMouseEnter={e => (e.currentTarget.style.background = "var(--surface2)")}
                onMouseLeave={e => (e.currentTarget.style.background = "")}>
                <td style={{ padding: "9px 12px", color: "var(--muted)", fontWeight: 700 }}>{i + 1}</td>
                <td style={{ padding: "9px 12px" }}>{f.failure_mode}</td>
                <td style={{ padding: "9px 12px", textAlign: "center" }}>{f.count}</td>
                <td style={{ padding: "9px 12px", fontWeight: 600, color: "var(--warn)" }}>£{f.cost.toLocaleString()}</td>
                <td style={{ padding: "9px 12px", color: "var(--muted)" }}>£{Math.round(f.cost / f.count).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Recent corrective WOs */}
      {recentWOs && (
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 20 }}>
          <h3 style={{ marginBottom: 14, fontWeight: 600, fontSize: 14 }}>Recent Corrective Work Orders</h3>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ background: "var(--surface2)", borderBottom: "1px solid var(--border)" }}>
                  {["WO Number", "Asset", "Failure Mode", "Date", "Actual Hours", "Actual Cost", "Notes"].map(h => (
                    <th key={h} style={{ padding: "9px 12px", textAlign: "left", color: "var(--muted)", fontWeight: 600, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.04em", whiteSpace: "nowrap" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recentWOs.items?.slice(0, 50).map((w: Record<string, string | number>) => (
                  <tr key={w.wo_number} style={{ borderBottom: "1px solid var(--border)" }}
                    onMouseEnter={e => (e.currentTarget.style.background = "var(--surface2)")}
                    onMouseLeave={e => (e.currentTarget.style.background = "")}>
                    <td style={{ padding: "9px 12px", fontFamily: "monospace", color: "var(--danger)", fontWeight: 600, whiteSpace: "nowrap" }}>{w.wo_number}</td>
                    <td style={{ padding: "9px 12px", fontFamily: "monospace", color: "var(--accent)", whiteSpace: "nowrap" }}>{w.asset_tag}</td>
                    <td style={{ padding: "9px 12px" }}>{w.failure_mode || "—"}</td>
                    <td style={{ padding: "9px 12px", color: "var(--muted)", whiteSpace: "nowrap" }}>{w.scheduled_date}</td>
                    <td style={{ padding: "9px 12px", textAlign: "center" }}>{w.actual_hours ?? "—"}</td>
                    <td style={{ padding: "9px 12px", color: "var(--warn)", fontWeight: 600 }}>
                      {w.actual_cost ? `£${Number(w.actual_cost).toLocaleString()}` : "—"}
                    </td>
                    <td style={{ padding: "9px 12px", color: "var(--muted)", fontSize: 12, maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{w.notes || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
