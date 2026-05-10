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

const SYSTEM_TOOLS_HEADER = `\
You are Scutum Research, a helpful AI search and research assistant.

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
- Skip artifacts entirely for purely conversational turns ("hi", "thanks").
`;

/**
 * Build the system prompt for a request. We always inject the prefetched
 * sources (deterministic, stable [^N] numbering). MCP follow-up tools are
 * mentioned only when actually wired, so the model can't hallucinate
 * available tools when MCP is offline.
 */
function buildSystemPrompt(
  prefetched: SearchResult[],
  mcpAvailable: boolean,
): string {
  const sourcesBlock = formatSourcesForPrompt(prefetched);
  const grounding = sourcesBlock
    ? `WEB SOURCES (already retrieved for this question)\n\n${sourcesBlock}\n\nCite these inline with [^N] markers (1-indexed). Don't invent citations — only cite a source actually listed above. If the sources don't cover the question, say so plainly rather than guessing.\n`
    : `No web sources were retrieved for this turn. Answer from your training data, and say so if you're uncertain.\n`;

  const mcpSection = mcpAvailable
    ? `\nADDITIONAL WEB TOOLS (use sparingly — at most 1–2 follow-ups)\n- \`tavily_search\` — only if the prefetched sources are clearly insufficient. Prefer 1 focused query.\n- \`tavily_extract\` — when a snippet isn't enough; pass the URL.\nDo NOT spend the whole step budget searching. Aim to write the answer within 2–3 steps.\n`
    : "";

  return `${SYSTEM_TOOLS_HEADER}\n${grounding}${mcpSection}`;
}

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

  // Run a deterministic single-shot search up-front (Tavily / Brave / hybrid
  // via SEARCH_PROVIDER) so sources always populate fast — Claude with full
  // MCP search latitude tends to over-search and burn step budget. The model
  // gets the sources injected into the system prompt and can focus on
  // composing the answer.
  //
  // BUT skip the search entirely on conversational turns ("hi", "thanks",
  // "build me a calculator", short greetings) where web sources won't help
  // and the ~3-5s prefetch is pure latency tax. The heuristic below is
  // intentionally conservative — when in doubt, search; only short clearly-
  // conversational/imperative messages skip.
  const lastUser = [...messages].reverse().find((m) => m.role === "user");
  const queryText =
    lastUser?.parts
      ?.filter((p): p is { type: "text"; text: string } => p.type === "text")
      .map((p) => p.text)
      .join(" ")
      .trim() ?? "";
  const initialSources = queryText && needsSearch(queryText)
    ? await searchWeb(queryText)
    : [];

  // MCP is optional now — when TAVILY_MCP_URL is set, the model gets
  // tavily_extract + follow-up tavily_search on top of the prefetched
  // sources. Otherwise we ship just render_artifact + the prefetched
  // sources via the system prompt. Either way render_artifact is always
  // available so artifacts work even with no search at all.
  const mcp = await openTavilyMCP();
  return runToolsMode(modelMessages, mcp, initialSources);
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
  initialSources: SearchResult[] = [],
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
  // Prefetched sources go into the panel first so they're stable [^1..N].
  addSources(initialSources);

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
      // Synthetic server-side execute: the artifact actually renders in the
      // browser from the tool input, but AI SDK v6 requires every tool call
      // to have a matching tool-result message — without that, the next user
      // turn fails with "Tool result is missing for tool call ...". Returning
      // a tiny confirmation here closes the loop, lets the model write
      // follow-up text after rendering, and keeps multi-turn conversations
      // valid.
      execute: async ({ title }) => ({
        rendered: true,
        title,
      }),
    }),
  };

  const result = streamText({
    model: scutum.chatModel(DEFAULT_MODEL),
    system: buildSystemPrompt(initialSources, mcp != null),
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

/**
 * Cheap heuristic: should we run the ~3-5s hybrid search prefetch on this
 * turn? Conservative — when in doubt, return true. Only skip when the
 * message is clearly a greeting, a thanks/sign-off, or a "build / make /
 * compute" imperative where web sources won't help.
 *
 * Saves ~5s on every conversational turn ("hi", "thanks!") and on every
 * pure-artifact request ("build me a tip calculator") where the prefetch
 * was wasted work.
 */
function needsSearch(text: string): boolean {
  const t = text.trim().toLowerCase();
  if (!t) return false;

  // Tiny utterances are almost always greetings or sign-offs.
  if (t.length < 8) return false;

  // Greeting / sign-off / acknowledgement patterns.
  const conversationalPatterns = [
    /^(hi|hey|hello|yo|sup|good (morning|afternoon|evening))[\s!.?,]*$/,
    /^(thanks|thank you|thx|ty|cheers|nice|cool|got it|ok|okay|great|perfect)[\s!.?,]*$/,
    /^(bye|goodbye|see ya|see you|later)[\s!.?,]*$/,
    /^(yes|no|yep|nope|sure|maybe)[\s!.?,]*$/,
  ];
  if (conversationalPatterns.some((re) => re.test(t))) return false;

  // Pure-artifact imperatives: "build me X", "make me X", "show me X with
  // sliders" — Recharts + React, no web data needed. Search adds latency
  // without improving the answer.
  const imperatives = [
    /^build\b/,
    /^make\b/,
    /^create\b/,
    /^design\b/,
    /^draw\b/,
    /^generate\b/,
    /^write me\b/,
    /^give me\b/,
  ];
  if (imperatives.some((re) => re.test(t))) {
    // BUT: "build me a comparison of X vs Y" / "build me a chart of YC W26
    // batch" do need search. Check for telltale data-grounded suffixes.
    const groundedSuffix = /\b(yc|y combinator|gdp|funding|batch|2024|2025|2026|latest|news|recent|stock|price|valuation|companies|startups|launched|announced|earnings|revenue)\b/;
    if (groundedSuffix.test(t)) return true;
    return false;
  }

  // Default: search. Long-tail questions almost always benefit.
  return true;
}
