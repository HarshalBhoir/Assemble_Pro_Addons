odoo.define('web_debranding.title', function(require) {

var core = require('web.core');
var QWeb = core.qweb;
var _t = core._t;
var WebClient = require('web.WebClient');
var Model = require('web.DataModel');
var Announcement = require('mail.announcement');


//Title
WebClient.include({
	init: function(parent, client_options) {
		this._super(parent, client_options);
		this.set('title_part', {"zopenerp": ''});
		this.get_title_part();
	},
	get_title_part: function(){
		//if (!openerp.session.db)
		//	return;
		var self = this;
		var model = new Model("ir.config_parameter");
	
		var r = model.query(['value'])
			.filter([['key', '=', 'web_debranding.new_title']])
			.limit(1)
			.all().then(function (data) {
				if (!data.length)
					return;
				title_part = data[0].value;
				title_part = title_part.trim();
				self.set('title_part', {"zopenerp": title_part});
				});
	},
	show_annoucement_bar: function() {},
});


// Admin Dashboard
var dashboard = require('web_settings_dashboard');
dashboard.Dashboard.include({
	start: function(){
		this.all_dashboards  = _.without(this.all_dashboards, 'planner', 'apps', 'share');
		this.$('.o_web_settings_dashboard_apps').parent().remove();
		this.$('.o_web_settings_dashboard_planner').parent().remove();
		this.$('.o_web_settings_dashboard_share').parent().remove();
		return this._super();
	},
});


// Dialog Box
var CrashManager = require('web.CrashManager');
CrashManager.include({
	init: function () {
		this._super();
		var self = this;
		var model = new Model("ir.config_parameter");
		self.debranding_new_name = _t('Software');
		//if (!openerp.session.db)
		//	return;
		var r = model.query(['value'])
			.filter([['key', '=', 'web_debranding.new_name']])
			.limit(1)
			.all().then(function (data) {
				if (!data.length)
					return;
				self.debranding_new_name = data[0].value;
			});
	},
});


// Dialog Box
var Dialog = require('web.Dialog');
Dialog.include({
	init: function (parent, options) {
		var debranding_new_name = ' ';
		// TODO find another way to get debranding_new_name
		if (parent && parent.debranding_new_name){
			debranding_new_name = parent.debranding_new_name;
		}
		options = options || {};
		if (options['title']){
			var title = options['title'].replace(/Odoo/ig, debranding_new_name);
			options['title'] = title;
		} else {
			options['title'] = debranding_new_name;
		}
		if (options.$content){
			if (!(options.$content instanceof $)){
				options.$content = $(options.$content)
			}
			var content_html = options.$content.html().replace(/Odoo/ig, debranding_new_name);
			options.$content.html(content_html);
		}
		this._super(parent, options);
	},
});


// Hide Enterprise links
var UpgradeBoolean = core.form_widget_registry.get('upgrade_boolean');
//var UpgradeRadio = core.form_widget_registry.get('upgrade_radio');

var include = {
	'start': function(){
		var $el = this.$el;
		var i = 1;
		var MAX = 10;
		while (true){
			if (i > MAX)
				break;
			i++;
			if ($el.prop("tagName") == 'TR'){
				$el.hide();
				break;
			}
			$el = $el.parent();
			if (!$el)
				break;
		}
	},
	'on_click_input':function(){
	}
};

//UpgradeRadio.include(include);
UpgradeBoolean.include(include);

});