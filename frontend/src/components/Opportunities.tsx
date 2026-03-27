import { useQuery } from "@tanstack/react-query";
import { getAllOpportunities } from "../api";
import { usePlatforms } from "../context/PlatformContext";

interface Opportunity {
  type: "duty_standby" | "deferral_pattern";
  potential_annual_saving: number;
  rationale: string;
  recommendation: string;
  criticality: string;
  equipment_class: string;
  system: string;
  // duty_standby fields
  duty_tag?: string;
  standby_tag?: string;
  shared_task_count?: number;
  duty_annual_cost?: number;
  standby_annual_cost?: number;
  // deferral fields
  asset_tag?: string;
  task_code?: string;
  task_description?: string;
  current_interval_days?: number;
  suggested_interval_days?: number;
  deferral_count?: number;
  avg_deferral_days?: number;
  max_deferral_days?: number;
  confirmed_failures_during_deferral?: number;
}

const badge = (text: string, color: string) => (
  <span style={{
    background: `${color}22`,
    color,
    border: `1px solid ${color}44`,
    borderRadius: 4,
    padding: "2px 8px",
    fontSize: 11,
    fontWeight: 600,
    textTransform: "uppercase" as const,
    letterSpacing: "0.04em",
  }}>{text}</span>
);

export default function Opportunities() {
  const { platformsParam } = usePlatforms();
  const { data, isLoading } = useQuery({
    queryKey: ["opportunities", platformsParam],
    queryFn: () => getAllOpportunities(platformsParam),
  });

  if (isLoading) return <div style={{ color: "var(--muted)", padding: 40 }}>Analysing data...</div>;
  if (!data) return null;

  const opps: Opportunity[] = data.opportunities;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Summary bar */}
      <div style={{
        background: "linear-gradient(135deg, #10b98122, #3b82f622)",
        border: "1px solid #10b98144",
        borderRadius: "var(--radius)",
        padding: "20px 24px",
        display: "flex",
        gap: 40,
        alignItems: "center",
        flexWrap: "wrap",
      }}>
        <div>
          <div style={{ color: "var(--muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em" }}>Total Opportunities</div>
          <div style={{ fontSize: 32, fontWeight: 700, color: "var(--accent2)" }}>{data.total_opportunities}</div>
        </div>
        <div>
          <div style={{ color: "var(--muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em" }}>Potential Annual Saving</div>
          <div style={{ fontSize: 32, fontWeight: 700, color: "var(--accent2)" }}>
            £{(data.total_potential_annual_saving / 1000).toFixed(0)}k
          </div>
        </div>
        <div style={{ marginLeft: "auto", color: "var(--muted)", fontSize: 13, maxWidth: 360 }}>
          Opportunities are ranked by estimated annual saving. All recommendations should be reviewed
          against the platform's risk register and ALARP framework before implementation.
        </div>
      </div>

      {/* Opportunity cards */}
      {opps.map((opp, i) => (
        <div key={i} style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          padding: 20,
        }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
                {opp.type === "duty_standby"
                  ? badge("Duty / Standby", "#3b82f6")
                  : badge("Deferral Pattern", "#f59e0b")
                }
                {badge(opp.criticality ? `Criticality ${opp.criticality}` : "", opp.criticality === "A" ? "#ef4444" : opp.criticality === "B" ? "#f59e0b" : "#10b981")}
                <span style={{ color: "var(--muted)", fontSize: 12 }}>{opp.equipment_class} · {opp.system}</span>
              </div>

              {opp.type === "duty_standby" && (
                <div style={{ marginBottom: 10 }}>
                  <span style={{ fontWeight: 600, fontSize: 15 }}>{opp.duty_tag} (Duty) ↔ {opp.standby_tag} (Standby)</span>
                  <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 4 }}>
                    {opp.shared_task_count} shared PPM tasks · Duty annual cost: £{opp.duty_annual_cost?.toLocaleString()} · Standby annual cost: £{opp.standby_annual_cost?.toLocaleString()}
                  </div>
                </div>
              )}

              {opp.type === "deferral_pattern" && (
                <div style={{ marginBottom: 10 }}>
                  <span style={{ fontWeight: 600, fontSize: 15 }}>{opp.asset_tag} — {opp.task_description} ({opp.task_code})</span>
                  <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 4 }}>
                    Deferred {opp.deferral_count}× · Avg deferral: {opp.avg_deferral_days} days · Max: {opp.max_deferral_days} days · Failures during deferral: {opp.confirmed_failures_during_deferral}
                  </div>
                  {opp.current_interval_days && (
                    <div style={{ fontSize: 12, marginTop: 4 }}>
                      <span style={{ color: "var(--muted)" }}>Current interval: </span>
                      <span style={{ color: "var(--text)" }}>{opp.current_interval_days} days</span>
                      <span style={{ color: "var(--muted)" }}> → Suggested: </span>
                      <span style={{ color: "var(--accent2)", fontWeight: 600 }}>{opp.suggested_interval_days} days</span>
                    </div>
                  )}
                </div>
              )}

              <p style={{ color: "var(--muted)", fontSize: 13, lineHeight: 1.6 }}>{opp.rationale}</p>
            </div>

            <div style={{ textAlign: "right", minWidth: 120 }}>
              <div style={{ color: "var(--muted)", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em" }}>Est. Annual Saving</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: "var(--accent2)" }}>
                £{(opp.potential_annual_saving / 1000).toFixed(0)}k
              </div>
            </div>
          </div>

          <div style={{
            background: "var(--surface2)",
            borderRadius: 4,
            padding: "10px 14px",
            fontSize: 13,
            borderLeft: "3px solid var(--accent)",
            color: "var(--text)",
          }}>
            <strong>Recommendation:</strong> {opp.recommendation}
          </div>
        </div>
      ))}
    </div>
  );
}
