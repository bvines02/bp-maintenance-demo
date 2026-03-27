import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getAssets } from "../api";
import { usePlatforms } from "../context/PlatformContext";

const critColor = (c: string) =>
  c === "A" ? "#ef4444" : c === "B" ? "#f59e0b" : "#10b981";

const statusColor = (s: string) =>
  s === "Duty" ? "#3b82f6" : s === "Standby" ? "#8b5cf6" : "#94a3b8";

export default function AssetRegister() {
  const { platformsParam } = usePlatforms();
  const [filter, setFilter] = useState({ equipment_class: "", criticality: "", operating_status: "" });
  const [page, setPage] = useState(0);
  const pageSize = 50;

  const params: Record<string, string> = { skip: String(page * pageSize), limit: String(pageSize) };
  if (filter.equipment_class) params.equipment_class = filter.equipment_class;
  if (filter.criticality) params.criticality = filter.criticality;
  if (filter.operating_status) params.operating_status = filter.operating_status;

  const { data } = useQuery({ queryKey: ["assets", params, platformsParam], queryFn: () => getAssets(params, platformsParam) });

  const selectStyle = {
    background: "var(--surface2)",
    border: "1px solid var(--border)",
    borderRadius: 4,
    color: "var(--text)",
    padding: "6px 10px",
    fontSize: 13,
  };

  const CLASSES = ["Centrifugal Pump","Reciprocating Pump","Centrifugal Compressor","Gas Turbine Generator",
    "Electric Motor","Pressure Vessel","Heat Exchanger","Control Valve","Pressure Transmitter",
    "Flow Meter","Fire & Gas Detector","Switchgear Panel","UPS","Fan / Blower","Safety Valve"];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Filters */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <select style={selectStyle} value={filter.equipment_class}
          onChange={e => { setFilter(f => ({ ...f, equipment_class: e.target.value })); setPage(0); }}>
          <option value="">All Equipment Classes</option>
          {CLASSES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select style={selectStyle} value={filter.criticality}
          onChange={e => { setFilter(f => ({ ...f, criticality: e.target.value })); setPage(0); }}>
          <option value="">All Criticality</option>
          <option>A</option><option>B</option><option>C</option>
        </select>
        <select style={selectStyle} value={filter.operating_status}
          onChange={e => { setFilter(f => ({ ...f, operating_status: e.target.value })); setPage(0); }}>
          <option value="">All Status</option>
          <option>Duty</option><option>Standby</option><option>Solo</option>
        </select>
        <span style={{ color: "var(--muted)", fontSize: 12, marginLeft: "auto" }}>
          {data?.total ?? "–"} assets
        </span>
      </div>

      {/* Table */}
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "var(--surface2)", borderBottom: "1px solid var(--border)" }}>
              {["Tag", "Description", "Class", "System", "Location", "Criticality", "Status", "Paired With", "Discipline"].map(h => (
                <th key={h} style={{ padding: "10px 12px", textAlign: "left", color: "var(--muted)", fontWeight: 600, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", whiteSpace: "nowrap" }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data?.items?.map((a: Record<string, string>) => (
              <tr key={a.tag} style={{ borderBottom: "1px solid var(--border)" }}
                onMouseEnter={e => (e.currentTarget.style.background = "var(--surface2)")}
                onMouseLeave={e => (e.currentTarget.style.background = "")}>
                <td style={{ padding: "9px 12px", fontWeight: 600, fontFamily: "monospace", color: "var(--accent)" }}>{a.tag}</td>
                <td style={{ padding: "9px 12px", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.description}</td>
                <td style={{ padding: "9px 12px", whiteSpace: "nowrap" }}>{a.equipment_class}</td>
                <td style={{ padding: "9px 12px", color: "var(--muted)", whiteSpace: "nowrap" }}>{a.system}</td>
                <td style={{ padding: "9px 12px", color: "var(--muted)" }}>{a.location}</td>
                <td style={{ padding: "9px 12px" }}>
                  <span style={{ color: critColor(a.criticality), fontWeight: 700 }}>{a.criticality}</span>
                </td>
                <td style={{ padding: "9px 12px" }}>
                  <span style={{ color: statusColor(a.operating_status), fontWeight: 600 }}>{a.operating_status}</span>
                </td>
                <td style={{ padding: "9px 12px", fontFamily: "monospace", fontSize: 12, color: "var(--muted)" }}>{a.paired_tag || "—"}</td>
                <td style={{ padding: "9px 12px", color: "var(--muted)" }}>{a.discipline}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", justifyContent: "flex-end" }}>
        <button
          disabled={page === 0}
          onClick={() => setPage(p => p - 1)}
          style={{ padding: "6px 14px", background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 4, color: page === 0 ? "var(--border)" : "var(--text)" }}>
          ← Prev
        </button>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>Page {page + 1}</span>
        <button
          disabled={!data || (page + 1) * pageSize >= data.total}
          onClick={() => setPage(p => p + 1)}
          style={{ padding: "6px 14px", background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 4, color: (!data || (page + 1) * pageSize >= data.total) ? "var(--border)" : "var(--text)" }}>
          Next →
        </button>
      </div>
    </div>
  );
}
