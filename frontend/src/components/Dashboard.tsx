import { useQuery } from "@tanstack/react-query";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import { getCostSummary, getAssetSummary, getWorkOrderSummary } from "../api";
import KpiCard from "./KpiCard";
import { usePlatforms } from "../context/PlatformContext";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

const fmt = (v: number) => `£${(v / 1000).toFixed(0)}k`;

export default function Dashboard() {
  const { platformsParam } = usePlatforms();
  const { data: cost } = useQuery({ queryKey: ["cost-summary", platformsParam], queryFn: () => getCostSummary(platformsParam) });
  const { data: assets } = useQuery({ queryKey: ["asset-summary", platformsParam], queryFn: () => getAssetSummary(platformsParam) });
  const { data: wos } = useQuery({ queryKey: ["wo-summary", platformsParam], queryFn: () => getWorkOrderSummary(platformsParam) });

  if (!cost || !assets || !wos) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 400, color: "var(--muted)" }}>
        Loading dashboard data...
      </div>
    );
  }

  const disciplineCostData = Object.entries(cost.cost_by_discipline as Record<string, number>)
    .map(([name, value]) => ({ name, value: Math.round(value) }))
    .sort((a, b) => b.value - a.value);

  const woTypeData = Object.entries(wos.by_type as Record<string, number>)
    .map(([name, value]) => ({ name, value }));

  const assetClassData = Object.entries(assets.by_equipment_class as Record<string, number>)
    .map(([name, value]) => ({ name: name.replace(" / ", "/"), value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8);

  const criticalityData = Object.entries(assets.by_criticality as Record<string, number>)
    .map(([name, value]) => ({ name: `Criticality ${name}`, value }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* KPI Row */}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <KpiCard label="Total Assets" value={cost.total_assets} sub={`${assets.duty_standby_pairs} duty/standby pairs`} />
        <KpiCard label="Work Orders (2019–2024)" value={cost.total_work_orders} />
        <KpiCard label="Total Maintenance Cost" value={`£${(cost.total_actual_cost / 1000000).toFixed(2)}M`} sub="2019–2024 actual" />
        <KpiCard
          label="Potential Annual Saving"
          value={`£${(cost.total_potential_annual_saving / 1000).toFixed(0)}k`}
          sub="Identified optimisation opportunities"
          color="var(--accent2)"
        />
      </div>

      {/* Cost breakdown row */}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 20, flex: 2, minWidth: 320 }}>
          <h3 style={{ marginBottom: 16, fontWeight: 600, fontSize: 14 }}>Maintenance Cost by Discipline</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={disciplineCostData} margin={{ left: 10 }}>
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#94a3b8" }} />
              <YAxis tickFormatter={fmt} tick={{ fontSize: 11, fill: "#94a3b8" }} />
              <Tooltip
                formatter={(v: number) => [`£${v.toLocaleString()}`, "Actual Cost"]}
                contentStyle={{ background: "#1a1d27", border: "1px solid #2e3347", borderRadius: 6 }}
              />
              <Bar dataKey="value" fill="#3b82f6" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 20, flex: 1, minWidth: 240 }}>
          <h3 style={{ marginBottom: 16, fontWeight: 600, fontSize: 14 }}>Work Order Split</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={woTypeData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false}>
                {woTypeData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: "#1a1d27", border: "1px solid #2e3347", borderRadius: 6 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 20, flex: 1, minWidth: 240 }}>
          <h3 style={{ marginBottom: 16, fontWeight: 600, fontSize: 14 }}>Asset Criticality</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={criticalityData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70}>
                {criticalityData.map((_, i) => (
                  <Cell key={i} fill={["#ef4444", "#f59e0b", "#10b981"][i % 3]} />
                ))}
              </Pie>
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ background: "#1a1d27", border: "1px solid #2e3347", borderRadius: 6 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Asset class bar */}
      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 20 }}>
        <h3 style={{ marginBottom: 16, fontWeight: 600, fontSize: 14 }}>Assets by Equipment Class</h3>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={assetClassData} layout="vertical" margin={{ left: 120 }}>
            <XAxis type="number" tick={{ fontSize: 11, fill: "#94a3b8" }} />
            <YAxis dataKey="name" type="category" width={120} tick={{ fontSize: 11, fill: "#94a3b8" }} />
            <Tooltip contentStyle={{ background: "#1a1d27", border: "1px solid #2e3347", borderRadius: 6 }} />
            <Bar dataKey="value" fill="#8b5cf6" radius={[0, 3, 3, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* PPM cost split */}
      <div style={{ display: "flex", gap: 16 }}>
        {[
          { label: "PPM Cost", value: cost.ppm_cost, color: "#3b82f6" },
          { label: "Statutory Cost", value: cost.statutory_cost, color: "#f59e0b" },
          { label: "Corrective Cost", value: cost.corrective_cost, color: "#ef4444" },
        ].map(item => (
          <div key={item.label} style={{
            flex: 1,
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            padding: "16px 20px",
          }}>
            <div style={{ color: "var(--muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
              {item.label}
            </div>
            <div style={{ fontSize: 22, fontWeight: 700, color: item.color }}>
              £{(item.value / 1000).toFixed(0)}k
            </div>
            <div style={{ color: "var(--muted)", fontSize: 11, marginTop: 4 }}>
              {((item.value / cost.total_actual_cost) * 100).toFixed(1)}% of total
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
