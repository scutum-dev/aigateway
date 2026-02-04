"""
Unified response models for gateway abstraction.
"""

from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class FinishReason(str, Enum):
    """Reasons for completion finishing."""
    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"


class Usage(BaseModel):
    """Token usage information."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    # Optional detailed breakdown
    cached_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None


class ToolCallResponse(BaseModel):
    """Tool call in response."""
    id: str
    type: Literal["function"] = "function"
    function: Dict[str, Any]


class ResponseMessage(BaseModel):
    """Message in response."""
    role: Literal["assistant"] = "assistant"
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCallResponse]] = None
    refusal: Optional[str] = None


class Choice(BaseModel):
    """A single completion choice."""
    index: int = 0
    message: ResponseMessage
    finish_reason: Optional[str] = None
    logprobs: Optional[Dict[str, Any]] = None


class StreamDelta(BaseModel):
    """Delta content for streaming."""
    role: Optional[str] = None
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class StreamChoice(BaseModel):
    """A streaming choice."""
    index: int = 0
    delta: StreamDelta
    finish_reason: Optional[str] = None


class ChatResponse(BaseModel):
    """
    Unified chat completion response.

    Compatible with OpenAI API format.
    """
    id: str = Field(default="")
    object: str = Field(default="chat.completion")
    created: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    model: str = Field(default="")
    choices: List[Choice] = Field(default_factory=list)
    usage: Optional[Usage] = None
    system_fingerprint: Optional[str] = None

    # Streaming
    is_stream: bool = False

    # Provider metadata
    provider: Optional[str] = None
    gateway: Optional[str] = None

    # Error handling
    error: Optional[Dict[str, Any]] = None

    @classmethod
    def from_openai(cls, data: Dict[str, Any], gateway: str = None) -> "ChatResponse":
        """Create from OpenAI API response."""
        choices = []
        for c in data.get("choices", []):
            message = c.get("message", {})
            choices.append(Choice(
                index=c.get("index", 0),
                message=ResponseMessage(
                    role=message.get("role", "assistant"),
                    content=message.get("content"),
                    tool_calls=[
                        ToolCallResponse(**tc) for tc in message.get("tool_calls", [])
                    ] if message.get("tool_calls") else None,
                ),
                finish_reason=c.get("finish_reason"),
            ))

        usage_data = data.get("usage")
        usage = Usage(**usage_data) if usage_data else None

        return cls(
            id=data.get("id", ""),
            object=data.get("object", "chat.completion"),
            created=data.get("created", int(datetime.now().timestamp())),
            model=data.get("model", ""),
            choices=choices,
            usage=usage,
            system_fingerprint=data.get("system_fingerprint"),
            provider="openai",
            gateway=gateway,
        )

    @classmethod
    def from_anthropic(cls, data: Dict[str, Any], gateway: str = None) -> "ChatResponse":
        """Create from Anthropic API response."""
        content = ""
        tool_calls = []

        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append(ToolCallResponse(
                    id=block.get("id", ""),
                    type="function",
                    function={
                        "name": block.get("name", ""),
                        "arguments": str(block.get("input", {})),
                    }
                ))

        choices = [Choice(
            index=0,
            message=ResponseMessage(
                role="assistant",
                content=content if content else None,
                tool_calls=tool_calls if tool_calls else None,
            ),
            finish_reason=data.get("stop_reason", "stop"),
        )]

        usage_data = data.get("usage", {})
        usage = Usage(
            prompt_tokens=usage_data.get("input_tokens", 0),
            completion_tokens=usage_data.get("output_tokens", 0),
            total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
        )

        return cls(
            id=data.get("id", ""),
            object="chat.completion",
            created=int(datetime.now().timestamp()),
            model=data.get("model", ""),
            choices=choices,
            usage=usage,
            provider="anthropic",
            gateway=gateway,
        )

    @classmethod
    def stream_chunk(
        cls,
        content: Optional[str] = None,
        model: str = "",
        finish_reason: Optional[str] = None,
        gateway: str = None,
    ) -> "ChatResponse":
        """Create a streaming chunk response."""
        return cls(
            id="",
            object="chat.completion.chunk",
            model=model,
            choices=[StreamChoice(
                index=0,
                delta=StreamDelta(content=content),
                finish_reason=finish_reason,
            )],
            is_stream=True,
            gateway=gateway,
        )

    def get_content(self) -> Optional[str]:
        """Get the content from the first choice."""
        if self.choices:
            return self.choices[0].message.content
        return None

    def get_tool_calls(self) -> List[ToolCallResponse]:
        """Get tool calls from the first choice."""
        if self.choices and self.choices[0].message.tool_calls:
            return self.choices[0].message.tool_calls
        return []
