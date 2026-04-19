import frappe
from .base import BaseProvider
from .claude_provider import ClaudeProvider
from .openai_compat_provider import OpenAICompatProvider


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

    else:
        frappe.throw(f"Unknown AI provider: {provider}")
