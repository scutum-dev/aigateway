/**
 * Web search wrapper. Tavily by default; designed so swapping providers later
 * is one function not a refactor. The shape we expose to the route handler is
 * deliberately minimal — title, url, snippet — so any provider can fulfil it.
 */

export type SearchResult = {
  title: string;
  url: string;
  snippet: string;
};

const TAVILY_ENDPOINT = "https://api.tavily.com/search";

export async function searchWeb(
  query: string,
  options: { maxResults?: number } = {},
): Promise<SearchResult[]> {
  const provider = process.env.SEARCH_PROVIDER ?? "tavily";
  const maxResults = options.maxResults ?? 5;

  if (provider === "none") return [];

  if (provider === "tavily") {
    const apiKey = process.env.TAVILY_API_KEY;
    if (!apiKey) {
      console.warn("TAVILY_API_KEY unset — returning empty search results");
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
        // include_raw_content: false — snippet only, keeps tokens down
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

  // Add brave / exa branches here as needed. Empty fallback keeps the chat
  // working even when search is misconfigured — model just answers without
  // grounding.
  return [];
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
