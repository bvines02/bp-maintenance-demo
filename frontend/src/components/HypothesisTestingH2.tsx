import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  ReferenceLine, Legend,
} from "recharts";
import { getH2_1, getH2_2, getH2_3, getH2_4 } from "../api";
import { usePlatforms } from "../context/PlatformContext";

// ─── Shared primitives (same as H1) ─────────────────────────────────────────

const CHART_STYLE = { background: "#1e293b", border: "1px solid #334155", borderRadius: 6, fontSize: 12 };
const TICK = { fontSize: 11, fill: "#94a3b8" };

function Loader() {
  return <div style={{ color: "var(--muted)", padding: 40, textAlign: "center" as const }}>Analysing data...</div>;
}

function Verdict({ level, text }: { level: "supported" | "partial" | "investigating"; text: string }) {
  const cfg = {
    supported:    { color: "#ef4444", label: "HYPOTHESIS SUPPORTED", bg: "#ef444418", border: "#ef444444" },
    partial:      { color: "#f59e0b", label: "PARTIAL EVIDENCE",     bg: "#f59e0b18", border: "#f59e0b44" },
    investigating:{ color: "#3b82f6", label: "INVESTIGATING",         bg: "#3b82f618", border: "#3b82f644" },
  }[level];
  return (
    <div style={{ background: cfg.bg, border: `1px solid ${cfg.border}`, borderRadius: 8, padding: "14px 18px", display: "flex", gap: 14, alignItems: "flex-start" }}>
      <span style={{ color: cfg.color, fontWeight: 700, fontSize: 12, letterSpacing: "0.06em", flexShrink: 0, marginTop: 1 }}>{cfg.label}</span>
      <span style={{ color: "var(--text)", fontSize: 13, lineHeight: 1.5 }}>{text}</span>
    </div>
  );
}

function EvidenceCard({ label, value, sub, color = "#3b82f6" }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "14px 18px", flex: 1, minWidth: 160 }}>
      <div style={{ color: "var(--muted)", fontSize: 11, fontWeight: 500, textTransform: "uppercase" as const, letterSpacing: "0.06em", marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700, color, lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ color: "var(--muted)", fontSize: 11, marginTop: 6 }}>{sub}</div>}
    </div>
  );
}

function Panel({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 20, flex: 1, minWidth: 300 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h3 style={{ fontWeight: 600, fontSize: 14 }}>{title}</h3>
        {action}
      </div>
      {children}
    </div>
  );
}

const signalColor = (s: string) =>
  s === "OVER-CONSERVATIVE" || s === "INVESTIGATE" ? "#ef4444" :
  s === "REVIEW" || s === "MODERATE" ? "#f59e0b" : "#10b981";

const patternColor = (p: string) =>
  p === "Random (exponential)" ? "#ef4444" :
  p === "Wear-out" ? "#10b981" :
  p === "Mixed" ? "#f59e0b" : "#64748b";

// ─── H2.1 ────────────────────────────────────────────────────────────────────

export function H2_1({ params }: { params: { over_conservative_threshold: number; review_threshold: number } }) {
  const { platformsParam } = usePlatforms();
  const { data, isLoading } = useQuery({
    queryKey: ["h2-1", platformsParam, params],
    queryFn: () => getH2_1(platformsParam, { over_conservative_threshold: params.over_conservative_threshold, review_threshold: params.review_threshold }),
  });
  if (isLoading) return <Loader />;
  if (!data) return null;

  type ClassRow = {
    equipment_class: string; asset_count: number;
    shortest_pm_interval_days: number; shortest_pm_task: string;
    empirical_mtbf_days: number | null; pm_cycles_per_failure: number | null;
    pct_assets_zero_corrective: number; signal: string;
  };
  const rows: ClassRow[] = data.class_analysis;
  const chartData = rows
    .filter(r => r.pm_cycles_per_failure !== null)
    .map(r => ({ name: r.equipment_class.replace(" / ", "/"), value: r.pm_cycles_per_failure!, signal: r.signal }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Verdict
        level={data.over_conservative_count >= 3 ? "supported" : "partial"}
        text={data.summary}
      />
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <EvidenceCard label="Over-Conservative Classes" value={data.over_conservative_count} sub="PM interval < 10% of observed MTBF" color="#ef4444" />
        <EvidenceCard label="Highest Ratio" value={`${Math.max(...rows.filter(r=>r.pm_cycles_per_failure).map(r=>r.pm_cycles_per_failure!))}×`} sub="PM cycles per observed failure" color="#f59e0b" />
        <EvidenceCard label="Classes Analysed" value={rows.length} sub="With time-based strategies" color="#3b82f6" />
        <EvidenceCard label="Zero-Failure Assets" value={`${Math.round(rows.reduce((a,r)=>a+r.pct_assets_zero_corrective,0)/Math.max(rows.length,1))}%`} sub="Avg assets with no corrective in 6yr" color="#8b5cf6" />
      </div>

      <Panel title="PM Cycles per Observed Failure by Equipment Class"
        action={<span style={{ color: "var(--muted)", fontSize: 11 }}>Higher = more conservative than data suggests</span>}>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 150 }}>
            <XAxis type="number" tick={TICK} label={{ value: "PM cycles fired per failure event", position: "insideBottom", offset: -5, fill: "#64748b", fontSize: 10 }} />
            <YAxis dataKey="name" type="category" width={148} tick={{ fontSize: 10, fill: "#94a3b8" }} />
            <Tooltip contentStyle={CHART_STYLE} formatter={(v: number) => [`${v}×`, "PM cycles / failure"]} />
            <ReferenceLine x={params.over_conservative_threshold} stroke="#ef4444" strokeDasharray="4 2" label={{ value: `${params.over_conservative_threshold}× threshold`, fill: "#ef4444", fontSize: 9, position: "insideTopRight" }} />
            <Bar dataKey="value" radius={[0, 3, 3, 0]}>
              {chartData.map((e, i) => <Cell key={i} fill={signalColor(e.signal)} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Panel>

      <Panel title="Full Class Analysis">
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Equipment Class", "Shortest PM Interval", "Empirical MTBF", "Ratio", "% Zero CM", "Signal"].map(h => (
                  <th key={h} style={{ padding: "6px 10px", textAlign: "left", color: "var(--muted)", fontWeight: 500, fontSize: 11 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "8px 10px", fontWeight: 500 }}>{r.equipment_class}</td>
                  <td style={{ padding: "8px 10px", color: "var(--muted)" }}>{r.shortest_pm_interval_days}d <span style={{ fontSize: 10 }}>({r.shortest_pm_task})</span></td>
                  <td style={{ padding: "8px 10px" }}>{r.empirical_mtbf_days ? `${r.empirical_mtbf_days}d` : <span style={{ color: "var(--muted)" }}>—</span>}</td>
                  <td style={{ padding: "8px 10px", fontWeight: 600, color: r.pm_cycles_per_failure ? signalColor(r.signal) : "var(--muted)" }}>
                    {r.pm_cycles_per_failure ? `${r.pm_cycles_per_failure}×` : "—"}
                  </td>
                  <td style={{ padding: "8px 10px" }}>{r.pct_assets_zero_corrective}%</td>
                  <td style={{ padding: "8px 10px" }}>
                    <span style={{ color: signalColor(r.signal), fontWeight: 600, fontSize: 11 }}>{r.signal}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

// ─── H2.2 ────────────────────────────────────────────────────────────────────

export function H2_2({ params }: { params: { random_cv_threshold: number; wearout_cv_threshold: number } }) {
  const { platformsParam } = usePlatforms();
  const { data, isLoading } = useQuery({
    queryKey: ["h2-2", platformsParam, params],
    queryFn: () => getH2_2(platformsParam, { random_cv_threshold: params.random_cv_threshold, wearout_cv_threshold: params.wearout_cv_threshold }),
  });
  if (isLoading) return <Loader />;
  if (!data) return null;

  type ClassRow = {
    equipment_class: string; total_failures: number;
    mean_inter_failure_days: number | null; cv: number | null;
    failure_pattern: string; hard_time_justified: boolean | null;
    recommendation: string;
  };
  const rows: ClassRow[] = data.class_analysis;
  const chartData = rows
    .filter(r => r.cv !== null)
    .map(r => ({ name: r.equipment_class.replace(" / ", "/"), cv: r.cv!, pattern: r.failure_pattern }))
    .sort((a, b) => b.cv - a.cv);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Verdict
        level={data.unjustified_count >= 3 ? "supported" : "partial"}
        text={data.summary}
      />
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <EvidenceCard label="Random Failure Classes" value={data.unjustified_count} sub={`CV > ${params.random_cv_threshold} — hard-time not justified`} color="#ef4444" />
        <EvidenceCard label="Wear-out Classes" value={rows.filter(r => r.hard_time_justified === true).length} sub={`CV < ${params.wearout_cv_threshold} — hard-time is justified`} color="#10b981" />
        <EvidenceCard label="Mixed / Uncertain" value={rows.filter(r => r.hard_time_justified === null && r.cv !== null).length} sub="0.5 < CV < 0.8" color="#f59e0b" />
        <EvidenceCard label="Insufficient Data" value={rows.filter(r => r.cv === null).length} sub="< 3 failure intervals recorded" color="#64748b" />
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <Panel title="Coefficient of Variation by Equipment Class"
          action={<span style={{ color: "var(--muted)", fontSize: 11 }}>CV &gt; {params.random_cv_threshold} = random · CV &lt; {params.wearout_cv_threshold} = wear-out</span>}>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 150 }}>
              <XAxis type="number" tick={TICK} domain={[0, 1.4]} />
              <YAxis dataKey="name" type="category" width={148} tick={{ fontSize: 10, fill: "#94a3b8" }} />
              <Tooltip contentStyle={CHART_STYLE} formatter={(v: number) => [v.toFixed(2), "CV"]} />
              <ReferenceLine x={params.random_cv_threshold} stroke="#ef4444" strokeDasharray="4 2" label={{ value: `Random (${params.random_cv_threshold})`, fill: "#ef4444", fontSize: 9, position: "insideTopRight" }} />
              <ReferenceLine x={params.wearout_cv_threshold} stroke="#10b981" strokeDasharray="4 2" label={{ value: `Wear-out (${params.wearout_cv_threshold})`, fill: "#10b981", fontSize: 9, position: "insideBottomRight" }} />
              <Bar dataKey="cv" radius={[0, 3, 3, 0]}>
                {chartData.map((e, i) => <Cell key={i} fill={patternColor(e.pattern)} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div style={{ display: "flex", gap: 16, marginTop: 10, flexWrap: "wrap" }}>
            {[["#ef4444","Random — replace strategy"], ["#f59e0b","Mixed — review"], ["#10b981","Wear-out — justified"], ["#64748b","Insufficient data"]].map(([color, label]) => (
              <div key={label} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--muted)" }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: color, display: "inline-block" }} />{label}
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <Panel title="Detailed Findings and Recommendations">
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {rows.filter(r => r.cv !== null).map((r, i) => (
            <div key={i} style={{ border: "1px solid var(--border)", borderRadius: 6, padding: "12px 14px" }}>
              <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 6 }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>{r.equipment_class}</span>
                <span style={{ color: patternColor(r.failure_pattern), fontSize: 11, fontWeight: 600, background: patternColor(r.failure_pattern) + "22", padding: "2px 8px", borderRadius: 4 }}>{r.failure_pattern}</span>
                {r.cv !== null && <span style={{ color: "var(--muted)", fontSize: 11 }}>CV = {r.cv.toFixed(2)}</span>}
                {r.mean_inter_failure_days && <span style={{ color: "var(--muted)", fontSize: 11 }}>Mean MTBF = {r.mean_inter_failure_days}d</span>}
                <span style={{ color: "var(--muted)", fontSize: 11, marginLeft: "auto" }}>{r.total_failures} failures</span>
              </div>
              <div style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.5 }}>{r.recommendation}</div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

// ─── H2.3 ────────────────────────────────────────────────────────────────────

export function H2_3({ params }: { params: { min_corrective_events: number } }) {
  const { platformsParam } = usePlatforms();
  const { data, isLoading } = useQuery({
    queryKey: ["h2-3", platformsParam, params],
    queryFn: () => getH2_3(platformsParam, { min_corrective_events: params.min_corrective_events }),
  });
  const [showUnder, setShowUnder] = useState(false);
  const [showOver, setShowOver] = useState(false);
  if (isLoading) return <Loader />;
  if (!data) return null;

  type CritRow = { criticality: string; asset_count: number; avg_annual_ppm_cost: number; avg_annual_cm_cost: number; avg_annual_ppm_wos: number; avg_annual_cm_events: number; cm_to_ppm_ratio_pct: number };
  type AssetRow = { asset_tag: string; equipment_class: string; platform: string; system?: string; corrective_events_total: number };

  const critRows: CritRow[] = data.by_criticality;
  const underInvested: AssetRow[] = data.under_invested_assets;
  const overMaintained: AssetRow[] = data.over_maintained_assets;

  const freqChartData = critRows.map(r => ({ name: `Criticality ${r.criticality}`, wos: r.avg_annual_ppm_wos, cm: r.avg_annual_cm_events }));
  const critARow = critRows.find(r => r.criticality === "A");
  const critCRow = critRows.find(r => r.criticality === "C");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Verdict
        level={underInvested.length > 5 ? "supported" : "partial"}
        text={data.summary}
      />
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <EvidenceCard label="Under-Invested (Crit A)" value={underInvested.length} sub={`Crit A assets with ${params.min_corrective_events}+ corrective events`} color="#ef4444" />
        <EvidenceCard label="Over-Maintained (Crit C)" value={overMaintained.length} sub="Low-criticality with above-average PM effort" color="#f59e0b" />
        {critARow && <EvidenceCard label="Crit A PPM WOs/yr" value={critARow.avg_annual_ppm_wos.toFixed(1)} sub="Avg per asset" color="#3b82f6" />}
        {critCRow && <EvidenceCard label="Crit C PPM WOs/yr" value={critCRow.avg_annual_ppm_wos.toFixed(1)} sub="Avg per asset" color="#8b5cf6" />}
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <Panel title="Average Annual WO Frequency per Asset by Criticality">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={freqChartData} margin={{ bottom: 10 }}>
              <XAxis dataKey="name" tick={TICK} />
              <YAxis tick={TICK} label={{ value: "WOs / asset / year", angle: -90, position: "insideLeft", fill: "#64748b", fontSize: 10, dy: 60 }} />
              <Tooltip contentStyle={CHART_STYLE} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="wos" name="PPM WOs/yr" fill="#3b82f6" radius={[3,3,0,0]} />
              <Bar dataKey="cm" name="CM events/yr" fill="#ef4444" radius={[3,3,0,0]} />
            </BarChart>
          </ResponsiveContainer>
          <div style={{ marginTop: 10, display: "flex", gap: 24, flexWrap: "wrap" }}>
            {critRows.map(r => (
              <div key={r.criticality} style={{ fontSize: 12 }}>
                <span style={{ color: "var(--muted)" }}>Crit {r.criticality} CM:PPM ratio: </span>
                <span style={{ fontWeight: 600, color: r.cm_to_ppm_ratio_pct > 150 ? "#ef4444" : "#f59e0b" }}>{r.cm_to_ppm_ratio_pct}%</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      {underInvested.length > 0 && (
        <Panel title={`Criticality A Assets with High Corrective Rate (${underInvested.length} assets)`}
          action={<button onClick={() => setShowUnder(v => !v)} style={{ fontSize: 11, color: "#3b82f6", background: "transparent", border: "none", cursor: "pointer" }}>{showUnder ? "Show less" : "Show all"}</button>}>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["Asset Tag", "Class", "Platform", "System", "Corrective Events"].map(h => (
                    <th key={h} style={{ padding: "6px 10px", textAlign: "left", color: "var(--muted)", fontWeight: 500, fontSize: 11 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(showUnder ? underInvested : underInvested.slice(0, 8)).map((r, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={{ padding: "7px 10px", fontFamily: "monospace", color: "var(--accent)", fontSize: 12 }}>{r.asset_tag}</td>
                    <td style={{ padding: "7px 10px" }}>{r.equipment_class}</td>
                    <td style={{ padding: "7px 10px", color: "var(--muted)" }}>{r.platform}</td>
                    <td style={{ padding: "7px 10px", color: "var(--muted)" }}>{r.system || "—"}</td>
                    <td style={{ padding: "7px 10px", fontWeight: 600, color: "#ef4444" }}>{r.corrective_events_total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {overMaintained.length > 0 && (
        <Panel title={`Criticality C Assets Receiving Above-Average PM Effort (${overMaintained.length} assets)`}
          action={<button onClick={() => setShowOver(v => !v)} style={{ fontSize: 11, color: "#3b82f6", background: "transparent", border: "none", cursor: "pointer" }}>{showOver ? "Show less" : "Show all"}</button>}>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["Asset Tag", "Class", "Platform", "CM Events"].map(h => (
                    <th key={h} style={{ padding: "6px 10px", textAlign: "left", color: "var(--muted)", fontWeight: 500, fontSize: 11 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(showOver ? overMaintained : overMaintained.slice(0, 8)).map((r, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={{ padding: "7px 10px", fontFamily: "monospace", color: "var(--accent)", fontSize: 12 }}>{r.asset_tag}</td>
                    <td style={{ padding: "7px 10px" }}>{r.equipment_class}</td>
                    <td style={{ padding: "7px 10px", color: "var(--muted)" }}>{r.platform}</td>
                    <td style={{ padding: "7px 10px" }}>{r.corrective_events_total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  );
}

// ─── H2.4 ────────────────────────────────────────────────────────────────────

export function H2_4() {
  const { platformsParam } = usePlatforms();
  const { data, isLoading } = useQuery({ queryKey: ["h2-4", platformsParam], queryFn: () => getH2_4(platformsParam) });
  if (isLoading) return <Loader />;
  if (!data) return null;

  type TaskRow = {
    task_code: string; task_description: string; regulation: string;
    current_interval_days: number; regulatory_minimum_days: number;
    frequency_multiplier: number; asset_count: number;
    avg_cost_per_wo: number; annual_excess_fleet_cost: number; notes: string;
  };
  const tasks: TaskRow[] = data.statutory_tasks;
  const chartData = tasks.map(t => ({ name: t.task_code, multiplier: t.frequency_multiplier, excess_wos_per_asset: +(365 / t.current_interval_days - 365 / t.regulatory_minimum_days).toFixed(2) }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Verdict
        level={tasks.length >= 3 ? "supported" : "partial"}
        text={data.summary}
      />
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <EvidenceCard label="Tasks Exceeding Minimum" value={tasks.length} sub="Performing more frequently than required" color="#ef4444" />
        <EvidenceCard label="Highest Multiplier" value={tasks.length > 0 ? `${Math.max(...tasks.map(t => t.frequency_multiplier))}×` : "—"} sub="Most gold-plated task" color="#8b5cf6" />
        <EvidenceCard label="Assets Affected" value={tasks.reduce((a, t) => a + t.asset_count, 0)} sub="Distinct assets with gold-plated tasks" color="#3b82f6" />
        <EvidenceCard label="Excess WOs / Asset / Yr" value={chartData.length > 0 ? Math.max(...chartData.map(t => t.excess_wos_per_asset)).toFixed(1) : "—"} sub="Highest excess frequency (single task)" color="#f59e0b" />
      </div>

      <Panel title="Excess Frequency vs Regulatory Minimum by Task"
        action={<span style={{ color: "var(--muted)", fontSize: 11 }}>How many times more frequent than required</span>}>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={chartData} margin={{ bottom: 10 }}>
            <XAxis dataKey="name" tick={TICK} />
            <YAxis tick={TICK} label={{ value: "Frequency multiplier (×)", angle: -90, position: "insideLeft", fill: "#64748b", fontSize: 10, dy: 60 }} />
            <Tooltip contentStyle={CHART_STYLE} formatter={(v: number) => [`${v}×`, "Frequency multiplier"]} />
            <ReferenceLine y={1} stroke="#64748b" strokeDasharray="4 2" label={{ value: "Regulatory minimum", fill: "#64748b", fontSize: 9 }} />
            <Bar dataKey="multiplier" fill="#f59e0b" radius={[3,3,0,0]} />
          </BarChart>
        </ResponsiveContainer>
      </Panel>

      <Panel title="Detailed Task Analysis">
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {tasks.map((t, i) => (
            <div key={i} style={{ border: "1px solid var(--border)", borderRadius: 6, padding: "14px 16px" }}>
              <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
                <span style={{ fontFamily: "monospace", color: "var(--accent)", fontWeight: 700, fontSize: 13 }}>{t.task_code}</span>
                <span style={{ fontWeight: 600, fontSize: 13 }}>{t.task_description}</span>
                <span style={{ color: "var(--muted)", fontSize: 11 }}>·</span>
                <span style={{ color: "#64748b", fontSize: 11 }}>{t.regulation}</span>
                <span style={{ marginLeft: "auto", color: "#f59e0b", fontWeight: 700 }}>{t.frequency_multiplier}× regulatory minimum</span>
              </div>
              <div style={{ display: "flex", gap: 20, marginBottom: 8, flexWrap: "wrap" }}>
                {[
                  ["Current interval", `${t.current_interval_days}d`],
                  ["Regulatory minimum", `${t.regulatory_minimum_days}d`],
                  ["Performing", `${t.frequency_multiplier}× as often as required`],
                  ["Assets affected", t.asset_count],
                  ["Excess WOs/asset/yr", +(365 / t.current_interval_days - 365 / t.regulatory_minimum_days).toFixed(2)],
                ].map(([label, value]) => (
                  <div key={String(label)} style={{ fontSize: 12 }}>
                    <span style={{ color: "var(--muted)" }}>{label}: </span>
                    <span style={{ fontWeight: 600 }}>{String(value)}</span>
                  </div>
                ))}
              </div>
              <div style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.5, borderTop: "1px solid var(--border)", paddingTop: 8 }}>{t.notes}</div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

// ─── Tab switcher ─────────────────────────────────────────────────────────────

type H2Tab = "h2-1" | "h2-2" | "h2-3" | "h2-4";

const H2_TABS: { id: H2Tab; label: string; title: string }[] = [
  { id: "h2-1", label: "H2.1", title: "OEM vs Actual Failure Rates" },
  { id: "h2-2", label: "H2.2", title: "Hard-Time vs Random Failure" },
  { id: "h2-3", label: "H2.3", title: "Criticality vs Maintenance Effort" },
  { id: "h2-4", label: "H2.4", title: "Statutory Gold-Plating" },
];

export default function HypothesisTestingH2() {
  const [active, setActive] = useState<H2Tab>("h2-1");
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Sub-tab bar */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {H2_TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setActive(t.id)}
            style={{
              padding: "7px 16px", borderRadius: 6, fontSize: 13,
              background: active === t.id ? "#3b82f622" : "transparent",
              color: active === t.id ? "#3b82f6" : "var(--muted)",
              fontWeight: active === t.id ? 600 : 400,
              border: active === t.id ? "1px solid #3b82f644" : "1px solid transparent",
              cursor: "pointer", transition: "all 0.15s",
            }}>
            <span style={{ fontFamily: "monospace", marginRight: 6 }}>{t.label}</span>
            {t.title}
          </button>
        ))}
      </div>

      {/* Active hypothesis */}
      <div>
        {active === "h2-1" && <H2_1 params={{ over_conservative_threshold: 10, review_threshold: 5 }} />}
        {active === "h2-2" && <H2_2 params={{ random_cv_threshold: 0.8, wearout_cv_threshold: 0.5 }} />}
        {active === "h2-3" && <H2_3 params={{ min_corrective_events: 3 }} />}
        {active === "h2-4" && <H2_4 />}
      </div>
    </div>
  );
}
