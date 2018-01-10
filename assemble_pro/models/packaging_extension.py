from openerp import models, fields, api, _, tools
from openerp.exceptions import UserError
from datetime import datetime
import time
import logging

_logger = logging.getLogger(__name__)

class packaging_extension(models.Model):
	_name = 'packaging.extension'
	
	@api.onchange('name')
	def onchange_name(self):
		if self.name:
			self.code = self.name.code

	name = fields.Many2one('product.packaging',string="Package")
	code = fields.Char(string="Code")
	code_name = fields.Char(string="Code Name")
	qty = fields.Integer(string="Qty")
	rate = fields.Float(string="Rate", track_visibility='always')
	amount = fields.Float(compute='_compute_product_amount', string='Amount', readonly=True, store=True)
	packaging_id = fields.Many2one('sale.order',string="Sale order")
	account_packaging_id = fields.Many2one('account.invoice',string="Account Invoice")
	product_temp_id = fields.Many2one('product.template',string="Product Template")
	cst = fields.Float(string="CST")
	hsn_no = fields.Char(string="HSN")
	# tax = fields.Many2one('account.tax',string="Tax 1")
	tax_id = fields.Many2many('account.tax', string='Taxes')
	tax_amount = fields.Char(string="Tax", store=True)
	# invoice_packaging_lines = fields.Many2many('account.invoice.line', 'packaging_extension_invoice_rel', 'packaging_line_id', 'invoice_packaging_id', string='Invoice Lines', copy=False)
	
	
	@api.multi
	def amount_calculate(self):
		self.amount = self.qty * self.rate
		
	@api.depends('qty', 'rate')
	def _compute_product_amount(self):
		# self.amount = self.qty * self.rate
		for line in self:
			price = line.qty * line.rate
			line.update({
				'amount': price,
			})
			
class product_packaging_extension(models.Model):
	_inherit = 'product.packaging'
	
	code = fields.Char(string="Code")
	main_box =  fields.Boolean('Main Box')
	product_temp_id = fields.Many2one('product.template', track_visibility='always')
	rate = fields.Float(string="Rate", track_visibility='always')
	amount = fields.Float(compute='_compute_product_amount', string='Amount', readonly=True, store=True)
	company_id = fields.Many2one('res.company', 'Company')
	
	
	@api.multi
	def amount_calculate(self):
		self.amount = self.qty * self.rate
		
	@api.depends('qty', 'rate')
	def _compute_product_amount(self):
		# self.amount = self.qty * self.rate
		for line in self:
			price = line.qty * line.rate
			line.update({
				'amount': price,
			})


	
class stock_quant_extension(models.Model):
	_inherit = 'stock.quant'
	
	finished_goods = fields.Boolean('Finished Goods')
	
	
	