# Custom Agent Gateway image with Node.js for stdio MCP servers
# The official agentgateway image is distroless (no shell/npx).
# This image copies the Rust binary into Ubuntu 24.04 (GLIBC 2.39)
# with Node.js so stdio MCP servers can be spawned.

FROM ghcr.io/agentgateway/agentgateway:0.11.0-alpha.18e45de0f30a108df129aeb08d49453ea0527db3 AS gateway

FROM ubuntu:24.04

# Install Node.js 22.x and Python 3 (for uvx-based MCP servers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg python3 python3-pip \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
       | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" \
       > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager, provides uvx)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy the agentgateway binary
COPY --from=gateway /app/agentgateway /app/agentgateway

# Pre-install MCP server packages globally so npx doesn't download on every request
# Pre-install Node.js MCP servers globally
RUN npm install -g \
    @modelcontextprotocol/server-filesystem \
    @modelcontextprotocol/server-postgres \
    @modelcontextprotocol/server-brave-search \
    @modelcontextprotocol/server-github \
    && npm cache clean --force

# Pre-install Python MCP servers
RUN uvx --from mcp-server-fetch mcp-server-fetch --help || true

EXPOSE 3000 15000 15020

ENTRYPOINT ["/app/agentgateway"]
