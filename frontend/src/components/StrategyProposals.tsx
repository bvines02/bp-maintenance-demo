import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getStrategyProposals } from "../api";
import { usePlatforms } from "../context/PlatformContext";

// ── Types ─────────────────────────────────────────────────────────────────────

interface RiskDetail {
  current_likelihood: number;
  current_likelihood_label: string;
  current_consequence: number;
  current_consequence_label: string;
  current_score: number;
  current_band: string;
  proposed_likelihood: number;
  proposed_likelihood_label: string;
  proposed_consequence: number;
  proposed_consequence_label: string;
  proposed_score: number;
  proposed_band: string;
  risk_delta: number;
  band_delta: number;
  alarp_status: string;
  alarp_description: string;
  compensating_measures: string[];
}

interface Proposal {
  id: string;
  equipment_class: string;
  task_code: string;
  task_description: string;
  discipline: string;
  current_interval_days: number;
  proposed_interval_days: number;
  affected_assets: number;
  dominant_criticality: string;
  deferral_evidence: { occurrences: number; avg_deferral_days: number; max_deferral_days: number };
  failure_data: { total_failures: number; assets_in_class: number; failure_rate_per_year: number };
  risk: RiskDetail;
  moc_readiness: "ready" | "review" | "insufficient";
  moc_label: string;
  total_hours_saved_per_year: number;
  evidence_hypotheses: string[];
}

interface ProposalsData {
  total_proposals: number;
  total_hours_saved_per_year: number;
  ready_for_moc: number;
  require_review: number;
  proposals: Proposal[];
}

// ── Constants ─────────────────────────────────────────────────────────────────

const BAND_COLOR: Record<string, string> = {
  Low: "#10b981",
  Medium: "#f59e0b",
  High: "#f97316",
  Extreme: "#ef4444",
};


const MOC_COLOR: Record<string, string> = {
  ready: "#10b981",
  review: "#f59e0b",
  insufficient: "#64748b",
};

// ── Risk Matrix ────────────────────────────────────────────────────────────────

function cellColor(l: number, c: number): string {
  const score = l * c;
  if (score <= 4) return "#10b98133";
  if (score <= 9) return "#f59e0b33";
  if (score <= 16) return "#f9731633";
  return "#ef444433";
}

function cellBorder(l: number, c: number): string {
  const score = l * c;
  if (score <= 4) return "#10b98155";
  if (score <= 9) return "#f59e0b55";
  if (score <= 16) return "#f9731655";
  return "#ef444455";
}

function RiskMatrix({ current, proposed }: { current: { l: number; c: number }; proposed: { l: number; c: number } }) {
  const LIKELIHOOD_LABELS = ["", "Rare", "Unlikely", "Possible", "Likely", "Almost\nCertain"];
  const CONSEQUENCE_LABELS = ["", "Negligible", "Minor", "Moderate", "Major", "Catastrophic"];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
        {/* Y-axis label */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "center",
          writingMode: "vertical-rl", transform: "rotate(180deg)",
          fontSize: 10, color: "var(--muted)", letterSpacing: 1, textTransform: "uppercase",
          height: 5 * 44, marginTop: 20,
        }}>
          Likelihood
        </div>

        <div>
          {/* Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "60px repeat(5, 44px)", gap: 2 }}>
            {/* Header row */}
            <div />
            {[1, 2, 3, 4, 5].map(c => (
              <div key={c} style={{
                textAlign: "center", fontSize: 9, color: "var(--muted)",
                padding: "2px 0", lineHeight: 1.2,
              }}>
                {CONSEQUENCE_LABELS[c]}
              </div>
            ))}

            {/* Data rows: likelihood 5 down to 1 */}
            {[5, 4, 3, 2, 1].map(l => (
              <>
                <div key={`label-${l}`} style={{
                  textAlign: "right", paddingRight: 6, fontSize: 9,
                  color: "var(--muted)", lineHeight: 1.2,
                  display: "flex", alignItems: "center", justifyContent: "flex-end",
                }}>
                  {LIKELIHOOD_LABELS[l]}
                </div>
                {[1, 2, 3, 4, 5].map(c => {
                  const isCurrent = current.l === l && current.c === c;
                  const isProposed = proposed.l === l && proposed.c === c;
                  const isSame = isCurrent && isProposed;
                  return (
                    <div key={`${l}-${c}`} style={{
                      width: 44, height: 44,
                      background: cellColor(l, c),
                      border: `1px solid ${cellBorder(l, c)}`,
                      borderRadius: 4,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      position: "relative",
                      gap: 4,
                    }}>
                      <div style={{
                        fontSize: 9, color: "#94a3b8", position: "absolute", top: 2, right: 3,
                      }}>{l * c}</div>

                      {isSame ? (
                        <div style={{
                          width: 14, height: 14, borderRadius: "50%",
                          background: BAND_COLOR[current.l * current.c <= 4 ? "Low" : current.l * current.c <= 9 ? "Medium" : current.l * current.c <= 16 ? "High" : "Extreme"],
                          border: "2px solid white",
                          boxShadow: "0 0 6px rgba(0,0,0,0.5)",
                        }} title="Current & Proposed" />
                      ) : (
                        <>
                          {isCurrent && (
                            <div style={{
                              width: 13, height: 13, borderRadius: "50%",
                              background: BAND_COLOR[current.l * current.c <= 4 ? "Low" : current.l * current.c <= 9 ? "Medium" : current.l * current.c <= 16 ? "High" : "Extreme"],
                              border: "2px solid white",
                              boxShadow: "0 0 6px rgba(0,0,0,0.4)",
                            }} title="Current position" />
                          )}
                          {isProposed && (
                            <div style={{
                              width: 13, height: 13, borderRadius: "50%",
                              background: "transparent",
                              border: `2px solid ${BAND_COLOR[proposed.l * proposed.c <= 4 ? "Low" : proposed.l * proposed.c <= 9 ? "Medium" : proposed.l * proposed.c <= 16 ? "High" : "Extreme"]}`,
                              boxShadow: "0 0 6px rgba(0,0,0,0.4)",
                            }} title="Proposed position" />
                          )}
                        </>
                      )}
                    </div>
                  );
                })}
              </>
            ))}
          </div>

          {/* X-axis label */}
          <div style={{
            textAlign: "center", fontSize: 10, color: "var(--muted)",
            letterSpacing: 1, textTransform: "uppercase", marginTop: 6, marginLeft: 62,
          }}>
            Consequence
          </div>
        </div>
      </div>

      {/* Legend */}
      <div style={{ display: "flex", gap: 16, marginTop: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--muted)" }}>
          <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#94a3b8", border: "2px solid white" }} />
          Current position
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--muted)" }}>
          <div style={{ width: 10, height: 10, borderRadius: "50%", background: "transparent", border: "2px solid #94a3b8" }} />
          Proposed position
        </div>
        {[["Low", "#10b981"], ["Medium", "#f59e0b"], ["High", "#f97316"], ["Extreme", "#ef4444"]].map(([band, color]) => (
          <div key={band} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--muted)" }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: color + "44", border: `1px solid ${color}66` }} />
            {band}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── MoC Badge ─────────────────────────────────────────────────────────────────

function MocBadge({ readiness, label }: { readiness: string; label: string }) {
  const color = MOC_COLOR[readiness] || "#64748b";
  return (
    <span style={{
      padding: "3px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600,
      background: color + "22", color, border: `1px solid ${color}44`,
    }}>
      {label}
    </span>
  );
}

// ── Proposal Card ─────────────────────────────────────────────────────────────

function ProposalCard({ proposal, selected, onClick }: { proposal: Proposal; selected: boolean; onClick: () => void }) {
  const r = proposal.risk;
  const intervalChange = Math.round(((proposal.proposed_interval_days - proposal.current_interval_days) / proposal.current_interval_days) * 100);

  return (
    <div
      onClick={onClick}
      style={{
        padding: "12px 14px",
        background: selected ? "#1e293b" : "var(--surface)",
        border: `1px solid ${selected ? "#3b82f6" : "var(--border)"}`,
        borderRadius: 6,
        cursor: "pointer",
        transition: "all 0.15s",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, marginBottom: 6 }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>{proposal.equipment_class}</div>
          <div style={{ fontSize: 11, color: "var(--muted)" }}>{proposal.task_description}</div>
        </div>
        <MocBadge readiness={proposal.moc_readiness} label={proposal.moc_label} />
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 8 }}>
        <div style={{ fontSize: 11 }}>
          <span style={{ color: "var(--muted)" }}>Interval: </span>
          <span style={{ fontWeight: 600 }}>{proposal.current_interval_days}d</span>
          <span style={{ color: "var(--muted)" }}> → </span>
          <span style={{ fontWeight: 600, color: "#10b981" }}>{proposal.proposed_interval_days}d</span>
          <span style={{ color: "#10b981", fontSize: 10, marginLeft: 4 }}>+{intervalChange}%</span>
        </div>
        <div style={{ fontSize: 11 }}>
          <span style={{ color: "var(--muted)" }}>Risk: </span>
          <span style={{ fontWeight: 600, color: BAND_COLOR[r.current_band] }}>{r.current_band}</span>
          {r.band_delta !== 0 && (
            <>
              <span style={{ color: "var(--muted)" }}> → </span>
              <span style={{ fontWeight: 600, color: BAND_COLOR[r.proposed_band] }}>{r.proposed_band}</span>
            </>
          )}
        </div>
        <div style={{ fontSize: 11 }}>
          <span style={{ color: "var(--muted)" }}>Assets: </span>
          <span style={{ fontWeight: 600 }}>{proposal.affected_assets}</span>
        </div>
        <div style={{ fontSize: 11 }}>
          <span style={{ color: "var(--muted)" }}>Hours saved/yr: </span>
          <span style={{ fontWeight: 600, color: "#3b82f6" }}>{proposal.total_hours_saved_per_year}</span>
        </div>
      </div>
    </div>
  );
}

// ── Detail Panel ──────────────────────────────────────────────────────────────

function DetailPanel({ proposal }: { proposal: Proposal }) {
  const r = proposal.risk;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Title */}
      <div>
        <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>{proposal.equipment_class}</div>
        <div style={{ color: "var(--muted)", fontSize: 13 }}>{proposal.task_description}</div>
        <div style={{ color: "var(--muted)", fontSize: 11, marginTop: 4 }}>
          {proposal.task_code} · {proposal.discipline} · Crit {proposal.dominant_criticality} · {proposal.affected_assets} assets affected
        </div>
      </div>

      {/* Interval change */}
      <div style={{
        background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 16,
        display: "flex", gap: 32, alignItems: "center",
      }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>Current Interval</div>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{proposal.current_interval_days}</div>
          <div style={{ fontSize: 11, color: "var(--muted)" }}>days</div>
        </div>
        <div style={{ fontSize: 20, color: "#10b981" }}>→</div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>Proposed Interval</div>
          <div style={{ fontSize: 28, fontWeight: 700, color: "#10b981" }}>{proposal.proposed_interval_days}</div>
          <div style={{ fontSize: 11, color: "var(--muted)" }}>days</div>
        </div>
        <div style={{ marginLeft: "auto", textAlign: "right" }}>
          <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>Hours Saved / Year</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: "#3b82f6" }}>{proposal.total_hours_saved_per_year}</div>
          <div style={{ fontSize: 11, color: "var(--muted)" }}>across {proposal.affected_assets} assets</div>
        </div>
      </div>

      {/* Risk Matrix */}
      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 14 }}>Risk Assessment (5×5)</div>
        <RiskMatrix
          current={{ l: r.current_likelihood, c: r.current_consequence }}
          proposed={{ l: r.proposed_likelihood, c: r.proposed_consequence }}
        />
      </div>

      {/* Risk detail table */}
      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Risk Change Summary</div>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              <th style={{ textAlign: "left", padding: "4px 8px", color: "var(--muted)", fontWeight: 500 }}></th>
              <th style={{ textAlign: "center", padding: "4px 8px", color: "var(--muted)", fontWeight: 500 }}>Current</th>
              <th style={{ textAlign: "center", padding: "4px 8px", color: "var(--muted)", fontWeight: 500 }}>Proposed</th>
            </tr>
          </thead>
          <tbody>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              <td style={{ padding: "6px 8px", color: "var(--muted)" }}>Likelihood</td>
              <td style={{ padding: "6px 8px", textAlign: "center", fontWeight: 600 }}>
                {r.current_likelihood} — {r.current_likelihood_label}
              </td>
              <td style={{ padding: "6px 8px", textAlign: "center", fontWeight: 600 }}>
                {r.proposed_likelihood} — {r.proposed_likelihood_label}
              </td>
            </tr>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              <td style={{ padding: "6px 8px", color: "var(--muted)" }}>Consequence</td>
              <td style={{ padding: "6px 8px", textAlign: "center", fontWeight: 600 }}>
                {r.current_consequence} — {r.current_consequence_label}
              </td>
              <td style={{ padding: "6px 8px", textAlign: "center", fontWeight: 600 }}>
                {r.proposed_consequence} — {r.proposed_consequence_label}
              </td>
            </tr>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              <td style={{ padding: "6px 8px", color: "var(--muted)" }}>Risk Score</td>
              <td style={{ padding: "6px 8px", textAlign: "center" }}>
                <span style={{ fontWeight: 700, color: BAND_COLOR[r.current_band] }}>
                  {r.current_score} ({r.current_band})
                </span>
              </td>
              <td style={{ padding: "6px 8px", textAlign: "center" }}>
                <span style={{ fontWeight: 700, color: BAND_COLOR[r.proposed_band] }}>
                  {r.proposed_score} ({r.proposed_band})
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* ALARP */}
      <div style={{
        background: "var(--surface)", border: `1px solid ${BAND_COLOR[r.proposed_band]}44`,
        borderRadius: 8, padding: 16,
        borderLeft: `3px solid ${BAND_COLOR[r.proposed_band]}`,
      }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: BAND_COLOR[r.proposed_band], marginBottom: 6 }}>
          {r.alarp_status}
        </div>
        <div style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.6 }}>
          {r.alarp_description}
        </div>
        {r.compensating_measures.length > 0 && r.band_delta > 0 && (
          <div style={{ marginTop: 10 }}>
            <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 6 }}>Compensating Measures:</div>
            {r.compensating_measures.map((m, i) => (
              <div key={i} style={{ fontSize: 11, color: "var(--muted)", padding: "2px 0", paddingLeft: 12 }}>
                · {m}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Evidence */}
      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Supporting Evidence</div>
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginBottom: 12 }}>
          <div>
            <div style={{ fontSize: 11, color: "var(--muted)" }}>Deferral occurrences</div>
            <div style={{ fontSize: 20, fontWeight: 700 }}>{proposal.deferral_evidence.occurrences}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--muted)" }}>Avg deferral</div>
            <div style={{ fontSize: 20, fontWeight: 700 }}>{proposal.deferral_evidence.avg_deferral_days}d</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--muted)" }}>Max deferral</div>
            <div style={{ fontSize: 20, fontWeight: 700 }}>{proposal.deferral_evidence.max_deferral_days}d</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--muted)" }}>Failure rate</div>
            <div style={{ fontSize: 20, fontWeight: 700 }}>{proposal.failure_data.failure_rate_per_year.toFixed(2)}/yr</div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {proposal.evidence_hypotheses.map(h => (
            <span key={h} style={{
              padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600,
              background: "#3b82f622", color: "#3b82f6", border: "1px solid #3b82f644",
            }}>{h}</span>
          ))}
        </div>
      </div>

      {/* MoC readiness */}
      <div style={{
        background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 16,
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>MoC Readiness</div>
          <div style={{ fontSize: 12, color: "var(--muted)" }}>
            {proposal.moc_readiness === "ready"
              ? "Sufficient evidence and acceptable risk delta. Ready for formal MoC submission."
              : proposal.moc_readiness === "review"
              ? "Evidence supports the change but engineering sign-off required before MoC submission."
              : "Insufficient evidence volume or elevated risk. Additional data collection recommended."}
          </div>
        </div>
        <MocBadge readiness={proposal.moc_readiness} label={proposal.moc_label} />
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function StrategyProposals() {
  const { platformsParam: selectedString } = usePlatforms();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "ready" | "review" | "insufficient">("all");

  const { data, isLoading } = useQuery<ProposalsData>({
    queryKey: ["strategy-proposals", selectedString],
    queryFn: () => getStrategyProposals(selectedString),
  });

  if (isLoading) {
    return <div style={{ color: "var(--muted)", padding: 40, textAlign: "center" }}>Loading proposals...</div>;
  }

  if (!data || data.proposals.length === 0) {
    return <div style={{ color: "var(--muted)", padding: 40, textAlign: "center" }}>No proposals generated.</div>;
  }

  const filtered = filter === "all" ? data.proposals : data.proposals.filter(p => p.moc_readiness === filter);
  const selected = data.proposals.find(p => p.id === selectedId) ?? data.proposals[0];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* KPI cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        {[
          { label: "Total Proposals", value: data.total_proposals, color: "#3b82f6" },
          { label: "Ready for MoC", value: data.ready_for_moc, color: "#10b981" },
          { label: "Require Review", value: data.require_review, color: "#f59e0b" },
          { label: "Total Hours Saved / Year", value: data.total_hours_saved_per_year, color: "#8b5cf6" },
        ].map(({ label, value, color }) => (
          <div key={label} style={{
            background: "var(--surface)", border: "1px solid var(--border)",
            borderRadius: 8, padding: "14px 16px",
          }}>
            <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 6 }}>{label}</div>
            <div style={{ fontSize: 26, fontWeight: 700, color }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Filter tabs */}
      <div style={{ display: "flex", gap: 4 }}>
        {(["all", "ready", "review", "insufficient"] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{
              padding: "5px 14px", borderRadius: 6, fontSize: 12,
              background: filter === f ? "#3b82f622" : "transparent",
              color: filter === f ? "#3b82f6" : "var(--muted)",
              border: filter === f ? "1px solid #3b82f644" : "1px solid transparent",
              cursor: "pointer",
              fontWeight: filter === f ? 600 : 400,
            }}
          >
            {f === "all" ? "All proposals" : f === "ready" ? "Ready for MoC" : f === "review" ? "Requires review" : "Insufficient evidence"}
            {f !== "all" && (
              <span style={{ marginLeft: 6, fontSize: 10, opacity: 0.8 }}>
                ({data.proposals.filter(p => p.moc_readiness === f).length})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Two-panel layout */}
      <div style={{ display: "grid", gridTemplateColumns: "380px 1fr", gap: 16, alignItems: "start" }}>
        {/* Left: Proposal list */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: "80vh", overflowY: "auto" }}>
          {filtered.map(p => (
            <ProposalCard
              key={p.id}
              proposal={p}
              selected={p.id === (selected?.id)}
              onClick={() => setSelectedId(p.id)}
            />
          ))}
          {filtered.length === 0 && (
            <div style={{ color: "var(--muted)", textAlign: "center", padding: 24, fontSize: 13 }}>
              No proposals in this category.
            </div>
          )}
        </div>

        {/* Right: Detail */}
        <div style={{ background: "var(--surface-raised, #0f172a)", border: "1px solid var(--border)", borderRadius: 8, padding: 20, overflowY: "auto", maxHeight: "80vh" }}>
          {selected ? (
            <DetailPanel proposal={selected} />
          ) : (
            <div style={{ color: "var(--muted)", textAlign: "center", padding: 40 }}>
              Select a proposal to view details
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
