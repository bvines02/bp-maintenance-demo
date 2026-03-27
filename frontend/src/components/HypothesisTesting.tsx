import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line, Legend, ReferenceLine,
} from "recharts";
import { getH1_1, getH1_2, getH1_3 } from "../api";
import { usePlatforms } from "../context/PlatformContext";

// ─── Shared primitives ───────────────────────────────────────────────────────

type VerdictLevel = "supported" | "partial" | "investigating";
const VERDICT_CONFIG: Record<VerdictLevel, { label: string; color: string; bg: string }> = {
  supported:     { label: "HYPOTHESIS SUPPORTED",      color: "#10b981", bg: "#10b98118" },
  partial:       { label: "PARTIAL EVIDENCE",          color: "#f59e0b", bg: "#f59e0b18" },
  investigating: { label: "UNDER INVESTIGATION",       color: "#3b82f6", bg: "#3b82f618" },
};

const Verdict = ({ level, text }: { level: VerdictLevel; text: string }) => {
  const cfg = VERDICT_CONFIG[level];
  return (
    <div style={{
      background: cfg.bg, border: `1px solid ${cfg.color}44`,
      borderRadius: "var(--radius)", padding: "16px 20px",
      display: "flex", gap: 16, alignItems: "flex-start",
    }}>
      <div style={{ flexShrink: 0 }}>
        <span style={{
          background: cfg.color, color: "#fff", borderRadius: 4,
          padding: "3px 10px", fontSize: 11, fontWeight: 800, letterSpacing: "0.06em",
        }}>{cfg.label}</span>
      </div>
      <p style={{ color: "var(--text)", fontSize: 13, lineHeight: 1.65, margin: 0 }}>{text}</p>
    </div>
  );
};

const EvidenceCard = ({ label, value, sub, color = "var(--text)" }: { label: string; value: string | number; sub?: string; color?: string }) => (
  <div style={{
    flex: 1, minWidth: 140,
    background: "var(--surface2)", border: "1px solid var(--border)",
    borderRadius: "var(--radius)", padding: "14px 18px",
  }}>
    <div style={{ color: "var(--muted)", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>{label}</div>
    <div style={{ fontSize: 26, fontWeight: 700, color, lineHeight: 1 }}>{typeof value === "number" ? value.toLocaleString() : value}</div>
    {sub && <div style={{ color: "var(--muted)", fontSize: 11, marginTop: 5 }}>{sub}</div>}
  </div>
);

const Panel = ({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) => (
  <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 20 }}>
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
      <h3 style={{ fontWeight: 600, fontSize: 14, margin: 0 }}>{title}</h3>
      {action}
    </div>
    {children}
  </div>
);

const Recommendation = ({ children }: { children: React.ReactNode }) => (
  <div style={{
    background: "var(--surface)", border: "1px solid #3b82f644",
    borderLeft: "4px solid #3b82f6", borderRadius: "var(--radius)", padding: "16px 20px",
  }}>
    <div style={{ color: "#3b82f6", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
      ▸ Recommendation
    </div>
    <div style={{ color: "var(--text)", fontSize: 13, lineHeight: 1.65 }}>{children}</div>
  </div>
);

const CHART_STYLE = { background: "#1a1d27", border: "1px solid #2e3347", borderRadius: 6 };
const TICK = { fontSize: 11, fill: "#94a3b8" };

// ─── H1.1 ────────────────────────────────────────────────────────────────────

function H1_1() {
  const { platformsParam } = usePlatforms();
  const { data, isLoading } = useQuery({ queryKey: ["h1-1", platformsParam], queryFn: () => getH1_1(platformsParam) });
  const [showAll, setShowAll] = useState(false);
  if (isLoading) return <Loader />;
  if (!data) return null;

  const tasks = data.over_conservative_tasks as Array<Record<string, unknown>>;
  const trend = data.yearly_deferral_vs_corrective_trend as Array<Record<string, unknown>>;
  const visible = showAll ? tasks : tasks.slice(0, 6);

  // Build bar chart: avg deferral per task
  const deferralChart = tasks.slice(0, 10).map((t) => ({
    name: t.task_code as string,
    deferral_pct: t.pct_assets_with_no_corrective as number,
    occurrences: t.deferred_occurrences as number,
  }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Verdict
        level="supported"
        text={data.summary as string}
      />

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <EvidenceCard label="Over-Conservative Task Types" value={tasks.length} sub="Consistently deferred, no consequence" color="#10b981" />
        <EvidenceCard label="Assets: Deferred, No Failure" value={data.assets_with_deferrals_no_corrective as number} sub="Repeated deferrals, zero corrective in same year" color="#10b981" />
        <EvidenceCard label="Strongest Signal" value={tasks.length > 0 ? `${(tasks[0].pct_assets_with_no_corrective as number)}%` : "—"} sub={tasks.length > 0 ? `of ${tasks[0].task_code} deferrals had no consequence` : ""} color="#f59e0b" />
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <Panel title="Fleet-Wide: PM Deferrals vs Corrective Events by Year" action={
          <span style={{ color: "var(--muted)", fontSize: 12 }}>Uncorrelated trend = over-conservative intervals</span>
        }>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={trend} margin={{ left: 10, right: 10 }}>
              <XAxis dataKey="year" tick={TICK} />
              <YAxis tick={TICK} />
              <Tooltip contentStyle={CHART_STYLE} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line type="monotone" dataKey="ppm_deferrals" name="PPM Deferrals (>14 days)" stroke="#f59e0b" strokeWidth={2.5} dot={{ r: 3 }} />
              <Line type="monotone" dataKey="corrective_events" name="Corrective Events" stroke="#ef4444" strokeWidth={2.5} dot={{ r: 3 }} />
              <Line type="monotone" dataKey="ppm_completed" name="PPM Completed" stroke="#3b82f6" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
            </LineChart>
          </ResponsiveContainer>
          <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 8, lineHeight: 1.5 }}>
            <strong style={{ color: "var(--text)" }}>How to read this:</strong> If deferrals climb while corrective events remain flat or decrease, the data supports H1.1 — equipment is tolerating the delayed maintenance without consequence.
          </div>
        </Panel>
      </div>

      {deferralChart.length > 0 && (
        <Panel title="No-Consequence Deferral Rate by Task (% of occurrences with no corrective event during deferral window)">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={deferralChart} margin={{ left: 10 }}>
              <XAxis dataKey="name" tick={TICK} />
              <YAxis tickFormatter={(v) => `${v}%`} tick={TICK} domain={[0, 100]} />
              <Tooltip
                contentStyle={CHART_STYLE}
                formatter={(v: number) => [`${v}%`, "No-consequence rate"]}
              />
              <ReferenceLine y={70} stroke="#10b981" strokeDasharray="4 2" label={{ value: "70% threshold", fill: "#10b981", fontSize: 10 }} />
              <Bar dataKey="deferral_pct" radius={[3, 3, 0, 0]}>
                {deferralChart.map((entry, i) => (
                  <Cell key={i} fill={entry.deferral_pct >= 90 ? "#10b981" : entry.deferral_pct >= 70 ? "#f59e0b" : "#3b82f6"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      )}

      {tasks.length > 0 && (
        <Panel title="Over-Conservative Tasks — Evidence Detail" action={
          tasks.length > 6 ? (
            <button onClick={() => setShowAll(!showAll)} style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 4, padding: "4px 12px", color: "var(--muted)", fontSize: 12 }}>
              {showAll ? "Show less" : `Show all ${tasks.length}`}
            </button>
          ) : undefined
        }>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "var(--surface2)", borderBottom: "1px solid var(--border)" }}>
                {["Task Code", "Description", "Occurrences Deferred", "Affected Assets", "No-Consequence Rate", "Current Interval", "Action"].map(h => (
                  <th key={h} style={{ padding: "9px 12px", textAlign: "left", color: "var(--muted)", fontWeight: 600, fontSize: 11, textTransform: "uppercase", whiteSpace: "nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map((t) => {
                const pct = t.pct_assets_with_no_corrective as number;
                const interval = t.current_interval_days as number | null;
                const suggested = interval ? Math.round(interval * (1 + (pct / 100) * 0.5)) : null;
                return (
                  <tr key={t.task_code as string} style={{ borderBottom: "1px solid var(--border)" }}
                    onMouseEnter={e => (e.currentTarget.style.background = "var(--surface2)")}
                    onMouseLeave={e => (e.currentTarget.style.background = "")}>
                    <td style={{ padding: "9px 12px", fontFamily: "monospace", color: "var(--accent)", fontWeight: 600 }}>{t.task_code as string}</td>
                    <td style={{ padding: "9px 12px" }}>{t.task_description as string}</td>
                    <td style={{ padding: "9px 12px", textAlign: "center" }}>{t.deferred_occurrences as number}</td>
                    <td style={{ padding: "9px 12px", textAlign: "center" }}>{t.affected_assets as number}</td>
                    <td style={{ padding: "9px 12px", textAlign: "center" }}>
                      <span style={{ fontWeight: 700, color: pct >= 90 ? "#10b981" : pct >= 70 ? "#f59e0b" : "var(--text)" }}>{pct}%</span>
                    </td>
                    <td style={{ padding: "9px 12px", textAlign: "center", color: "var(--muted)" }}>{interval ? `${interval}d` : "—"}</td>
                    <td style={{ padding: "9px 12px", color: "#10b981", fontSize: 12, fontWeight: 600 }}>
                      {suggested && interval && suggested > interval ? `Propose ${suggested}d` : "Review basis"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Panel>
      )}

      <Recommendation>
        {tasks.length > 0
          ? `${tasks.length} PM task types demonstrate a consistent pattern of safe deferral. The evidence supports reviewing these task intervals through a formal FMECA or RCM workshop. Priority tasks are ${tasks.slice(0, 3).map(t => t.task_code).join(", ")}. Proposed interval extensions should be reviewed against failure mode criticality and approved through the MOC process before implementation.`
          : "Insufficient deferral pattern data to support this hypothesis at current thresholds. Consider lowering the minimum deferral threshold or extending the analysis window."
        }
      </Recommendation>
    </div>
  );
}

// ─── H1.2 ────────────────────────────────────────────────────────────────────

function H1_2() {
  const { platformsParam } = usePlatforms();
  const { data, isLoading } = useQuery({ queryKey: ["h1-2", platformsParam], queryFn: () => getH1_2(platformsParam) });
  const [expanded, setExpanded] = useState<number | null>(0);
  if (isLoading) return <Loader />;
  if (!data) return null;

  const overlaps = data.overlaps as Array<Record<string, unknown>>;
  const duplicates = overlaps.filter(o => o.overlap_type === "Duplicate function");
  const nested = overlaps.filter(o => o.overlap_type === "Nested interval");

  const savingByClass: Record<string, number> = {};
  overlaps.forEach(o => {
    const cls = o.equipment_class as string;
    savingByClass[cls] = (savingByClass[cls] || 0) + (o.fleet_annual_mob_saving as number);
  });
  const savingChart = Object.entries(savingByClass)
    .map(([name, value]) => ({ name: name.replace(" / ", "/"), value: Math.round(value) }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Verdict
        level={duplicates.length > 0 ? "supported" : "partial"}
        text={data.summary as string}
      />

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <EvidenceCard label="Overlap Groups Found" value={overlaps.length} sub="Same component & function, separate tasks" color="#f59e0b" />
        <EvidenceCard label="Duplicate Functions" value={duplicates.length} sub="Identical component & function — one may be redundant" color="#ef4444" />
        <EvidenceCard label="Nested Intervals" value={nested.length} sub="Shorter task that could combine with longer visit" color="#f59e0b" />
        <EvidenceCard label="Est. Fleet Annual Saving" value={`£${((data.total_fleet_annual_saving as number) / 1000).toFixed(0)}k`} sub="Mobilisation & efficiency gains from consolidation" color="#10b981" />
      </div>

      {savingChart.length > 0 && (
        <Panel title="Estimated Annual Saving by Equipment Class (Consolidation Opportunities)">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={savingChart} layout="vertical" margin={{ left: 140 }}>
              <XAxis type="number" tickFormatter={(v) => `£${(v / 1000).toFixed(0)}k`} tick={TICK} />
              <YAxis dataKey="name" type="category" width={140} tick={{ fontSize: 10, fill: "#94a3b8" }} />
              <Tooltip contentStyle={CHART_STYLE} formatter={(v: number) => [`£${v.toLocaleString()}`, "Annual saving"]} />
              <Bar dataKey="value" radius={[0, 3, 3, 0]} fill="#f59e0b" />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      )}

      <Panel title="Overlap Detail — Click to expand">
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {overlaps.map((o, i) => {
            type TaskRow = { task_code: string; task_description: string; interval_days: number; estimated_hours: number; basis: string; annual_wo_count: number };
            const tasks = o.overlapping_tasks as TaskRow[];
            const isOpen = expanded === i;
            const isDuplicate = o.overlap_type === "Duplicate function";
            return (
              <div key={i} style={{ border: "1px solid var(--border)", borderRadius: 6, overflow: "hidden" }}>
                {/* Header row */}
                <button
                  onClick={() => setExpanded(isOpen ? null : i)}
                  style={{
                    width: "100%", display: "flex", alignItems: "center", gap: 12,
                    padding: "12px 16px", background: isOpen ? "var(--surface2)" : "transparent",
                    color: "var(--text)", textAlign: "left", fontSize: 13,
                  }}>
                  <span style={{ color: "var(--muted)", fontSize: 12, flexShrink: 0 }}>{isOpen ? "▾" : "▸"}</span>
                  <span style={{ fontWeight: 600 }}>{o.equipment_class as string}</span>
                  <span style={{ color: "var(--muted)" }}>·</span>
                  <span style={{ color: "var(--muted)" }}>{o.component as string} — {o.function as string}</span>
                  <span style={{
                    marginLeft: 4, flexShrink: 0,
                    background: isDuplicate ? "#ef444422" : "#f59e0b22",
                    color: isDuplicate ? "#ef4444" : "#f59e0b",
                    border: `1px solid ${isDuplicate ? "#ef444444" : "#f59e0b44"}`,
                    borderRadius: 4, padding: "1px 8px", fontSize: 10, fontWeight: 700, textTransform: "uppercase",
                  }}>{o.overlap_type as string}</span>
                  <span style={{ marginLeft: "auto", color: "#10b981", fontWeight: 700, fontSize: 13, flexShrink: 0 }}>
                    £{(o.fleet_annual_mob_saving as number).toLocaleString()}/yr
                  </span>
                </button>

                {/* Expanded content */}
                {isOpen && (
                  <div style={{ padding: "14px 16px", borderTop: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: 12 }}>
                    {/* Task cards */}
                    <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                      {tasks.map(t => (
                        <div key={t.task_code as string} style={{
                          flex: 1, minWidth: 200,
                          background: "var(--bg)", border: "1px solid var(--border)",
                          borderRadius: 6, padding: "10px 14px",
                        }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                            <span style={{ fontFamily: "monospace", color: "var(--accent)", fontWeight: 700, fontSize: 13 }}>{t.task_code as string}</span>
                            <span style={{ color: "var(--muted)", fontSize: 11 }}>{t.interval_days}d interval</span>
                          </div>
                          <div style={{ fontSize: 12, color: "var(--text)", marginBottom: 3 }}>{t.task_description as string}</div>
                          <div style={{ fontSize: 11, color: "var(--muted)" }}>{t.estimated_hours}h · {t.basis as string} · {t.annual_wo_count} WOs in dataset</div>
                        </div>
                      ))}
                    </div>

                    {/* Metrics */}
                    <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                      {[
                        { label: "Assets in class", value: o.asset_count as number },
                        { label: "Combined visit opportunities/year", value: `${(o.annual_combined_opportunities as number).toFixed(1)}x` },
                        { label: "Hours saved per combined visit", value: `${o.hours_saving_per_visit}h` },
                        { label: "Fleet mob saving/year", value: `£${(o.fleet_annual_mob_saving as number).toLocaleString()}` },
                      ].map(m => (
                        <div key={m.label} style={{ background: "var(--surface2)", borderRadius: 4, padding: "8px 12px", flex: 1, minWidth: 120 }}>
                          <div style={{ color: "var(--muted)", fontSize: 10, textTransform: "uppercase", marginBottom: 2 }}>{m.label}</div>
                          <div style={{ fontWeight: 700, fontSize: 14 }}>{m.value}</div>
                        </div>
                      ))}
                    </div>

                    <div style={{ background: "var(--surface2)", borderLeft: "3px solid #f59e0b", padding: "8px 12px", borderRadius: 4, fontSize: 12, color: "var(--text)" }}>
                      {o.recommendation as string}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Panel>

      <Recommendation>
        {overlaps.length > 0
          ? `${overlaps.length} overlap groups identified across the fleet. Immediate priority: ${duplicates.length} duplicate-function task pairs should be reviewed — one task in each pair may be fully redundant. Nested-interval tasks represent scheduling consolidation opportunities. Recommend a task rationalisation workshop using the component-function matrix above. Fleet mobilisation saving alone: £${((data.total_fleet_annual_saving as number) / 1000).toFixed(0)}k/year before considering labour efficiency gains.`
          : "No significant task overlaps identified at current thresholds."
        }
      </Recommendation>
    </div>
  );
}

// ─── H1.3 ────────────────────────────────────────────────────────────────────

function H1_3() {
  const { platformsParam } = usePlatforms();
  const { data, isLoading } = useQuery({ queryKey: ["h1-3", platformsParam], queryFn: () => getH1_3(platformsParam) });
  const [showAllAssets, setShowAllAssets] = useState(false);
  if (isLoading) return <Loader />;
  if (!data) return null;

  type RatioRow = { equipment_class: string; cm_to_ppm_ratio_pct: number; ppm_count: number; corrective_count: number; total_cm_cost: number; signal: string; name: string };
  const ratioData: RatioRow[] = (data.cm_to_ppm_ratio_by_class as Array<Record<string, unknown>>)
    .slice(0, 10)
    .map(r => ({ ...(r as Omit<RatioRow, "name">), name: (r.equipment_class as string).replace(" / ", "/") }));
  const trendData = data.corrective_trend_by_class as Array<Record<string, unknown>>;
  const topClasses: string[] = data.top_classes_for_trend;
  const repeatAssets = data.repeat_failure_assets as Array<Record<string, unknown>>;
  const highRisk = data.high_risk_classes as Array<Record<string, unknown>>;

  const TREND_COLORS = ["#ef4444", "#f59e0b", "#3b82f6", "#8b5cf6"];
  const visibleAssets = showAllAssets ? repeatAssets : repeatAssets.slice(0, 8);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Verdict
        level={highRisk.length >= 3 ? "supported" : "partial"}
        text={data.summary as string}
      />

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <EvidenceCard label="Repeat-Failure Assets" value={repeatAssets.length} sub="3 or more corrective events 2019–2024" color="#ef4444" />
        <EvidenceCard label="High-Risk Equipment Classes" value={highRisk.length} sub="CM:PPM ratio >20% — strategy not preventing failures" color="#ef4444" />
        <EvidenceCard label="Worst Offender" value={ratioData.length > 0 ? `${ratioData[0].cm_to_ppm_ratio_pct as number}%` : "—"} sub={ratioData.length > 0 ? `${ratioData[0].equipment_class as string} CM:PPM ratio` : ""} color="#f59e0b" />
        <EvidenceCard label="Total Corrective Cost" value={`£${((data.total_corrective_cost as number || 0) / 1000000).toFixed(2) !== "NaN" ? ((data.total_corrective_cost as number) / 1000).toFixed(0) : "—"}k`} sub="Across all corrective events" color="#f59e0b" />
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <Panel title="Corrective-to-PPM Ratio by Equipment Class" action={
          <span style={{ color: "var(--muted)", fontSize: 11 }}>&gt;20% = strategy gap  ·  &gt;10% = moderate risk</span>
        }>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={ratioData} layout="vertical" margin={{ left: 140 }}>
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={TICK} />
              <YAxis dataKey="name" type="category" width={140} tick={{ fontSize: 10, fill: "#94a3b8" }} />
              <Tooltip contentStyle={CHART_STYLE} formatter={(v: number) => [`${v}%`, "CM:PPM Ratio"]} />
              <ReferenceLine x={20} stroke="#ef4444" strokeDasharray="4 2" label={{ value: "20% threshold", fill: "#ef4444", fontSize: 9, position: "top" }} />
              <ReferenceLine x={10} stroke="#f59e0b" strokeDasharray="4 2" />
              <Bar dataKey="cm_to_ppm_ratio_pct" radius={[0, 3, 3, 0]}>
                {ratioData.map((entry, i) => (
                  <Cell key={i} fill={(entry.cm_to_ppm_ratio_pct as number) > 20 ? "#ef4444" : (entry.cm_to_ppm_ratio_pct as number) > 10 ? "#f59e0b" : "#10b981"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Corrective Trend Over Time — Top Equipment Classes">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={trendData} margin={{ left: 10, right: 10 }}>
              <XAxis dataKey="year" tick={TICK} />
              <YAxis tick={TICK} />
              <Tooltip contentStyle={CHART_STYLE} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {topClasses.map((cls, i) => (
                <Line key={cls} type="monotone" dataKey={cls} stroke={TREND_COLORS[i % TREND_COLORS.length]} strokeWidth={2} dot={{ r: 3 }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
          <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 8 }}>
            A rising trend despite a compliant PPM programme signals that the maintenance strategy is not addressing the root failure mechanisms.
          </div>
        </Panel>
      </div>

      {highRisk.length > 0 && (
        <Panel title="High-Risk Equipment Classes — Strategy Review Required">
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {highRisk.map((cls) => (
              <div key={cls.equipment_class as string} style={{
                display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap",
                background: "var(--surface2)", borderRadius: 6, padding: "12px 16px",
                borderLeft: "3px solid #ef4444",
              }}>
                <div style={{ flex: 2, minWidth: 180 }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{cls.equipment_class as string}</div>
                  <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 2 }}>
                    {cls.ppm_count as number} PPM tasks · {cls.corrective_count as number} corrective events
                  </div>
                </div>
                <div style={{ textAlign: "center", minWidth: 80 }}>
                  <div style={{ fontSize: 22, fontWeight: 800, color: "#ef4444" }}>{cls.cm_to_ppm_ratio_pct as number}%</div>
                  <div style={{ color: "var(--muted)", fontSize: 10, textTransform: "uppercase" }}>CM:PPM ratio</div>
                </div>
                <div style={{ textAlign: "right", minWidth: 100 }}>
                  <div style={{ fontWeight: 700, color: "#f59e0b" }}>£{(cls.total_cm_cost as number).toLocaleString()}</div>
                  <div style={{ color: "var(--muted)", fontSize: 11 }}>corrective cost</div>
                </div>
                <div style={{
                  background: "#ef444422", color: "#ef4444", border: "1px solid #ef444444",
                  borderRadius: 4, padding: "3px 10px", fontSize: 11, fontWeight: 700, textTransform: "uppercase",
                }}>STRATEGY REVIEW</div>
              </div>
            ))}
          </div>
        </Panel>
      )}

      <Panel title={`Repeat-Failure Assets (3+ Breakdowns) — ${repeatAssets.length} total`} action={
        repeatAssets.length > 8 ? (
          <button onClick={() => setShowAllAssets(!showAllAssets)} style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 4, padding: "4px 12px", color: "var(--muted)", fontSize: 12 }}>
            {showAllAssets ? "Show less" : `Show all ${repeatAssets.length}`}
          </button>
        ) : undefined
      }>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "var(--surface2)", borderBottom: "1px solid var(--border)" }}>
              {["Asset", "Class", "Status", "Crit.", "Breakdowns", "Failure Modes", "Total CM Cost"].map(h => (
                <th key={h} style={{ padding: "9px 12px", textAlign: "left", color: "var(--muted)", fontWeight: 600, fontSize: 11, textTransform: "uppercase", whiteSpace: "nowrap" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleAssets.map((a) => (
              <tr key={a.asset_tag as string} style={{ borderBottom: "1px solid var(--border)" }}
                onMouseEnter={e => (e.currentTarget.style.background = "var(--surface2)")}
                onMouseLeave={e => (e.currentTarget.style.background = "")}>
                <td style={{ padding: "9px 12px", fontFamily: "monospace", color: "var(--accent)", fontWeight: 600 }}>{a.asset_tag as string}</td>
                <td style={{ padding: "9px 12px", whiteSpace: "nowrap" }}>{a.equipment_class as string}</td>
                <td style={{ padding: "9px 12px", color: a.operating_status === "Duty" ? "#3b82f6" : a.operating_status === "Standby" ? "#8b5cf6" : "var(--muted)" }}>{a.operating_status as string}</td>
                <td style={{ padding: "9px 12px", fontWeight: 700, color: a.criticality === "A" ? "#ef4444" : a.criticality === "B" ? "#f59e0b" : "#10b981" }}>{a.criticality as string}</td>
                <td style={{ padding: "9px 12px", textAlign: "center", fontWeight: 700, color: (a.corrective_count as number) >= 5 ? "#ef4444" : "#f59e0b" }}>{a.corrective_count as number}</td>
                <td style={{ padding: "9px 12px", color: "var(--muted)", fontSize: 12, maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{(a.failure_modes as string[]).join(", ") || "—"}</td>
                <td style={{ padding: "9px 12px", color: "#f59e0b", fontWeight: 600, whiteSpace: "nowrap" }}>£{(a.total_corrective_cost as number).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <Recommendation>
        {highRisk.length > 0
          ? `${highRisk.length} equipment classes have a corrective-to-PPM ratio exceeding 20%, indicating the current preventive strategy is failing to intercept failures before they occur. Priority classes for strategy review: ${highRisk.slice(0, 3).map(c => c.equipment_class).join(", ")}. Recommended actions: (1) FMECA review of failure modes not currently covered by the PM schedule, (2) consider condition-based monitoring tasks for the highest corrective-cost failure modes, (3) investigate whether maintenance execution quality (tools, spares, procedures) is a contributing factor on the ${repeatAssets.length} repeat-failure assets.`
          : "No equipment classes currently exceed the 20% CM:PPM risk threshold."
        }
      </Recommendation>
    </div>
  );
}

// ─── Loader ──────────────────────────────────────────────────────────────────

const Loader = () => (
  <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "40px 0", color: "var(--muted)" }}>
    <div style={{ width: 18, height: 18, border: "2px solid var(--border)", borderTopColor: "var(--accent)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
    Analysing dataset...
    <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
  </div>
);

// ─── Root component ───────────────────────────────────────────────────────────

const HYPOTHESES = [
  {
    id: "h1-1",
    code: "H1.1",
    title: "PM intervals more conservative than required",
    description: "Tasks consistently deferred with no corrective consequence",
    component: H1_1,
  },
  {
    id: "h1-2",
    code: "H1.2",
    title: "Duplicate or overlapping PM tasks",
    description: "Same failure mode covered by multiple tasks — never rationalised",
    component: H1_2,
  },
  {
    id: "h1-3",
    code: "H1.3",
    title: "Corrective patterns reveal strategy gaps",
    description: "Repeat failures and high CM:PPM ratio signal insufficient prevention",
    component: H1_3,
  },
];

export default function HypothesisTesting() {
  const [active, setActive] = useState("h1-1");
  const current = HYPOTHESES.find(h => h.id === active)!;
  const Component = current.component;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Hypothesis navigation */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        {HYPOTHESES.map(h => (
          <button
            key={h.id}
            onClick={() => setActive(h.id)}
            style={{
              flex: 1, minWidth: 220, textAlign: "left",
              background: active === h.id ? "#1a1d27" : "var(--surface)",
              border: `1px solid ${active === h.id ? "#3b82f6" : "var(--border)"}`,
              borderRadius: "var(--radius)", padding: "14px 18px",
              color: "var(--text)", transition: "all 0.15s",
              boxShadow: active === h.id ? "0 0 0 1px #3b82f640" : "none",
            }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
              <span style={{
                background: active === h.id ? "#3b82f6" : "var(--surface2)",
                color: active === h.id ? "#fff" : "var(--muted)",
                borderRadius: 4, padding: "2px 8px", fontSize: 11, fontWeight: 800, letterSpacing: "0.04em",
              }}>{h.code}</span>
            </div>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4, color: active === h.id ? "var(--text)" : "var(--muted)" }}>{h.title}</div>
            <div style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.4 }}>{h.description}</div>
          </button>
        ))}
      </div>

      {/* Divider with active hypothesis label */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ height: 1, background: "var(--border)", flex: 1 }} />
        <span style={{ color: "var(--muted)", fontSize: 12, whiteSpace: "nowrap" }}>{current.code}: {current.title}</span>
        <div style={{ height: 1, background: "var(--border)", flex: 1 }} />
      </div>

      <Component />
    </div>
  );
}
