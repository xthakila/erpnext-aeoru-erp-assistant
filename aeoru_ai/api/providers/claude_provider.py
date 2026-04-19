import frappe
import json
from .base import BaseProvider, AIResponse, ToolCall, ToolResult

try:
    import anthropic
except ImportError:
    anthropic = None


class ClaudeProvider(BaseProvider):
    """Anthropic Claude provider with native tool_use and vision support."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514",
                 temperature: float = 0.3, max_tokens: int = 4096):
        super().__init__(api_key, model, temperature, max_tokens)
        if not anthropic:
            frappe.throw("anthropic package is not installed. Run: pip install anthropic")
        self.client = anthropic.Anthropic(api_key=api_key)

    def chat(self, messages: list, tools: list = None, system_prompt: str = "") -> AIResponse:
        """Send messages to Claude with tool_use support."""
        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": self._prepare_messages(messages),
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        if tools:
            kwargs["tools"] = self._format_tools(tools)

        try:
            response = self.client.messages.create(**kwargs)
            return self._parse_response(response)
        except anthropic.APIError as e:
            frappe.log_error(f"Claude API Error: {str(e)}", "AI Assistant")
            return AIResponse(text=f"Claude API error: {str(e)}", stop_reason="error")

    def _prepare_messages(self, messages: list) -> list:
        """Convert internal message format to Claude format."""
        claude_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                continue  # System messages handled separately

            claude_msg = {"role": msg["role"]}

            if isinstance(msg.get("content"), list):
                # Already formatted (e.g., with images or tool results)
                claude_msg["content"] = msg["content"]
            elif msg.get("images"):
                # Message with image attachments
                content = []
                for img in msg["images"]:
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": img["media_type"],
                            "data": img["data"],
                        }
                    })
                if msg.get("content"):
                    content.append({"type": "text", "text": msg["content"]})
                claude_msg["content"] = content
            else:
                claude_msg["content"] = msg.get("content", "")

            claude_messages.append(claude_msg)

        return claude_messages

    def _format_tools(self, tools: list) -> list:
        """Convert tool definitions to Claude's tool format."""
        claude_tools = []
        for tool in tools:
            claude_tools.append({
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool.get("parameters", tool.get("input_schema", {})),
            })
        return claude_tools

    def _parse_response(self, response) -> AIResponse:
        """Parse Claude's response into unified AIResponse."""
        text_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input if isinstance(block.input, dict) else json.loads(block.input),
                ))

        return AIResponse(
            text="\n".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=response.stop_reason,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        )

    def format_tool_result(self, tool_result: ToolResult) -> dict:
        """Format tool result for Claude's message format."""
        return {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_result.tool_call_id,
                "content": tool_result.content,
                "is_error": tool_result.is_error,
            }]
        }

    def format_tool_calls_message(self, response: AIResponse) -> dict:
        """Format assistant message with tool calls for Claude."""
        content = []
        if response.text:
            content.append({"type": "text", "text": response.text})
        for tc in response.tool_calls:
            content.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.arguments,
            })
        return {"role": "assistant", "content": content}
