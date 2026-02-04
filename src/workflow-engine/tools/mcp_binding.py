"""
MCP client for tool integration via Agent Gateway.
"""

import logging
from typing import Optional, Dict, Any, List
import httpx

logger = logging.getLogger(__name__)


class MCPClient:
    """
    Async HTTP client for MCP tools via Agent Gateway.

    Provides tool invocation for workflows.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:3000",
        timeout: float = 30.0,
    ):
        """
        Initialize MCP client.

        Args:
            base_url: Agent Gateway URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def post(self, path: str, json: Dict[str, Any]) -> httpx.Response:
        """
        Make a POST request.

        Args:
            path: API path
            json: JSON body

        Returns:
            HTTP response
        """
        client = await self._get_client()
        return await client.post(path, json=json)

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List available MCP tools.

        Returns:
            List of tool definitions
        """
        client = await self._get_client()

        response = await client.post(
            "/mcp/tools/list",
            json={}
        )

        if response.status_code != 200:
            logger.warning(f"Failed to list tools: {response.status_code}")
            return []

        return response.json().get("tools", [])

    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Call an MCP tool.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result
        """
        client = await self._get_client()

        response = await client.post(
            "/mcp/tools/call",
            json={
                "name": name,
                "arguments": arguments,
            }
        )

        if response.status_code != 200:
            raise Exception(f"Tool call failed: {response.status_code} - {response.text}")

        return response.json()

    async def read_file(self, path: str) -> str:
        """
        Read a file using filesystem MCP.

        Args:
            path: File path

        Returns:
            File contents
        """
        result = await self.call_tool("read_file", {"path": path})
        return result.get("content", "")

    async def write_file(self, path: str, content: str) -> bool:
        """
        Write a file using filesystem MCP.

        Args:
            path: File path
            content: File content

        Returns:
            Success status
        """
        result = await self.call_tool("write_file", {"path": path, "content": content})
        return result.get("success", False)

    async def search_web(self, query: str, count: int = 10) -> List[Dict[str, Any]]:
        """
        Search the web using Brave Search MCP.

        Args:
            query: Search query
            count: Number of results

        Returns:
            Search results
        """
        result = await self.call_tool("brave_search", {"query": query, "count": count})
        return result.get("results", [])

    async def query_database(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute a database query using PostgreSQL MCP.

        Args:
            query: SQL query

        Returns:
            Query results
        """
        result = await self.call_tool("postgres_query", {"query": query})
        return result.get("results", [])
