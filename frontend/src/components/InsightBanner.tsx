export default function InsightBanner({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      background: "#0f2744",
      border: "1px solid #1e3a5f",
      borderLeft: "3px solid #3b82f6",
      borderRadius: 6,
      padding: "11px 16px",
      marginBottom: 20,
      display: "flex",
      gap: 10,
      alignItems: "flex-start",
    }}>
      <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="#3b82f6"
        strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"
        style={{ flexShrink: 0, marginTop: 2 }}>
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="16" x2="12" y2="12" />
        <line x1="12" y1="8" x2="12.01" y2="8" />
      </svg>
      <div style={{ fontSize: 13, color: "#93c5fd", lineHeight: 1.6 }}>{children}</div>
    </div>
  );
}
