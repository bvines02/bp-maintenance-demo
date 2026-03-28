import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line, Legend, ReferenceLine,
} from "recharts";
import { getH1_1, getH1_2, getH1_3, getH1_4 } from "../api";
import { usePlatforms } from "../context/PlatformContext";
import { H2_1, H2_2, H2_3, H2_4 } from "./HypothesisTestingH2";

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

function H1_1({ params }: { params: { min_deferral_days: number } }) {
  const { platformsParam } = usePlatforms();
  const { data, isLoading } = useQuery({
    queryKey: ["h1-1", platformsParam, params],
    queryFn: () => getH1_1(platformsParam, { min_deferral_days: params.min_deferral_days }),
  });
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

  const hoursByClass: Record<string, number> = {};
  overlaps.forEach(o => {
    const cls = o.equipment_class as string;
    hoursByClass[cls] = (hoursByClass[cls] || 0) + (o.hours_saving_per_visit as number) * (o.annual_combined_opportunities as number);
  });
  const savingChart = Object.entries(hoursByClass)
    .map(([name, value]) => ({ name: name.replace(" / ", "/"), value: +value.toFixed(1) }))
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
        <EvidenceCard label="Combined Visit Opportunities" value={overlaps.reduce((a, o) => a + (o.annual_combined_opportunities as number), 0).toFixed(0)} sub="Visits per year that could consolidate tasks" color="#10b981" />
      </div>

      {savingChart.length > 0 && (
        <Panel title="Estimated Hours Saved per Year by Equipment Class (Task Consolidation)">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={savingChart} layout="vertical" margin={{ left: 140 }}>
              <XAxis type="number" tickFormatter={(v) => `${v}h`} tick={TICK} />
              <YAxis dataKey="name" type="category" width={140} tick={{ fontSize: 10, fill: "#94a3b8" }} />
              <Tooltip contentStyle={CHART_STYLE} formatter={(v: number) => [`${v}h`, "Hours saved/yr"]} />
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
                    {(o.hours_saving_per_visit as number)}h saved / visit
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
                        { label: "Combined visit opportunities/year", value: `${(o.annual_combined_opportunities as number).toFixed(1)}×` },
                        { label: "Hours saved per combined visit", value: `${o.hours_saving_per_visit}h` },
                        { label: "Est. hours saved/year", value: `${Math.round((o.hours_saving_per_visit as number) * (o.annual_combined_opportunities as number))}h` },
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
          ? `${overlaps.length} overlap groups identified across the fleet. Immediate priority: ${duplicates.length} duplicate-function task pairs should be reviewed — one task in each pair may be fully redundant. Nested-interval tasks represent scheduling consolidation opportunities. Recommend a task rationalisation workshop using the component-function matrix above.`
          : "No significant task overlaps identified at current thresholds."
        }
      </Recommendation>
    </div>
  );
}

// ─── H1.3 ────────────────────────────────────────────────────────────────────

function H1_3({ params }: { params: { cm_ppm_threshold: number; min_repeat_failures: number } }) {
  const { platformsParam } = usePlatforms();
  const { data, isLoading } = useQuery({
    queryKey: ["h1-3", platformsParam, params],
    queryFn: () => getH1_3(platformsParam, { cm_ppm_threshold: params.cm_ppm_threshold, min_repeat_failures: params.min_repeat_failures }),
  });
  const [showAllAssets, setShowAllAssets] = useState(false);
  if (isLoading) return <Loader />;
  if (!data) return null;

  type RatioRow = { equipment_class: string; cm_to_ppm_ratio_pct: number; ppm_count: number; corrective_count: number; signal: string; name: string };
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
        <EvidenceCard label="Repeat-Failure Assets" value={repeatAssets.length} sub={`${params.min_repeat_failures}+ corrective events 2019–2024`} color="#ef4444" />
        <EvidenceCard label="High-Risk Equipment Classes" value={highRisk.length} sub={`CM:PPM ratio >${params.cm_ppm_threshold}% — strategy not preventing failures`} color="#ef4444" />
        <EvidenceCard label="Worst Offender" value={ratioData.length > 0 ? `${ratioData[0].cm_to_ppm_ratio_pct as number}%` : "—"} sub={ratioData.length > 0 ? `${ratioData[0].equipment_class as string} CM:PPM ratio` : ""} color="#f59e0b" />
        <EvidenceCard label="Total Corrective Events" value={(data.total_corrective_events as number | undefined) ?? repeatAssets.reduce((a, r) => a + (r.corrective_count as number), 0)} sub="Across all assets and years" color="#f59e0b" />
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <Panel title="Corrective-to-PPM Ratio by Equipment Class" action={
          <span style={{ color: "var(--muted)", fontSize: 11 }}>&gt;{params.cm_ppm_threshold}% = strategy gap  ·  &gt;{params.cm_ppm_threshold/2}% = moderate risk</span>
        }>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={ratioData} layout="vertical" margin={{ left: 140 }}>
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={TICK} />
              <YAxis dataKey="name" type="category" width={140} tick={{ fontSize: 10, fill: "#94a3b8" }} />
              <Tooltip contentStyle={CHART_STYLE} formatter={(v: number) => [`${v}%`, "CM:PPM Ratio"]} />
              <ReferenceLine x={params.cm_ppm_threshold} stroke="#ef4444" strokeDasharray="4 2" label={{ value: `${params.cm_ppm_threshold}% threshold`, fill: "#ef4444", fontSize: 9, position: "top" }} />
              <ReferenceLine x={params.cm_ppm_threshold / 2} stroke="#f59e0b" strokeDasharray="4 2" />
              <Bar dataKey="cm_to_ppm_ratio_pct" radius={[0, 3, 3, 0]}>
                {ratioData.map((entry, i) => (
                  <Cell key={i} fill={(entry.cm_to_ppm_ratio_pct as number) > params.cm_ppm_threshold ? "#ef4444" : (entry.cm_to_ppm_ratio_pct as number) > params.cm_ppm_threshold/2 ? "#f59e0b" : "#10b981"} />
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
                  <div style={{ fontWeight: 700, color: "#f59e0b" }}>{cls.corrective_count as number} events</div>
                  <div style={{ color: "var(--muted)", fontSize: 11 }}>corrective WOs</div>
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
              {["Asset", "Class", "Status", "Crit.", "Breakdowns", "Failure Modes"].map(h => (
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

// ─── Params panel ─────────────────────────────────────────────────────────────

type ParamDef = { label: string; min: number; max: number; step: number; unit?: string };

function ParamsPanel({
  params, defaults, defs, onChange,
}: {
  params: Record<string, number>;
  defaults: Record<string, number>;
  defs: Record<string, ParamDef>;
  onChange: (k: string, v: number) => void;
}) {
  const [open, setOpen] = useState(true);
  const modified = Object.entries(params).some(([k, v]) => v !== defaults[k]);
  if (Object.keys(defs).length === 0) return null;
  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius)", overflow: "hidden" }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: "100%", padding: "9px 16px", display: "flex", alignItems: "center", gap: 10,
          background: modified ? "#3b82f608" : "transparent", color: "var(--text)",
          border: "none", cursor: "pointer", textAlign: "left",
        }}>
        <span style={{ color: "var(--muted)", fontSize: 13 }}>⚙</span>
        <span style={{ fontSize: 12, fontWeight: 500, color: "var(--muted)" }}>Analysis Parameters</span>
        {modified && <span style={{ fontSize: 11, color: "#3b82f6" }}>• modified</span>}
        <span style={{ marginLeft: "auto", color: "var(--muted)", fontSize: 11 }}>{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div style={{ padding: "14px 16px", borderTop: "1px solid var(--border)", display: "flex", gap: 24, flexWrap: "wrap", alignItems: "flex-end", background: "var(--surface2)" }}>
          {Object.entries(defs).map(([key, cfg]) => (
            <div key={key} style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 180 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <label style={{ fontSize: 11, color: "var(--muted)" }}>{cfg.label}</label>
                <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text)" }}>{params[key]}{cfg.unit ?? ""}</span>
              </div>
              <input
                type="range" min={cfg.min} max={cfg.max} step={cfg.step} value={params[key]}
                onChange={e => onChange(key, Number(e.target.value))}
                style={{ accentColor: "#3b82f6" }}
              />
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--muted)" }}>
                <span>{cfg.min}{cfg.unit ?? ""}</span><span>{cfg.max}{cfg.unit ?? ""}</span>
              </div>
            </div>
          ))}
          {modified && (
            <button
              onClick={() => Object.entries(defaults).forEach(([k, v]) => onChange(k, v))}
              style={{ fontSize: 11, color: "var(--muted)", background: "transparent", border: "1px solid var(--border)", borderRadius: 4, padding: "5px 12px", cursor: "pointer", whiteSpace: "nowrap" }}>
              Reset defaults
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function H1_4() {
  const { platformsParam } = usePlatforms();
  const { data, isLoading } = useQuery({
    queryKey: ["h1-4", platformsParam],
    queryFn: () => getH1_4(platformsParam),
  });

  if (isLoading) return <div style={{ color: "var(--muted)", padding: 40, textAlign: "center" }}>Loading analysis...</div>;
  if (!data) return null;

  const verdictColor = data.verdict === "supported" ? "#10b981" : data.verdict === "partial" ? "#f59e0b" : "#64748b";
  const verdictLabel = data.verdict === "supported" ? "Supported" : data.verdict === "partial" ? "Partially Supported" : "Not Supported";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* Verdict + summary */}
      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: verdictColor, background: verdictColor + "22", border: `1px solid ${verdictColor}44`, padding: "3px 10px", borderRadius: 4 }}>
            {verdictLabel}
          </span>
          <span style={{ fontSize: 13, fontWeight: 600 }}>H1.4 — Maintenance strategies do not account for equipment redundancy</span>
        </div>
        <p style={{ fontSize: 13, color: "var(--muted)", lineHeight: 1.7, margin: 0 }}>{data.summary}</p>
      </div>

      {/* KPI cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        {[
          { label: "Duty/Standby Pairs", value: data.total_pairs, color: "#3b82f6" },
          { label: "Pairs with Higher Duty Rate", value: `${data.pct_with_higher_duty_rate}%`, color: "#f59e0b" },
          { label: "Fleet Duty:Standby Ratio", value: data.fleet_rate_ratio ? `${data.fleet_rate_ratio}×` : "N/A", color: "#8b5cf6" },
          { label: "Extension Candidates", value: data.extension_candidates.length, color: "#10b981" },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "14px 16px" }}>
            <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 6 }}>{label}</div>
            <div style={{ fontSize: 26, fontWeight: 700, color }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Failure rate comparison chart */}
      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 20 }}>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Duty vs Standby Failure Rate by Equipment Class</div>
        <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 16 }}>Failures per asset per year — confirms different operational stress profiles</div>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data.failure_rate_by_class.filter((e: any) => e.pair_count > 0)} margin={{ left: 0, right: 10 }}>
            <XAxis dataKey="equipment_class" tick={{ fontSize: 10, fill: "#64748b" }} interval={0} angle={-20} textAnchor="end" height={50} />
            <YAxis tick={{ fontSize: 11, fill: "#64748b" }} tickFormatter={(v: number) => v.toFixed(2)} />
            <Tooltip
              contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 6, fontSize: 12 }}
              formatter={(v: number, name: string) => [`${v.toFixed(3)} failures/yr`, name === "avg_duty_failure_rate" ? "Duty" : "Standby"]}
            />
            <Legend formatter={(v: string) => v === "avg_duty_failure_rate" ? "Duty" : "Standby"} />
            <Bar dataKey="avg_duty_failure_rate" name="avg_duty_failure_rate" fill="#3b82f6" radius={[3, 3, 0, 0]} />
            <Bar dataKey="avg_standby_failure_rate" name="avg_standby_failure_rate" fill="#10b981" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Extension candidates */}
      {data.extension_candidates.length > 0 && (
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 20 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Standby Interval Extension Candidates</div>
          <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 16 }}>
            Equipment classes where duty failure rate is ≥1.5× standby — standby interval extension is justified
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {data.extension_candidates.map((ec: any) => (
              <div key={ec.equipment_class} style={{ border: "1px solid var(--border)", borderRadius: 6, padding: 14 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                  <div>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{ec.equipment_class}</span>
                    <span style={{ fontSize: 11, color: "var(--muted)", marginLeft: 10 }}>{ec.pair_count} pairs</span>
                  </div>
                  <div style={{ display: "flex", gap: 16, fontSize: 12 }}>
                    <span><span style={{ color: "var(--muted)" }}>Duty: </span><span style={{ fontWeight: 600, color: "#3b82f6" }}>{ec.avg_duty_failure_rate.toFixed(3)}/yr</span></span>
                    <span><span style={{ color: "var(--muted)" }}>Standby: </span><span style={{ fontWeight: 600, color: "#10b981" }}>{ec.avg_standby_failure_rate.toFixed(3)}/yr</span></span>
                    <span style={{ fontWeight: 700, color: "#f59e0b" }}>{ec.rate_ratio}× ratio</span>
                  </div>
                </div>
                {ec.condition_tasks.length > 0 && (
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--border)" }}>
                        <th style={{ textAlign: "left", padding: "4px 8px", color: "var(--muted)", fontWeight: 500 }}>Task</th>
                        <th style={{ textAlign: "center", padding: "4px 8px", color: "var(--muted)", fontWeight: 500 }}>Current Interval</th>
                        <th style={{ textAlign: "center", padding: "4px 8px", color: "var(--muted)", fontWeight: 500 }}>Proposed Standby</th>
                        <th style={{ textAlign: "center", padding: "4px 8px", color: "var(--muted)", fontWeight: 500 }}>Change</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ec.condition_tasks.slice(0, 5).map((t: any) => (
                        <tr key={t.task_code} style={{ borderBottom: "1px solid var(--border)" }}>
                          <td style={{ padding: "6px 8px" }}>
                            <span style={{ fontFamily: "monospace", fontSize: 11, color: "#3b82f6", marginRight: 8 }}>{t.task_code}</span>
                            {t.task_description}
                          </td>
                          <td style={{ padding: "6px 8px", textAlign: "center" }}>{t.interval_days}d</td>
                          <td style={{ padding: "6px 8px", textAlign: "center", fontWeight: 600, color: "#10b981" }}>{t.proposed_standby_interval}d</td>
                          <td style={{ padding: "6px 8px", textAlign: "center", color: "#10b981", fontWeight: 600 }}>+100%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Engineering rationale */}
      <div style={{ background: "var(--surface)", border: "1px solid #1e3a5f", borderLeft: "3px solid #3b82f6", borderRadius: 6, padding: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#93c5fd", marginBottom: 8 }}>Engineering Basis for Standby Interval Extension</div>
        <div style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.8 }}>
          <strong style={{ color: "#e2e8f0" }}>Consequence differentiation:</strong> Standby failure does not cause production loss — it reduces system redundancy. The appropriate response is recovery to full redundancy within a defined timeframe, not an equivalent PM burden to duty assets.<br />
          <strong style={{ color: "#e2e8f0" }}>Stress-based justification:</strong> Standby assets experience lower cyclic stress, fewer starts/stops, and reduced thermal cycling. OREDA data consistently shows 2–4× lower failure rates on standby vs duty for rotating equipment.<br />
          <strong style={{ color: "#e2e8f0" }}>RCM precedent:</strong> RCM methodology (MSG-3, IEC 60300) explicitly allows different maintenance tasks and intervals for redundant equipment based on the hidden vs evident failure distinction and system consequence analysis.
        </div>
      </div>
    </div>
  );
}

// ─── Hypothesis registry ───────────────────────────────────────────────────────

type HypothesisEntry = {
  id: string; code: string; group: "H1" | "H2";
  title: string; description: string;
  defaults: Record<string, number>;
  paramDefs: Record<string, ParamDef>;
  render: (params: Record<string, number>) => React.ReactNode;
};

const HYPOTHESES: HypothesisEntry[] = [
  {
    id: "h1-1", code: "H1.1", group: "H1",
    title: "PM intervals more conservative than required",
    description: "Tasks consistently deferred with no corrective consequence",
    defaults: { min_deferral_days: 14 },
    paramDefs: { min_deferral_days: { label: "Min deferral to count (days)", min: 3, max: 60, step: 1, unit: "d" } },
    render: (p) => <H1_1 params={p as { min_deferral_days: number }} />,
  },
  {
    id: "h1-2", code: "H1.2", group: "H1",
    title: "Duplicate or overlapping PM tasks",
    description: "Same failure mode covered by multiple tasks — never rationalised",
    defaults: {}, paramDefs: {},
    render: () => <H1_2 />,
  },
  {
    id: "h1-3", code: "H1.3", group: "H1",
    title: "Corrective patterns reveal strategy gaps",
    description: "Repeat failures and high CM:PPM ratio signal insufficient prevention",
    defaults: { cm_ppm_threshold: 20, min_repeat_failures: 3 },
    paramDefs: {
      cm_ppm_threshold: { label: "High-risk CM:PPM threshold (%)", min: 5, max: 50, step: 5, unit: "%" },
      min_repeat_failures: { label: "Min repeat failures to flag", min: 2, max: 8, step: 1 },
    },
    render: (p) => <H1_3 params={p as { cm_ppm_threshold: number; min_repeat_failures: number }} />,
  },
  {
    id: "h1-4", code: "H1.4", group: "H1",
    title: "Strategies ignore equipment redundancy",
    description: "Identical intervals applied to duty and standby despite different stress profiles",
    defaults: {}, paramDefs: {},
    render: () => <H1_4 />,
  },
  {
    id: "h2-1", code: "H2.1", group: "H2",
    title: "OEM vs actual failure rates",
    description: "PM intervals anchored to OEM, not validated against observed MTBF",
    defaults: { over_conservative_threshold: 10, review_threshold: 5 },
    paramDefs: {
      over_conservative_threshold: { label: "Over-conservative ratio (×)", min: 4, max: 30, step: 1, unit: "×" },
      review_threshold: { label: "Review threshold (×)", min: 2, max: 15, step: 1, unit: "×" },
    },
    render: (p) => <H2_1 params={p as { over_conservative_threshold: number; review_threshold: number }} />,
  },
  {
    id: "h2-2", code: "H2.2", group: "H2",
    title: "Hard-time vs random failure",
    description: "Hard-time replacements where no age-related failure pattern exists",
    defaults: { random_cv_threshold: 0.8, wearout_cv_threshold: 0.5 },
    paramDefs: {
      random_cv_threshold: { label: "Random failure CV threshold", min: 0.5, max: 1.2, step: 0.05 },
      wearout_cv_threshold: { label: "Wear-out CV threshold", min: 0.2, max: 0.7, step: 0.05 },
    },
    render: (p) => <H2_2 params={p as { random_cv_threshold: number; wearout_cv_threshold: number }} />,
  },
  {
    id: "h2-3", code: "H2.3", group: "H2",
    title: "Criticality vs maintenance effort",
    description: "Maintenance effort not proportional to equipment criticality",
    defaults: { min_corrective_events: 3 },
    paramDefs: { min_corrective_events: { label: "Min corrective events (Crit A flag)", min: 1, max: 8, step: 1 } },
    render: (p) => <H2_3 params={p as { min_corrective_events: number }} />,
  },
  {
    id: "h2-4", code: "H2.4", group: "H2",
    title: "Statutory gold-plating",
    description: "Compliance-driven tasks exceed regulatory and statutory minimums",
    defaults: {}, paramDefs: {},
    render: () => <H2_4 />,
  },
];

// ─── Root component ────────────────────────────────────────────────────────────

export default function HypothesisTesting({ onNavigate }: { onNavigate?: (tab: string) => void }) {
  const [activeId, setActiveId] = useState("h1-1");
  const [allParams, setAllParams] = useState<Record<string, Record<string, number>>>(
    Object.fromEntries(HYPOTHESES.map(h => [h.id, { ...h.defaults }]))
  );

  const active = HYPOTHESES.find(h => h.id === activeId)!;
  const params = allParams[activeId];

  const handleParam = (key: string, value: number) => {
    setAllParams(prev => ({ ...prev, [activeId]: { ...prev[activeId], [key]: value } }));
  };

  const H1_HYPS = HYPOTHESES.filter(h => h.group === "H1");
  const H2_HYPS = HYPOTHESES.filter(h => h.group === "H2");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* Unified tab bar */}
      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", overflow: "hidden" }}>
        {/* Group rows */}
        {[{ group: "H1", label: "H1 — Interval Optimisation", hyps: H1_HYPS }, { group: "H2", label: "H2 — Strategy Effectiveness", hyps: H2_HYPS }].map(({ group, label, hyps }) => (
          <div key={group} style={{ borderBottom: group === "H1" ? "1px solid var(--border)" : "none" }}>
            <div style={{ padding: "6px 16px 4px", fontSize: 10, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.07em", background: "var(--surface2)" }}>
              {label}
            </div>
            <div style={{ display: "flex", padding: "8px 12px", gap: 6, flexWrap: "wrap" }}>
              {hyps.map(h => {
                const isActive = h.id === activeId;
                return (
                  <button
                    key={h.id}
                    onClick={() => setActiveId(h.id)}
                    title={h.description}
                    style={{
                      padding: "8px 16px", borderRadius: 6, fontSize: 12,
                      background: isActive ? "#3b82f6" : "transparent",
                      color: isActive ? "#fff" : "var(--muted)",
                      fontWeight: isActive ? 600 : 400,
                      border: isActive ? "1px solid #3b82f6" : "1px solid transparent",
                      cursor: "pointer", transition: "all 0.15s", whiteSpace: "nowrap",
                    }}>
                    <span style={{ fontFamily: "monospace", fontWeight: 700, marginRight: 6 }}>{h.code}</span>
                    <span style={{ opacity: 0.85 }}>{h.title}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Params panel */}
      <ParamsPanel
        params={params}
        defaults={active.defaults}
        defs={active.paramDefs}
        onChange={handleParam}
      />

      {/* Active hypothesis content */}
      {active.render(params)}

      {/* Link to Strategy Proposals for relevant hypotheses */}
      {["h1-1", "h1-3", "h1-4", "h2-1"].includes(activeId) && onNavigate && (
        <div style={{
          background: "var(--surface)", border: "1px solid #1e3a5f",
          borderLeft: "3px solid #3b82f6", borderRadius: 6,
          padding: "14px 20px", display: "flex", alignItems: "center",
          justifyContent: "space-between", gap: 16,
        }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#93c5fd", marginBottom: 3 }}>
              This analysis feeds into Strategy Proposals
            </div>
            <div style={{ fontSize: 12, color: "var(--muted)" }}>
              {activeId === "h1-1" && "Deferral evidence from H1.1 is used to generate interval extension candidates with 5×5 risk assessment."}
              {activeId === "h1-3" && "Equipment classes with low CM rates identified here appear as lower-risk candidates in Strategy Proposals."}
              {activeId === "h1-4" && "Standby interval extension candidates from H1.4 appear as Strategy Proposals with risk assessment and MoC readiness."}
              {activeId === "h2-1" && "Over-conservative intervals flagged in H2.1 directly map to proposals with ALARP justification."}
            </div>
          </div>
          <button
            onClick={() => onNavigate("proposals")}
            style={{
              padding: "8px 18px", borderRadius: 6, fontSize: 13, fontWeight: 600,
              background: "#3b82f6", color: "white", border: "none",
              cursor: "pointer", whiteSpace: "nowrap", flexShrink: 0,
              display: "flex", alignItems: "center", gap: 6,
            }}
          >
            View Strategy Proposals
            <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}
