"use client";

import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import type { UIMessage } from "ai";
import type { SearchResult } from "@/lib/search";

type MessageProps = {
  message: UIMessage<{ sources?: SearchResult[] }>;
};

/**
 * Renders one chat turn. Assistant messages go through a markdown renderer
 * (headings, bold, lists, code, links) plus a pre-pass that turns `[^N]`
 * citation markers into markdown links pointing at the matching source.
 *
 * We also strip the model's bottom-of-message footnote-definition lines
 * (e.g. `[1]: https://...`) because we render the source list separately
 * in a styled details element.
 */
export default function Message({ message }: MessageProps) {
  const isUser = message.role === "user";
  const sources = message.metadata?.sources ?? [];

  return (
    <div
      className={
        isUser ? "" : "border-l-2 border-[var(--color-border-strong)] pl-4"
      }
    >
      <div className="text-xs uppercase tracking-wider text-[var(--color-text-subtle)] mb-2">
        {isUser ? "You" : "Scutum"}
      </div>

      <div className="prose-sm max-w-none">
        {message.parts.map((part, i) => {
          if (part.type === "text") {
            return (
              <MarkdownWithCitations
                key={i}
                text={part.text}
                sources={sources}
                isUser={isUser}
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
 * Strip footnote-definition lines like `[1]: https://...` and `[^1]: ...`
 * that some models emit at the bottom of an answer. We render the source
 * list ourselves from the metadata, so these definitions are noise.
 */
function stripFootnoteDefinitions(text: string): string {
  return text
    .split("\n")
    .filter((line) => !/^\s*\[\^?\d+\]:\s*\S+/.test(line))
    .join("\n");
}

/**
 * Inject [^N] citation markers as markdown links to the matching source URL.
 * Both `[^1]` (markdown-footnote shape we ask for) and bare `[1]` (which
 * some models prefer) are recognized. Links render inline; we style them
 * as superscript via the link component override below.
 */
function injectCitations(text: string, sources: SearchResult[]): string {
  return text.replace(/\[\^?(\d+)\](?!\()/g, (_, n) => {
    const idx = parseInt(n, 10) - 1;
    const src = sources[idx];
    if (!src) return `[${n}]`;
    // Output as a markdown link whose visible label is `[N]`. We escape the
    // brackets so the markdown parser treats them as literal text inside
    // the link, not as another link/footnote.
    return `[\\[${n}\\]](${src.url} "${escapeForTitle(src.title || src.url)}")`;
  });
}

function escapeForTitle(s: string) {
  return s.replace(/"/g, "'");
}

const markdownComponents = (sources: SearchResult[]): Components => ({
  // Citation links: visible label is `[N]`; render as superscript.
  a({ children, href, title, ...rest }) {
    const isCitation =
      typeof children === "string"
        ? /^\[\d+\]$/.test(children.trim())
        : Array.isArray(children) &&
          children.length === 1 &&
          typeof children[0] === "string" &&
          /^\[\d+\]$/.test((children[0] as string).trim());
    if (isCitation && href) {
      return (
        <a
          href={href}
          title={title}
          target="_blank"
          rel="noopener noreferrer"
          className="citation"
          {...rest}
        >
          {children}
        </a>
      );
    }
    return (
      <a
        href={href}
        title={title}
        target="_blank"
        rel="noopener noreferrer"
        className="underline hover:no-underline"
        {...rest}
      >
        {children}
      </a>
    );
  },
  // Headings — soft shrink so they don't dominate the chat bubble.
  h1: ({ children }) => (
    <h1 className="text-xl font-semibold mt-4 mb-2">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-lg font-semibold mt-3 mb-2">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-base font-semibold mt-3 mb-1">{children}</h3>
  ),
  // Lists with a bit of room.
  ul: ({ children }) => (
    <ul className="list-disc pl-5 my-2 space-y-1">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal pl-5 my-2 space-y-1">{children}</ol>
  ),
  // Inline + block code.
  code: ({ className, children, ...rest }) => {
    const isInline = !className;
    if (isInline) {
      return (
        <code
          className="px-1 py-0.5 bg-[var(--color-bg-elevated)] border border-[var(--color-border)] rounded text-[0.85em]"
          {...rest}
        >
          {children}
        </code>
      );
    }
    return (
      <code
        className="block p-3 bg-[var(--color-bg-elevated)] border border-[var(--color-border)] rounded text-[0.85em] overflow-x-auto"
        {...rest}
      >
        {children}
      </code>
    );
  },
  pre: ({ children }) => <pre className="my-2">{children}</pre>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-[var(--color-border-strong)] pl-3 italic text-[var(--color-text-muted)] my-2">
      {children}
    </blockquote>
  ),
  p: ({ children }) => <p className="my-2 leading-relaxed">{children}</p>,
  // We strip them in stripFootnoteDefinitions but keep the override defensive.
  hr: () => <hr className="border-[var(--color-border)] my-3" />,
  // Reference sources var so the closure stays "useful" if we add more
  // logic that depends on the active source list.
  ...(sources.length === 0 ? {} : {}),
});

function MarkdownWithCitations({
  text,
  sources,
  isUser,
}: {
  text: string;
  sources: SearchResult[];
  isUser: boolean;
}) {
  // User messages: render literal text without markdown semantics. Avoids
  // accidental italics from a stray `*`, code from backticks, etc. — chat
  // input is most natural as plain text.
  if (isUser) {
    return <p className="whitespace-pre-wrap leading-relaxed">{text}</p>;
  }

  const cleaned = stripFootnoteDefinitions(text);
  const withCitations = injectCitations(cleaned, sources);

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={markdownComponents(sources)}
    >
      {withCitations}
    </ReactMarkdown>
  );
}

function SourceList({ sources }: { sources: SearchResult[] }) {
  return (
    <details className="mt-4 text-sm" open={sources.length <= 5}>
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
              {hostname(s.url)}
            </span>
          </li>
        ))}
      </ol>
    </details>
  );
}

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}
