# Copyright (c) 2013, Saif Ur Rehman and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cint, flt, cstr, get_first_day, get_last_day, getdate, get_fullname
from uniseal_custom.uniseal_custom.report.visit_plan_completion_rate.visit_plan_completion_rate import get_key,\
	set_converted_customer, get_lead_to_customer_map, get_party_name
import datetime


def execute(filters=None):
	filters = frappe._dict(filters)

	columns = get_colums(filters)
	data = get_data(filters)
	return columns, data


def get_data(filters):
	data_map = {}

	visit_conditions = get_conditions(filters, "Activity Form")
	visit_data = frappe.db.sql("""
		select t.date, t.user, t.activity_with as party_type, t.party_name as party, t.customer_name as party_name
		from `tabActivity Form` t
		where t.docstatus = 1 and ifnull(activity_with, '') != '' and ifnull(party_name, '') != '' {0}
	""".format(visit_conditions), filters, as_dict=1)

	op_conditions = get_conditions(filters, "Opportunity")
	opp_data = frappe.db.sql("""
		select t.transaction_date as date, t.owner as user, opportunity_from as party_type, t.party_name as party,
			t.customer_name as party_name, t.opportunity_amount as total
		from `tabOpportunity` t
		where t.docstatus < 2 {0}
	""".format(op_conditions), filters, as_dict=1)

	qtn_conditions = get_conditions(filters, "Quotation")
	qtn_data = frappe.db.sql("""
		select t.transaction_date as date, t.owner as user, t.quotation_to as party_type, t.party_name as party,
			t.customer_name as party_name, t.grand_total_usd as total
		from `tabQuotation` t
		where t.docstatus = 1 {0}
	""".format(qtn_conditions), filters, as_dict=1)

	so_data = []
	if not filters.party_type or filters.party_type == "Customer":
		so_conditions = get_conditions(filters, "Sales Order")
		so_data = frappe.db.sql("""
			select t.transaction_date as date, t.owner as user, 'Customer' as party_type, t.customer as party,
				t.customer_name as party_name, t.grand_total_usd as total
			from `tabSales Order` t
			where t.docstatus = 1 {0}
		""".format(so_conditions), filters, as_dict=1)

	lead_list = list(set(
		[d.party for d in visit_data if d.party_type == "Lead"]
		+ [d.party for d in qtn_data if d.party_type == "Lead"]
		+ [d.party for d in so_data if d.party_type == "Lead"]
		+ [d.party for d in opp_data if d.party_type == "Lead"]
	))
	lead_to_customer_map = get_lead_to_customer_map(lead_list)

	# prepare data
	prepare_data(visit_data, lead_to_customer_map)
	prepare_data(opp_data, lead_to_customer_map)
	prepare_data(qtn_data, lead_to_customer_map)
	prepare_data(so_data, lead_to_customer_map)

	# add visit data
	for d in visit_data:
		row = get_row(d, data_map)
		row.actual_visits = flt(row.actual_visits) + 1

	# add opportunity data
	for d in opp_data:
		row = get_row(d, data_map)
		row.opportunities = flt(row.opportunities) + 1

	# add quotation data
	for d in qtn_data:
		row = get_row(d, data_map)
		row.quotations = flt(row.quotations) + 1
		row.quotation_total = flt(row.quotation_total) + flt(d.total)

	# add sales order data
	for d in so_data:
		row = get_row(d, data_map)
		row.sales_orders = flt(row.sales_orders) + 1
		row.sales_order_total = flt(row.sales_order_total) + flt(d.total)

	data = sorted(data_map.values(), key=lambda d: (d.from_date, d.user, cstr(d.party_type), cstr(d.party)))

	# post process data
	for d in data:
		postprocess_data(d)

	# total row
	if filters.show_total_row:
		total_row = frappe._dict()
		total_row.period = '<b>Total</b>'

		sum_fields = ['actual_visits', 'opportunities', 'quotations', 'sales_orders', 'quotation_total', 'sales_order_total']
		for f in sum_fields:
			total_row[f] = 0

		for d in data:
			for f in sum_fields:
				total_row[f] += flt(d.get(f))

		postprocess_data(total_row)

		data.append(total_row)

	return data


def prepare_data(data, lead_to_customer_map):
	for d in data:
		set_converted_customer(d, lead_to_customer_map)
		d.date = getdate(d.date)
		d.year = d.date.year
		d.month = d.date.month
		d.month_long = d.date.strftime("%B")
		d.from_date = get_first_day(d.date)
		d.to_date = get_last_day(d.from_date)
		d.period = "{0} {1}".format(d.month_long, d.year)


def get_row(d, data_map):
	key = get_key(d)
	if key not in data_map:
		data_map[key] = d.copy()
		data_map[key]['actual_visits'] = 0
		data_map[key]['opportunities'] = 0
		data_map[key]['quotations'] = 0
		data_map[key]['sales_orders'] = 0

		data_map[key]['sales_order_total'] = 0
		data_map[key]['quotation_total'] = 0

	return data_map[key]


def postprocess_data(d):
	if d.user:
		d.user_name = get_fullname(d.user)

	d.party_name = get_party_name(d)
	d.currency = 'USD'

	if flt(d.actual_visits):
		d.opportunity_per_visit = flt(d.opportunities) / flt(d.actual_visits)
		d.quotation_per_visit = flt(d.quotations) / flt(d.actual_visits)
		d.sales_order_per_visit = flt(d.sales_orders) / flt(d.actual_visits)
		d.so_value_per_visit = flt(d.sales_order_total) / flt(d.actual_visits)
		d.qtn_value_per_visit = flt(d.quotation_total) / flt(d.actual_visits)

	if flt(d.quotations):
		d.sales_order_per_quotation = flt(d.sales_orders) / flt(d.quotations)

	if flt(d.quotation_total):
		d.so_value_per_qtn_value = flt(d.sales_order_total) / flt(d.quotation_total)

def get_conditions(filters, doctype):
	conditions = []

	date_field = "t.date" if doctype == "Activity Form" else "transaction_date"

	party_type_fieldname = 't.party_type'
	party_fieldname = 't.party'
	if doctype == "Activity Form":
		party_type_fieldname = 't.activity_with'
		party_fieldname = 't.party_name'
	elif doctype == "Opportunity":
		party_type_fieldname = 't.opportunity_from'
		party_fieldname = 't.party_name'
	elif doctype == "Quotation":
		party_type_fieldname = 't.quotation_to'
		party_fieldname = 't.party_name'
	elif doctype == "Sales Order":
		party_type_fieldname = "'Customer'"
		party_fieldname = 't.customer'

	filters.year = cint(filters.year)
	if filters.year:
		conditions.append("year({0}) = %(year)s".format(date_field))

	if filters.month_long == 'Month':
		filters.month_long = ''

	if filters.month_long:
		filters.month = datetime.datetime.strptime(filters.month_long, "%B").month
		conditions.append("month({0}) = %(month)s".format(date_field))

	if filters.user:
		conditions.append("t.user = %(user)s")

	if filters.party_type and filters.party:
		if filters.party_type == "Lead":
			converted_customer = frappe.db.get_value("Customer", filters={"lead_name": filters.party})
			if converted_customer:
				filters.other_party_type = "Customer"
				filters.other_party = converted_customer

		elif filters.party_type == "Customer":
			from_lead = frappe.get_cached_value("Customer", filters.party, "lead_name")
			if from_lead:
				filters.other_party_type = "Lead"
				filters.other_party = from_lead

		party_condition = "({0} = %(party_type)s and {1} = %(party)s)".format(party_type_fieldname, party_fieldname)
		if filters.party_type == "Customer" and filters.other_party_type and filters.other_party:
			party_condition += " or ({0} = %(other_party_type)s and {1} = %(other_party)s)".format(party_type_fieldname, party_fieldname)

		if party_condition:
			conditions.append("({0})".format(party_condition))
	else:
		if filters.party_type:
			conditions.append("{0} = %(party_type)s".format(party_type_fieldname))

		if filters.party:
			conditions.append("{0} = %(party)s".format(party_fieldname))

	condition_str = " and " + " and ".join(conditions) if conditions else ""
	return condition_str


def get_colums(filters):
	return [
		{"label": _("Period"), "fieldname": "period", "fieldtype": "Data", "width": 90},
		{"label": _("Sales Person ID"), "fieldname": "user", "fieldtype": "Link", "options": "User", "width": 150},
		{"label": _("Sales Person Name"), "fieldname": "user_name", "fieldtype": "Data", "width": 150},
		{"label": _("Party Type"), "fieldname": "party_type", "fieldtype": "Data", "width": 80},
		{"label": _("Party"), "fieldname": "party", "fieldtype": "Dynamic Link", "options": "party_type", "width": 100},
		{"label": _("Party Name"), "fieldname": "party_name", "fieldtype": "Data", "width": 150},
		{"label": _("Visits"), "fieldname": "actual_visits", "fieldtype": "Int", "width": 70},
		{"label": _("Opportunities"), "fieldname": "opportunities", "fieldtype": "Int", "width": 90},
		{"label": _("Quotations"), "fieldname": "quotations", "fieldtype": "Int", "width": 90},
		{"label": _("Sales Orders"), "fieldname": "sales_orders", "fieldtype": "Int", "width": 90},
		{"label": _("Qtn Value"), "fieldname": "quotation_total", "fieldtype": "Currency", "options": "currency", "width": 90},
		{"label": _("SO Value"), "fieldname": "sales_order_total", "fieldtype": "Currency", "options": "currency", "width": 90},
		{"label": _("Opportunity/Visit"), "fieldname": "opportunity_per_visit", "fieldtype": "Float", "width": 125},
		{"label": _("Qtn/Visit"), "fieldname": "quotation_per_visit", "fieldtype": "Float", "width": 80},
		{"label": _("SO/Visit"), "fieldname": "sales_order_per_visit", "fieldtype": "Float", "width": 80},
		{"label": _("Qtn Value/Visit"), "fieldname": "qtn_value_per_visit", "fieldtype": "Currency", "options": "currency", "width": 110},
		{"label": _("SO Value/Visit"), "fieldname": "so_value_per_visit", "fieldtype": "Currency", "options": "currency", "width": 110},
		{"label": _("SO/Qtn"), "fieldname": "sales_order_per_quotation", "fieldtype": "Float", "width": 90},
		{"label": _("SO Value/Qtn Value"), "fieldname": "so_value_per_qtn_value", "fieldtype": "Float", "width": 140},
		{"label": _("From Lead"), "fieldname": "from_lead", "fieldtype": "Link", "options": "Lead", "width": 100},
	]


@frappe.whitelist()
def get_years():
	activity_years = frappe.db.sql_list("""
		select distinct YEAR(date)
		from `tabActivity Form`
		where docstatus = 1
		order by YEAR(date) desc
	""")

	return ['Year'] + activity_years
