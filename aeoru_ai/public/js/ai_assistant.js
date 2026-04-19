/**
 * AI Assistant - Entry Point
 * Creates the floating action button and lazy-initializes the chat panel
 */
(function() {
    'use strict';

    let panel = null;
    let fabButton = null;

    function createFAB() {
        if (fabButton) return;

        fabButton = document.createElement('button');
        fabButton.className = 'ai-assistant-fab';
        fabButton.innerHTML = '&#129302;';  // Robot face emoji
        fabButton.title = 'AI Assistant';

        fabButton.addEventListener('click', () => {
            if (!panel) {
                panel = new AIAssistantPanel();
                panel.mount();
            }
            panel.toggle();
            fabButton.classList.toggle('panel-open', panel.isVisible());
        });

        document.body.appendChild(fabButton);
    }

    // Initialize when Frappe is ready
    $(document).on('app_ready', function() {
        // Check if AI Assistant is enabled via a quick settings check
        frappe.xcall('aeoru_ai.api.chat.is_enabled').then((enabled) => {
            if (enabled) {
                createFAB();
            }
        }).catch(() => {
            // If the endpoint doesn't exist yet or errors, still show FAB
            // (settings might not be configured yet)
            createFAB();
        });
    });

    // Expose globally for debugging
    window.AIAssistant = {
        getPanel: () => panel,
        show: () => {
            if (!panel) {
                panel = new AIAssistantPanel();
                panel.mount();
            }
            panel.show();
            if (fabButton) fabButton.classList.add('panel-open');
        },
        hide: () => {
            if (panel) panel.hide();
            if (fabButton) fabButton.classList.remove('panel-open');
        },
    };
})();
