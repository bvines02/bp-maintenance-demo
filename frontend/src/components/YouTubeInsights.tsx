import { useState } from "react";
import { transcribeYouTube, saveInsightsToNotion } from "../api";

interface Concept {
  concept: string;
  explanation: string;
}

interface InsightsResult {
  video_id: string;
  language: string;
  transcript_excerpt: string;
  summary: string;
  key_learnings: string[];
  key_concepts: Concept[];
  action_items: string[];
  notable_quotes: string[];
}

const S = {
  card: {
    background: "#0a1628",
    border: "1px solid #0f1f35",
    borderRadius: 10,
    padding: "20px 24px",
    marginBottom: 16,
  } as React.CSSProperties,
  sectionTitle: {
    fontSize: 12,
    fontWeight: 700,
    letterSpacing: "0.08em",
    color: "#334155",
    marginBottom: 12,
    textTransform: "uppercase" as const,
  },
  bullet: {
    display: "flex",
    gap: 10,
    marginBottom: 10,
    alignItems: "flex-start",
  } as React.CSSProperties,
  dot: {
    width: 6,
    height: 6,
    borderRadius: "50%",
    background: "#3b82f6",
    flexShrink: 0,
    marginTop: 6,
  } as React.CSSProperties,
  text: {
    fontSize: 14,
    color: "#94a3b8",
    lineHeight: 1.6,
  } as React.CSSProperties,
  quote: {
    borderLeft: "3px solid #1e3a5f",
    paddingLeft: 14,
    marginBottom: 12,
    color: "#64748b",
    fontStyle: "italic",
    fontSize: 14,
    lineHeight: 1.6,
  } as React.CSSProperties,
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={S.card}>
      <div style={S.sectionTitle}>{title}</div>
      {children}
    </div>
  );
}

export default function YouTubeInsights() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<InsightsResult | null>(null);
  const [showTranscript, setShowTranscript] = useState(false);
  const [notionPageId, setNotionPageId] = useState("");
  const [notionSaving, setNotionSaving] = useState(false);
  const [notionResult, setNotionResult] = useState<{ url: string } | null>(null);
  const [notionError, setNotionError] = useState<string | null>(null);

  async function handleSaveToNotion() {
    if (!result || !notionPageId.trim()) return;
    setNotionSaving(true);
    setNotionError(null);
    setNotionResult(null);
    try {
      const data = await saveInsightsToNotion({
        page_id: notionPageId.trim(),
        video_id: result.video_id,
        video_url: url,
        summary: result.summary,
        key_learnings: result.key_learnings,
        key_concepts: result.key_concepts as { concept: string; explanation: string }[],
        action_items: result.action_items,
        notable_quotes: result.notable_quotes,
      });
      setNotionResult({ url: data.notion_url });
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Failed to save to Notion.";
      setNotionError(msg);
    } finally {
      setNotionSaving(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setShowTranscript(false);
    try {
      const data = await transcribeYouTube(url.trim());
      setResult(data);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Failed to process video. Check the URL and try again.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 860 }}>
      {/* Input */}
      <form onSubmit={handleSubmit} style={{ marginBottom: 24, display: "flex", gap: 10 }}>
        <input
          type="text"
          value={url}
          onChange={e => setUrl(e.target.value)}
          placeholder="Paste a YouTube URL (e.g. https://youtube.com/watch?v=...)"
          style={{
            flex: 1,
            background: "#0a1628",
            border: "1px solid #1e3a5f",
            borderRadius: 8,
            padding: "11px 16px",
            color: "#e2e8f0",
            fontSize: 14,
            outline: "none",
          }}
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !url.trim()}
          style={{
            background: loading || !url.trim() ? "#0f2744" : "#3b82f6",
            color: loading || !url.trim() ? "#334155" : "white",
            border: "none",
            borderRadius: 8,
            padding: "11px 22px",
            fontSize: 14,
            fontWeight: 600,
            cursor: loading || !url.trim() ? "default" : "pointer",
            whiteSpace: "nowrap",
            transition: "background 0.15s",
          }}
        >
          {loading ? "Analysing…" : "Generate Insights"}
        </button>
      </form>

      {/* Loading */}
      {loading && (
        <div style={{ ...S.card, display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{
            width: 18, height: 18, border: "2px solid #1e3a5f",
            borderTop: "2px solid #3b82f6", borderRadius: "50%",
            animation: "spin 0.8s linear infinite",
          }} />
          <span style={{ color: "#64748b", fontSize: 14 }}>
            Fetching transcript and generating insights with Claude…
          </span>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{
          ...S.card,
          border: "1px solid #7f1d1d",
          background: "#1c0a0a",
          color: "#fca5a5",
          fontSize: 14,
        }}>
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <>
          {/* Video info bar */}
          <div style={{
            ...S.card,
            display: "flex",
            alignItems: "center",
            gap: 14,
            marginBottom: 20,
            padding: "14px 20px",
          }}>
            <a
              href={`https://www.youtube.com/watch?v=${result.video_id}`}
              target="_blank"
              rel="noreferrer"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 40,
                height: 28,
                background: "#7f1d1d",
                borderRadius: 5,
                textDecoration: "none",
                flexShrink: 0,
              }}
            >
              <svg width={14} height={14} viewBox="0 0 24 24" fill="white">
                <path d="M8 5v14l11-7z" />
              </svg>
            </a>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, color: "#64748b" }}>
                Video ID: <span style={{ color: "#93c5fd", fontFamily: "monospace" }}>{result.video_id}</span>
                &nbsp;·&nbsp;Language: {result.language}
              </div>
            </div>
            <button
              onClick={() => setShowTranscript(v => !v)}
              style={{
                background: "transparent",
                border: "1px solid #1e3a5f",
                borderRadius: 6,
                color: "#475569",
                fontSize: 12,
                padding: "5px 12px",
                cursor: "pointer",
              }}
            >
              {showTranscript ? "Hide transcript" : "Show transcript excerpt"}
            </button>
          </div>

          {/* Notion export panel */}
          <div style={{ ...S.card, marginBottom: 16, padding: "14px 20px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="#94a3b8"
                strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                <path d="M4 4h16v16H4z" />
                <path d="M9 9h6M9 13h4" />
              </svg>
              <span style={{ fontSize: 13, color: "#64748b", flexShrink: 0 }}>Save to Notion</span>
              <input
                type="text"
                value={notionPageId}
                onChange={e => setNotionPageId(e.target.value)}
                placeholder="Notion page ID (from the page URL)"
                style={{
                  flex: 1,
                  minWidth: 180,
                  background: "#06101f",
                  border: "1px solid #1e3a5f",
                  borderRadius: 6,
                  padding: "7px 12px",
                  color: "#e2e8f0",
                  fontSize: 13,
                  outline: "none",
                }}
                disabled={notionSaving}
              />
              <button
                onClick={handleSaveToNotion}
                disabled={notionSaving || !notionPageId.trim()}
                style={{
                  background: notionSaving || !notionPageId.trim() ? "#0f2744" : "#1e3a5f",
                  color: notionSaving || !notionPageId.trim() ? "#334155" : "#93c5fd",
                  border: "1px solid #1e3a5f",
                  borderRadius: 6,
                  padding: "7px 16px",
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: notionSaving || !notionPageId.trim() ? "default" : "pointer",
                  whiteSpace: "nowrap",
                  flexShrink: 0,
                }}
              >
                {notionSaving ? "Saving…" : "Export"}
              </button>
            </div>
            {notionResult && (
              <div style={{ marginTop: 10, fontSize: 13, color: "#10b981" }}>
                Saved!{" "}
                {notionResult.url && (
                  <a href={notionResult.url} target="_blank" rel="noreferrer"
                    style={{ color: "#34d399", textDecoration: "underline" }}>
                    Open in Notion →
                  </a>
                )}
              </div>
            )}
            {notionError && (
              <div style={{ marginTop: 10, fontSize: 13, color: "#fca5a5" }}>{notionError}</div>
            )}
          </div>

          {showTranscript && (
            <div style={{
              ...S.card,
              background: "#06101f",
              color: "#475569",
              fontSize: 13,
              lineHeight: 1.7,
              fontFamily: "monospace",
              whiteSpace: "pre-wrap",
              maxHeight: 200,
              overflowY: "auto",
              marginBottom: 16,
            }}>
              {result.transcript_excerpt}
            </div>
          )}

          <Section title="Summary">
            <p style={{ ...S.text, margin: 0 }}>{result.summary}</p>
          </Section>

          {result.key_learnings.length > 0 && (
            <Section title="Key Learnings">
              {result.key_learnings.map((item, i) => (
                <div key={i} style={S.bullet}>
                  <div style={S.dot} />
                  <span style={S.text}>{item}</span>
                </div>
              ))}
            </Section>
          )}

          {result.key_concepts.length > 0 && (
            <Section title="Key Concepts">
              {result.key_concepts.map((c, i) => (
                <div key={i} style={{ marginBottom: 14 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#93c5fd", marginBottom: 3 }}>
                    {c.concept}
                  </div>
                  <div style={S.text}>{c.explanation}</div>
                </div>
              ))}
            </Section>
          )}

          {result.action_items.length > 0 && (
            <Section title="Action Items">
              {result.action_items.map((item, i) => (
                <div key={i} style={S.bullet}>
                  <div style={{
                    ...S.dot,
                    background: "#10b981",
                    width: 14, height: 14, marginTop: 2, flexShrink: 0,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    borderRadius: "50%",
                  }}>
                    <svg width={8} height={8} viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={3}
                      strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  </div>
                  <span style={S.text}>{item}</span>
                </div>
              ))}
            </Section>
          )}

          {result.notable_quotes.length > 0 && (
            <Section title="Notable Quotes">
              {result.notable_quotes.map((q, i) => (
                <div key={i} style={S.quote}>"{q}"</div>
              ))}
            </Section>
          )}
        </>
      )}
    </div>
  );
}
