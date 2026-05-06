/**
 * POST /api/chat — streaming chat endpoint with optional web-search RAG.
 *
 * Flow per request:
 *   1. Take the latest user message.
 *   2. Run a web search via lib/search (Tavily by default).
 *   3. Inject sources as a system-prompt prefix instructing the model to
 *      cite using `[^N]` matching the numbered list.
 *   4. Stream the completion from scutum.dev/v1/chat/completions via the
 *      Vercel AI SDK's OpenAI-compatible provider — so we get streaming +
 *      tool-call protocol + retries for free.
 *   5. Attach the source list to the response as data annotations so the UI
 *      can render the footer panel + hover cards.
 *
 * Why call scutum.dev/v1 instead of Anthropic/OpenAI directly: every chat
 * query becomes a row in your audit log, picks up your routing config, and
 * counts toward your gateway's cost reports. That is the entire moat — do
 * not bypass it from the chat-ui server.
 */

import { createOpenAICompatible } from "@ai-sdk/openai-compatible";
import { streamText, convertToModelMessages, type UIMessage } from "ai";
import { searchWeb, formatSourcesForPrompt } from "@/lib/search";

// Allow streams to run for up to 5 minutes; long research answers take
// time. Vercel hobby tier caps this at 10s and pro at 300s — match pro.
export const maxDuration = 300;

/**
 * GET /api/chat — used by AI SDK v6 useChat() to probe for an in-flight
 * stream to resume on page reload. We don't persist streams (stateless
 * MVP), so respond with a no-content 200 to signal "nothing to resume."
 * Without this handler, Next.js returns 405 Method Not Allowed and the
 * client surfaces "Something went wrong: Method Not Allowed".
 */
export async function GET() {
  return new Response(null, { status: 204 });
}

const SCUTUM_API_URL = process.env.SCUTUM_API_URL ?? "https://scutum.dev/v1";
const SCUTUM_API_KEY = process.env.SCUTUM_API_KEY ?? "";
const DEFAULT_MODEL = process.env.SCUTUM_DEFAULT_MODEL ?? "scutum-research";

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
  // The AI SDK v6 DefaultChatTransport may send {messages: UIMessage[]} or
  // {message: UIMessage, ...} depending on protocol version. Be tolerant —
  // if we can't find a messages array, log the body shape so we can adapt.
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

  // Pull the latest user message text for the search query. Multi-modal
  // (images/files) future-proofing left to a later pass — for now we just
  // glue any string parts together.
  const lastUser = [...messages].reverse().find((m) => m.role === "user");
  const queryText =
    lastUser?.parts
      ?.filter((p): p is { type: "text"; text: string } => p.type === "text")
      .map((p) => p.text)
      .join(" ")
      .trim() ?? "";

  // Run search in the background of building the request. If it fails or
  // times out we fall through to ungrounded answer rather than blocking.
  const sources = queryText ? await searchWeb(queryText) : [];
  const sourcesBlock = formatSourcesForPrompt(sources);

  // convertToModelMessages is async in AI SDK v6 — it returns a Promise that
  // must be awaited before passing to streamText. Skipping the await passes
  // a Promise object instead of an array, and streamText internally calls
  // messages.some(...) → "messages.some is not a function".
  const modelMessages = await convertToModelMessages(messages);

  const result = streamText({
    model: scutum.chatModel(DEFAULT_MODEL),
    system: sourcesBlock ? SYSTEM_GROUNDED(sourcesBlock) : SYSTEM_UNGROUNDED,
    messages: modelMessages,
    temperature: 0.3,
    onError: ({ error }) => {
      console.error("[chat] streamText error:", error);
    },
  });

  // Send sources as a custom data part on the stream so the client can
  // render a citation panel synchronized with the streaming text.
  return result.toUIMessageStreamResponse({
    messageMetadata: () => ({ sources }),
  });
}
