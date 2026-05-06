"use client";

import type { UIMessage } from "ai";
import type { SearchResult } from "@/lib/search";

type MessageProps = {
  message: UIMessage<{ sources?: SearchResult[] }>;
};

/**
 * Renders one chat turn. The user message is plain. The assistant message
 * walks the `parts` array (text/tool/etc.), parses `[^N]` citation markers
 * inside text parts, and renders them as superscript links to the source
 * URL. A footer shows the de-duplicated source list when present.
 */
export default function Message({ message }: MessageProps) {
  const isUser = message.role === "user";
  const sources = message.metadata?.sources ?? [];

  return (
    <div className={isUser ? "" : "border-l-2 border-[var(--color-border-strong)] pl-4"}>
      <div className="text-xs uppercase tracking-wider text-[var(--color-text-subtle)] mb-2">
        {isUser ? "You" : "Scutum"}
      </div>

      <div className="prose prose-sm max-w-none">
        {message.parts.map((part, i) => {
          if (part.type === "text") {
            return (
              <TextWithCitations
                key={i}
                text={part.text}
                sources={sources}
              />
            );
          }
          // Future: render tool calls, reasoning, files. Skip silently for now.
          return null;
        })}
      </div>

      {!isUser && sources.length > 0 && <SourceList sources={sources} />}
    </div>
  );
}

/**
 * Parses `[^N]` markers and replaces them with clickable superscripts that
 * link to the matching source. We match the simplest markdown-footnote-ish
 * shape because most well-aligned models produce exactly that with the
 * system prompt we pass.
 */
function TextWithCitations({
  text,
  sources,
}: {
  text: string;
  sources: SearchResult[];
}) {
  const parts: Array<string | { n: number }> = [];
  const regex = /\[\^(\d+)\]/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push({ n: parseInt(match[1], 10) });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));

  return (
    <p className="whitespace-pre-wrap leading-relaxed">
      {parts.map((p, i) => {
        if (typeof p === "string") return <span key={i}>{p}</span>;
        const source = sources[p.n - 1];
        if (!source) {
          // Stray citation that doesn't map to any source — render as plain
          // marker so the user can see the model hallucinated it.
          return (
            <span key={i} className="citation" title="unknown source">
              [{p.n}]
            </span>
          );
        }
        return (
          <a
            key={i}
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="citation"
            title={`${source.title}\n${source.url}`}
          >
            [{p.n}]
          </a>
        );
      })}
    </p>
  );
}

function SourceList({ sources }: { sources: SearchResult[] }) {
  return (
    <details className="mt-4 text-sm">
      <summary className="cursor-pointer text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
        {sources.length} {sources.length === 1 ? "source" : "sources"}
      </summary>
      <ol className="mt-2 space-y-2 list-decimal list-inside">
        {sources.map((s, i) => (
          <li key={i} className="text-[var(--color-text-muted)]">
            <a
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-[var(--color-text)] underline-offset-2 hover:underline"
            >
              {s.title || s.url}
            </a>
            <span className="text-xs ml-2 text-[var(--color-text-subtle)]">
              {new URL(s.url).hostname}
            </span>
          </li>
        ))}
      </ol>
    </details>
  );
}
