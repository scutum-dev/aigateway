/**
 * Tavily MCP integration. Connects to the hosted Tavily MCP server
 * (https://mcp.tavily.com/mcp/?tavilyApiKey=...) and surfaces its tool
 * catalogue as an AI-SDK ToolSet that the model can call mid-stream.
 *
 * Why MCP instead of the bare REST search: lets the model decide *when*
 * to search, do multi-hop / extract / crawl follow-ups, and skip search
 * entirely on conversational turns that don't need it. That alone makes
 * answers materially better than the single-shot pre-search the v0
 * route handler did.
 *
 * The MCP URL embeds the API key as a query param. Treat it as a secret —
 * never expose to the client, never log, never commit.
 */

import { createMCPClient, type MCPClient } from "@ai-sdk/mcp";
import type { ToolSet } from "ai";

export type TavilyMCP = {
  tools: ToolSet;
  close: () => Promise<void>;
  serverName?: string;
};

/**
 * Open a fresh MCP connection per request. Edge / serverless functions don't
 * persist between invocations, so caching the client globally would just leak
 * sockets after cold start. Connection setup is ~150ms — acceptable for a
 * search-augmented chat turn that already takes seconds.
 */
export async function openTavilyMCP(): Promise<TavilyMCP | null> {
  const url = process.env.TAVILY_MCP_URL;
  if (!url) return null;

  let client: MCPClient;
  try {
    client = await createMCPClient({
      transport: { type: "http", url },
      clientName: "scutum-chat",
      onUncaughtError: (err) => {
        console.error("[mcp] uncaught error from Tavily MCP:", err);
      },
    });
  } catch (err) {
    console.error("[mcp] failed to connect to Tavily MCP:", err);
    return null;
  }

  let tools: ToolSet;
  try {
    tools = (await client.tools()) as ToolSet;
  } catch (err) {
    console.error("[mcp] failed to list Tavily tools:", err);
    await client.close().catch(() => {});
    return null;
  }

  return {
    tools,
    close: () => client.close().catch(() => {}),
    serverName: client.serverInfo?.name,
  };
}
