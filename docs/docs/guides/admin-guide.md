# Admin UI Guide

A page-by-page walkthrough of the AI Control Plane Admin Console at **http://localhost:5173**.

## Login

When you first open the Admin UI, you see the login screen:

1. Enter your **API Key** in the password field. Use the LiteLLM master key (the value of `SCUTUM_API_KEY` from `config/.env`, e.g., `$SCUTUM_API_KEY`).
2. Click **Sign In**.
3. The UI validates your key against LiteLLM and issues a JWT token that is stored in your browser for 8 hours.

Only keys with admin privileges can log in. The master key always has admin access. Regular user keys will receive a "Admin access required" error.

## Navigation

After logging in, you see a dark sidebar on the left with the following pages:

| Page           | Icon               | Description                                  |
|----------------|--------------------|----------------------------------------------|
| Dashboard      | Home               | Real-time metrics and charts                 |
| Models         | Cube               | Model configuration table                    |
| API Keys       | Key                | API key generation and management            |
| Teams          | User Group         | Team management with members                 |
| Budgets        | Dollar             | Budget cards with spending limits            |
| Organizations  | Building           | Multi-tenant org and business unit hierarchy |
| Audit Log      | Clipboard          | Filterable log of all admin actions          |
| Prompts        | Document           | Prompt template registry with versioning     |
| Rate Limits    | Clock              | Granular rate limiting policies              |
| Model Access   | Lock               | Access tier management and request workflow  |
| Chargeback     | Banknotes          | Cost allocation rules and chargeback reports |
| SLA Monitor    | Heart              | Provider health, SLA tracking, failover      |
| A/B Tests      | Beaker             | Model comparison experiments                 |
| Events         | Bell               | Event subscriptions and notification routing |
| MCP Servers    | Server             | Model Context Protocol server config         |
| A2A Agents     | Chip               | Agent-to-Agent protocol agent management     |
| Guardrails     | Shield             | Content safety rules and DLP detectors       |
| Workflows      | Database           | Workflow templates and execution history     |
| Settings       | Gear               | Platform-wide toggles and defaults           |

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

## Organizations

The Organizations page provides multi-tenant organization management with a hierarchical structure of organizations, business units, teams, and members.

### Tab Layout

The page is organized into four tabs:

| Tab             | Description                                           |
|-----------------|-------------------------------------------------------|
| Business Units  | Sub-divisions within an organization                  |
| Teams           | Teams scoped to a business unit                       |
| Members         | Individual user membership and role assignments       |
| SSO Config      | Single sign-on provider configuration per org         |

An organization selector at the top of the page lets you switch context between organizations. All tabs filter their content to the selected organization.

### Managing Organizations

1. Click **Create Organization** to add a new org.
2. Fill in the name, display name, and optional description.
3. Click **Create**. The new org appears in the organization selector.

To edit or delete an organization, use the action buttons next to the organization selector.

### Business Units

Business units represent departments, divisions, or cost centers within an organization.

Each business unit row shows its name, description, and the number of teams assigned to it.

1. Click **Add Business Unit** to create a new one within the selected organization.
2. Provide a name and optional description.
3. Click **Create**.

Business units can be edited or deleted using the row action icons.

### Members

The Members tab displays all users within the selected organization in a table with columns for user ID, display name, role, business unit assignment, and status.

Member roles determine access within the organization:

| Role        | Description                                                    |
|-------------|----------------------------------------------------------------|
| org_admin   | Full administrative access across the entire organization      |
| bu_admin    | Administrative access scoped to a specific business unit       |
| member      | Standard access within assigned teams                          |
| viewer      | Read-only access to dashboards and reports                     |

To add a member:

1. Click **Add Member**.
2. Enter the user ID, select a role from the dropdown, and optionally assign a business unit.
3. Click **Add**.

Member roles can be changed inline by clicking the role badge and selecting a new value.

### SSO Config

The SSO Config tab allows you to configure single sign-on for the selected organization. SSO settings include the identity provider URL, client ID, client secret, and allowed domains. Once configured, members of the organization can authenticate through the configured identity provider instead of using API keys.

## Audit Log

The Audit Log page provides a searchable, filterable record of all administrative actions performed on the platform.

### Table Columns

| Column     | Description                                                   |
|------------|---------------------------------------------------------------|
| Timestamp  | When the action occurred (displayed in local time)            |
| Actor      | The user or API key that performed the action                 |
| Action     | The type of operation (create, update, delete, login, etc.)   |
| Resource   | The entity affected (model, team, budget, key, etc.)          |
| Changes    | A diff summary showing what was modified                      |

### Filtering

The page provides the following filter controls above the table:

- **Organization** -- filter events to a specific organization
- **Actor** -- filter by the user who performed the action
- **Resource Type** -- filter by entity type (model, team, budget, api_key, org, etc.)
- **Date Range** -- start and end date pickers to narrow the time window

Filters can be combined. The table updates in real time as filters are applied.

### Export

Click the **Export** button in the top-right corner to download the current filtered view. Two formats are available:

- **CSV** -- comma-separated values, suitable for spreadsheet tools
- **JSON** -- structured data, suitable for programmatic processing

The export includes all rows matching the current filters, not just the visible page.

## Prompts

The Prompts page provides a centralized registry for managing prompt templates with version control and an approval workflow.

### Template List

The main view shows all prompt templates in a table with columns for template name, current version, status, last modified date, and usage count.

### Creating a Template

1. Click **Create Template** in the top-right corner.
2. Fill in the form:
   - **Name** -- a unique identifier for the template (e.g., "customer-support-reply")
   - **Description** -- what the template is used for
   - **Content** -- the prompt text, using `{{variable}}` syntax for placeholder variables (e.g., `{{customer_name}}`, `{{issue_description}}`)
3. Click **Create**. The template is created with version 1 in `draft` status.

### Template Editor

Click any template row to open the template editor. The editor displays:

- **Content area** -- a text editor for the prompt body with syntax highlighting for `{{variable}}` placeholders
- **Variables panel** -- an auto-detected list of all variables found in the template, with optional default values
- **Preview** -- a rendered preview with sample values substituted into placeholders

### Version History

Each template maintains a full version history. The version history panel shows:

- Version number
- Author who created the version
- Timestamp
- Status badge
- A diff view comparing the version against its predecessor

To create a new version, edit the template content and click **Save as New Version**. The previous version is preserved and remains accessible.

### Approval Workflow

Prompt templates follow a four-stage lifecycle:

| Status           | Description                                                    |
|------------------|----------------------------------------------------------------|
| draft            | Initial state; editable, not available for production use      |
| pending_review   | Submitted for approval; read-only until reviewed               |
| approved         | Reviewed and approved; available for use in API requests       |
| deprecated       | Retired; no longer available for new requests                  |

To submit a draft for review, click **Submit for Review**. Reviewers can then **Approve** or **Reject** the template from the review panel. Rejected templates return to `draft` status with reviewer comments.

### Usage Analytics

Each template version displays usage analytics showing the number of times it has been used in API requests, broken down by time period. This helps identify which templates are actively used and which can be deprecated.

## Rate Limits

The Rate Limits page manages granular rate limiting policies that control request throughput at multiple scopes.

### Policy List

The main view shows all rate limit policies in a table with columns for policy name, scope, limits, burst multiplier, and status.

### Scope Levels

Rate limit policies can be applied at five different scopes:

| Scope        | Description                                               |
|--------------|-----------------------------------------------------------|
| user         | Limits applied to an individual user                      |
| team         | Limits shared across all members of a team                |
| model        | Limits applied to a specific model regardless of caller   |
| user_model   | Per-user limits scoped to a specific model                |
| team_model   | Per-team limits scoped to a specific model                |

### Limit Types

Each policy can define one or more of the following limits:

| Limit | Description                    |
|-------|--------------------------------|
| RPM   | Requests per minute            |
| TPM   | Tokens per minute              |
| RPD   | Requests per day               |
| TPD   | Tokens per day                 |

### Burst Multiplier

Each policy includes a burst multiplier (default 1.0) that allows short bursts of traffic above the stated limit. For example, a policy with RPM=100 and burst multiplier=1.5 allows bursts up to 150 requests per minute for short periods before enforcement kicks in.

### Creating a Policy

1. Click **Create Policy** in the top-right corner.
2. Fill in the form:
   - **Name** -- a descriptive name for the policy
   - **Scope** -- select the scope level from the dropdown
   - **Entity ID** -- the user, team, or model identifier (depends on scope)
   - **RPM / TPM / RPD / TPD** -- set one or more limits
   - **Burst Multiplier** -- optional, defaults to 1.0
3. Click **Create**.

### Real-Time Usage

Each policy row displays a real-time usage indicator sourced from Redis, showing the current consumption against the configured limit. The indicator turns yellow when usage exceeds 80% of the limit and red when the limit is reached.

## Model Access

The Model Access page manages access tiers for models and provides a request-based workflow for granting access to restricted models.

### Access Tiers

Models are organized into access tiers that determine who can use them and under what conditions:

| Tier          | Description                                                         |
|---------------|---------------------------------------------------------------------|
| standard      | Available to all authenticated users without approval               |
| premium       | Requires explicit access grant; may require justification           |
| experimental  | Restricted access with mandatory approval and time-limited grants   |

### Tier Definitions

Each tier is configured with the following properties:

- **requires_approval** -- whether a request must be approved before access is granted
- **requires_justification** -- whether the requester must provide a written justification
- **max_grant_duration_days** -- the maximum number of days an access grant remains valid before it expires (applies to time-limited tiers)

To edit tier definitions, click the **pencil icon** on any tier card and modify the properties.

### Access Requests

Users who need access to a premium or experimental model submit an access request. The request workflow follows these stages:

| Status    | Description                                                       |
|-----------|-------------------------------------------------------------------|
| pending   | Request submitted, awaiting admin review                          |
| approved  | Access granted; the user can use the model until expiration       |
| rejected  | Access denied; the requester receives the rejection reason        |
| expired   | A previously approved grant has passed its expiration date        |

The Access Requests table shows all requests with columns for requester, model, tier, justification, status, and dates. Admins can **Approve** or **Reject** pending requests directly from the table using the action buttons.

When approving a request, the admin can optionally set a custom expiration date. If not set, the tier's `max_grant_duration_days` is used.

## Chargeback

The Chargeback page provides cost allocation tools for mapping AI spend to internal cost centers and generating chargeback reports for finance teams.

### Cost Allocation Rules

The top section displays allocation rules that map teams to financial entities. Each rule specifies:

- **Team** -- the team whose costs are being allocated
- **Cost Center** -- the internal cost center code
- **Project** -- the project identifier
- **Department** -- the department name
- **Allocation Percentage** -- the percentage of the team's costs allocated to this rule (allows split allocations across multiple cost centers)

To create a rule:

1. Click **Add Rule**.
2. Select a team, enter the cost center, project, and department.
3. Set the allocation percentage (default 100%).
4. Click **Create**.

Multiple rules can exist for a single team to split costs across cost centers.

### Chargeback Reports

The reports section allows you to generate and manage chargeback reports for specific time periods.

Each report progresses through a lifecycle:

| Status    | Description                                                       |
|-----------|-------------------------------------------------------------------|
| draft     | Report generated but not yet reviewed; costs can be adjusted      |
| finalized | Report reviewed and locked; no further edits allowed              |
| exported  | Report has been exported to an external system                    |

To generate a report:

1. Click **Generate Report**.
2. Select the reporting period (month/year).
3. Click **Generate**. The system calculates costs for all teams and applies allocation rules.

The generated report shows a breakdown by cost center, project, and department, with line items for each team's model usage and total cost.

### Budget Forecasts

The forecast section displays projected costs for upcoming periods based on historical trends. Forecasts include:

- **Projected spend** for the next period
- **Confidence intervals** (low, medium, high) based on spend variability
- **Trend direction** indicator showing whether costs are increasing, stable, or decreasing

### Export

Click **Export** on any finalized report to download it. Supported formats:

- **CSV** -- standard comma-separated format
- **JSON** -- structured data for programmatic ingestion
- **SAP** -- formatted for SAP financial system import

## SLA Monitor

The SLA Monitor page tracks provider health, monitors service level agreements, and manages failover rules.

### Provider Health Cards

The top section displays a health card for each configured provider. Each card shows:

- **Provider name** and current health status indicator:
  - Green: all SLA targets are met
  - Yellow: one or more targets are at risk (within 10% of threshold)
  - Red: one or more SLA violations detected
- **Current latency** (p50, p95, p99) in milliseconds
- **Error rate** percentage over the current monitoring window
- **Availability** percentage (uptime)

### SLA Definitions

Below the health cards, the SLA definitions table lists all configured SLAs with their targets:

| Field            | Description                                         |
|------------------|-----------------------------------------------------|
| Provider         | The provider this SLA applies to                    |
| p50 Latency      | Median latency target in milliseconds               |
| p95 Latency      | 95th percentile latency target                      |
| p99 Latency      | 99th percentile latency target                      |
| Error Rate       | Maximum acceptable error rate percentage            |
| Availability     | Minimum required availability percentage            |

To create an SLA definition:

1. Click **Add SLA**.
2. Select a provider and set the latency, error rate, and availability targets.
3. Click **Create**.

### Health Metrics History

Each provider card can be expanded to show a time-series chart of latency and error rate over the selected period. The chart overlays the SLA threshold lines so deviations are visually obvious.

### Violations

The Violations table lists all SLA breaches with columns for timestamp, provider, metric, target value, actual value, and duration. Violations are color-coded by severity and sorted by most recent first.

### Failover Rules

Failover rules define automatic model substitution when a provider's health degrades.

Each rule specifies:

- **Primary model** -- the model that receives traffic under normal conditions
- **Fallback model** -- the model that receives traffic when the primary triggers a failover
- **Trigger condition** -- the health metric and threshold that activates the failover (e.g., "error_rate > 5%" or "p95_latency > 2000ms")
- **Cooldown period** -- minimum time before traffic can return to the primary model

To create a failover rule:

1. Click **Add Failover Rule**.
2. Select the primary and fallback models.
3. Define the trigger condition and cooldown period.
4. Click **Create**.

When a failover is active, a banner appears on the provider health card indicating which models have been rerouted.

### Compliance Reports

Click **Generate Compliance Report** to produce an SLA compliance summary for a given time period. The report includes uptime percentages, violation counts, and mean time to recovery for each provider. Reports can be exported as CSV or JSON.

## A/B Tests

The A/B Tests page enables controlled experiments comparing two models side by side to evaluate performance, cost, and quality differences.

### Test List

The main view shows all A/B tests in a table with columns for test name, base model, variant model, traffic split, status, and creation date.

### Creating a Test

1. Click **Create Test** in the top-right corner.
2. Fill in the form:
   - **Name** -- a descriptive name for the experiment
   - **Base Model** -- the current production model (control group)
   - **Variant Model** -- the model being evaluated (treatment group)
   - **Traffic Split** -- the percentage of traffic routed to the variant (e.g., 10 means 10% to variant, 90% to base)
   - **Description** -- optional notes about the test hypothesis
3. Click **Create**. The test is created in `draft` status.

### Test Lifecycle

| Status      | Description                                                        |
|-------------|--------------------------------------------------------------------|
| draft       | Test defined but not yet active; traffic is not split              |
| running     | Test is live; traffic is being split between base and variant      |
| completed   | Test has been stopped; results are final                           |
| rolled_back | Variant was rejected; all traffic returned to the base model       |

To start a test, click **Start** on a draft test. To stop a running test, click **Complete**.

### Metrics Comparison

Each test displays a metrics comparison panel showing side-by-side statistics for the base and variant models:

| Metric         | Description                                            |
|----------------|--------------------------------------------------------|
| Requests       | Total number of requests routed to each model          |
| Avg Latency    | Mean response time in milliseconds                     |
| p95 Latency    | 95th percentile response time                          |
| Error Rate     | Percentage of failed requests                          |
| Avg Cost       | Mean cost per request                                  |
| Total Cost     | Cumulative cost during the test period                 |

Metrics are displayed as snapshots captured periodically during the test run.

### Promote and Rollback

After a test is completed, two actions are available:

- **Promote** -- adopts the variant model as the new default, replacing the base model in production routing
- **Rollback** -- discards the variant results and confirms the base model remains in use

Both actions update the test status accordingly and log the decision in the audit trail.

## Events

The Events page manages event subscriptions that route platform notifications to external systems.

### Event Types

The platform generates events for significant operational conditions:

| Event Type           | Description                                                |
|----------------------|------------------------------------------------------------|
| budget.exceeded      | A budget soft or hard limit has been reached               |
| guardrail.blocked    | A request was blocked by a content safety guardrail        |
| model.error          | A model request failed with a provider error               |
| sla.violation        | An SLA target was breached for a provider                  |

### Notification Channels

Events can be routed to one or more notification channels:

| Channel    | Description                                            |
|------------|--------------------------------------------------------|
| slack      | Posts to a Slack channel via webhook URL               |
| pagerduty  | Triggers a PagerDuty incident via integration key      |
| email      | Sends an email to specified recipients                 |
| webhook    | Sends an HTTP POST to a custom URL                     |
| sns        | Publishes to an AWS SNS topic                          |
| sqs        | Sends to an AWS SQS queue                              |

### Creating a Subscription

1. Click **Create Subscription** in the top-right corner.
2. Fill in the form:
   - **Name** -- a descriptive name for the subscription
   - **Event Type** -- select one or more event types to subscribe to
   - **Channel** -- select the notification channel
   - **Configuration** -- channel-specific settings (e.g., webhook URL, Slack channel, email addresses, SNS topic ARN)
   - **Filters** -- optional filters to narrow which events trigger the subscription (e.g., specific team, model, or budget)
3. Click **Create**.

### Event Log

The bottom section of the page displays a chronological log of all events that have fired. Each entry shows the event type, timestamp, affected resource, and delivery status for each subscription.

Filters above the log let you narrow by event type, date range, and delivery status (delivered, failed, pending).

### Test Event

Click the **Test** button on any subscription to send a synthetic test event through the configured channel. This validates that the channel configuration is correct and the destination is reachable. A toast notification confirms whether the test was delivered successfully.

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

## A2A Agents

The A2A Agents page manages agents registered with the Agent-to-Agent (A2A) protocol runtime.

### Agent List

The main view displays all registered agents in a table with the following columns:

| Column        | Description                                              |
|---------------|----------------------------------------------------------|
| Name          | The agent's display name                                 |
| Agent ID      | Unique identifier used in A2A protocol routing           |
| Capabilities  | List of declared capabilities the agent provides         |
| Status        | Current agent status (active, inactive, error)           |
| Last Seen     | Timestamp of the agent's most recent heartbeat           |

### Agent Details

Click any agent row to view its detail panel, which shows:

- **Full capability list** with descriptions
- **Endpoint URL** -- the address where the agent is reachable
- **Protocol version** -- the A2A protocol version the agent supports
- **Metadata** -- additional key-value pairs registered by the agent

### Managing Agents

Agents typically self-register with the A2A runtime when they start. From this page, admins can:

- **Deactivate** an agent to remove it from the routing pool without deleting its registration
- **Reactivate** a previously deactivated agent
- **Delete** an agent registration permanently

A2A Agents require the `workflows` profile to be active:

```bash
docker compose --env-file config/.env --profile workflows up -d
```

## Guardrails

The Guardrails page manages content safety rules and data loss prevention (DLP) detectors that inspect requests and responses passing through the gateway.

### Guardrail List

The main view shows all guardrails in a table with columns for name, type, action (block or flag), scope, and status.

### Creating a Guardrail

1. Click **Create Guardrail** in the top-right corner.
2. Fill in the form:
   - **Name** -- a descriptive name for the guardrail
   - **Type** -- the category of content check
   - **Action** -- `block` (reject the request) or `flag` (allow but log a warning)
   - **Scope** -- which teams or models the guardrail applies to (leave empty for global)
3. Click **Create**.

### DLP Content Detectors

Guardrails can include one or more DLP content detectors that scan request and response payloads for sensitive data. Three detector types are available:

| Detector Type   | Description                                                          |
|-----------------|----------------------------------------------------------------------|
| regex           | Matches content against a regular expression pattern (e.g., SSN, credit card numbers, API keys) |
| dictionary      | Matches against a list of keywords or phrases (e.g., internal project names, restricted terms) |
| external_dlp    | Delegates detection to an external DLP service via HTTP callback     |

To add a detector to a guardrail:

1. Click the **Add Detector** button on the guardrail detail view.
2. Select the detector type.
3. Configure the detector:
   - For **regex**: provide the pattern and optional flags
   - For **dictionary**: provide the word list (one entry per line)
   - For **external_dlp**: provide the service URL and authentication details
4. Click **Add**.

A guardrail can have multiple detectors. Content is checked against all attached detectors, and the guardrail action triggers if any detector matches.

### Team Content Policies

Guardrails can be scoped to specific teams through content policies. A content policy links a set of guardrails to a team, ensuring that all requests from that team are subject to the specified checks. To create a content policy:

1. Navigate to the guardrail detail view.
2. Under **Team Policies**, click **Add Team**.
3. Select the team and click **Save**.

The team's requests will be inspected by the guardrail's detectors on all subsequent API calls.

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

**Use organizations to enforce multi-tenancy.** Create separate organizations for each business entity, with business units mapping to departments. This establishes clear boundaries for access control, cost allocation, and audit trails.

**Use teams to organize access.** Assign each department or project its own team with a default model and monthly budget. This creates natural cost boundaries and simplifies reporting.

**Set soft limits to 70-80%.** This gives budget owners enough warning time to review spend before the hard limit is reached. A soft limit too close to 100% defeats its purpose.

**Keep the model table sorted by cost.** When reviewing model configurations, sort by input cost descending to see your most expensive models at the top. Consider whether premium models are being used appropriately.

**Disable unused models.** If a model is no longer needed, edit it and set its active status to off rather than removing it from the config. This preserves historical data while preventing new requests.

**Use maintenance mode for deployments.** Before updating the platform, enable maintenance mode to gracefully drain active requests. Re-disable it once the update is complete.

**Review routing policies periodically.** As your team structure and requirements change, routing policies may need updates. Stale policies can cause unexpected routing behavior.

**Configure event subscriptions for critical alerts.** Set up Slack or PagerDuty subscriptions for `budget.exceeded` and `sla.violation` events so your team is notified immediately when limits are breached or providers degrade.

**Use A/B tests before model migrations.** Before switching production traffic to a new model, run an A/B test with a small traffic split to validate latency, cost, and error rate differences.

**Set up SLA failover rules for production models.** Define failover rules for your most critical models so traffic is automatically rerouted if a provider experiences an outage.

**Enforce guardrails with DLP detectors.** Attach regex-based detectors for common sensitive patterns (credit cards, SSNs, API keys) to prevent data leakage through LLM requests.

**Review the audit log after incidents.** When investigating unexpected behavior, filter the audit log by time range and resource type to trace the sequence of configuration changes that may have caused the issue.

## Related Guides

- [Quickstart Guide](./quickstart.md) -- get the platform running in 5 minutes
- [API Integration Guide](./api-integration.md) -- code examples for all languages
- [Model Routing Guide](./model-routing.md) -- understand how models are selected
- [Cost Management Guide](./cost-management.md) -- budgets, alerts, and FinOps reporting
