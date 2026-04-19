frappe.ui.form.on('AI Assistant Settings', {
    refresh: function(frm) {
        // Add "Open Terminal" button in the Claude Code section
        frm.add_custom_button('Open Claude Code Terminal', function() {
            if (window.claudeTerminal) {
                window.claudeTerminal.open();
            } else {
                frappe.show_alert({ message: 'Terminal not loaded. Please refresh the page.', indicator: 'red' });
            }
        }, 'Claude Code');
    }
});
