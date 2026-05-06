/**
 * POST /api/chat — streaming chat endpoint with web-search RAG.
 *
 * Two modes, picked at request time:
 *
 *   tools mode (preferred, when TAVILY_MCP_URL is set):
 *     The model gets MCP tools (`tavily_search`, `tavily_extract`, ...)
 *     and decides when to call them. Multi-hop is allowed up to N steps.
 *     Sources are extracted from tool results and attached as messageMetadata
 *     so the UI's source panel still renders.
 *
 *   prefetch mode (fallback):
 *     We run a single web search up-front via lib/search (Tavily / Brave /
 *     hybrid REST), inject the sources as a system-prompt prefix, and stream
 *     a grounded answer. No tool calls.
 *
 * Why call scutum.dev/v1 instead of Anthropic/OpenAI directly: every chat
 * query becomes a row in your audit log, picks up your routing config, and
 * counts toward your gateway's cost reports. That is the entire moat — do
 * not bypass it from the chat-ui server.
 */

import { createOpenAICompatible } from "@ai-sdk/openai-compatible";
import {
  streamText,
  convertToModelMessages,
  stepCountIs,
  tool,
  type UIMessage,
  type ToolSet,
} from "ai";
import { z } from "zod";
import { searchWeb, formatSourcesForPrompt, type SearchResult } from "@/lib/search";
import { openTavilyMCP } from "@/lib/mcp";

// Allow streams to run for up to 5 minutes; long research answers take time.
// Vercel hobby tier caps this at 10s and pro at 300s — match pro.
export const maxDuration = 300;

/**
 * GET /api/chat — used by AI SDK v6 useChat() to probe for an in-flight
 * stream to resume on page reload. We don't persist streams (stateless
 * MVP), so respond with a 204 to signal "nothing to resume." Without this
 * handler Next.js returns 405 and the client surfaces "Method Not Allowed".
 */
export async function GET() {
  return new Response(null, { status: 204 });
}

// `||` (not `??`) so empty-string env vars fall through to defaults — see
// the same note in app/layout.tsx for why this matters at build time.
const SCUTUM_API_URL = process.env.SCUTUM_API_URL || "https://scutum.dev/v1";
const SCUTUM_API_KEY = process.env.SCUTUM_API_KEY ?? "";
const DEFAULT_MODEL = process.env.SCUTUM_DEFAULT_MODEL || "scutum-research";
const MAX_TOOL_STEPS = parseInt(process.env.MAX_TOOL_STEPS || "5", 10);

const scutum = createOpenAICompatible({
  name: "scutum",
  baseURL: SCUTUM_API_URL,
  headers: { Authorization: `Bearer ${SCUTUM_API_KEY}` },
});

const SYSTEM_GROUNDED = (sourcesBlock: string) => `\
You are Scutum Research, a helpful AI search assistant. Answer the user's
question using the sources provided below. Cite sources inline using
[^N] markers that match the numbered list. Do not invent citations — only
use [^N] for sources actually listed.

If the sources don't contain enough information, say so explicitly rather
than inventing facts.

${sourcesBlock}
`;

const SYSTEM_TOOLS = `\
You are Scutum Research, a helpful AI search assistant with two kinds of tools:

WEB SEARCH (Tavily MCP)
- \`tavily_search\` — when the user asks something that benefits from
  up-to-date or external information. Prefer concise queries; you can call
  multiple times to follow up.
- \`tavily_extract\` — when a search snippet isn't enough; pass the URL.
- For conversational turns ("hi", "thanks") skip the search entirely.

INTERACTIVE ARTIFACTS (\`render_artifact\`)
- Call \`render_artifact\` to render a real, interactive React component
  inline with your answer. Use it whenever a UI beats prose: data
  visualisations (charts, comparisons over time), calculators, side-by-side
  feature tables, decision trees, mini-explorers. Don't use it for static
  prose that markdown could already render.
- The \`code\` field must be valid JSX/TSX in react-live \`noInline\` form:
  define one or more components, then call \`render(<MyComponent />)\` at
  the end. Example:
    function Demo() {
      const [n, setN] = useState(0);
      return (
        <div className="p-4">
          <p className="text-2xl font-semibold">{n}</p>
          <button className="px-3 py-1 border rounded" onClick={() => setN(n + 1)}>+1</button>
        </div>
      );
    }
    render(<Demo />);
- Available scope (already imported, do NOT import them):
  React hooks: useState, useEffect, useMemo
  Recharts: LineChart, Line, BarChart, Bar, AreaChart, Area, PieChart, Pie,
            Cell, RadarChart, Radar, ScatterChart, Scatter, XAxis, YAxis,
            ZAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
            PolarGrid, PolarAngleAxis, PolarRadiusAxis, RadialBarChart,
            RadialBar
- For charts wrap in \`<ResponsiveContainer width="100%" height={300}>\`.
- Use Tailwind utility classes for styling (className="..."). Don't import
  any libraries, don't fetch from URLs, don't access window/document directly.
- Keep components self-contained and under ~150 lines.

CITATIONS
Cite web sources inline using [^N] markers, where N matches the order in
which sources first appeared across your tool calls (1-indexed). Only cite
sources you actually retrieved.
`;

const SYSTEM_UNGROUNDED = `\
You are Scutum Research, a helpful AI assistant. Answer the user's question
clearly and concisely. If you don't know something, say so.
`;

export async function POST(req: Request) {
  if (!SCUTUM_API_KEY) {
    return new Response(
      JSON.stringify({ error: "SCUTUM_API_KEY not configured" }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }

  const body = await req.json();
  let messages: UIMessage[] = Array.isArray(body?.messages) ? body.messages : [];
  if (messages.length === 0 && body?.message) {
    messages = [body.message as UIMessage];
  }
  if (messages.length === 0) {
    console.error("[chat] no messages in request body. shape:", Object.keys(body ?? {}));
    return new Response(
      JSON.stringify({ error: "no messages provided", got: Object.keys(body ?? {}) }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  const modelMessages = await convertToModelMessages(messages);

  // Always run in tools mode — render_artifact is available unconditionally,
  // Tavily MCP search tools layer on top when TAVILY_MCP_URL is configured.
  // The system prompt adapts to whatever's wired up.
  const mcp = await openTavilyMCP();
  return runToolsMode(modelMessages, mcp);
}

/**
 * Streaming run with MCP tools. Sources are accumulated from each tool
 * result and emitted via messageMetadata so the source-panel UI works
 * exactly the same as in prefetch mode — only the *origin* of the sources
 * differs.
 */
function runToolsMode(
  modelMessages: Awaited<ReturnType<typeof convertToModelMessages>>,
  mcp: Awaited<ReturnType<typeof openTavilyMCP>>,
) {
  const sources: SearchResult[] = [];
  const seenUrls = new Set<string>();
  const addSources = (newOnes: SearchResult[]) => {
    for (const s of newOnes) {
      const key = s.url.toLowerCase();
      if (!key || seenUrls.has(key)) continue;
      seenUrls.add(key);
      sources.push(s);
    }
  };

  const tools: ToolSet = {
    ...(mcp?.tools ?? {}),
    render_artifact: tool({
      description:
        "Render a real, interactive React component inline in the chat. Use for visualisations, charts, calculators, comparisons — anything where a UI beats prose. Code must be react-live noInline form: define components then call render(<MyComponent />) at the end.",
      inputSchema: z.object({
        title: z
          .string()
          .describe("Short label shown above the artifact (e.g. 'GDP by country')."),
        code: z
          .string()
          .describe(
            "JSX/TSX source. Available scope: useState, useEffect, useMemo, and Recharts primitives (LineChart, BarChart, etc). End with render(<Component />). Don't import anything. Don't fetch.",
          ),
      }),
      // No execute — the model emits the code and we render it client-side.
      // AI SDK treats tools without execute as "client-side": the tool call
      // streams to the UI as a tool-input-available part, the UI renders it,
      // and the model continues with the input as confirmation.
    }),
  };

  const result = streamText({
    model: scutum.chatModel(DEFAULT_MODEL),
    system: SYSTEM_TOOLS,
    messages: modelMessages,
    tools,
    stopWhen: stepCountIs(MAX_TOOL_STEPS),
    temperature: 0.3,
    onStepFinish: async (step) => {
      for (const r of step.toolResults ?? []) {
        if (process.env.DEBUG_MCP === "1") {
          console.log("[chat] toolResult keys:", Object.keys(r as object));
          console.log("[chat] toolResult sample:", JSON.stringify(r).slice(0, 800));
        }
        addSources(extractSources(r));
      }
    },
    onFinish: async () => {
      if (mcp) await mcp.close();
    },
    onAbort: async () => {
      if (mcp) await mcp.close();
    },
    onError: ({ error }) => console.error("[chat] streamText error:", error),
  });

  return result.toUIMessageStreamResponse({
    messageMetadata: () => ({ sources }),
  });
}

/**
 * Pull SearchResult-shaped entries out of an MCP tool result. We don't know
 * the exact wire shape — Tavily's MCP server may return a parsed object or
 * MCP-spec content blocks (`[{type: 'text', text: 'JSON-stringified'}]`).
 * We try both and silently fall through if neither matches.
 */
function extractSources(result: unknown): SearchResult[] {
  const payload = unwrapToolPayload(result);
  if (!payload) return [];

  // Tavily search response shape: { results: [{title, url, content, ...}] }.
  const arr = (payload as { results?: unknown }).results;
  if (!Array.isArray(arr)) return [];

  return arr
    .map((r): SearchResult | null => {
      if (!r || typeof r !== "object") return null;
      const obj = r as Record<string, unknown>;
      const url = typeof obj.url === "string" ? obj.url : "";
      if (!url) return null;
      const rawSnippet =
        typeof obj.content === "string"
          ? obj.content
          : typeof obj.snippet === "string"
            ? obj.snippet
            : typeof obj.raw_content === "string"
              ? obj.raw_content
              : "";
      return {
        title: typeof obj.title === "string" ? obj.title : url,
        url,
        // tavily_extract returns full page text in raw_content — truncate
        // to a snippet-sized chunk so source-panel hover cards stay readable
        // and the model's prompt context doesn't bloat on re-cite.
        snippet: rawSnippet.slice(0, 400),
      };
    })
    .filter((s): s is SearchResult => s !== null);
}

/**
 * MCP tool results can arrive in several shapes:
 *   - already-parsed object on `.output`
 *   - array of content blocks `[{type: 'text', text: '<json>'}]`
 *   - plain string of JSON
 * Best-effort flatten to a parsed object.
 */
function unwrapToolPayload(result: unknown): unknown {
  if (!result || typeof result !== "object") return null;
  const obj = result as Record<string, unknown>;
  let candidate: unknown = obj.output ?? obj.result ?? obj;

  // MCP tool results land as `{ content: [{type: 'text', text: '<json>'}] }`
  // — peel one extra layer if we see that shape.
  if (
    candidate &&
    typeof candidate === "object" &&
    !Array.isArray(candidate) &&
    Array.isArray((candidate as Record<string, unknown>).content)
  ) {
    candidate = (candidate as Record<string, unknown>).content;
  }

  if (Array.isArray(candidate)) {
    const text = candidate
      .map((c) =>
        c && typeof c === "object" && "text" in c
          ? String((c as { text: unknown }).text ?? "")
          : "",
      )
      .join("");
    return tryParse(text) ?? candidate;
  }
  if (typeof candidate === "string") return tryParse(candidate);
  return candidate;
}

function tryParse(s: string): unknown {
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}
