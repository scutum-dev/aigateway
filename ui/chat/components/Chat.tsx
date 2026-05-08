"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, type UIMessage } from "ai";
import { useState } from "react";
import Message from "./Message";
import type { SearchResult } from "@/lib/search";

type ScutumMessageMetadata = { sources?: SearchResult[] };
type ScutumUIMessage = UIMessage<ScutumMessageMetadata>;

// Lead with the most visceral example so first-time visitors form a strong
// mental model from a single click. The retirement calculator demonstrates
// adjustable inputs + recomputed chart — the "wow this isn't text" moment
// that screenshots and conversational queries don't capture.
// Order matters: most users only read the first 2-3 examples.
const EXAMPLE_QUERIES = [
  "Build me a retirement calculator with adjustable returns",
  "Compare Postgres vs MongoDB for a 50-person team",
  "Show me sprint velocity over the last 6 sprints",
];

export default function Chat() {
  const { messages, sendMessage, status, error } = useChat<ScutumUIMessage>({
    transport: new DefaultChatTransport({ api: "/api/chat" }),
  });
  const [input, setInput] = useState("");

  const isStreaming = status === "submitted" || status === "streaming";

  // Single send path — both form submit + example-chip click route through
  // here so the same disabled/streaming guards apply.
  const send = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) return;
    sendMessage({ text: trimmed });
    setInput("");
  };

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Empty state — visible when no messages yet */}
      {messages.length === 0 && (
        <div className="flex-1 flex flex-col items-center justify-center text-center px-4">
          <h1
            className="text-5xl mb-4"
            style={{ fontFamily: "var(--font-serif)", fontStyle: "italic" }}
          >
            What do you want to know?
          </h1>
          <p className="text-[var(--color-text-muted)] max-w-xl leading-relaxed">
            Ask anything. We return interactive answers — calculators, charts,
            comparison tables — not walls of text. Sources cited inline.
          </p>
        </div>
      )}

      {/* Conversation */}
      {messages.length > 0 && (
        <div className="flex-1 overflow-y-auto space-y-6 pb-6">
          {messages.map((m) => (
            <Message key={m.id} message={m} />
          ))}
          {isStreaming &&
            messages[messages.length - 1]?.role === "user" && (
              <div className="text-sm text-[var(--color-text-subtle)] italic">
                Searching, routing, thinking…
              </div>
            )}
        </div>
      )}

      {/* Input */}
      <form
        className="flex gap-2 border-t border-[var(--color-border)] pt-4 mt-auto"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            messages.length === 0
              ? "Ask anything…"
              : "Ask a follow-up…"
          }
          disabled={isStreaming}
          className="flex-1 px-4 py-3 border border-[var(--color-border)] rounded-md focus:outline-none focus:border-[var(--color-text)] disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={isStreaming || !input.trim()}
          className="px-5 py-3 bg-[var(--color-accent)] text-white rounded-md font-medium hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {isStreaming ? "…" : "Ask"}
        </button>
      </form>

      {/*
        Example chips — shown only on the empty state. Each one pre-fills
        and submits in a single click. Perplexity / Claude / ChatGPT all
        do this on their landing surfaces; meaningfully lifts activation
        because curious-but-not-typing visitors get to see the magic with
        zero typing friction. Disabled while streaming so a click during
        an in-flight request doesn't double-fire.
      */}
      {messages.length === 0 && (
        <div className="mt-4">
          <p className="text-xs uppercase tracking-wider text-[var(--color-text-subtle)] mb-2">
            Try one
          </p>
          <div className="flex flex-col sm:flex-row sm:flex-wrap gap-2">
            {EXAMPLE_QUERIES.map((q) => (
              <button
                key={q}
                type="button"
                disabled={isStreaming}
                onClick={() => send(q)}
                className="text-left text-sm px-3 py-2 rounded-md border border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-accent)] hover:text-[var(--color-text)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {q} <span className="text-[var(--color-accent)]">→</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {error && (
        <p className="text-sm text-red-600 mt-2">
          Something went wrong: {error.message}
        </p>
      )}
    </div>
  );
}
