FROM node:20-alpine

WORKDIR /app

# Install PostgreSQL client libraries
RUN apk add --no-cache postgresql-client

# Install the official PostgreSQL MCP server
RUN npm install -g @modelcontextprotocol/server-postgres

EXPOSE 3000

CMD ["npx", "-y", "@modelcontextprotocol/server-postgres", "$POSTGRES_CONNECTION_STRING"]
