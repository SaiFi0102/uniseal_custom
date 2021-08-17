from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		{
			"label": _("Uniseal Custom Reports"),
			"icon": "fa fa-star",
			"items": [
				{
					"type": "report",
					"is_query_report": True,
					"name": "Visit Plan Completion Rate",
					"doctype": "Monthly Visit Plan",
				},
				{
					"type": "report",
					"is_query_report": True,
					"name": "Visit Productivity",
					"doctype": "Activity Form",
				},
			]
		},
	]
