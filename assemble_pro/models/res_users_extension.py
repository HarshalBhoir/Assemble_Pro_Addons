from openerp import models, fields, api, _

class res_users_extension(models.Model):
	_inherit = 'res.users'
	
	code = fields.Char(string="Assembler Code")
