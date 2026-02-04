FROM node:20-alpine

WORKDIR /app

# Install the GitHub MCP server
RUN npm install -g @modelcontextprotocol/server-github

EXPOSE 3000

CMD ["npx", "-y", "@modelcontextprotocol/server-github"]
