import frappe
from frappe import _


def validate_converted_lead(lead_name, row_idx=None):
	converted_customer = frappe.db.get_value("Customer", filters={"lead_name": lead_name})
	if converted_customer:
		row_msg = _("Row #{0}: ").format(row_idx) if row_idx else ""
		frappe.throw(_("{0}Cannot select Lead {1} because it is already converted to customer. Please use Customer {2}")
			.format(row_msg, frappe.bold(lead_name), frappe.bold(converted_customer)))


def validate_visit_plan_lead(self, method):
	for d in self.customer_visits_plan:
		if d.party_type == "Lead" and d.party:
			validate_converted_lead(d.party, d.idx)


def validate_activity_form_lead(self, method):
	if self.activity_with == "Lead" and self.party_name:
		validate_converted_lead(self.party_name)


def validate_opportunity_lead(self, method):
	if self.opportunity_from == "Lead" and self.party_name:
		validate_converted_lead(self.party_name)


def validate_quotation_lead(self, method):
	if self.quotation_to == "Lead" and self.party_name:
		validate_converted_lead(self.party_name)
