import { useQuery } from "@tanstack/react-query";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ReferenceLine, Cell,
} from "recharts";
import { getWeibullAnalysis } from "../api";
import { usePlatforms } from "../context/PlatformContext";
import { SkeletonCard } from "./Skeleton";
import InsightBanner from "./InsightBanner";

const BETA_COLORS: Record<string, string> = {
  "Infant Mortality": "#f59e0b",
  "Random Failure":   "#3b82f6",
  "Mild Wear-Out":    "#10b981",
  "Wear-Out":         "#8b5cf6",
};

function ClassificationBadge({ label }: { label: string }) {
  const color = BETA_COLORS[label] || "#64748b";
  return (
    <span style={{
      background: color + "22",
      color,
      border: `1px solid ${color}44`,
      borderRadius: 4,
      padding: "2px 8px",
      fontSize: 11,
      fontWeight: 600,
      whiteSpace: "nowrap",
    }}>{label}</span>
  );
}

function BetaBar({ beta }: { beta: number }) {
  const pct = Math.min((beta / 3) * 100, 100);
  const color = beta < 0.9 ? "#f59e0b" : beta <= 1.1 ? "#3b82f6" : beta <= 1.5 ? "#10b981" : "#8b5cf6";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, background: "#0f1f35", borderRadius: 3, height: 6, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, background: color, height: "100%", borderRadius: 3, transition: "width 0.5s" }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 700, color, minWidth: 32, textAlign: "right" }}>{beta.toFixed(2)}</span>
    </div>
  );
}

export default function WeibullAnalysis() {
  const { platformsParam } = usePlatforms();
  const { data, isLoading } = useQuery({
    queryKey: ["weibull", platformsParam],
    queryFn: () => getWeibullAnalysis(platformsParam),
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

  const chartData = [...data.results].sort((a: { beta: number }, b: { beta: number }) => b.beta - a.beta);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* KPI row */}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        {[
          { label: "Classes Analysed", value: data.classes_analysed, sub: "equipment types", color: "#3b82f6" },
          { label: "Wear-Out (β > 1.1)", value: data.wear_out_count, sub: "time-based PM effective", color: "#8b5cf6" },
          { label: "Random Failure (β ≈ 1)", value: data.random_failure_count, sub: "consider CBM / RTF", color: "#3b82f6" },
          { label: "Infant Mortality (β < 0.9)", value: data.infant_mortality_count, sub: "review commissioning", color: "#f59e0b" },
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

      <InsightBanner>{data.summary}</InsightBanner>

      {/* Beta chart */}
      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 20 }}>
        <h3 style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>Weibull Shape Parameter β by Equipment Class</h3>
        <p style={{ color: "var(--muted)", fontSize: 12, marginBottom: 16 }}>
          β &lt; 0.9 = infant mortality · β ≈ 1 = random · β &gt; 1.1 = wear-out · reference lines shown
        </p>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 160, right: 40 }}>
            <XAxis type="number" domain={[0, 3]} tickCount={7} tick={{ fontSize: 11, fill: "#94a3b8" }}
              label={{ value: "β (shape parameter)", position: "insideBottom", offset: -2, fill: "#64748b", fontSize: 11 }} />
            <YAxis dataKey="equipment_class" type="category" width={155} tick={{ fontSize: 11, fill: "#94a3b8" }} />
            <Tooltip
              contentStyle={{ background: "#1a1d27", border: "1px solid #2e3347", borderRadius: 6 }}
              formatter={(v: number, _: string, props: { payload?: { classification?: string; eta_days?: number; data_source?: string } }) => [
                `β = ${Number(v).toFixed(2)} · ${props.payload?.classification ?? ""}${props.payload?.eta_days ? ` · η = ${Math.round(props.payload.eta_days)}d` : ""}`,
                "Weibull β",
              ]}
            />
            <ReferenceLine x={0.9} stroke="#f59e0b" strokeDasharray="4 2" label={{ value: "0.9", fill: "#f59e0b", fontSize: 10 }} />
            <ReferenceLine x={1.1} stroke="#3b82f6" strokeDasharray="4 2" label={{ value: "1.1", fill: "#3b82f6", fontSize: 10 }} />
            <ReferenceLine x={1.5} stroke="#8b5cf6" strokeDasharray="4 2" label={{ value: "1.5", fill: "#8b5cf6", fontSize: 10 }} />
            <Bar dataKey="beta" radius={[0, 3, 3, 0]}>
              {chartData.map((row: { classification: string }, i: number) => (
                <Cell key={i} fill={BETA_COLORS[row.classification] || "#64748b"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Detail table */}
      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 20 }}>
        <h3 style={{ fontWeight: 600, fontSize: 14, marginBottom: 16 }}>Equipment Class Detail</h3>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Equipment Class", "β (Shape)", "η (Char. Life)", "Failures", "Source", "Classification", "Strategy Implication"].map(h => (
                  <th key={h} style={{ textAlign: "left", padding: "8px 12px", color: "var(--muted)", fontWeight: 600, fontSize: 11, whiteSpace: "nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.results.map((row: {
                equipment_class: string;
                beta: number;
                eta_days: number | null;
                n_failures: number;
                data_source: string;
                oreda_reference: string | null;
                classification: string;
                maintenance_implication: string;
              }) => (
                <tr key={row.equipment_class} style={{ borderBottom: "1px solid #0f1f35" }}>
                  <td style={{ padding: "10px 12px", fontWeight: 600, color: "#e2e8f0" }}>{row.equipment_class}</td>
                  <td style={{ padding: "10px 12px" }}>
                    <BetaBar beta={row.beta} />
                  </td>
                  <td style={{ padding: "10px 12px", color: "#94a3b8" }}>
                    {row.eta_days ? `${Math.round(row.eta_days)}d` : "—"}
                  </td>
                  <td style={{ padding: "10px 12px", color: "#94a3b8", textAlign: "center" }}>{row.n_failures}</td>
                  <td style={{ padding: "10px 12px" }}>
                    <span style={{
                      fontSize: 10, padding: "2px 6px", borderRadius: 3,
                      background: row.data_source === "empirical" ? "#10b98122" : "#f59e0b22",
                      color: row.data_source === "empirical" ? "#10b981" : "#f59e0b",
                      fontWeight: 600,
                    }}>
                      {row.data_source === "empirical" ? "Empirical" : "OREDA ref"}
                    </span>
                    {row.oreda_reference && (
                      <div style={{ fontSize: 10, color: "#475569", marginTop: 2 }}>{row.oreda_reference}</div>
                    )}
                  </td>
                  <td style={{ padding: "10px 12px" }}>
                    <ClassificationBadge label={row.classification} />
                  </td>
                  <td style={{ padding: "10px 12px", color: "#94a3b8", maxWidth: 300, lineHeight: 1.5 }}>
                    {row.maintenance_implication}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Methodology note */}
      <div style={{
        background: "#080f1e", border: "1px solid #0f1f35",
        borderRadius: "var(--radius)", padding: 16, fontSize: 12, color: "#475569", lineHeight: 1.7,
      }}>
        <span style={{ color: "#64748b", fontWeight: 600 }}>METHODOLOGY — </span>
        Weibull β estimated via Median Rank Regression (MRR) on inter-failure times derived from corrective work order history (minimum 5 intervals required).
        Where empirical data is insufficient, OREDA 6th Edition reference values are applied.
        η (characteristic life) represents the time at which 63.2% of a population is expected to have failed.
        Classification thresholds: β &lt; 0.9 = infant mortality, 0.9–1.1 = random, 1.1–1.5 = mild wear-out, &gt; 1.5 = wear-out.
      </div>
    </div>
  );
}
