# Real MCP Servers

These are official MCP servers from Anthropic's Model Context Protocol:

## Available Servers

1. **Filesystem Server** (@modelcontextprotocol/server-filesystem)
   - Read/write files
   - List directories
   - Search files
   - Port: 8100

2. **PostgreSQL Server** (@modelcontextprotocol/server-postgres)
   - Query database
   - List tables
   - Get schema info
   - Port: 8101

3. **Brave Search** (@modelcontextprotocol/server-brave-search)
   - Web search capabilities
   - Port: 8102

4. **GitHub** (@modelcontextprotocol/server-github)
   - Repository operations
   - File operations
   - Port: 8103

## Build and Run

```bash
# Build all MCP servers
docker-compose build mcp-filesystem mcp-database mcp-brave-search mcp-github

# Run MCP servers
docker-compose up -d mcp-filesystem mcp-database mcp-brave-search mcp-github

# Check status
docker-compose ps | grep mcp
```

## More MCP Servers

See https://github.com/modelcontextprotocol/servers for more official servers:
- @modelcontextprotocol/server-slack
- @modelcontextprotocol/server-gdrive
- @modelcontextprotocol/server-git
- @modelcontextprotocol/server-puppeteer
- And many more...
