/**
 * AI Assistant Message Renderer
 * Renders AI messages with markdown, document links, and code highlighting
 */
class AIAssistantMessage {
    /**
     * Render a message bubble
     * @param {string} role - 'user' or 'assistant'
     * @param {string} content - Message content (may contain markdown)
     * @returns {HTMLElement} Message element
     */
    static render(role, content) {
        const wrapper = document.createElement('div');
        wrapper.className = `ai-message ${role}`;

        if (role === 'assistant') {
            wrapper.innerHTML = AIAssistantMessage.renderMarkdown(content);
            AIAssistantMessage.enhanceLinks(wrapper);
        } else {
            wrapper.textContent = content;
        }

        return wrapper;
    }

    /**
     * Render markdown content using Frappe's markdown renderer
     * @param {string} text - Markdown text
     * @returns {string} HTML string
     */
    static renderMarkdown(text) {
        if (!text) return '';

        try {
            // Use Frappe's built-in markdown renderer
            if (frappe.markdown) {
                return frappe.markdown(text);
            }
        } catch (e) {
            // Fallback: basic markdown
        }

        return AIAssistantMessage.basicMarkdown(text);
    }

    /**
     * Basic markdown fallback if Frappe's renderer isn't available
     * @param {string} text
     * @returns {string}
     */
    static basicMarkdown(text) {
        let html = text;

        // Escape HTML
        html = html.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

        // Code blocks
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>');

        // Inline code
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Bold
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Italic
        html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

        // Links
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');

        // Line breaks
        html = html.replace(/\n/g, '<br>');

        return html;
    }

    /**
     * Convert ERPNext document references to clickable links
     * @param {HTMLElement} element
     */
    static enhanceLinks(element) {
        // Find document reference patterns like [Customer Name](/app/customer/CUST-001)
        // These are already handled by markdown, but enhance with Frappe routing
        const links = element.querySelectorAll('a[href^="/app/"]');
        links.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                frappe.set_route(link.getAttribute('href'));
            });
        });
    }

    /**
     * Create typing indicator element
     * @returns {HTMLElement}
     */
    static createTypingIndicator() {
        const wrapper = document.createElement('div');
        wrapper.className = 'ai-typing-indicator';
        wrapper.innerHTML = `
            <div class="dot"></div>
            <div class="dot"></div>
            <div class="dot"></div>
        `;
        return wrapper;
    }

    /**
     * Create confirmation bar element
     * @param {Object} confirmation - {tool_name, arguments}
     * @param {Function} onConfirm - Callback when confirmed
     * @param {Function} onCancel - Callback when cancelled
     * @returns {HTMLElement}
     */
    static createConfirmationBar(confirmation, onConfirm, onCancel) {
        const bar = document.createElement('div');
        bar.className = 'ai-confirmation-bar';

        const toolName = confirmation.tool_name.replace(/_/g, ' ');
        const doctype = confirmation.arguments?.doctype || '';
        const name = confirmation.arguments?.name || '';

        bar.innerHTML = `
            <span class="confirm-text">
                Confirm <strong>${toolName}</strong>${doctype ? ` on ${doctype}` : ''}${name ? ` "${name}"` : ''}?
            </span>
            <div class="confirm-actions">
                <button class="btn-cancel-action">Cancel</button>
                <button class="btn-confirm">Confirm</button>
            </div>
        `;

        bar.querySelector('.btn-confirm').addEventListener('click', () => onConfirm());
        bar.querySelector('.btn-cancel-action').addEventListener('click', () => onCancel());

        return bar;
    }
}
