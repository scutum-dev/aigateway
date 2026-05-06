"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, type UIMessage } from "ai";
import { useState } from "react";
import Message from "./Message";
import type { SearchResult } from "@/lib/search";

type ScutumMessageMetadata = { sources?: SearchResult[] };
type ScutumUIMessage = UIMessage<ScutumMessageMetadata>;

export default function Chat() {
  const { messages, sendMessage, status, error } = useChat<ScutumUIMessage>({
    transport: new DefaultChatTransport({ api: "/api/chat" }),
  });
  const [input, setInput] = useState("");

  const isStreaming = status === "submitted" || status === "streaming";

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
          <p className="text-[var(--color-text-muted)] max-w-md">
            Ask anything. We search the web, route to the best model for the
            task, and cite our sources.
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
          const trimmed = input.trim();
          if (!trimmed || isStreaming) return;
          sendMessage({ text: trimmed });
          setInput("");
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

      {error && (
        <p className="text-sm text-red-600 mt-2">
          Something went wrong: {error.message}
        </p>
      )}
    </div>
  );
}
