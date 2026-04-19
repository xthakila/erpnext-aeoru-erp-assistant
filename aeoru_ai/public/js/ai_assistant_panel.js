/**
 * AI Assistant Panel
 * Main chat panel with message area, input, file upload, and confirmation
 */
class AIAssistantPanel {
    constructor() {
        this.panelEl = null;
        this.messagesEl = null;
        this.inputEl = null;
        this.sendBtn = null;
        this.conversationId = null;
        this.pendingConfirmation = null;
        this.isLoading = false;
        this.provider = null;
        this.confirmationBarEl = null;
    }

    /**
     * Create and mount the panel DOM
     */
    mount() {
        if (this.panelEl) return;

        this.panelEl = document.createElement('div');
        this.panelEl.className = 'ai-assistant-panel';
        this.panelEl.innerHTML = this._getTemplate();

        document.body.appendChild(this.panelEl);

        // Cache element references
        this.messagesEl = this.panelEl.querySelector('.ai-messages-area');
        this.inputEl = this.panelEl.querySelector('.ai-input-textarea');
        this.sendBtn = this.panelEl.querySelector('.btn-send');

        this._bindEvents();
        this._showEmptyState();
    }

    /**
     * Show/hide the panel
     */
    toggle() {
        if (!this.panelEl) this.mount();
        this.panelEl.classList.toggle('visible');
        if (this.panelEl.classList.contains('visible')) {
            this.inputEl.focus();
        }
    }

    show() {
        if (!this.panelEl) this.mount();
        this.panelEl.classList.add('visible');
        this.inputEl.focus();
    }

    hide() {
        if (this.panelEl) {
            this.panelEl.classList.remove('visible');
        }
    }

    isVisible() {
        return this.panelEl && this.panelEl.classList.contains('visible');
    }

    /**
     * Send a message to the AI
     */
    async sendMessage(text, fileUrls = null) {
        if (!text?.trim() && !fileUrls) return;
        if (this.isLoading) return;

        const message = text.trim();
        this.inputEl.value = '';
        this._autoResize();

        // Show user message
        this._clearEmptyState();
        this._appendMessage('user', message);

        // Show typing indicator
        this.isLoading = true;
        this.sendBtn.disabled = true;
        const typingEl = AIAssistantMessage.createTypingIndicator();
        this.messagesEl.appendChild(typingEl);
        this._scrollToBottom();

        try {
            const args = {
                message: message,
                conversation_id: this.conversationId || undefined,
                provider: this.provider || undefined,
            };

            if (fileUrls) {
                args.file_urls = JSON.stringify(fileUrls);
            }

            if (this.pendingConfirmation) {
                args.confirmed_action = JSON.stringify(this.pendingConfirmation);
                this.pendingConfirmation = null;
                this._removeConfirmationBar();
            }

            const response = await frappe.xcall('aeoru_ai.api.chat.send_message', args);

            // Remove typing indicator
            if (typingEl.parentNode) {
                typingEl.parentNode.removeChild(typingEl);
            }

            if (response.error) {
                this._appendMessage('assistant', `Error: ${response.response}`);
            } else {
                // Update conversation ID
                if (response.conversation_id) {
                    this.conversationId = response.conversation_id;
                }

                // Show assistant response
                if (response.response) {
                    this._appendMessage('assistant', response.response);
                }

                // Handle pending confirmation
                if (response.pending_confirmation) {
                    this._showConfirmationBar(response.pending_confirmation);
                }
            }
        } catch (err) {
            if (typingEl.parentNode) {
                typingEl.parentNode.removeChild(typingEl);
            }
            this._appendMessage('assistant', `Error: ${err.message || 'Something went wrong'}`);
            console.error('AI Assistant error:', err);
        } finally {
            this.isLoading = false;
            this.sendBtn.disabled = false;
            this._scrollToBottom();
        }
    }

    /**
     * Start a new conversation
     */
    newConversation() {
        this.conversationId = null;
        this.pendingConfirmation = null;
        this._removeConfirmationBar();
        if (this.messagesEl) {
            this.messagesEl.innerHTML = '';
        }
        this._showEmptyState();
    }

    /**
     * Load an existing conversation
     */
    async loadConversation(conversationId) {
        try {
            const messages = await frappe.xcall(
                'aeoru_ai.api.chat.get_conversation_messages',
                { conversation_id: conversationId }
            );

            this.conversationId = conversationId;
            this.messagesEl.innerHTML = '';
            this._clearEmptyState();

            messages.forEach(msg => {
                if (msg.role === 'user' || msg.role === 'assistant') {
                    this._appendMessage(msg.role, msg.content);
                }
            });

            this._scrollToBottom();
        } catch (err) {
            frappe.show_alert({ message: `Error loading conversation: ${err.message}`, indicator: 'red' });
        }
    }

    // -- Private Methods --

    _getTemplate() {
        return `
            <div class="ai-panel-header">
                <span class="title">AI Assistant</span>
                <div class="header-actions">
                    <select class="provider-select">
                        <option value="">Default</option>
                        <option value="Claude">Claude</option>
                        <option value="Claude Code">Claude Code</option>
                        <option value="DeepSeek">DeepSeek</option>
                        <option value="GLM-5">GLM-5</option>
                    </select>
                    <button class="btn-new-chat" title="New conversation" style="background:none;border:none;color:white;cursor:pointer;font-size:16px;opacity:0.8;">
                        +
                    </button>
                    <button class="btn-close-panel" title="Close">&times;</button>
                </div>
            </div>
            <div class="ai-messages-area"></div>
            <div class="ai-input-area">
                <textarea class="ai-input-textarea" placeholder="Ask anything about your ERPNext data..." rows="1"></textarea>
                <div class="input-actions">
                    <button class="btn-attach" title="Attach file">&#128206;</button>
                    <button class="btn-send" title="Send">&#10148;</button>
                </div>
            </div>
        `;
    }

    _bindEvents() {
        // Close button
        this.panelEl.querySelector('.btn-close-panel').addEventListener('click', () => this.hide());

        // New chat
        this.panelEl.querySelector('.btn-new-chat').addEventListener('click', () => this.newConversation());

        // Provider selector
        this.panelEl.querySelector('.provider-select').addEventListener('change', (e) => {
            this.provider = e.target.value || null;
        });

        // Send button
        this.sendBtn.addEventListener('click', () => this.sendMessage(this.inputEl.value));

        // Enter to send (Shift+Enter for newline)
        this.inputEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage(this.inputEl.value);
            }
        });

        // Auto-resize textarea
        this.inputEl.addEventListener('input', () => this._autoResize());

        // File upload
        this.panelEl.querySelector('.btn-attach').addEventListener('click', () => this._handleFileUpload());
    }

    _appendMessage(role, content) {
        const messageEl = AIAssistantMessage.render(role, content);
        this.messagesEl.appendChild(messageEl);
        this._scrollToBottom();
    }

    _scrollToBottom() {
        requestAnimationFrame(() => {
            this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
        });
    }

    _autoResize() {
        this.inputEl.style.height = 'auto';
        this.inputEl.style.height = Math.min(this.inputEl.scrollHeight, 100) + 'px';
    }

    _showEmptyState() {
        if (this.messagesEl.querySelector('.ai-empty-state')) return;
        const empty = document.createElement('div');
        empty.className = 'ai-empty-state';
        empty.innerHTML = `
            <div class="icon">&#129302;</div>
            <div class="title">AI Assistant</div>
            <div class="subtitle">
                Ask me anything about your ERPNext data.<br>
                I can create, read, update, and delete documents for you.
            </div>
        `;
        this.messagesEl.appendChild(empty);
    }

    _clearEmptyState() {
        const empty = this.messagesEl.querySelector('.ai-empty-state');
        if (empty) empty.remove();
    }

    _showConfirmationBar(confirmation) {
        this._removeConfirmationBar();

        this.confirmationBarEl = AIAssistantMessage.createConfirmationBar(
            confirmation,
            () => {
                // Confirm action
                this.pendingConfirmation = confirmation;
                this.sendMessage('Yes, confirmed.');
            },
            () => {
                // Cancel action
                this.pendingConfirmation = null;
                this._removeConfirmationBar();
                this._appendMessage('assistant', 'Action cancelled.');
            }
        );

        // Insert before input area
        const inputArea = this.panelEl.querySelector('.ai-input-area');
        this.panelEl.insertBefore(this.confirmationBarEl, inputArea);
    }

    _removeConfirmationBar() {
        if (this.confirmationBarEl && this.confirmationBarEl.parentNode) {
            this.confirmationBarEl.parentNode.removeChild(this.confirmationBarEl);
            this.confirmationBarEl = null;
        }
    }

    _handleFileUpload() {
        new frappe.ui.FileUploader({
            as_dataurl: false,
            allow_multiple: true,
            on_success: (file_doc) => {
                const url = file_doc.file_url;
                this.sendMessage(`[Attached file: ${file_doc.file_name}]`, [url]);
            }
        });
    }
}
