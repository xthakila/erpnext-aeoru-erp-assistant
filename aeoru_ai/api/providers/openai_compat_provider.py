import frappe
import json
import time
import requests
from .base import BaseProvider, AIResponse, ToolCall, ToolResult

try:
    import jwt as pyjwt
except ImportError:
    pyjwt = None


class OpenAICompatProvider(BaseProvider):
    """OpenAI-compatible provider for DeepSeek and GLM-5."""

    def __init__(self, api_key: str, model: str, base_url: str,
                 temperature: float = 0.3, max_tokens: int = 4096,
                 use_jwt: bool = False):
        super().__init__(api_key, model, temperature, max_tokens)
        self.base_url = base_url.rstrip("/")
        self.use_jwt = use_jwt

    def _get_auth_header(self) -> dict:
        """Get authorization header, using JWT for GLM-5 if needed."""
        if self.use_jwt:
            token = self._generate_jwt()
            return {"Authorization": f"Bearer {token}"}
        return {"Authorization": f"Bearer {self.api_key}"}

    def _generate_jwt(self) -> str:
        """Generate JWT token for GLM-5 (z.ai) authentication.
        API key format: {id}.{secret}
        """
        if not pyjwt:
            frappe.throw("PyJWT package is not installed. Run: pip install PyJWT")

        parts = self.api_key.split(".")
        if len(parts) != 2:
            frappe.throw("GLM-5 API key must be in 'id.secret' format")

        api_id, api_secret = parts

        now = int(time.time())
        payload = {
            "api_key": api_id,
            "exp": now + 3600,  # 1 hour expiry
            "timestamp": now,
        }
        headers = {
            "alg": "HS256",
            "sign_type": "SIGN",
        }

        return pyjwt.encode(payload, api_secret, algorithm="HS256", headers=headers)

    def chat(self, messages: list, tools: list = None, system_prompt: str = "") -> AIResponse:
        """Send messages using OpenAI-compatible chat completions API."""
        openai_messages = self._prepare_messages(messages, system_prompt)

        payload = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        if tools:
            payload["tools"] = self._format_tools(tools)
            payload["tool_choice"] = "auto"

        headers = {
            "Content-Type": "application/json",
            **self._get_auth_header(),
        }

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=120,
            )
            resp.raise_for_status()
            return self._parse_response(resp.json())
        except requests.RequestException as e:
            frappe.log_error(f"OpenAI-compat API Error: {str(e)}", "AI Assistant")
            return AIResponse(text=f"API error: {str(e)}", stop_reason="error")

    def _prepare_messages(self, messages: list, system_prompt: str = "") -> list:
        """Convert internal message format to OpenAI format."""
        openai_messages = []

        if system_prompt:
            openai_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            role = msg.get("role", "user")

            if role == "tool":
                # Tool result message
                openai_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id", ""),
                    "content": msg.get("content", ""),
                })
            elif msg.get("tool_calls"):
                # Assistant message with tool calls
                openai_messages.append({
                    "role": "assistant",
                    "content": msg.get("content") or None,
                    "tool_calls": msg["tool_calls"],
                })
            elif isinstance(msg.get("content"), list):
                # Handle image content — fallback to text for non-vision models
                text_parts = []
                has_image = False
                for part in msg["content"]:
                    if part.get("type") == "text":
                        text_parts.append(part["text"])
                    elif part.get("type") in ("image", "image_url", "tool_result"):
                        if part.get("type") == "tool_result":
                            # Claude-format tool result in content array — convert
                            openai_messages.append({
                                "role": "tool",
                                "tool_call_id": part.get("tool_use_id", ""),
                                "content": part.get("content", ""),
                            })
                            continue
                        has_image = True
                if has_image:
                    text_parts.append("[Image attached — switch to Claude for image analysis]")
                if text_parts:
                    openai_messages.append({"role": role, "content": "\n".join(text_parts)})
            else:
                openai_messages.append({"role": role, "content": msg.get("content", "")})

        return openai_messages

    def _format_tools(self, tools: list) -> list:
        """Convert tool definitions to OpenAI function calling format."""
        openai_tools = []
        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("parameters", tool.get("input_schema", {})),
                }
            })
        return openai_tools

    def _parse_response(self, data: dict) -> AIResponse:
        """Parse OpenAI-compatible response into unified AIResponse."""
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        tool_calls = []
        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                func = tc.get("function", {})
                args = func.get("arguments", "{}")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}
                tool_calls.append(ToolCall(
                    id=tc.get("id", ""),
                    name=func.get("name", ""),
                    arguments=args,
                ))

        usage = data.get("usage", {})

        return AIResponse(
            text=message.get("content") or "",
            tool_calls=tool_calls,
            stop_reason=choice.get("finish_reason", ""),
            usage={
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            }
        )

    def format_tool_result(self, tool_result: ToolResult) -> dict:
        """Format tool result for OpenAI's message format."""
        content = tool_result.content
        if tool_result.is_error:
            content = f"Error: {content}"
        return {
            "role": "tool",
            "tool_call_id": tool_result.tool_call_id,
            "content": content,
        }

    def format_tool_calls_message(self, response: AIResponse) -> dict:
        """Format assistant message with tool calls for OpenAI format."""
        tool_calls = []
        for tc in response.tool_calls:
            tool_calls.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments),
                }
            })
        return {
            "role": "assistant",
            "content": response.text or None,
            "tool_calls": tool_calls,
        }
