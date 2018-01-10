#
# Web Debranding by Aqua-Giraffe
#

from openerp import models, fields, api, _, SUPERUSER_ID, tools
from openerp.tools.safe_eval import safe_eval
from lxml import etree, html


class web_debranding_config_settings(models.TransientModel):
	_name = 'web.debranding.config.settings'
	_inherit = 'res.config.settings'
	
	name = fields.Char(string="Software Name", required=True)
	title = fields.Char(string="Software Title", required=True)
	favicon_url = fields.Char(string="Favicon URL", required=True)
	
	@api.model
	def get_default_name(self, fields):
		name = False
		if 'name' in fields:
			name = self.env['ir.config_parameter'].sudo().get_param('web_debranding.new_name')
		return {'name': name}
	
	@api.multi
	def set_name(self):
		for config in self:
			self.env['ir.config_parameter'].sudo().set_param('web_debranding.new_name', config.name)
	
	@api.model
	def get_default_title(self, fields):
		title = False
		if 'title' in fields:
			title = self.env['ir.config_parameter'].sudo().get_param('web_debranding.new_title')
		return {'title': title}
	
	@api.multi
	def set_title(self):
		for config in self:
			self.env['ir.config_parameter'].sudo().set_param('web_debranding.new_title', config.title)
			
			web_layout = self.env['ir.ui.view'].search([('name','ilike','Rebranding Web layout'),('mode','=','extension')])
			if web_layout:
				xml_data = web_layout.arch_base
				node = etree.fromstring(xml_data)
				title = node.xpath('//title')
				title[0].text = config.name
				web_layout.arch_base = html.tostring(node)
	
	@api.model
	def get_default_favicon_url(self, fields):
		favicon_url = False
		if 'favicon_url' in fields:
			favicon_url = self.env['ir.config_parameter'].sudo().get_param('web_debranding.favicon_url')
		return {'favicon_url': favicon_url}
	
	@api.multi
	def set_favicon_url(self):
		for config in self:
			self.env['ir.config_parameter'].sudo().set_param('web_debranding.favicon_url', config.favicon_url)