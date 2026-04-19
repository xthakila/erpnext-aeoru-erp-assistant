/**
 * AI Assistant - Entry Point
 * Creates the floating action button and lazy-initializes the chat panel.
 * Compatible with Frappe v15 (/app) and v16 (/desk).
 */
(function() {
    'use strict';

    let panel = null;
    let fabButton = null;
    let initialized = false;

    function createFAB() {
        if (fabButton) return;

        fabButton = document.createElement('button');
        fabButton.className = 'ai-assistant-fab';
        fabButton.textContent = '\u{1F916}';  // Robot face emoji
        fabButton.title = 'AI Assistant';

        fabButton.addEventListener('click', function() {
            if (!panel) {
                panel = new AIAssistantPanel();
                panel.mount();
            }
            panel.toggle();
            fabButton.classList.toggle('panel-open', panel.isVisible());
        });

        document.body.appendChild(fabButton);
    }

    function tryInit() {
        if (initialized) return;
        // Only init if user is logged in (not Guest)
        if (!frappe || !frappe.session || frappe.session.user === 'Guest') return;

        initialized = true;

        frappe.xcall('aeoru_ai.api.chat.is_enabled').then(function(enabled) {
            if (enabled) createFAB();
        }).catch(function() {
            // Settings not configured yet — show FAB anyway
            createFAB();
        });
    }

    // Strategy 1: Frappe v15 app_ready event
    if (typeof $ !== 'undefined') {
        $(document).on('app_ready', tryInit);
    }

    // Strategy 2: Frappe v16 — frappe.after_ajax or direct check
    if (typeof frappe !== 'undefined' && frappe.boot) {
        // Already loaded (v16 desk scripts run after boot)
        setTimeout(tryInit, 500);
    }

    // Strategy 3: Fallback — poll until frappe.session exists
    var pollCount = 0;
    var pollTimer = setInterval(function() {
        pollCount++;
        if (pollCount > 20) {
            clearInterval(pollTimer);
            return;
        }
        if (typeof frappe !== 'undefined' && frappe.session && frappe.session.user !== 'Guest') {
            clearInterval(pollTimer);
            tryInit();
        }
    }, 500);

    // Expose globally
    window.AIAssistant = {
        getPanel: function() { return panel; },
        show: function() {
            if (!panel) {
                panel = new AIAssistantPanel();
                panel.mount();
            }
            panel.show();
            if (fabButton) fabButton.classList.add('panel-open');
        },
        hide: function() {
            if (panel) panel.hide();
            if (fabButton) fabButton.classList.remove('panel-open');
        },
    };
})();
