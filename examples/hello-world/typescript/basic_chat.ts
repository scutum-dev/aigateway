/**
 * TypeScript Hello World: AI Control Plane
 *
 * Same concept as the Python examples — use the standard OpenAI SDK,
 * point it at the control plane. Works with any of 100+ models.
 *
 * Run: npx tsx basic_chat.ts
 */

import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://localhost:4000",
  apiKey: "$LITELLM_KEY",
});

async function main() {
  console.log("=== Basic Chat ===\n");

  const response = await client.chat.completions.create({
    model: "gpt-4o-mini",
    messages: [
      { role: "system", content: "You are a helpful assistant." },
      { role: "user", content: "What is an AI control plane and why do enterprises need one?" },
    ],
    max_tokens: 200,
  });

  console.log("Model:", response.model);
  console.log("Tokens:", response.usage);
  console.log("\nResponse:", response.choices[0].message.content);

  // --- Streaming ---
  console.log("\n=== Streaming ===\n");

  const stream = await client.chat.completions.create({
    model: "claude-haiku-4.5",
    messages: [{ role: "user", content: "Write a haiku about APIs." }],
    max_tokens: 50,
    stream: true,
  });

  process.stdout.write("Response: ");
  for await (const chunk of stream) {
    const content = chunk.choices[0]?.delta?.content;
    if (content) process.stdout.write(content);
  }
  console.log("\n");

  // --- Multi-model comparison ---
  console.log("=== Multi-Model Comparison ===\n");

  const models = ["gpt-4o-mini", "claude-haiku-4.5", "gemini-2.5-flash"];
  const prompt = "What is 7 * 8? Reply with just the number.";

  for (const model of models) {
    const start = Date.now();
    try {
      const r = await client.chat.completions.create({
        model,
        messages: [{ role: "user", content: prompt }],
        max_tokens: 10,
      });
      const ms = Date.now() - start;
      console.log(
        `  ${model.padEnd(25)} → ${r.choices[0].message.content?.trim()}  (${ms}ms, ${r.usage?.total_tokens} tokens)`
      );
    } catch (e: any) {
      console.log(`  ${model.padEnd(25)} → Error: ${e.message}`);
    }
  }

  console.log("\nAll requests routed through one AI Control Plane at localhost:4000");
  console.log("View costs at: http://localhost:5173");
}

main().catch(console.error);
