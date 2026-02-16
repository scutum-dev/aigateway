# Admin UI Guide

A page-by-page walkthrough of the AI Control Plane Admin Console at **http://localhost:5173**.

## Login

When you first open the Admin UI, you see the login screen:

1. Enter your **API Key** in the password field. Use the LiteLLM master key (the value of `LITELLM_MASTER_KEY` from `config/.env`, e.g., `$LITELLM_KEY`).
2. Click **Sign In**.
3. The UI validates your key against LiteLLM and issues a JWT token that is stored in your browser for 8 hours.

Only keys with admin privileges can log in. The master key always has admin access. Regular user keys will receive a "Admin access required" error.

## Navigation

After logging in, you see a dark sidebar on the left with the following pages:

| Page         | Icon        | Description                              |
|-------------|-------------|------------------------------------------|
| Dashboard   | Home        | Real-time metrics and charts             |
| API Keys    | Key         | API key generation and management        |
| Models      | Cube        | Model configuration table                |
| Budgets     | Dollar      | Budget cards with spending limits        |
| Teams       | User Group  | Team management with members             |
| MCP Servers | Server      | Model Context Protocol server config     |
| Workflows   | Database    | Workflow templates and execution history |
| Settings    | Gear        | Platform-wide toggles and defaults       |

The sidebar can be collapsed to icon-only mode using the chevron toggle. A **Logout** button is at the bottom.

On mobile, the sidebar becomes a slide-out panel accessible via the hamburger menu.

The top of the main content area shows a breadcrumb with the current page name.

## Dashboard

The Dashboard is the landing page after login. It shows a real-time snapshot of the platform for the current day.

### Stat Cards

Four metric cards across the top:

- **Requests/min** -- current request throughput (averaged over the day)
- **Total Cost Today** -- dollar amount spent across all providers
- **Total Tokens Today** -- combined input and output tokens
- **Error Rate** -- percentage of failed requests

### Charts

- **Cost Over Time** (line chart) -- hourly cost distribution for today, with an indigo fill area showing the spending curve.
- **Model Usage** (doughnut chart) -- top 6 models by request count, showing the distribution of traffic across models.

### Provider Status

Below the charts, the provider status section shows a green or red indicator for each provider, based on the most recent health check.

### Onboarding

If this is a fresh installation with no data, the Dashboard displays an onboarding guide with quick-start steps for configuring your first model, creating a team, and making a test request.

## Models

The Models page displays all configured models in a sortable, searchable table.

### Table Columns

| Column             | Description                                      | Sortable |
|--------------------|--------------------------------------------------|----------|
| Model ID           | The name used in API requests                    | Yes      |
| Provider           | Source provider (openai, anthropic, google, etc.) | Yes      |
| Tier               | Routing tier (standard, premium, economy)        | Yes      |
| Input Cost         | Cost per 1K input tokens ($)                     | Yes      |
| Output Cost        | Cost per 1K output tokens ($)                    | --       |
| Latency SLA        | Target response time in milliseconds             | Yes      |
| Streaming          | Whether the model supports streaming             | --       |
| Function Calling   | Whether the model supports tool use              | --       |

### Filtering and Sorting

- **Search bar** at the top filters models by model ID or provider name as you type.
- **Provider filter** dropdown lets you show only models from a specific provider.
- Click any sortable column header to sort ascending; click again to sort descending. A chevron icon indicates the current sort direction.

### Editing a Model

1. Click the **pencil icon** on any row to enter edit mode.
2. Editable fields appear inline: tier, input cost, output cost, latency SLA, streaming toggle, and function calling toggle.
3. Click the **check icon** to save, or the **X icon** to cancel.
4. A success toast notification confirms the update.

Model edits are saved to the database immediately and take effect on the next request.

## Budgets

The Budgets page displays all configured budgets as cards in a responsive grid (1 column on mobile, 2 on tablet, 3 on desktop).

### Budget Cards

Each card shows:

- **Name** and entity type badge (team, user, or global)
- **Progress bar** showing current spend relative to the monthly limit
- **Current spend** dollar amount and **monthly limit**
- **Soft limit** and **hard limit** percentages
- **Alert email** (if configured)
- **Active status** toggle

The progress bar color indicates status:
- Green: spend is below the soft limit
- Yellow: spend is between soft and hard limits
- Red: spend has exceeded the hard limit

### Creating a Budget

1. Click the **Create Budget** button in the top-right corner.
2. A form panel appears with fields for:
   - Name
   - Entity Type (dropdown: team, user, global)
   - Entity ID (the team or user identifier)
   - Monthly Limit ($)
   - Soft Limit Percent (0 to 1, default 0.8)
   - Hard Limit Percent (0 to 1, default 1.0)
   - Alert Email
3. Click **Create** to save, or close the panel to cancel.

### Editing a Budget

1. Click the **pencil icon** on any budget card.
2. The card switches to an edit form with the same fields.
3. Modify the values and click **Save**, or click the **X** to cancel.

## Teams

The Teams page displays all teams as cards in a grid layout.

### Team Cards

Each card shows:

- **Team name** and description
- **Monthly budget** (if set)
- **Default model** (if configured)
- **Member count** with a list of member IDs
- **Active status** indicator

### Creating a Team

1. Click **Create Team** in the top-right corner.
2. Fill in the form:
   - **Name** (required)
   - **Description**
   - **Monthly Budget** (optional dollar amount)
   - **Default Model** (optional model name)
3. Click **Create**.

### Editing a Team

1. Click the **pencil icon** on any team card.
2. The card switches to an edit form with the same fields as creation.
3. Modify the values and click **Save**, or click the **X** to cancel.

Via API:

```bash
curl -X PUT http://localhost:8086/api/v1/teams/{team_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"description": "Updated description", "monthly_budget": 500}'
```

### Deleting a Team

1. Click the **delete icon** on any team card.
2. Confirm the deletion in the dialog.

Via API:

```bash
curl -X DELETE http://localhost:8086/api/v1/teams/{team_id} \
  -H "Authorization: Bearer $TOKEN"
```

### Adding Members

1. Click the **Add Member** icon on any team card.
2. A form appears requesting:
   - **User ID** -- the identifier for the user to add
   - **Role** -- either `member` or `admin`
3. Click **Add** to save. The member appears in the team card immediately.

## API Keys

The API Keys page lets you create and manage API keys for authenticating against the LLM proxy. Keys are managed through LiteLLM and can have per-key budgets, model restrictions, and team assignments.

### Key List

The page displays all API keys in a table showing:
- **Key** (masked) -- the API key value, partially hidden for security
- **Alias** -- a human-readable name for the key
- **Spend** -- total spend accumulated by this key
- **Max Budget** -- spending cap for the key (if set)
- **Models** -- list of models this key is allowed to access (empty means all)
- **Team** -- the team this key belongs to (if any)
- **Expires** -- expiration date (if set)

### Generating a Key

1. Click **Generate Key** in the top-right corner.
2. Fill in the form:
   - **Key Alias** -- a descriptive name (e.g., "backend-service-prod")
   - **Max Budget** ($) -- optional spending cap
   - **Models** -- optional comma-separated list of allowed models
   - **Team ID** -- optional team assignment
   - **Duration** -- optional expiry (e.g., "30d", "90d")
3. Click **Generate**.
4. **Copy the key immediately** -- it will not be shown again.

### Updating and Revoking Keys

- Click **Edit** on any key row to update its alias, budget, models, or duration.
- Click **Revoke** to permanently delete a key. This action cannot be undone.

## MCP Servers

The MCP Servers page manages Model Context Protocol server configurations that extend the gateway with external tools.

### Server List

Each server is displayed as a card showing:
- **Name** and server type badge (`stdio` or `http`)
- **Command** (for stdio servers) or **URL** (for HTTP servers)
- **Arguments** list
- **Environment variables** (displayed as key-value pairs)
- **Discovered tools** list
- **Active status** indicator

### Adding a Server

1. Click **Add Server** in the top-right corner.
2. Fill in the form:
   - **Name**: A descriptive name for the server
   - **Type**: Choose `stdio` or `http`
   - **Command**: For stdio servers, the executable command (e.g., `npx -y @anthropic/mcp-server-brave-search`)
   - **URL**: For HTTP servers, the endpoint URL
   - **Args**: Space-separated command-line arguments
   - **Env**: Environment variables as a JSON object (e.g., `{"BRAVE_API_KEY": "your-key"}`)
3. Click **Create**.

### stdio vs. http

- **stdio servers** are local processes that communicate via stdin/stdout. The gateway spawns them as child processes. Use these for tools like file system access, Brave Search, or GitHub.
- **http servers** are remote services that expose an HTTP endpoint. The gateway connects to them over the network. Use these for cloud-hosted tool services.

### Testing a Server

Click the **Test** button on any server card to verify connectivity:
- For **http** servers, the gateway makes an HTTP request to the configured URL and reports the status code.
- For **stdio** servers, the gateway validates the command and arguments are configured correctly.

A toast notification shows the test result.

### Deploy to Gateway

MCP server configurations stored in the database are not automatically applied to the running Agent Gateway. To push your changes:

1. Click **"Preview Config"** in the page header to see the YAML that will be generated for the Agent Gateway.
2. Review the preview -- it shows all active servers mapped to the agentgateway `config.yaml` format.
3. Click **"Deploy to Gateway"** to push the config.
4. A confirmation dialog shows the number of active servers that will be deployed.
5. Click **Deploy** to update the Agent Gateway's ConfigMap and trigger a rolling restart.

The deploy operation:
- Patches the `agentgateway-config` Kubernetes ConfigMap with the generated YAML
- Triggers a rolling restart of the Agent Gateway deployment via annotation patch
- Existing connections drain gracefully (zero downtime with a PodDisruptionBudget)

> **Note:** Deploy to Gateway requires Kubernetes. In local Docker Compose development, the button will return an informational error.

## Workflows

The Workflows page shows pre-built workflow templates and any custom workflows configured in the database.

### Pre-built Templates

Three template cards are always visible:

| Template        | Description                                          | Nodes                                                          |
|-----------------|------------------------------------------------------|----------------------------------------------------------------|
| Research Agent  | Multi-source research with web search and report gen | parse_query, search_web, search_database, analyze_results, generate_report |
| Coding Agent    | Iterative code generation with analysis              | understand_task, read_code, generate_code, analyze_code, finalize_code |
| Data Analysis   | SQL generation, analysis, and visualization          | parse_question, query_data, analyze_data, generate_visualization, summarize |

Each template card displays the workflow name, description, and a visual list of processing nodes.

### Custom Workflows

Below the templates, any workflows saved in the database are listed with their name, template type, description, active status, and creation date.

Workflows require the `workflows` profile to be active:

```bash
docker compose --env-file config/.env --profile workflows up -d
```

### Testing a Workflow

Each pre-built template and custom workflow has a **Test Workflow** (or **Run**) button:

1. Click the button to open the execute modal.
2. Enter a prompt describing what you want the workflow to do.
3. Click **Execute** to start the workflow.
4. A success toast confirms the execution has started.

### Execution History

Below the workflow cards, the **Execution History** table shows all past runs with:
- **ID** -- short execution identifier
- **Workflow** -- the workflow name
- **Status** -- pending, running, completed, or failed (color-coded badges)
- **Cost** -- total cost of the execution
- **Started** -- timestamp when the execution began
- **Duration** -- elapsed time

### Execution Details

Click any row in the Execution History table to expand a detail panel showing:

- **Step-by-step progress** -- each workflow node with a status indicator (green = completed, blue = running, red = failed, gray = pending), duration, and per-step cost
- **Output** -- the final result from the workflow, displayed in a formatted code block
- **Error details** -- if the execution failed, the error message is shown in a red banner
- **Summary footer** -- total tokens, total cost, duration, and the current node (for running executions)

The detail panel auto-refreshes every 2 seconds while the execution is running or pending.

## Settings

The Settings page provides platform-wide configuration organized into four sections.

### General

- **Default Model**: The model used when a request does not specify one. Default is `gpt-4o-mini`.
- **Global Rate Limit**: Maximum requests per minute across the entire platform. Default is 1000.

### Caching

- **Enable Caching** (toggle): When on, LLM responses for identical requests are cached in Redis. Default is on.
- **Cache TTL**: How long cached responses remain valid, in seconds. Default is 3600 (1 hour).

### Features

Three feature toggles:

- **Cost Tracking** (toggle): Track token usage and compute costs per request. Default is on.
- **Budget Enforcement** (toggle): Enforce budget limits and block requests when hard limits are exceeded. Default is on.
- **Routing Policies** (toggle): Enable Cedar policy-based model routing. Default is on.

### Maintenance Mode

A red-bordered card at the bottom with a single toggle:

- **Enable Maintenance Mode**: When activated, the gateway blocks all API requests except health checks, returning 503 to clients. Use this for planned maintenance windows.

### Saving

Click the **Save Settings** button at the bottom to persist all changes. A green "Settings saved successfully!" message confirms the save.

All settings changes take effect immediately -- no restart is required.

## Tips for Effective Administration

**Check the Dashboard daily.** The cost and usage charts make it easy to spot anomalies early -- a sudden spike in spend or an unusual model distribution can indicate a misconfigured client or an unintended model choice.

**Use teams to organize access.** Assign each department or project its own team with a default model and monthly budget. This creates natural cost boundaries and simplifies reporting.

**Set soft limits to 70-80%.** This gives budget owners enough warning time to review spend before the hard limit is reached. A soft limit too close to 100% defeats its purpose.

**Keep the model table sorted by cost.** When reviewing model configurations, sort by input cost descending to see your most expensive models at the top. Consider whether premium models are being used appropriately.

**Disable unused models.** If a model is no longer needed, edit it and set its active status to off rather than removing it from the config. This preserves historical data while preventing new requests.

**Use maintenance mode for deployments.** Before updating the platform, enable maintenance mode to gracefully drain active requests. Re-disable it once the update is complete.

**Review routing policies periodically.** As your team structure and requirements change, routing policies may need updates. Stale policies can cause unexpected routing behavior.

## Related Guides

- [Quickstart Guide](./QUICKSTART.md) -- get the platform running in 5 minutes
- [API Integration Guide](./API_INTEGRATION.md) -- code examples for all languages
- [Model Routing Guide](./MODEL_ROUTING.md) -- understand how models are selected
- [Cost Management Guide](./COST_MANAGEMENT.md) -- budgets, alerts, and FinOps reporting
