/**
 * Claude Code Terminal
 * Opens a real interactive terminal (via ttyd) in an iframe for Claude Code CLI management.
 * Includes quick-action buttons for common operations and a native terminal experience.
 */
window.ClaudeTerminal = class ClaudeTerminal {
    constructor() {
        this.dialog = null;
        this.ttydPort = 7681;
    }

    /**
     * Open the terminal dialog with ttyd iframe
     */
    open() {
        if (this.dialog) {
            this.dialog.show();
            return;
        }

        this.dialog = new frappe.ui.Dialog({
            title: 'Claude Code Terminal',
            size: 'extra-large',
            minimizable: true,
        });

        // Build terminal DOM
        const container = this._buildDOM();
        this.dialog.$body.empty().append(container);
        this.dialog.$wrapper.find('.modal-dialog').css('max-width', '960px');
        this.dialog.$wrapper.find('.modal-body').css('padding', '0');

        this._bindEvents();
        this.dialog.show();
    }

    close() {
        if (this.dialog) this.dialog.hide();
    }

    _buildDOM() {
        const container = document.createElement('div');
        container.className = 'cc-terminal';

        // Toolbar
        const toolbar = document.createElement('div');
        toolbar.className = 'cc-terminal-toolbar';

        const buttons = [
            { cls: 'btn btn-xs btn-default cc-btn-check', text: 'Check Auth', dot: true },
            { cls: 'btn btn-xs btn-primary cc-btn-login', text: 'Login' },
            { cls: 'btn btn-xs btn-default cc-btn-version', text: 'Version' },
            { cls: 'btn btn-xs btn-default cc-btn-reload', text: 'Reload', style: 'margin-left:auto' },
        ];

        buttons.forEach(b => {
            const btn = document.createElement('button');
            btn.className = b.cls;
            if (b.dot) {
                const dot = document.createElement('span');
                dot.className = 'cc-status-dot';
                btn.appendChild(dot);
                btn.appendChild(document.createTextNode(' ' + b.text));
            } else {
                btn.textContent = b.text;
            }
            if (b.style) btn.style.cssText = b.style;
            toolbar.appendChild(btn);
        });

        // Help text
        const help = document.createElement('div');
        help.className = 'cc-terminal-help';
        help.textContent = 'Run: claude → /login → paste code. Or type any claude command.';

        // ttyd iframe
        const iframe = document.createElement('iframe');
        iframe.className = 'cc-ttyd-frame';
        iframe.src = window.location.protocol + '//' + window.location.hostname + ':' + this.ttydPort;
        iframe.setAttribute('allow', 'clipboard-read; clipboard-write');

        container.appendChild(toolbar);
        container.appendChild(help);
        container.appendChild(iframe);

        return container;
    }

    _bindEvents() {
        const $body = this.dialog.$body;

        $body.find('.cc-btn-check').on('click', async () => {
            try {
                const result = await frappe.xcall('aeoru_ai.api.claude_cli.check_auth');
                const dot = $body.find('.cc-status-dot');
                if (result.authenticated) {
                    dot.css('background', '#22c55e');
                    frappe.show_alert({ message: 'Authenticated' + (result.account ? ' as ' + result.account : ''), indicator: 'green' });
                } else {
                    dot.css('background', '#ef4444');
                    frappe.show_alert({ message: 'Not authenticated', indicator: 'red' });
                }
            } catch (err) {
                frappe.show_alert({ message: 'Error: ' + err.message, indicator: 'red' });
            }
        });

        $body.find('.cc-btn-login').on('click', () => {
            // Focus the iframe and send keystrokes for /login
            const iframe = $body.find('.cc-ttyd-frame')[0];
            if (iframe) iframe.focus();
            frappe.show_alert({ message: 'Type /login in the terminal below, then paste the auth code.', indicator: 'blue' });
        });

        $body.find('.cc-btn-version').on('click', async () => {
            try {
                const result = await frappe.xcall('aeoru_ai.api.claude_cli.get_version');
                frappe.show_alert({ message: 'Claude Code ' + (result.version || 'unknown'), indicator: 'green' });
            } catch (err) {
                frappe.show_alert({ message: 'Error: ' + err.message, indicator: 'red' });
            }
        });

        $body.find('.cc-btn-reload').on('click', () => {
            const iframe = $body.find('.cc-ttyd-frame')[0];
            if (iframe) {
                iframe.src = iframe.src;
            }
        });

        // Check auth status on open
        $body.find('.cc-btn-check').trigger('click');
    }
};

// Global instance — always use latest class definition
window.claudeTerminal = new window.ClaudeTerminal();
