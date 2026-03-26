import { useState, useRef, useEffect } from "react";
import { sendChat } from "../api";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const SUGGESTIONS = [
  "Should standby pumps have the same maintenance interval as duty pumps?",
  "Which tasks have the strongest case for interval extension based on deferral history?",
  "What is the total potential saving if we optimise all identified opportunities?",
  "Which criticality A assets have deferred maintenance tasks?",
  "Compare the maintenance cost of duty vs standby centrifugal pumps",
];

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  return (
    <div style={{
      display: "flex",
      justifyContent: isUser ? "flex-end" : "flex-start",
      marginBottom: 16,
    }}>
      {!isUser && (
        <div style={{
          width: 30, height: 30, borderRadius: "50%", background: "#3b82f622",
          border: "1px solid #3b82f644", display: "flex", alignItems: "center",
          justifyContent: "center", fontSize: 14, marginRight: 10, flexShrink: 0, marginTop: 2,
        }}>
          🛢
        </div>
      )}
      <div style={{
        maxWidth: "75%",
        background: isUser ? "#3b82f6" : "var(--surface2)",
        border: `1px solid ${isUser ? "#3b82f6" : "var(--border)"}`,
        borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
        padding: "12px 16px",
        color: isUser ? "#fff" : "var(--text)",
        fontSize: 14,
        lineHeight: 1.65,
        whiteSpace: "pre-wrap",
      }}>
        {msg.content}
      </div>
    </div>
  );
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Hello! I'm your maintenance optimisation analyst for Alpha Platform.\n\nI have access to the full asset register, 6 years of work order history, and all identified optimisation opportunities. Ask me anything — from testing a hypothesis to drilling into specific equipment or cost drivers.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = async (text: string) => {
    if (!text.trim() || loading) return;
    const userMsg: Message = { role: "user", content: text };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput("");
    setLoading(true);
    try {
      const res = await sendChat(newMessages.map(m => ({ role: m.role, content: m.content })));
      setMessages(prev => [...prev, { role: "assistant", content: res.response }]);
    } catch {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: "Sorry, I couldn't connect to the analysis engine. Please check the ANTHROPIC_API_KEY is configured.",
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 160px)", minHeight: 500 }}>
      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", padding: "16px 0" }}>
        {messages.map((m, i) => <MessageBubble key={i} msg={m} />)}
        {loading && (
          <div style={{ display: "flex", gap: 8, alignItems: "center", color: "var(--muted)", fontSize: 13, padding: "8px 0" }}>
            <div style={{
              width: 30, height: 30, borderRadius: "50%", background: "#3b82f622",
              border: "1px solid #3b82f644", display: "flex", alignItems: "center",
              justifyContent: "center", fontSize: 14, flexShrink: 0,
            }}>🛢</div>
            <span>Analysing...</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions */}
      {messages.length === 1 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ color: "var(--muted)", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
            Suggested questions
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {SUGGESTIONS.map(s => (
              <button
                key={s}
                onClick={() => send(s)}
                style={{
                  background: "var(--surface2)",
                  border: "1px solid var(--border)",
                  borderRadius: 20,
                  padding: "6px 14px",
                  color: "var(--text)",
                  fontSize: 12,
                  lineHeight: 1.4,
                  textAlign: "left",
                }}>
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
          placeholder="Ask a question or test a hypothesis... (Enter to send, Shift+Enter for new line)"
          rows={2}
          style={{
            flex: 1,
            background: "var(--surface2)",
            border: "1px solid var(--border)",
            borderRadius: 10,
            padding: "12px 14px",
            color: "var(--text)",
            resize: "none",
            outline: "none",
            lineHeight: 1.5,
          }}
        />
        <button
          onClick={() => send(input)}
          disabled={!input.trim() || loading}
          style={{
            background: input.trim() && !loading ? "#3b82f6" : "var(--surface2)",
            color: input.trim() && !loading ? "#fff" : "var(--muted)",
            border: "1px solid var(--border)",
            borderRadius: 10,
            padding: "12px 20px",
            fontWeight: 600,
            fontSize: 13,
          }}>
          Send
        </button>
      </div>
    </div>
  );
}
