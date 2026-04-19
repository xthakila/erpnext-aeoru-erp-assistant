import frappe
import json
from datetime import datetime
from aeoru_ai.api.providers import get_provider
from aeoru_ai.api.providers.base import ToolResult
from aeoru_ai.api.tools.definitions import ALL_TOOLS, DESTRUCTIVE_TOOLS
from aeoru_ai.api.tools.executor import execute_tool
from aeoru_ai.api.providers.base import ToolCall


SYSTEM_PROMPT = """You are an AI assistant embedded in ERPNext. You help users manage their business data through natural language.

RULES:
1. You can create, read, update, and delete any ERPNext document the user has permission for.
2. ALWAYS call get_doctype_schema before creating or updating a document to understand the required fields.
3. NEVER fabricate or guess values for required fields. If information is missing, ASK the user.
4. For destructive actions (delete, submit, cancel), ALWAYS explain what will happen and wait for confirmation.
5. When you create or modify a document, include a clickable link: [DocType Name](/app/doctype-slug/document-name)
6. Be concise but helpful. Explain what you did after each action.
7. If a permission error occurs, explain it clearly and suggest the user contact their administrator.
8. Format responses using markdown for readability.
9. When listing documents, present them in a clean table or list format.
10. If unsure about anything, ask for clarification rather than guessing."""


MAX_ROUNDS = 10


@frappe.whitelist()
def send_message(message: str, conversation_id: str = None, provider: str = None,
                 file_urls: str = None, confirmed_action: str = None):
    """Main chat endpoint.

    Args:
        message: User's text message
        conversation_id: Existing conversation ID (None for new)
        provider: Override AI provider (Claude/DeepSeek/GLM-5)
        file_urls: JSON array of Frappe file URLs to attach
        confirmed_action: JSON string of confirmed destructive action
    """
    try:
        # Parse file attachments
        files = []
        images = []
        file_text = ""
        if file_urls:
            from aeoru_ai.api.file_parser import parse_files
            parsed = parse_files(json.loads(file_urls) if isinstance(file_urls, str) else file_urls)
            file_text = parsed.get("text", "")
            images = parsed.get("images", [])

        # Build user message content
        user_content = message
        if file_text:
            user_content += f"\n\n--- Attached File Content ---\n{file_text}"

        # Get or create conversation
        conversation = _get_or_create_conversation(conversation_id, provider)

        # Save user message
        _save_message(conversation, "user", user_content)

        # Build message history
        history = _build_history(conversation)

        # Add images to last user message if present (Claude vision)
        if images and history:
            last_msg = history[-1]
            if last_msg.get("role") == "user":
                last_msg["images"] = images

        # Get provider settings
        settings = frappe.get_single("AI Assistant Settings")
        custom_prompt = settings.system_prompt or ""
        system_prompt = SYSTEM_PROMPT
        if custom_prompt:
            system_prompt += f"\n\nAdditional instructions:\n{custom_prompt}"

        ai_provider = get_provider(provider or conversation.provider)

        # Handle confirmed destructive action
        confirmed = False
        if confirmed_action:
            confirmed_data = json.loads(confirmed_action) if isinstance(confirmed_action, str) else confirmed_action
            confirmed = True

        # Agentic loop
        for round_num in range(MAX_ROUNDS):
            response = ai_provider.chat(
                messages=history,
                tools=ALL_TOOLS,
                system_prompt=system_prompt,
            )

            if not response.has_tool_calls:
                # Final answer
                _save_message(conversation, "assistant", response.text)
                conversation.save(ignore_permissions=True)
                frappe.db.commit()
                return {
                    "response": response.text,
                    "conversation_id": conversation.name,
                    "usage": response.usage,
                }

            # Process tool calls
            # Add assistant message with tool calls to history
            history.append(ai_provider.format_tool_calls_message(response))

            tool_results = []
            pending_confirmation = None

            for tool_call in response.tool_calls:
                # Check for destructive actions needing confirmation
                if tool_call.name in DESTRUCTIVE_TOOLS and not confirmed:
                    pending_confirmation = {
                        "tool_name": tool_call.name,
                        "arguments": tool_call.arguments,
                        "tool_call_id": tool_call.id,
                    }
                    # Return confirmation request with AI's text
                    confirmation_text = response.text or f"I need to perform a destructive action: **{tool_call.name}**. Please confirm."
                    _save_message(conversation, "assistant", confirmation_text)
                    conversation.save(ignore_permissions=True)
                    frappe.db.commit()
                    return {
                        "response": confirmation_text,
                        "conversation_id": conversation.name,
                        "pending_confirmation": pending_confirmation,
                        "usage": response.usage,
                    }

                result = execute_tool(tool_call, confirmed=confirmed)
                tool_results.append(result)

                # Check if tool returned confirmation_required
                try:
                    result_data = json.loads(result.content)
                    if isinstance(result_data, dict) and result_data.get("status") == "confirmation_required":
                        pending_confirmation = {
                            "tool_name": tool_call.name,
                            "arguments": tool_call.arguments,
                            "tool_call_id": tool_call.id,
                        }
                        _save_message(conversation, "assistant", result_data["message"])
                        conversation.save(ignore_permissions=True)
                        frappe.db.commit()
                        return {
                            "response": result_data["message"],
                            "conversation_id": conversation.name,
                            "pending_confirmation": pending_confirmation,
                        }
                except (json.JSONDecodeError, KeyError):
                    pass

                # Add tool result to history
                history.append(ai_provider.format_tool_result(result))

            # Reset confirmed after first successful round
            confirmed = False

        # Max rounds reached
        fallback = "I wasn't able to complete this request within the allowed steps. Please try rephrasing or breaking it into smaller requests."
        _save_message(conversation, "assistant", fallback)
        conversation.save(ignore_permissions=True)
        frappe.db.commit()
        return {
            "response": fallback,
            "conversation_id": conversation.name,
        }

    except Exception as e:
        frappe.log_error(f"AI Chat Error: {str(e)}", "AI Assistant")
        return {
            "response": f"An error occurred: {str(e)}",
            "error": True,
        }


@frappe.whitelist(allow_guest=False)
def is_enabled():
    """Check if AI Assistant is enabled. Called by frontend FAB."""
    try:
        settings = frappe.get_single("AI Assistant Settings")
        return bool(settings.enabled)
    except Exception:
        return False


@frappe.whitelist()
def get_conversations():
    """Get all conversations for the current user."""
    conversations = frappe.get_list(
        "AI Conversation",
        filters={"user": frappe.session.user, "is_active": 1},
        fields=["name", "title", "provider", "modified"],
        order_by="modified desc",
        limit_page_length=50,
    )
    return conversations


@frappe.whitelist()
def get_conversation_messages(conversation_id: str):
    """Get all messages for a conversation."""
    conv = frappe.get_doc("AI Conversation", conversation_id)

    # Permission check
    if conv.user != frappe.session.user and "System Manager" not in frappe.get_roles():
        frappe.throw("You don't have permission to view this conversation.")

    messages = []
    for msg in conv.messages:
        messages.append({
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.timestamp,
        })

    return messages


@frappe.whitelist()
def delete_conversation(conversation_id: str):
    """Soft-delete a conversation."""
    conv = frappe.get_doc("AI Conversation", conversation_id)
    if conv.user != frappe.session.user and "System Manager" not in frappe.get_roles():
        frappe.throw("You don't have permission to delete this conversation.")

    conv.is_active = 0
    conv.save(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "deleted"}


def _get_or_create_conversation(conversation_id: str = None, provider: str = None):
    """Get existing or create new conversation."""
    if conversation_id:
        conv = frappe.get_doc("AI Conversation", conversation_id)
        if conv.user != frappe.session.user:
            frappe.throw("You don't have permission to access this conversation.")
        return conv

    settings = frappe.get_single("AI Assistant Settings")
    conv = frappe.new_doc("AI Conversation")
    conv.user = frappe.session.user
    conv.provider = provider or settings.default_provider
    conv.title = "New Conversation"
    conv.insert(ignore_permissions=True)
    frappe.db.commit()
    return conv


def _save_message(conversation, role: str, content: str):
    """Append a message to the conversation."""
    conversation.append("messages", {
        "role": role,
        "content": content,
        "timestamp": datetime.now(),
    })

    # Auto-title from first user message
    if role == "user" and conversation.title == "New Conversation":
        conversation.title = content[:100] if len(content) > 100 else content


def _build_history(conversation) -> list:
    """Build message history from conversation document."""
    history = []
    for msg in conversation.messages:
        if msg.role in ("user", "assistant", "system"):
            history.append({
                "role": msg.role,
                "content": msg.content or "",
            })
    return history
