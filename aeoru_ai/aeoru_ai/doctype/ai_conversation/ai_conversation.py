import frappe
from frappe.model.document import Document


class AIConversation(Document):
    def before_insert(self):
        if not self.user:
            self.user = frappe.session.user
        if not self.title:
            self.title = "New Conversation"
