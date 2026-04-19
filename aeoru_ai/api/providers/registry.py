import frappe
from .base import BaseProvider
from .claude_provider import ClaudeProvider
from .openai_compat_provider import OpenAICompatProvider
from .claude_code_provider import ClaudeCodeProvider


def get_provider(provider_name: str = None) -> BaseProvider:
    """Get configured AI provider instance.

    Args:
        provider_name: Override provider name. If None, uses default from settings.

    Returns:
        Configured BaseProvider instance

    Raises:
        frappe.ValidationError if provider is not configured
    """
    settings = frappe.get_single("AI Assistant Settings")

    if not settings.enabled:
        frappe.throw("AI Assistant is not enabled. Please enable it in AI Assistant Settings.")

    provider = provider_name or settings.default_provider

    # Get common settings
    temperature = float(settings.temperature or 0.3)
    max_tokens = int(settings.max_tokens or 4096)

    if provider == "Claude":
        api_key = settings.get_password("claude_api_key")
        if not api_key:
            frappe.throw("Claude API key is not configured in AI Assistant Settings.")
        return ClaudeProvider(
            api_key=api_key,
            model=settings.claude_model or "claude-sonnet-4-20250514",
            temperature=temperature,
            max_tokens=max_tokens,
        )

    elif provider == "DeepSeek":
        api_key = settings.get_password("deepseek_api_key")
        if not api_key:
            frappe.throw("DeepSeek API key is not configured in AI Assistant Settings.")
        return OpenAICompatProvider(
            api_key=api_key,
            model="deepseek-chat",
            base_url=settings.deepseek_base_url or "https://api.deepseek.com/v1",
            temperature=temperature,
            max_tokens=max_tokens,
            use_jwt=False,
        )

    elif provider == "GLM-5":
        api_key = settings.get_password("glm_api_key")
        if not api_key:
            frappe.throw("GLM-5 API key is not configured in AI Assistant Settings.")
        return OpenAICompatProvider(
            api_key=api_key,
            model="glm-4-plus",
            base_url=settings.glm_base_url or "https://open.bigmodel.cn/api/paas/v4",
            temperature=temperature,
            max_tokens=max_tokens,
            use_jwt=True,
        )

    elif provider == "Claude Code":
        # Locate the MCP runner script for ERPNext tools
        import os
        mcp_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "mcp_runner.sh"
        )
        if not os.path.exists(mcp_path):
            mcp_path = ""

        return ClaudeCodeProvider(
            model=settings.claude_code_model or "sonnet",
            cli_path=settings.claude_code_cli_path or "/usr/local/bin/claude",
            max_budget_usd=float(settings.claude_code_max_budget or 1.00),
            timeout=int(settings.claude_code_timeout or 120),
            max_concurrent=int(settings.claude_code_max_concurrent or 3),
            allowed_tools=settings.claude_code_allowed_tools or "",
            mcp_server_path=mcp_path,
        )

    else:
        frappe.throw(f"Unknown AI provider: {provider}")
