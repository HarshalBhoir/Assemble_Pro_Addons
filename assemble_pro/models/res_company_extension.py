from openerp import models, fields, api, _

class res_company_extension(models.Model):
	_inherit = 'res.company'
	
	# customer_company_name = fields.Char(string="Customer Company Name")
	customer_company_name = fields.Many2one('res.partner', string="Customer Company Name")
	vendor_code = fields.Char(string="Vendor Code")
	vendor_number = fields.Char(string="Vendor Number")
	company_range = fields.Char(string="Range")
	division = fields.Char(string="Division")
	commissionrate = fields.Char(string="Commissionerate")
	sac_code = fields.Char(string='SAC Code')
	gstin_no = fields.Char(string='GSTIN No')