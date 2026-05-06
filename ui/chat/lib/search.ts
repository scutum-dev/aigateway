/**
 * Web search wrapper. Dispatches on SEARCH_PROVIDER:
 *   - "tavily" — Tavily Search API (purpose-built for AI / RAG)
 *   - "brave"  — Brave Search API (fresher news/tech, 2k free/month)
 *   - "hybrid" — both in parallel, deduped by URL, interleaved by rank
 *   - "none"   — no search; model answers without grounding
 *
 * The shape we expose to the route handler is deliberately minimal — title,
 * url, snippet — so any provider can fulfil it.
 */

export type SearchResult = {
  title: string;
  url: string;
  snippet: string;
};

const TAVILY_ENDPOINT = "https://api.tavily.com/search";
const BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search";

export async function searchWeb(
  query: string,
  options: { maxResults?: number } = {},
): Promise<SearchResult[]> {
  const provider = (process.env.SEARCH_PROVIDER ?? "tavily").toLowerCase();
  const maxResults = options.maxResults ?? 5;

  if (provider === "none") return [];
  if (provider === "tavily") return searchTavily(query, maxResults);
  if (provider === "brave") return searchBrave(query, maxResults);
  if (provider === "hybrid") {
    const [tavily, brave] = await Promise.all([
      searchTavily(query, maxResults).catch(() => []),
      searchBrave(query, maxResults).catch(() => []),
    ]);
    return mergeAndDedupe(tavily, brave, maxResults);
  }

  console.warn(`Unknown SEARCH_PROVIDER=${provider}; returning no results`);
  return [];
}

async function searchTavily(
  query: string,
  maxResults: number,
): Promise<SearchResult[]> {
  const apiKey = process.env.TAVILY_API_KEY;
  if (!apiKey) {
    console.warn("TAVILY_API_KEY unset — Tavily branch returning empty");
    return [];
  }
  const resp = await fetch(TAVILY_ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      api_key: apiKey,
      query,
      search_depth: "basic",
      max_results: maxResults,
    }),
  });
  if (!resp.ok) {
    console.warn(`Tavily search failed: ${resp.status} ${await resp.text()}`);
    return [];
  }
  const body = (await resp.json()) as {
    results?: Array<{ title?: string; url?: string; content?: string }>;
  };
  return (body.results ?? []).map((r) => ({
    title: r.title ?? r.url ?? "",
    url: r.url ?? "",
    snippet: r.content ?? "",
  }));
}

async function searchBrave(
  query: string,
  maxResults: number,
): Promise<SearchResult[]> {
  const apiKey = process.env.BRAVE_API_KEY;
  if (!apiKey) {
    console.warn("BRAVE_API_KEY unset — Brave branch returning empty");
    return [];
  }
  const url = `${BRAVE_ENDPOINT}?q=${encodeURIComponent(query)}&count=${maxResults}`;
  const resp = await fetch(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
      "Accept-Encoding": "gzip",
      "X-Subscription-Token": apiKey,
    },
  });
  if (!resp.ok) {
    console.warn(`Brave search failed: ${resp.status} ${await resp.text()}`);
    return [];
  }
  const body = (await resp.json()) as {
    web?: {
      results?: Array<{ title?: string; url?: string; description?: string }>;
    };
  };
  return (body.web?.results ?? []).map((r) => ({
    title: r.title ?? r.url ?? "",
    url: r.url ?? "",
    snippet: stripHtml(r.description ?? ""),
  }));
}

/**
 * Round-robin interleave so both providers get fair representation in the
 * top-N (rather than all-Tavily-then-all-Brave). Dedupe by normalised URL —
 * trailing-slash and tracking-fragment differences shouldn't double-count.
 */
function mergeAndDedupe(
  a: SearchResult[],
  b: SearchResult[],
  cap: number,
): SearchResult[] {
  const seen = new Set<string>();
  const out: SearchResult[] = [];
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len && out.length < cap; i++) {
    for (const r of [a[i], b[i]]) {
      if (!r) continue;
      const key = normaliseUrl(r.url);
      if (!key || seen.has(key)) continue;
      seen.add(key);
      out.push(r);
      if (out.length >= cap) break;
    }
  }
  return out;
}

function normaliseUrl(url: string): string {
  if (!url) return "";
  try {
    const u = new URL(url);
    u.hash = "";
    let s = `${u.protocol}//${u.host}${u.pathname}${u.search}`;
    if (s.endsWith("/")) s = s.slice(0, -1);
    return s.toLowerCase();
  } catch {
    return url.toLowerCase();
  }
}

/** Brave returns descriptions with `<strong>` highlights — strip for token thrift. */
function stripHtml(s: string): string {
  return s.replace(/<[^>]+>/g, "");
}

/**
 * Format search results for injection into the system prompt. Each result
 * gets a numbered marker the model is instructed to cite as [^N]. The UI
 * parses [^N] back out and links to the corresponding source URL.
 */
export function formatSourcesForPrompt(results: SearchResult[]): string {
  if (results.length === 0) return "";
  const lines = results.map(
    (r, i) =>
      `[${i + 1}] ${r.title}\n    URL: ${r.url}\n    ${r.snippet}`.trim(),
  );
  return `Sources:\n\n${lines.join("\n\n")}`;
}
