import { useCountUp } from "../hooks/useCountUp";

interface KpiCardProps {
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
}

function AnimatedValue({ value, color }: { value: number; color: string }) {
  const animated = useCountUp(value);
  return (
    <div style={{ fontSize: 28, fontWeight: 700, color, lineHeight: 1 }}>
      {animated.toLocaleString()}
    </div>
  );
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
      {typeof value === "number" ? (
        <AnimatedValue value={value} color={color} />
      ) : (
        <div style={{ fontSize: 28, fontWeight: 700, color, lineHeight: 1 }}>
          {value}
        </div>
      )}
      {sub && <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 6 }}>{sub}</div>}
    </div>
  );
}
