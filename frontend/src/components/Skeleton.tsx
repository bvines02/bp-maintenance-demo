export function Skeleton({ width = "100%", height = 16, borderRadius = 4 }: {
  width?: string | number;
  height?: number;
  borderRadius?: number;
}) {
  return (
    <div style={{
      width,
      height,
      borderRadius,
      background: "#1e293b",
      backgroundImage: "linear-gradient(90deg, #1e293b 0px, #273549 40px, #1e293b 80px)",
      backgroundSize: "400px 100%",
      animation: "skeleton-shimmer 1.4s ease-in-out infinite",
    }} />
  );
}

export function SkeletonCard({ lines = 3, height = 120 }: { lines?: number; height?: number }) {
  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--border)",
      borderRadius: 8, padding: 20, flex: 1,
      display: "flex", flexDirection: "column", gap: 10, minHeight: height,
    }}>
      <Skeleton height={18} width="55%" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} height={12} width={`${85 - i * 12}%`} />
      ))}
    </div>
  );
}
