# Copyright (c) 2013, Saif Ur Rehman and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cint, flt, cstr, get_first_day, get_last_day, getdate, get_fullname
import datetime


def execute(filters=None):
	filters = frappe._dict(filters)

	columns = get_colums(filters)
	data = get_data(filters)
	return columns, data


def get_data(filters):
	data_map = {}

	plan_conditions = get_conditions(filters, "Monthly Visit Plan")
	plan_data = frappe.db.sql("""
		select p.year, p.month as month_long, p.user, v.party_type, v.party, v.party_name, v.planned_visits
		from `tabCustomer Visits` v
		inner join `tabMonthly Visit Plan` p on p.name = v.parent
		where p.docstatus = 1 {0}
	""".format(plan_conditions), filters, as_dict=1)

	visit_conditions = get_conditions(filters, "Activity Form")
	visit_data = frappe.db.sql("""
		select a.date, a.user, a.activity_with as party_type, a.party_name as party, a.customer_name as party_name
		from `tabActivity Form` a
		where a.docstatus = 1 and ifnull(a.activity_with, '') != '' and ifnull(a.party_name, '') != ''
			and a.planned_activity = 'Planned' {0}
	""".format(visit_conditions), filters, as_dict=1)

	lead_list = list(set([d.party for d in plan_data if d.party_type == "Lead"] + [d.party for d in visit_data if d.party_type == "Lead"]))
	lead_to_customer_map = get_lead_to_customer_map(lead_list)

	# prepare plan data
	for d in plan_data:
		set_converted_customer(d, lead_to_customer_map)
		d.year = cint(d.year)
		d.month = datetime.datetime.strptime(d.month_long, "%B").month
		d.from_date = datetime.date(d.year, d.month, 1)
		d.to_date = get_last_day(d.from_date)
		d.period = "{0} {1}".format(d.month_long, d.year)

	# prepare visit data
	for d in visit_data:
		set_converted_customer(d, lead_to_customer_map)
		d.date = getdate(d.date)
		d.year = d.date.year
		d.month = d.date.month
		d.month_long = d.date.strftime("%B")
		d.from_date = get_first_day(d.date)
		d.to_date = get_last_day(d.from_date)
		d.period = "{0} {1}".format(d.month_long, d.year)

	# add plan data
	for d in plan_data:
		key = get_key(d)
		if key not in data_map:
			data_map[key] = d.copy()
			data_map[key].planned_visits = 0
			data_map[key].actual_visits = 0

		row = data_map[key]
		row.planned_visits += d.planned_visits

	# add visit data
	for d in visit_data:
		key = get_key(d)
		if key not in data_map:
			data_map[key] = d.copy()
			data_map[key].planned_visits = 0
			data_map[key].actual_visits = 0

		row = data_map[key]
		row.actual_visits += 1

	data = sorted(data_map.values(), key=lambda d: (d.from_date, d.user, d.party_type, d.party))

	# post process data
	for d in data:
		postprocess_data(d)

	# total row
	if filters.show_total_row:
		total_row = frappe._dict()
		total_row.period = '<b>Total</b>'

		sum_fields = ['actual_visits', 'planned_visits']
		for f in sum_fields:
			total_row[f] = 0

		for d in data:
			for f in sum_fields:
				total_row[f] += flt(d.get(f))

		postprocess_data(total_row)

		data.append(total_row)

	return data


def postprocess_data(d):
	if d.user:
		d.user_name = get_fullname(d.user)

	d.party_name = get_party_name(d)

	d.visit_variance = flt(d.actual_visits) - flt(d.planned_visits)

	if flt(d.planned_visits):
		d.completion_rate = flt(d.actual_visits) / flt(d.planned_visits)


def get_lead_to_customer_map(lead_list):
	lead_to_customer_map = {}

	if not lead_list:
		return lead_to_customer_map

	customer_data = frappe.db.sql("""
		select lead_name, name
		from `tabCustomer`
		where lead_name in %s
	""", [lead_list])

	for lead, customer in customer_data:
		lead_to_customer_map[lead] = customer

	return lead_to_customer_map


def set_converted_customer(d, lead_to_customer_map):
	if d.party_type == "Lead" and d.party in lead_to_customer_map:
		d.from_lead = d.party
		d.party_type = "Customer"
		d.party = lead_to_customer_map[d.party]


def get_conditions(filters, doctype):
	conditions = []

	filters.year = cint(filters.year)
	if filters.year:
		if doctype == "Monthly Visit Plan":
			conditions.append("p.year = %(year)s")
		elif doctype == "Activity Form":
			conditions.append("year(a.date) = %(year)s")

	if filters.month_long == 'Month':
		filters.month_long = ''

	if filters.month_long:
		filters.month = datetime.datetime.strptime(filters.month_long, "%B").month
		if doctype == "Monthly Visit Plan":
			conditions.append("p.month = %(month_long)s")
		elif doctype == "Activity Form":
			conditions.append("month(a.date) = %(month)s")

	if filters.user:
		if doctype == "Monthly Visit Plan":
			conditions.append("p.user = %(user)s")
		elif doctype == "Activity Form":
			conditions.append("a.user = %(user)s")

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

		party_condition = ""
		if doctype == "Monthly Visit Plan":
			party_condition = "(v.party_type = %(party_type)s and v.party = %(party)s)"
			if filters.other_party_type and filters.other_party:
				party_condition += " or (v.party_type = %(other_party_type)s and v.party = %(other_party)s)"
		elif doctype == "Activity Form":
			party_condition = "(a.activity_with = %(party_type)s and a.party_name = %(party)s)"
			if filters.party_type == "Customer" and filters.other_party_type and filters.other_party:
				party_condition += " or (a.activity_with = %(other_party_type)s and a.party_name = %(other_party)s)"

		if party_condition:
			conditions.append("({0})".format(party_condition))
	else:
		if filters.party_type:
			if doctype == "Monthly Visit Plan":
				conditions.append("v.party_type = %(party_type)s")
			elif doctype == "Activity Form":
				conditions.append("a.activity_with = %(party_type)s")

		if filters.party:
			if doctype == "Monthly Visit Plan":
				conditions.append("v.party = %(party)s")
			elif doctype == "Activity Form":
				conditions.append("a.party_name = %(party)s")

	condition_str = " and " + " and ".join(conditions) if conditions else ""
	return condition_str


def get_key(d):
	return d.year, d.month, d.user, cstr(d.party_type), cstr(d.party) or cstr(d.party_name), cint(bool(d.party))


def get_party_name(d):
	if d.party_type and d.party:
		if d.party_type == "Customer":
			return frappe.get_cached_value(d.party_type, d.party, 'customer_name')
		elif d.party_type == "Lead":
			company_name, lead_name = frappe.get_cached_value(d.party_type, d.party, ['company_name', 'lead_name'])
			return company_name or lead_name
	else:
		return d.get('party_name')


def get_colums(filters):
	return [
		{"label": _("Period"), "fieldname": "period", "fieldtype": "Data", "width": 90},
		{"label": _("Sales Person ID"), "fieldname": "user", "fieldtype": "Link", "options": "User", "width": 150},
		{"label": _("Sales Person Name"), "fieldname": "user_name", "fieldtype": "Data", "width": 150},
		{"label": _("Party Type"), "fieldname": "party_type", "fieldtype": "Data", "width": 80},
		{"label": _("Party"), "fieldname": "party", "fieldtype": "Dynamic Link", "options": "party_type", "width": 100},
		{"label": _("Party Name"), "fieldname": "party_name", "fieldtype": "Data", "width": 150},
		{"label": _("Planned Visits"), "fieldname": "planned_visits", "fieldtype": "Int", "width": 110},
		{"label": _("Actual Visits"), "fieldname": "actual_visits", "fieldtype": "Int", "width": 110},
		{"label": _("Visit Variance"), "fieldname": "visit_variance", "fieldtype": "Int", "width": 110},
		{"label": _("Completion Rate"), "fieldname": "completion_rate", "fieldtype": "Float", "width": 110},
		{"label": _("From Lead"), "fieldname": "from_lead", "fieldtype": "Link", "options": "Lead", "width": 100},
	]


@frappe.whitelist()
def get_years():
	plan_years = frappe.db.sql_list("""
		select distinct `year`
		from `tabMonthly Visit Plan`
		where docstatus = 1
	""")

	activity_years = frappe.db.sql_list("""
		select distinct YEAR(date)
		from `tabActivity Form`
		where docstatus = 1
	""")

	years = []
	for year in plan_years:
		if cint(year):
			years.append(cint(year))

	for year in activity_years:
		if cint(year):
			years.append(cint(year))

	years = list(set(years))
	years = sorted(years, reverse=True)

	return ['Year'] + years
