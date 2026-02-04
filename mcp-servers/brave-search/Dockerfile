FROM node:20-alpine

WORKDIR /app

# Install the Brave Search MCP server
RUN npm install -g @modelcontextprotocol/server-brave-search

EXPOSE 3000

CMD ["npx", "-y", "@modelcontextprotocol/server-brave-search"]
