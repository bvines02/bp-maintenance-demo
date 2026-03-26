interface KpiCardProps {
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
}

export default function KpiCard({ label, value, sub, color = "var(--accent)" }: KpiCardProps) {
  return (
    <div style={{
      background: "var(--surface)",
      border: "1px solid var(--border)",
      borderRadius: "var(--radius)",
      padding: "20px 24px",
      flex: 1,
      minWidth: 180,
    }}>
      <div style={{ color: "var(--muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color, lineHeight: 1 }}>
        {typeof value === "number" ? value.toLocaleString() : value}
      </div>
      {sub && <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 6 }}>{sub}</div>}
    </div>
  );
}
