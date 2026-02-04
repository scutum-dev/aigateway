"""
Unified request models for gateway abstraction.
"""

from typing import Optional, List, Dict, Any, Union, Literal
from pydantic import BaseModel, Field


class FunctionDefinition(BaseModel):
    """Function definition for tool use."""
    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class Tool(BaseModel):
    """Tool definition."""
    type: Literal["function"] = "function"
    function: FunctionDefinition


class ToolCall(BaseModel):
    """Tool call in a message."""
    id: str
    type: Literal["function"] = "function"
    function: Dict[str, Any]  # {"name": str, "arguments": str}


class Message(BaseModel):
    """
    Unified message format.

    Supports:
    - System messages
    - User messages (text or multimodal)
    - Assistant messages (with optional tool calls)
    - Tool messages (results)
    """
    role: Literal["system", "user", "assistant", "tool"]
    content: Optional[Union[str, List[Dict[str, Any]]]] = None
    name: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None

    class Config:
        extra = "allow"


class ChatRequest(BaseModel):
    """
    Unified chat completion request.

    Compatible with OpenAI API format with extensions for
    other providers.
    """
    # Required
    model: str = Field(..., description="Model identifier")
    messages: List[Message] = Field(..., description="Conversation messages")

    # Optional parameters
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    top_p: Optional[float] = Field(default=None, ge=0, le=1)
    n: Optional[int] = Field(default=None, ge=1)
    stream: bool = Field(default=False)
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = Field(default=None, ge=1)
    presence_penalty: Optional[float] = Field(default=None, ge=-2, le=2)
    frequency_penalty: Optional[float] = Field(default=None, ge=-2, le=2)
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None

    # Tool use
    tools: Optional[List[Tool]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None

    # Response format
    response_format: Optional[Dict[str, str]] = None

    # Provider-specific extensions
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"

    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI API format."""
        data = {
            "model": self.model,
            "messages": [
                {k: v for k, v in m.model_dump().items() if v is not None}
                for m in self.messages
            ],
        }

        # Add optional parameters
        optional_fields = [
            "temperature", "top_p", "n", "stream", "stop", "max_tokens",
            "presence_penalty", "frequency_penalty", "logit_bias", "user",
            "tools", "tool_choice", "response_format"
        ]

        for field in optional_fields:
            value = getattr(self, field, None)
            if value is not None:
                data[field] = value

        return data

    def to_anthropic_format(self) -> Dict[str, Any]:
        """Convert to Anthropic API format."""
        # Extract system message
        system = None
        messages = []

        for m in self.messages:
            if m.role == "system":
                system = m.content
            else:
                msg = {"role": m.role, "content": m.content}
                messages.append(msg)

        data = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens or 4096,
        }

        if system:
            data["system"] = system

        if self.temperature is not None:
            data["temperature"] = self.temperature

        if self.top_p is not None:
            data["top_p"] = self.top_p

        if self.stop:
            data["stop_sequences"] = self.stop if isinstance(self.stop, list) else [self.stop]

        if self.stream:
            data["stream"] = True

        return data
