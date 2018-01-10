from openerp import models, fields, api, tools, _
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
from openerp.exceptions import UserError, MissingError, ValidationError
from openerp.tools import amount_to_text_en

class account_invoice_extension(models.Model):
	_inherit = 'account.invoice'
	
	product_packaging_one2many = fields.One2many('packaging.extension','account_packaging_id',string="Box Details")
	
	invoice_lines_boolean = fields.Boolean(string = 'Invoice Lines')
	type_order = fields.Selection([
		('sale', 'Sale Order'),
		('claim', 'Claim order'),
		], string='Type of Order', store=True )
	variant_amount = fields.Float(string="Variant Amount", default=0.0)
	delivery_price = fields.Float(string='Estimated Delivery Price', store=True)
	carrier_id = fields.Many2one('delivery.carrier',string="Delivery Method")
	amount_freight = fields.Monetary(string='Freight Amount', store=True, readonly=True, track_visibility='always')
	# invoice_shipping_on_delivery = fields.Boolean(string="Invoice Shipping on Delivery")
	grn_no = fields.Char(string="GRN No.")
	
	l_r_no = fields.Char("L.R No")
	transporter = fields.Char("Transporter")
	vehicle_no = fields.Char("Vehicle No")
	mode_of_transport = fields.Char("Mode of Transporter")
	destination = fields.Char("Destination")
	
	po_order = fields.Char('PO number/Group',size=120)
	
	removal_date = fields.Datetime("Removal date")
	gstin_no = fields.Char(string='GSTIN No', related="partner_id.gstin_no")
	company_gstin_no = fields.Char(string='Company GSTIN No', related="company_id.gstin_no")
	tax_class = fields.Many2many('account.tax.class',string='Tax Class', related="partner_id.tax_class")
	# _sql_constraints = [
	# ('unique_reference', 'UNIQUE(reference)', 'Supplier invoice number already present in the System \
	#   \n Supplier invoice number must be unique!'),
	# ]
	def total_amount_in_words(self):
		return self.amount_total and  amount_to_text_en.amount_to_text_in(self.amount_total, 'Rupees') or ""

	@api.one
	@api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'currency_id', 'company_id','amount_freight')
	def _compute_amount(self):
		self.amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
		self.amount_tax = sum(line.amount for line in self.tax_line_ids)
		self.amount_total = self.amount_untaxed + self.amount_tax +  self.amount_freight
		amount_total_company_signed = self.amount_total
		amount_untaxed_signed = self.amount_untaxed
		if self.currency_id and self.currency_id != self.company_id.currency_id:
			amount_total_company_signed = self.currency_id.compute(self.amount_total, self.company_id.currency_id)
			amount_untaxed_signed = self.currency_id.compute(self.amount_untaxed, self.company_id.currency_id)
		sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
		self.amount_total_company_signed = amount_total_company_signed * sign
		self.amount_total_signed = self.amount_total * sign
		self.amount_untaxed_signed = amount_untaxed_signed * sign
	
	
	@api.multi
	def get_taxes_values(self):
		tax_grouped = {}
		for line in self.invoice_line_ids:
			price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
			taxes = line.invoice_line_tax_ids.compute_all(price_unit, self.currency_id, line.quantity, line.product_id, self.partner_id)['taxes']
			variant_tax = line.invoice_line_tax_ids.compute_all(line.variant_amount, self.currency_id, 1, line.product_id, self.partner_id)['taxes']
			# print "AAAAAAAAAAAA",line.variant_amount, variant_tax
			variant_amt = 0
			if variant_tax:
				variant_amt = variant_tax[0]['amount']
			for tax in taxes:
				val = {
					'invoice_id': self.id,
					'name': tax['name'],
					'tax_id': tax['id'],
					'amount': tax['amount'] + variant_amt,
					'manual': False,
					'sequence': tax['sequence'],
					'account_analytic_id': tax['analytic'] and line.account_analytic_id.id or False,
					'account_id': self.type in ('out_invoice', 'in_invoice') and (tax['account_id'] or line.account_id.id) or (tax['refund_account_id'] or line.account_id.id),
				}

				# If the taxes generate moves on the same financial account as the invoice line,
				# propagate the analytic account from the invoice line to the tax line.
				# This is necessary in situations were (part of) the taxes cannot be reclaimed,
				# to ensure the tax move is allocated to the proper analytic account.
				if not val.get('account_analytic_id') and line.account_analytic_id and val['account_id'] == line.account_id.id:
					val['account_analytic_id'] = line.account_analytic_id.id

				key = tax['id']
				if key not in tax_grouped:
					tax_grouped[key] = val
				else:
					tax_grouped[key]['amount'] += val['amount']
		return tax_grouped
	
	@api.model
	def tax_line_move_line_get(self):
		res = super(account_invoice_extension,self).tax_line_move_line_get()
		if self.amount_freight:
			if not self.carrier_id.product_id.property_account_income_id.id:
				raise ValidationError("Kindly fill Account for the Delivery Method ") 
			
			move_line_dict = {
				# 'invl_id': line.id,
				'type': 'src',
				'name': self.carrier_id.name.split('\n')[0][:64],
				'price_unit': self.amount_freight,
				'quantity': 1,
				'price': self.amount_freight,
				'account_id': self.carrier_id.product_id.property_account_income_id.id,
				'product_id': self.carrier_id.product_id.id,
				'uom_id': self.carrier_id.product_id.uom_id.id,
				'invoice_id': self.id,
			}
			res.append(move_line_dict)
		return res

class account_invoice_line_extension(models.Model):
	_inherit = "account.invoice.line"
	
	variant_amount = fields.Float(string="Variant Amount", default=0.0)
	hsn_code = fields.Char(string='HSN', related="product_id.hsn_code")
	
	@api.one
	@api.depends('price_unit', 'discount', 'invoice_line_tax_ids', 'quantity',
		'product_id', 'invoice_id.partner_id', 'invoice_id.currency_id', 'invoice_id.company_id','variant_amount')
	def _compute_price(self):
		currency = self.invoice_id and self.invoice_id.currency_id or None
		price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
		taxes = False
		if self.invoice_line_tax_ids:
			taxes = self.invoice_line_tax_ids.compute_all(price, currency, self.quantity, product=self.product_id, partner=self.invoice_id.partner_id)
			variant_tax = self.invoice_line_tax_ids.compute_all(self.variant_amount,currency, 1, product=self.product_id, partner=self.invoice_id.partner_id)
		self.price_subtotal = price_subtotal_signed = (taxes['total_excluded'] + variant_tax['total_excluded']) if taxes else ((self.quantity * price) + self.variant_amount)
		if self.invoice_id.currency_id and self.invoice_id.currency_id != self.invoice_id.company_id.currency_id:
			price_subtotal_signed = self.invoice_id.currency_id.compute(price_subtotal_signed, self.invoice_id.company_id.currency_id)
		sign = self.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
		self.price_subtotal_signed = price_subtotal_signed * sign
		
	
class account_tax_extension(models.Model):
	_inherit = "account.tax"
	
	tally_acc = fields.Char(string="Tally Account")
	active = fields.Boolean(string="Active", default=True)
