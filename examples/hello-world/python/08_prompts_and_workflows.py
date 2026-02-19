"""
Example 8: Prompt Registry & Workflow Execution

Demonstrates two developer experience features:
  1. Prompt Registry — versioned templates with variable rendering and LLM execution
  2. Workflows — trigger LangGraph research/coding/data-analysis pipelines
"""

import os

import httpx

ADMIN_API = "http://localhost:8086"
MASTER_KEY = os.getenv("LITELLM_KEY") or os.getenv("LITELLM_MASTER_KEY", "")

# Authenticate
resp = httpx.post(f"{ADMIN_API}/auth/login", json={"api_key": MASTER_KEY})
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def print_section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


# --------------------------------------------------------------------------
# Part 1: Prompt Registry
# --------------------------------------------------------------------------
print_section("Prompt Registry")

# 1a. Create a prompt template with variables
print("  Creating prompt template: code-review")
template = httpx.post(
    f"{ADMIN_API}/api/v1/prompts",
    headers=headers,
    json={
        "name": "Code Review Assistant",
        "slug": "code-review-demo",
        "description": "Reviews code for bugs, security issues, and style",
        "category": "engineering",
        "template_text": (
            "You are a senior {{language}} developer.\n"
            "Review the following code for bugs, security issues, and style.\n"
            "Be concise — max 3 bullet points.\n\n"
            "```{{language}}\n{{code}}\n```"
        ),
        "variables": [
            {"name": "language", "type": "string", "required": True},
            {"name": "code", "type": "string", "required": True},
        ],
        "model_hint": "gpt-4o-mini",
        "tags": ["engineering", "code-review"],
    },
).json()
template_id = template.get("id", "")
print(f"  Created: {template.get('name')} (v{template.get('version', 1)})")
print(f"  Slug: {template.get('slug')}")
print(f"  Status: {template.get('status')}")
print(f"  Variables: {[v['name'] for v in template.get('variables', [])]}")

# 1b. Render the template (preview without calling LLM)
print("\n  Rendering template with variables...")
rendered = httpx.post(
    f"{ADMIN_API}/api/v1/prompts/code-review-demo/render",
    headers=headers,
    json={
        "variables": {
            "language": "python",
            "code": "def login(user, pw):\n    query = f\"SELECT * FROM users WHERE name='{user}' AND pass='{pw}'\"\n    return db.execute(query)",
        }
    },
).json()
print("  Rendered prompt:\n")
for line in rendered.get("rendered", "").split("\n"):
    print(f"    {line}")
print(f"\n  Unresolved variables: {rendered.get('unresolved_variables', [])}")

# 1c. Execute the template (render + call LLM)
print("\n  Executing template (calling LLM)...")
result = httpx.post(
    f"{ADMIN_API}/api/v1/prompts/code-review-demo/execute",
    headers=headers,
    json={
        "variables": {
            "language": "python",
            "code": "def login(user, pw):\n    query = f\"SELECT * FROM users WHERE name='{user}' AND pass='{pw}'\"\n    return db.execute(query)",
        },
        "model": "gpt-4o-mini",
        "max_tokens": 200,
    },
    timeout=30.0,
).json()

if "response" in result:
    print(f"  Model: {result.get('model')}")
    usage = result.get("usage", {})
    print(f"  Tokens: {usage.get('input_tokens', 0)} in / {usage.get('output_tokens', 0)} out")
    print(f"  Latency: {usage.get('latency_ms', 0)}ms")
    print("\n  Review:\n")
    for line in result.get("response", "").split("\n"):
        print(f"    {line}")
else:
    print(f"  Execute result: {result}")

# 1d. Create a new version of the template
print("\n\n  Creating version 2 (adding severity levels)...")
v2 = httpx.post(
    f"{ADMIN_API}/api/v1/prompts/code-review-demo/versions",
    headers=headers,
    json={
        "template_text": (
            "You are a senior {{language}} developer.\n"
            "Review the following code. For each issue found, rate severity (HIGH/MEDIUM/LOW).\n"
            "Be concise — max 5 bullet points.\n\n"
            "```{{language}}\n{{code}}\n```"
        ),
    },
).json()
print(f"  Created version {v2.get('version')} (status: {v2.get('status')})")

# 1e. List all versions
versions = httpx.get(f"{ADMIN_API}/api/v1/prompts/code-review-demo/versions", headers=headers).json()
print("\n  All versions:")
for v in versions:
    current = " (current)" if v.get("is_current") else ""
    print(f"    v{v['version']}: {v['status']}{current}")


# --------------------------------------------------------------------------
# Part 2: Workflows
# --------------------------------------------------------------------------
print_section("Workflows")

# 2a. List available workflow templates
print("  Available workflow templates:")
templates = httpx.get(f"{ADMIN_API}/api/v1/workflow-templates", headers=headers)
if templates.status_code == 200:
    tmpl_data = templates.json()
    if isinstance(tmpl_data, list):
        for t in tmpl_data:
            name = t.get("name", t.get("template", "unknown"))
            desc = t.get("description", "")
            print(f"    - {name}: {desc}")
    elif isinstance(tmpl_data, dict):
        for name, info in tmpl_data.items():
            desc = info if isinstance(info, str) else info.get("description", "")
            print(f"    - {name}: {desc}")
else:
    print(f"    (Workflow engine not available — status {templates.status_code})")

# 2b. Register a workflow definition in admin DB
print("\n  Registering workflow definition...")
wf = httpx.post(
    f"{ADMIN_API}/api/v1/workflows",
    headers=headers,
    json={
        "name": "quick-research-demo",
        "template_type": "research",
        "description": "Quick research workflow for demo purposes",
    },
).json()
print(f"  Registered: {wf.get('name')} (type: {wf.get('template_type')})")

# 2c. Execute a workflow
print("\n  Executing research workflow...")
execution = httpx.post(
    f"{ADMIN_API}/api/v1/workflow-executions",
    headers=headers,
    json={
        "template_type": "research",
        "input_text": "What are the top 3 benefits of using an AI gateway?",
    },
    timeout=60.0,
)

if execution.status_code == 200:
    exec_data = execution.json()
    exec_id = exec_data.get("execution_id", exec_data.get("id", "N/A"))
    print(f"  Execution ID: {exec_id}")
    print(f"  Status: {exec_data.get('status', 'submitted')}")

    # Check if there's output
    output = exec_data.get("output", exec_data.get("result"))
    if output:
        text = output if isinstance(output, str) else str(output)[:300]
        print(f"\n  Result preview:\n    {text[:300]}...")
    else:
        print("\n  Workflow is running asynchronously.")
        print(f"  Check status: GET /api/v1/workflow-executions/{exec_id}")
else:
    print(f"  Workflow engine returned {execution.status_code}")
    detail = execution.json().get("detail", execution.text[:200])
    print(f"  Detail: {detail}")
    print("  (This is expected if the workflow engine is not running)")

# 2d. List recent executions
print("\n  Recent workflow executions:")
execs = httpx.get(f"{ADMIN_API}/api/v1/workflow-executions", headers=headers)
if execs.status_code == 200:
    exec_list = execs.json()
    items = exec_list if isinstance(exec_list, list) else exec_list.get("executions", [])
    for e in items[:5]:
        eid = e.get("execution_id", e.get("id", "?"))[:8]
        tmpl = e.get("template", e.get("template_type", "?"))
        st = e.get("status", "?")
        print(f"    {eid}...  {tmpl:<15} {st}")
    if not items:
        print("    No executions yet.")
else:
    print(f"    (Not available — workflow engine status {execs.status_code})")


# --------------------------------------------------------------------------
# Cleanup
# --------------------------------------------------------------------------
print_section("Cleanup")

if template_id:
    httpx.delete(f"{ADMIN_API}/api/v1/prompts/{template_id}", headers=headers)
    print("  Deleted prompt template: code-review-demo")

print("\n  Manage prompts: http://localhost:5173/prompts")
print("  Manage workflows: http://localhost:5173/workflows\n")
