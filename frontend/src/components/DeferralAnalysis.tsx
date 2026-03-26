import { useQuery } from "@tanstack/react-query";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { getDeferralSummary } from "../api";

interface DeferralRow {
  task_code: string;
  task_description: string;
  affected_assets: number;
  total_deferrals: number;
  avg_deferral_days: number;
  max_deferral_days: number;
  current_interval_days: number | null;
}

export default function DeferralAnalysis() {
  const { data, isLoading } = useQuery({
    queryKey: ["deferral-summary"],
    queryFn: getDeferralSummary,
  });

  if (isLoading) return <div style={{ color: "var(--muted)", padding: 40 }}>Loading deferral data...</div>;
  if (!data) return null;

  const rows: DeferralRow[] = data;
  const chartData = rows.slice(0, 12).map(r => ({
    name: r.task_code,
    avg: r.avg_deferral_days,
    max: r.max_deferral_days,
  }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        padding: "16px 20px",
        color: "var(--muted)",
        fontSize: 13,
        lineHeight: 1.6,
      }}>
        <strong style={{ color: "var(--text)" }}>What is deferral pattern analysis?</strong><br />
        Tasks that are consistently completed significantly later than their scheduled date — without resulting in
        equipment failure — are strong candidates for interval extension. This analysis identifies those patterns
        across the entire asset fleet.
      </div>

      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 20 }}>
        <h3 style={{ marginBottom: 16, fontWeight: 600, fontSize: 14 }}>Average Deferral by Task (Top 12)</h3>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={chartData} margin={{ left: 10, bottom: 20 }}>
            <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#94a3b8" }} angle={-35} textAnchor="end" interval={0} />
            <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} label={{ value: "Days", angle: -90, position: "insideLeft", fill: "#94a3b8", fontSize: 11 }} />
            <Tooltip
              contentStyle={{ background: "#1a1d27", border: "1px solid #2e3347", borderRadius: 6 }}
              formatter={(v: number, n: string) => [`${v} days`, n === "avg" ? "Avg Deferral" : "Max Deferral"]}
            />
            <Bar dataKey="avg" name="avg" radius={[3, 3, 0, 0]}>
              {chartData.map((entry, i) => (
                <Cell key={i} fill={entry.avg > 90 ? "#ef4444" : entry.avg > 45 ? "#f59e0b" : "#3b82f6"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "var(--surface2)", borderBottom: "1px solid var(--border)" }}>
              {["Task Code", "Description", "Affected Assets", "Total Deferrals", "Avg Deferral (days)", "Max Deferral (days)", "Current Interval (days)", "Opportunity"].map(h => (
                <th key={h} style={{ padding: "10px 12px", textAlign: "left", color: "var(--muted)", fontWeight: 600, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.04em", whiteSpace: "nowrap" }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(r => {
              const hasOpportunity = r.avg_deferral_days > 30 && r.total_deferrals >= 4;
              const suggested = r.current_interval_days
                ? r.current_interval_days + Math.round(r.avg_deferral_days * 0.75)
                : null;
              return (
                <tr key={r.task_code} style={{ borderBottom: "1px solid var(--border)" }}
                  onMouseEnter={e => (e.currentTarget.style.background = "var(--surface2)")}
                  onMouseLeave={e => (e.currentTarget.style.background = "")}>
                  <td style={{ padding: "9px 12px", fontWeight: 600, fontFamily: "monospace", color: "var(--accent)", whiteSpace: "nowrap" }}>{r.task_code}</td>
                  <td style={{ padding: "9px 12px" }}>{r.task_description}</td>
                  <td style={{ padding: "9px 12px", textAlign: "center" }}>{r.affected_assets}</td>
                  <td style={{ padding: "9px 12px", textAlign: "center" }}>{r.total_deferrals}</td>
                  <td style={{ padding: "9px 12px", textAlign: "center", fontWeight: 600, color: r.avg_deferral_days > 90 ? "#ef4444" : r.avg_deferral_days > 45 ? "#f59e0b" : "var(--text)" }}>
                    {r.avg_deferral_days}
                  </td>
                  <td style={{ padding: "9px 12px", textAlign: "center", color: "var(--muted)" }}>{r.max_deferral_days}</td>
                  <td style={{ padding: "9px 12px", textAlign: "center", color: "var(--muted)" }}>{r.current_interval_days ?? "—"}</td>
                  <td style={{ padding: "9px 12px" }}>
                    {hasOpportunity && suggested ? (
                      <span style={{ color: "#10b981", fontWeight: 600 }}>
                        Extend to {suggested} days
                      </span>
                    ) : (
                      <span style={{ color: "var(--border)" }}>—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
