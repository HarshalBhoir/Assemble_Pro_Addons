from openerp import models, fields, api, _, SUPERUSER_ID, tools
from openerp.addons import base
from datetime import datetime
from dateutil import relativedelta

class res_partner_extension(models.Model):
	_inherit = 'res.partner'
	
	lead_time = fields.Float(string='Lead Time')
	travel_time = fields.Float(string='Travel Time')
	supplier_ref = fields.Text(string="Supplier Ref")
	delivery_terms = fields.Text()
	mot = fields.Char(string="MOT", track_visibility='always')
	freight = fields.Char(string="Freight", track_visibility='always')
	vehicle_no = fields.Char(string="Vehicle No.", track_visibility='always')
	transporter = fields.Char(string="Transporter", track_visibility='always')
	packaging_forwarding = fields.Char(string="Packaging & Forwarding", track_visibility='always')
	tax_detail2 = fields.One2many('tax.extension','tax_detail_id',string="Tax Details")
	ecc_no = fields.Char(string='E.C.C No')
	vat_no = fields.Char(string='VAT TIN')
	cst_no = fields.Char(string='CST TIN')
	service_tax_no = fields.Char(string='Service Tax Code No')
	pan_no = fields.Char(string='Pan No')
	cin_no = fields.Char(string='CIN No')
	gstin_no = fields.Char(string='GSTIN No')
	tax_class = fields.Many2many('account.tax.class',string='Tax Class')
			
class tax_extension(models.Model):
	_name = 'tax.extension'
	
	@api.onchange('name')
	def onchange_name(self):
		if self.name:
			self.amount = self.name.amount

	name = fields.Many2one('account.tax',string="Particulars")
	amount = fields.Float(string='Rate of Tax')
	tax_detail_id = fields.Many2one('res.partner',string="Partner")


class account_tax_class(models.Model):
	_name = 'account.tax.class'
	
	name = fields.Char(string="Tax Class")