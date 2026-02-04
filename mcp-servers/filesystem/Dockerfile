FROM python:3.11-slim

WORKDIR /app

# Install Node.js for MCP server
RUN apt-get update && apt-get install -y nodejs npm curl && rm -rf /var/lib/apt/lists/*

# Install Flask for HTTP wrapper
RUN pip install flask flask-cors

# Install the official filesystem MCP server
RUN npm install -g @modelcontextprotocol/server-filesystem

# Copy HTTP wrapper
COPY ../http-wrapper.py /app/wrapper.py
RUN chmod +x /app/wrapper.py

EXPOSE 3000

CMD ["python", "/app/wrapper.py", "npx", "-y", "@modelcontextprotocol/server-filesystem", "/workspace"]
