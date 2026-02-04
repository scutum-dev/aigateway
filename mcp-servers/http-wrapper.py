#!/usr/bin/env python3
"""
HTTP wrapper for MCP servers that run on stdio.
Exposes MCP tools via REST API.
"""
import json
import subprocess
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# MCP server command (passed as environment variable)
MCP_COMMAND = sys.argv[1:] if len(sys.argv) > 1 else ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/workspace"]

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "server": "mcp-http-wrapper"})

@app.route('/mcp/tools', methods=['GET'])
def list_tools():
    """List available tools from MCP server"""
    try:
        # Send list_tools request to MCP server
        request_msg = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list"
        })

        result = subprocess.run(
            MCP_COMMAND,
            input=request_msg + "\n",
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and result.stdout:
            response = json.loads(result.stdout)
            tools = response.get("result", {}).get("tools", [])
            return jsonify({"tools": tools})

        return jsonify({"tools": []}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/mcp/invoke', methods=['POST'])
def invoke_tool():
    """Invoke a tool on the MCP server"""
    try:
        data = request.json
        tool_name = data.get("tool")
        params = data.get("params", {})

        # Send tool invocation request
        request_msg = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": params
            }
        })

        result = subprocess.run(
            MCP_COMMAND,
            input=request_msg + "\n",
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0 and result.stdout:
            response = json.loads(result.stdout)
            return jsonify(response.get("result", {}))

        return jsonify({"error": "Tool invocation failed", "stderr": result.stderr}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print(f"Starting MCP HTTP Wrapper for: {' '.join(MCP_COMMAND)}")
    app.run(host='0.0.0.0', port=3000)
