/**
 * TypeScript: Enterprise Admin Setup
 *
 * Shows how a platform admin automates organization provisioning
 * using the Admin API. This is the TypeScript equivalent of
 * python/04_enterprise_setup.py.
 *
 * Run: npx tsx admin_setup.ts
 */

const ADMIN_API = "http://localhost:8086";
const LITELLM = "http://localhost:4000";
const MASTER_KEY = process.env.LITELLM_KEY || process.env.LITELLM_MASTER_KEY || "";

async function main() {
  // --- Authenticate ---
  console.log("Step 0: Authenticate\n");

  const loginResp = await fetch(`${ADMIN_API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: MASTER_KEY }),
  });
  const { access_token: token } = (await loginResp.json()) as any;
  console.log(`  Token: ${token.slice(0, 20)}...`);

  const adminHeaders = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
  const litellmHeaders = {
    Authorization: `Bearer ${MASTER_KEY}`,
    "Content-Type": "application/json",
  };

  // --- Create Organization ---
  console.log("\nStep 1: Create Organization\n");

  const orgResp = await fetch(`${ADMIN_API}/api/v1/organizations`, {
    method: "POST",
    headers: adminHeaders,
    body: JSON.stringify({
      name: "Acme Corp TS",
      slug: "acme-corp-ts",
      description: "TypeScript example org",
      max_budget: 500.0,
    }),
  });
  const org = (await orgResp.json()) as any;
  console.log(`  Created org: ${org.name} (${org.id})`);

  // --- Create Team ---
  console.log("\nStep 2: Create Team\n");

  const teamResp = await fetch(`${LITELLM}/team/new`, {
    method: "POST",
    headers: litellmHeaders,
    body: JSON.stringify({
      team_alias: "acme-frontend-ts",
      max_budget: 100.0,
      budget_duration: "30d",
      models: ["gpt-4o-mini", "claude-haiku-4.5"],
    }),
  });
  const team = (await teamResp.json()) as any;
  console.log(`  Created team: acme-frontend-ts (${team.team_id})`);

  // --- Generate API Key ---
  console.log("\nStep 3: Generate API Key\n");

  const keyResp = await fetch(`${LITELLM}/key/generate`, {
    method: "POST",
    headers: litellmHeaders,
    body: JSON.stringify({
      team_id: team.team_id,
      key_alias: "acme-frontend-ts-key",
      max_budget: 25.0,
      budget_duration: "30d",
    }),
  });
  const key = (await keyResp.json()) as any;
  console.log(`  API Key: ${key.key?.slice(0, 30)}...`);

  // --- Use the key ---
  console.log("\nStep 4: Use Team Key\n");

  if (key.key) {
    const { default: OpenAI } = await import("openai");
    const client = new OpenAI({ baseURL: LITELLM, apiKey: key.key });

    const response = await client.chat.completions.create({
      model: "gpt-4o-mini",
      messages: [{ role: "user", content: "Say hello in Japanese" }],
      max_tokens: 50,
    });

    console.log(`  Model: ${response.model}`);
    console.log(`  Response: ${response.choices[0].message.content}`);
    console.log(`  Tokens: ${response.usage?.total_tokens}`);
    console.log(`\n  This request was tracked against the acme-frontend-ts team budget.`);
  }

  console.log(`\n  Dashboard: http://localhost:5173\n`);
}

main().catch(console.error);
