from openerp import models, fields, api, _

class res_country_extension(models.Model):
	_inherit = 'res.country'
	
	active = fields.Boolean(string="Active", default=True) 
	
class res_country_state_extension(models.Model):
    _inherit = 'res.country.state'
    
    active = fields.Boolean(string="Active", default=True) 
