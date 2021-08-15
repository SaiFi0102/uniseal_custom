// Copyright (c) 2016, Saif Ur Rehman and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Visit Productivity"] = {
	filters: [
		{
			label: __("Year"),
			fieldname: "year",
			fieldtype: "Select",
			options: ['Year'],
			default: 'Year'
		},
		{
			label: __("Month"),
			fieldname: "month_long",
			fieldtype: "Select",
			options: ['Month', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
				'October', 'November', 'December'],
			default: 'Month'
		},
		{
			label: __("Sales Person"),
			fieldname: "sales_person",
			fieldtype: "Link",
			options: "Sales Person",
		},
		{
			label: __("Party Type"),
			fieldname: "party_type",
			fieldtype: "Link",
			options: "DocType",
			get_query: function() {
				return {
					filters: {'name': ['in', ['Lead', 'Customer']]}
				};
			},
			on_change: function() {
				frappe.query_report.set_filter_value('party', "");
			}
		},
		{
			label: __("Party"),
			fieldname: "party",
			fieldtype: "Dynamic Link",
			options: "party_type",
		},
		{
			label: __("Show Total Row"),
			fieldname: "show_total_row",
			fieldtype: "Check",
			default: 1,
		},
	],

	onload: function() {
		return  frappe.call({
			method: "uniseal_custom.uniseal_custom.report.visit_productivity.visit_productivity.get_years",
			callback: function(r) {
				var year_filter = frappe.query_report.get_filter('year');
				year_filter.df.options = r.message;
				year_filter.refresh();
			}
		});
	}
};
