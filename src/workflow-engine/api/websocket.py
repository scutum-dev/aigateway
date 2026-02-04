"""
WebSocket endpoint for streaming workflow execution updates.
"""

import logging
import json
import asyncio
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for execution streaming."""

    def __init__(self):
        # execution_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, execution_id: str):
        """Accept a new WebSocket connection."""
        await websocket.accept()

        async with self._lock:
            if execution_id not in self.active_connections:
                self.active_connections[execution_id] = set()
            self.active_connections[execution_id].add(websocket)

        logger.info(f"WebSocket connected for execution {execution_id}")

    async def disconnect(self, websocket: WebSocket, execution_id: str):
        """Remove a WebSocket connection."""
        async with self._lock:
            if execution_id in self.active_connections:
                self.active_connections[execution_id].discard(websocket)
                if not self.active_connections[execution_id]:
                    del self.active_connections[execution_id]

        logger.info(f"WebSocket disconnected for execution {execution_id}")

    async def broadcast(self, execution_id: str, message: dict):
        """Broadcast a message to all connections for an execution."""
        async with self._lock:
            connections = self.active_connections.get(execution_id, set()).copy()

        if not connections:
            return

        message_str = json.dumps(message)
        disconnected = set()

        for connection in connections:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.warning(f"Failed to send to websocket: {e}")
                disconnected.add(connection)

        # Clean up disconnected connections
        if disconnected:
            async with self._lock:
                if execution_id in self.active_connections:
                    self.active_connections[execution_id] -= disconnected


# Global connection manager
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, execution_id: str):
    """
    WebSocket endpoint for streaming execution updates.

    Connect to /ws/executions/{execution_id} to receive real-time updates.

    Message types:
    - status: Execution status change
    - node_start: Node started executing
    - node_complete: Node completed
    - output: Intermediate or final output
    - error: Error occurred
    """
    await manager.connect(websocket, execution_id)

    try:
        # Send initial connection acknowledgment
        await websocket.send_json({
            "type": "connected",
            "execution_id": execution_id,
            "message": "Connected to execution stream"
        })

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages (or just keep alive)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )

                # Handle ping/pong
                if data == "ping":
                    await websocket.send_text("pong")
                else:
                    # Echo back any other messages
                    await websocket.send_json({
                        "type": "echo",
                        "data": data
                    })

            except asyncio.TimeoutError:
                # Send keepalive
                try:
                    await websocket.send_json({"type": "keepalive"})
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from execution {execution_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await manager.disconnect(websocket, execution_id)


async def send_execution_update(
    execution_id: str,
    update_type: str,
    data: dict
):
    """
    Send an update to all connected clients for an execution.

    Args:
        execution_id: Execution ID
        update_type: Type of update (status, node_start, node_complete, output, error)
        data: Update data
    """
    await manager.broadcast(execution_id, {
        "type": update_type,
        "execution_id": execution_id,
        **data
    })
