import frappe
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ToolCall:
    """Represents a tool call from the AI model."""
    id: str
    name: str
    arguments: dict = field(default_factory=dict)


@dataclass
class ToolResult:
    """Result of executing a tool."""
    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass
class AIResponse:
    """Unified response from any AI provider."""
    text: str = ""
    tool_calls: list = field(default_factory=list)  # List[ToolCall]
    stop_reason: str = ""
    usage: dict = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class BaseProvider(ABC):
    """Abstract base class for AI providers."""

    def __init__(self, api_key: str = None, model: str = "", temperature: float = 0.3, max_tokens: int = 4096):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    @property
    def supports_tool_calls(self) -> bool:
        """Whether this provider supports tool calls in the agentic loop.
        Providers that return False handle everything internally (e.g. CLI-based)."""
        return True

    @abstractmethod
    def chat(self, messages: list, tools: list = None, system_prompt: str = "") -> AIResponse:
        """Send messages to the AI model and get a response.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: List of tool definition dicts
            system_prompt: System-level instructions

        Returns:
            AIResponse with text and/or tool_calls
        """
        pass

    @abstractmethod
    def format_tool_result(self, tool_result: ToolResult) -> dict:
        """Format a tool result into provider-specific message format.

        Args:
            tool_result: The result of a tool execution

        Returns:
            Dict formatted for this provider's message format
        """
        pass

    @abstractmethod
    def format_tool_calls_message(self, response: AIResponse) -> dict:
        """Format the assistant's tool call response into a message for history.

        Args:
            response: The AI response containing tool calls

        Returns:
            Dict formatted as an assistant message with tool calls
        """
        pass
