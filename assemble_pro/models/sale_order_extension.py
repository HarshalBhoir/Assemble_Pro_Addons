from openerp.exceptions import UserError, MissingError, ValidationError
import csv
import base64
import decimal
import openerp

from openerp import models, fields, api, _, tools
from openerp.exceptions import UserError
from datetime import datetime
import datetime
import time
import logging
from openerp.tools import float_is_zero,openerp,image_colorize, image_resize_image_big
import re , collections
# from datetime import date
# import pandas
from collections import Counter
import string
import openerp.addons.decimal_precision as dp

class AccountInvoiceTax(models.Model):
	_inherit = "account.invoice.tax"
	
	sale_id = fields.Many2one('sale.order', string='Sales', ondelete='cascade', index=True)
	
	@api.multi
	@api.onchange('tax_id')
	def onchange_tax_ids(self):
		for record in self:
			if record.sale_id and record.tax_id and record.tax_id.type_tax_use == 'sale':
				record.name = record.tax_id.name
				record.account_id = record.tax_id.account_id.id
				if 'Central' in record.tax_id.name:
					if record.tax_id.amount > 0:
						record.amount = record.tax_id.amount * self.sale_id.amount_total
				

class sale_order_line_entension(models.Model):
	_inherit = ['sale.order.line']
	
	length = fields.Float(string="Length", track_visibility='always')
	default_code = fields.Char(string="Code" , related="product_id.default_code")
	# box_code = fields.Char('Box code' , related="product_id.product_packaging_id.name" ,store= True)
	claim_selection=fields.Boolean()
	box_code = fields.Many2one('product.packaging', string='Box code')

	stops = fields.Integer(string="Stops", track_visibility='always')
	variant_amount = fields.Float(string="Variant Amount", default=0.0)
	box_code_name = fields.Char('code')
	hsn_no = fields.Char(string="HSN")
	pcb_material = fields.Boolean('PCB Material' , related="product_id.product_tmpl_id.pcb_material")
	hsn_code = fields.Char(string='HSN',related="product_id.product_tmpl_id.hsn_code" , store=True)
	dummy = fields.Boolean(string="Dummy")
	
	@api.onchange('product_id')
	def onchange_product(self):
		if self.product_id:
			self.default_code = self.product_id.default_code
			self.box_code = self.product_id.product_packaging_id.name
	
	@api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id','variant_amount')
	def _compute_amount(self):
		"""
		Compute the amounts of the SO line.
		"""
		for line in self:
			price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
			taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_id)
			variant_tax = line.tax_id.compute_all(line.variant_amount, line.order_id.currency_id, 1, product=line.product_id, partner=line.order_id.partner_id)
			line.update({
				'price_tax': (taxes['total_included'] - taxes['total_excluded']) + (variant_tax['total_included'] - variant_tax['total_excluded']),
				'price_total': taxes['total_included'] + variant_tax['total_included'],
				'price_subtotal': taxes['total_excluded'] + variant_tax['total_excluded'],
			})
			
			
	@api.multi
	def _prepare_invoice_line(self, qty):
		res = super(sale_order_line_entension,self)._prepare_invoice_line(qty)
		res['variant_amount'] = self.variant_amount
		return res
	


	@api.multi
	@api.onchange('product_id')
	def product_id_change(self):
		if not self.product_id:
			return {'domain': {'product_uom': []}}
	
		vals = {}
		domain = {'product_uom': [('category_id', '=', self.product_id.uom_id.category_id.id)]}
		if not (self.product_uom and (self.product_id.uom_id.category_id.id == self.product_uom.category_id.id)):
			vals['product_uom'] = self.product_id.uom_id
	
		product = self.product_id.with_context(
			lang=self.order_id.partner_id.lang,
			partner=self.order_id.partner_id.id,
			quantity=self.product_uom_qty,
			date=self.order_id.date_order,
			pricelist=self.order_id.pricelist_id.id,
			uom=self.product_uom.id
		)
	
		name = product.name_get()[0][1]
		if product.description_sale:
			name += '\n' + product.description_sale
		vals['name'] = name
	
		self._compute_tax_id()
	
		if self.order_id.pricelist_id and self.order_id.partner_id:
			customer_pricelist = self.order_id.pricelist_id
			if len(customer_pricelist):
				for price in customer_pricelist[0]:
					for line in price.pricelist_line_id:
						if self.product_id.product_tmpl_id.id == line.product_tmpl_id.id:
							vals['price_unit'] = line.rate or 0
			else:
				vals['price_unit'] = 0.0
			
			# vals['price_unit'] = self.env['account.tax']._fix_tax_included_price(product.price, product.taxes_id, self.tax_id)
		self.update(vals)
		return {'domain': domain}
	

	@api.onchange('product_uom', 'product_uom_qty')
	def product_uom_change(self):
		if not self.product_uom:
			self.price_unit = 0.0
			return
		if self.order_id.pricelist_id and self.order_id.partner_id:
			product = self.product_id.with_context(
				lang=self.order_id.partner_id.lang,
				partner=self.order_id.partner_id.id,
				quantity=self.product_uom_qty,
				date_order=self.order_id.date_order,
				pricelist=self.order_id.pricelist_id.id,
				uom=self.product_uom.id,
				fiscal_position=self.env.context.get('fiscal_position')
			)
			customer_pricelist = self.order_id.pricelist_id
			if len(customer_pricelist):
				for price in customer_pricelist[0]:
					for line in price.pricelist_line_id:
						if self.product_id.product_tmpl_id.id == line.product_tmpl_id.id:
							self.price_unit = line.rate or 0
			else:
				self.price_unit = 0.0
			# self.price_unit = self.env['account.tax']._fix_tax_included_price(product.price, product.taxes_id, self.tax_id)
			
			
			
	# @api.multi
	# def invoice_line_create(self, invoice_id, qty):
	# 	precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
	# 	for line in self:
	# 		if not float_is_zero(qty, precision_digits=precision):
	# 			vals = line._prepare_invoice_line(qty=qty)
	# 			vals.update({'invoice_id': invoice_id, 'sale_line_ids': [(6, 0, [line.id])], 'package_line_ids': [(6, 0, [line.id])]})
	# 			self.env['account.invoice.line'].create(vals)
			
# class AccountInvoiceLine(models.Model):
# 	_inherit = 'account.invoice.line'
# 	package_line_ids = fields.Many2many('packaging.extension', 'packaging_extension_invoice_rel', 'invoice_packaging_id', 'packaging_line_id', string='Packaging Extension Lines', readonly=True, copy=False)


	

class sale_order_extension(models.Model):
	_inherit = ['sale.order']
	
	import_text = fields.Boolean(String="Import Trough Text File")
	po_order = fields.Char('PO number/Group',size=120)
	po_date = fields.Date(string="PO Date" )
	vat_no = fields.Char(String='VAT TIN')
	cst_no = fields.Char(String='CST TIN')
	service_tax_no = fields.Char(String='Service Tax Code No')
	delivery_date = fields.Date(string="Delivery date" )
	carrier_id = fields.Many2one("delivery.carrier", string="Delivery Method", help="Fill this field if you plan to invoice the shipping based on picking.", default='draft')
	# product_packaging_id = fields.Many2one('packaging.extension',string="Box Details")
	product_packaging_one2many = fields.One2many('packaging.extension','packaging_id',string="Box Details")
	amount_package = fields.Monetary(string='Package Amount', store=True, readonly=True, compute='_amount_all', track_visibility='always')
	amount_cst = fields.Monetary(string='CST', store=True, readonly=True, compute='_amount_all', track_visibility='always')
	amount_total_char = fields.Monetary('Amount Total CHAR' , related="amount_total", store=True)
	
	delivery_price = fields.Float(string='Estimated Delivery Price', compute=False)
	tax_line_ids = fields.One2many('account.invoice.tax', 'sale_id', string='Tax Lines')
	cst_visible = fields.Boolean(String="CST Visible")
	manual_tax = fields.Boolean(String="Manual Tax")
	reason = fields.Text(String="Reason For Changing Tax")
	gstin_no = fields.Char(string='Customer GSTIN No', store=True, related="partner_id.gstin_no")
	delivery_gstin_no = fields.Char(string='Delivery GSTIN No', store=True , related="partner_shipping_id.gstin_no")
	company_gstin_no = fields.Char(string='Company GSTIN No', store=True , related="company_id.gstin_no")
	tax_class = fields.Many2many('account.tax.class',string='Tax Class', related="partner_id.tax_class")
	supplier_no = fields.Char(string='Supplier No', store=True)
	
	
	# delivery_price = fields.Float(string='Estimated Delivery Price', compute='_compute_delivery_price', store=True)
	# carrier_id = fields.Many2one("delivery.carrier", string="Delivery Method", help="Fill this field if you plan to invoice the shipping based on picking.")
	# invoice_shipping_on_delivery = fields.Boolean(string="Invoice Shipping on Delivery")

	# @api.onchange('order_line')
	# def onchange_order_line(self):
	# 	result = []
	# 	for rec in self:
	# 		for record in rec.order_line:
	# 			if record.product_id  and record.product_id.product_packaging_one2many:
	# 				for box in record.product_id.product_packaging_one2many:
	# 					vals = {
	# 						'name':box.name,
	# 						'code':box.code,
	# 						'qty':box.qty,
	# 						'rate':box.rate,
	# 						'amount':box.amount
	# 					}
	# 					result.append(vals)
	# 		rec.product_packaging_one2many = result
	
	# claim_order_id = fields.Many2one('sale.order',string="Claim No.")
	# type_order = fields.Selection([
	# 	('sale', 'Sale Order'),
	# 	('work', 'Work Order'),
	# 	('claim', 'Claim order'),
	# 	], string='Type of Order', store=True)


	# @api.depends('product_packaging_one2many.amount')
	# def _amount_package(self):
	# 	for order in self:
	# 		amount_pkg = amount_tax = 0.0
	# 		for line in order.product_packaging_one2many:
	# 			amount_pkg += line.amount
	# 		order.update({
	# 			'amount_package': order.pricelist_id.currency_id.round(amount_pkg),
	# 		})
			
	# @api.depends('order_line.price_total','product_packaging_one2many.amount')
	# def _amount_all(self):
	# 	"""
	# 	Compute the total amounts of the SO.
	# 	"""
	# 	super(sale_order_extension, self)._amount_all()
	# 	for res in self:
	# 		amount_pkg = 0.0
	# 		for line in res.product_packaging_one2many:
	# 			amount_pkg += line.amount
	# 		res.update({
	# 			'amount_package': res.pricelist_id.currency_id.round(amount_pkg),
	# 			'amount_total': res.amount_untaxed + res.amount_tax + amount_pkg,
	# 		})
	
	@api.multi
	@api.onchange('partner_id')
	def onchange_partner_id(self):
		"""
		Update the following fields when the partner is changed:
		- Pricelist
		- Payment term
		- Invoice address
		- Delivery address
		"""
		if not self.partner_id:
			self.update({
				'partner_invoice_id': False,
				'partner_shipping_id': False,
				'payment_term_id': False,
				'fiscal_position_id': False,
			})
			return
	
		addr = self.partner_id.address_get(['delivery', 'invoice'])
		values = {
			# 'pricelist_id': self.partner_id.property_product_pricelist and self.partner_id.property_product_pricelist.id or False, # commented for new functionality
			'payment_term_id': self.partner_id.property_payment_term_id and self.partner_id.property_payment_term_id.id or False,
			'partner_invoice_id': addr['invoice'],
			'partner_shipping_id': addr['delivery'],
			'note': self.with_context(lang=self.partner_id.lang).env.user.company_id.sale_note,
		}
	
		if self.partner_id.user_id:
			values['user_id'] = self.partner_id.user_id.id
		if self.partner_id.team_id:
			values['team_id'] = self.partner_id.team_id.id
		self.update(values)

	
	@api.onchange('partner_id','date_order')
	def onchange_partner_date(self):
		dt = datetime.datetime.strptime(self.date_order,'%Y-%m-%d %H:%M:%S')
		dd = dt.date()
		if not self.partner_id:
			self.pricelist_id = False
		else:
			prod_sup = self.env['product.pricelist'].search([('name','=',self.partner_id.name)],order="create_date desc")
			if len(prod_sup):
				self.pricelist_id = prod_sup[0].id
			else:
				self.pricelist_id = False
			
		return {}


	@api.depends('order_line.price_total','tax_line_ids.amount')
	def _amount_all(self):
		"""
		Compute the total amounts of the SO.
		"""
		super(sale_order_extension, self)._amount_all()
		for res in self:
			amount_cst = 0.0
			for line in res.tax_line_ids:
				amount_cst += line.amount
			res.update({
				'amount_cst': res.pricelist_id.currency_id.round(amount_cst),
				'amount_total': res.amount_untaxed + res.amount_tax + amount_cst,
			})
	

	@api.multi
	def delivery_set(self):
	
		# Remove delivery products from the sale order
		# self._delivery_unset() # as per LCPL Condition
	
		for order in self:
			carrier = order.carrier_id
			if carrier:
				if order.state not in ('draft', 'sent','sale'):
					raise UserError(_('The order state have to be draft to add delivery lines.'))
	
				if carrier.delivery_type not in ['fixed', 'base_on_rule']:
					# Shipping providers are used when delivery_type is other than 'fixed' or 'base_on_rule'
					price_unit = order.carrier_id.get_shipping_price_from_so(order)[0]
				else:
					# Classic grid-based carriers
					carrier = order.carrier_id.verify_carrier(order.partner_shipping_id)
					if not carrier:
						raise UserError(_('No carrier matching.'))
					price_unit = carrier.get_price_available(order)
					
					if order.company_id.currency_id.id != order.pricelist_id.currency_id.id:
						price_unit = order.company_id.currency_id.with_context(date=order.date_order).compute(price_unit, order.pricelist_id.currency_id)
					else:
						order.delivery_price = price_unit
	
				# order._create_delivery_line(carrier, price_unit)  # as per LCPL Condition
	
			else:
				raise UserError(_('No carrier set for this order.'))

	@api.multi
	def action_invoice_create(self, grouped=False, final=False, split_invoice=False):
		"""
		Create the invoice associated to the SO.
		:param grouped: if True, invoices are grouped by SO id. If False, invoices are grouped by
						(partner, currency)
		:param final: if True, refunds will be generated if necessary
		:returns: list of created invoices
		"""
		
		
		
		# @api.onchange('invoice_line_ids')
		# def _onchange_invoice_line_ids(self):
		# 	taxes_grouped = self.get_taxes_values()
		# 	tax_lines = self.tax_line_ids.browse([])
		# 	for tax in taxes_grouped.values():
		# 		tax_lines += tax_lines.new(tax)
		# 	self.tax_line_ids = tax_lines
		# 	return
		inv_obj = self.env['account.invoice']
		tax_line_vals = []
		
		if self.type_order == 'claim':
			res = []
			for inv in self:
				inv_res = super(sale_order_extension, inv).action_invoice_create(grouped=grouped, final=final)
				result_obj = inv_obj.search([('id','in',inv_res)])
				for result in result_obj:
					result.type_order = 'claim'
					if result.company_id.id == 1:
						result.carrier_id = inv.carrier_id.id
						result.amount_freight = inv.delivery_price

			return res
		
		# if self.invoice_ids and self.import_text :
		# 	print "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
		# 	for result in self.invoice_ids:
		# 		print "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
		# 		record.carrier_id = self.carrier_id.name or False
		# 		record.delivery_price = self.amount_freight
					
		
		if not split_invoice:
			res = []
			for order in self:
				order_res = super(sale_order_extension, order).action_invoice_create(grouped=grouped, final=final)
				res.append(order_res)
				inv_rec = inv_obj.search([('id','in',order_res)])
				
				
				for invoice in inv_rec:
					if order.import_text:
						invoice.invoice_lines_boolean = order.import_text
					if invoice.company_id.id == 1:
						invoice.carrier_id = order.carrier_id.id
						invoice.amount_freight = order.delivery_price
						
					for box_line in order.product_packaging_one2many:
						line_tax = []
						# for tax in box_line.tax_id:
						# 	print "DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD" , tax.id
						# 	line_tax = tax.id
						box_vals = {
							'name': box_line.name.id,
							'code': box_line.code,
							'code_name': box_line.code_name,
							'hsn_no': box_line.hsn_no,
							'amount': box_line.amount,
							'rate': box_line.rate,
							'tax_id': [(4, x.id) for x in box_line.tax_id],
							'qty': box_line.qty,
							'tax_amount': box_line.tax_amount,
							'cst': box_line.cst,
							'account_packaging_id': invoice.id
						}
						a= self.env['packaging.extension'].create(box_vals)
			
			
			if self.tax_line_ids:
				for line in self.tax_line_ids:
					amount = (inv_rec.amount_untaxed + inv_rec.amount_tax) * line.tax_id.amount
					tax_line_values = {
						'invoice_id':inv_rec.id,
						'tax_id':line.tax_id.id,
						'name':line.name,
						'account_id':line.account_id.id,
						'amount':amount
					}
					
					tax_line_vals.append(tax_line_values.copy())
					for line in tax_line_vals:
						tax_line_obj = inv_rec.tax_line_ids.create(line)
						
			return res
		else:

			precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
			invoices = {}
			
			for order in self:
				comp_dict = {}
				
				for box_line in order.product_packaging_one2many:
					c_id = box_line.name.company_id.id
					if c_id in comp_dict:
						comp_dict[c_id].append(box_line.code)
					else:
						comp_dict[c_id] = [box_line.code]
			
				for key,value in comp_dict.items():
					invoice = False
					group_key = str(order.id) + "," + str(key)
					
					# for line in order.order_line.sorted(key=lambda l: l.qty_to_invoice < 0):
					for line in order.order_line.sorted(key=lambda l: l.product_id.product_packaging_id.code):
						if line.box_code.code in value:
							if float_is_zero(line.qty_to_invoice, precision_digits=precision):
								continue
							if group_key not in invoices:
								inv_data = order._prepare_invoice()
								inv_data['company_id'] = key
								inv_data['invoice_lines_boolean'] = order.import_text
								if key == 1:
									inv_data['carrier_id'] = order.carrier_id.id
									inv_data['amount_freight'] = order.delivery_price
									
								invoice = inv_obj.create(inv_data)
								invoices[group_key] = invoice
								# print "HHHHHHHHHHHHHHHHHHHHHH" , invoice
							elif group_key in invoices and order.name not in invoices[group_key].origin.split(', '):
								invoices[group_key].write({'origin': invoices[group_key].origin + ', ' + order.name})
							if line.qty_to_invoice > 0:
								
								line.invoice_line_create(invoices[group_key].id, line.qty_to_invoice)
							elif line.qty_to_invoice < 0 and final:
								line.invoice_line_create(invoices[group_key].id, line.qty_to_invoice)
					
					for box_line in order.product_packaging_one2many:
						if box_line.code in value:
							box_vals = {
								'name': box_line.name.id,
								'code': box_line.code,
								'amount': box_line.amount,
								'rate': box_line.rate,
								'qty': box_line.qty,
								'account_packaging_id': invoice.id if invoice else False
							}
							self.env['packaging.extension'].create(box_vals)
			
			# print "EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE" , invoices
			for invoice in invoices.values():
				# If invoice is negative, do a refund invoice instead
				if invoice.amount_untaxed < 0:
					invoice.type = 'out_refund'
					for line in invoice.invoice_line_ids:
						line.quantity = -line.quantity
				# Necessary to force computation of taxes. In account_invoice, they are triggered
				# by onchanges, which are not triggered when doing a create.
				invoice.compute_taxes()
				
				if self.tax_line_ids:
					
					for line in self.tax_line_ids:
						# print "TTTTTTTTTTTTTTTTTTTT",line, line.name
						amount = (invoice.amount_untaxed + invoice.amount_tax) * line.tax_id.amount
						tax_line_values = {
							'invoice_id':invoice.id,
							'tax_id':line.tax_id.id,
							'name':line.name,
							'account_id':line.account_id.id,
							'amount':amount
						}
						tax_line_obj = invoice.tax_line_ids.create(tax_line_values)
	
			return [inv.id for inv in invoices.values()]

			
	@api.onchange('order_line')
	def onchange_order_line(self):
		result = {}
		box_dict = {}
		saved_dict = {}
		box_code_dict = {}
		hsn_dict = {}
		tax_dict = {}
		final_result = []

		for line in self.product_packaging_one2many:
			result[line.code] = []
			box_dict[line.code] = line.name.id
			saved_dict[line.code] = line
		
		for record in self.order_line:
			if record.box_code:
				box_code = record.box_code.code.encode("utf-8")
				if box_code not in box_code_dict:
					box_code_dict[box_code] = record.box_code_name
				if box_code not in hsn_dict:
					hsn_dict[box_code] = record.hsn_no
				if box_code not in tax_dict:
					tax_dict[box_code] = record.tax_id
				if box_code in result:
					result[box_code].append(record.price_subtotal)
				else:
					box_dict[box_code] = record.box_code.id
					result[box_code] = [record.price_subtotal]
		
		
		for key,value in result.items():
			total_amount = sum(value)
			# print "KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK" , tax_dict[key]
			tax_amount = 0.0
			for tax_amt in tax_dict[key]:
				tax_amount += ((total_amount * tax_amt.amount) / 100)
			vals = {
				'name':box_dict[key],
				'code':key,
				'code_name':box_code_dict[key],
				'hsn_no':hsn_dict[key],
				'qty':1,
				'rate':total_amount,
				'amount':total_amount,
				'tax_id':tax_dict[key],
				'tax_amount':tax_amount if tax_amount else 0.0,
			}
			if key in saved_dict:
				saved_dict[key].write(vals)
			else:
				final_result.append(vals)
		
		self.product_packaging_one2many = final_result
		
		for line in self.product_packaging_one2many:
			if line.amount == 0.0:
				self.product_packaging_one2many = self.product_packaging_one2many - line
	
	@api.multi
	def action_confirm(self):
		res = super(sale_order_extension, self).action_confirm()
		if self.picking_ids:
			for record in self.picking_ids:
				record.import_text = self.import_text
				record.po_order = self.po_order
		return res
	
	@api.multi
	def _prepare_invoice(self):
		res = super(sale_order_extension,self)._prepare_invoice()
		res['po_order'] = self.po_order
		return res

class sale_order_import(models.Model):
	_name = 'sale.order.import'
	_inherit = ['mail.thread']
	_order = 'create_date desc'

	name = fields.Char('Name',size=120)
	file_name = fields.Char('File Name',size=120)
	import_file = fields.Binary(string="Import File" ,attachment=True , required=True)
	import_text = fields.Boolean(String="Import Trough Text File")
	# date = fields.Date(string="Date",default=lambda self: datetime.now())
	po_order = fields.Char('PO No/Group',size=120)
	po_date = fields.Date(string="PO Date" )
	vat_no = fields.Char(String='VAT TIN')
	cst_no = fields.Char(String='CST TIN')
	service_tax_no = fields.Char(String='Service Tax Code No')
	delivery_date = fields.Date(string="Delivery date" )
	product_uom_qty = fields.Char()
	price_unit = fields.Char()
	tax_id = fields.Char()
	product_id = fields.Many2one('product.product',string="Product")
	pricelist_id = fields.Many2one('product.pricelist',string="Pricelist")
	state = fields.Selection([
		('draft', 'Draft'),
		('done', 'Imported'),
		('cancel', 'Cancelled'),
		], string='Status', readonly=True,
		copy=False, index=True, track_visibility='always', default='draft')
	note = fields.Text()
	attach_doc_count = fields.Integer(string="Number of documents attached", compute='count_docs')
	neglected_products = fields.Text("Neglected Products")
	neglect_boolean = fields.Boolean("Neglect")
	
	
	@api.multi
	def unlink(self):
		for order in self:
			if order.state != 'draft':
				raise UserError(_('You can only delete Draft Entries'))
		return super(sale_order_import, self).unlink()
	
	@api.one
	def import_csv_file(self):
		code = []
		code_variant_list = []
		box_codes = []
		order_line_ids = []
		order_line_vals = []
		tax_line_vals = []
		absent_products = []
		default_code_ids = []
		def_code_ids = []
		error_lines = []
		error_price_lines = []
		product_error = []
		boxes_error =[]
		boxes_error2 =[]
		sd_error = []
		variant_list = []
		line_default_code_ids = []
		validation_line_ids = []
		new_ids = []
		line_sale = []
		line_sd_var_list = []
		neglected_list = []
		neglected_lines = []
		elements_fetched = []
		line_amount_untaxed = 0.0
		underscore_detected = False
		current_box = False
		customer_pricelist = False
		customer_pricelist_dict = {}
		tax_line_values = {}
		central_tax_id = False
		line_tax_id = False
		current_box_code = line_box_code = line_hsn = ''
		
		prod_package = self.env['product.packaging'].search([])
		for pro_p in prod_package:
			box_codes.append(pro_p.code.encode('utf-8').strip())
			
		customer = self.env['res.partner'].search([('name','=','SCHINDLER INDIA PVT LTD')])
		if len(customer) >= 1:
			customer = customer[0]
		else:
			raise ValidationError('Kindly Create a Customer for "SCHINDLER INDIA PVT LTD" ')
		
		warehouse_ids = self.env['stock.warehouse'].search([('id','>',0)],order="id asc", limit=1)
		warehouse = warehouse_ids[0]

		payment_term = self.env['account.payment.term'].search([('name','=','Immediate Payment')])
		
#--------------------- Product And Variants ---------------------------#
		prod = self.product_id.search([])
		prod_code = [x.default_code for x in prod]
		for pro in prod_code:
			if pro != False:
				code.append(pro.encode('utf-8').strip())
				
		for code_variant in code:
			code_var = code_variant[:-1]
			code_variant_list.append(code_var)
#--------------------- Product And Variants ---------------------------#
				
#--------------------- Pricelist ---------------------------#
		if not self.pricelist_id:
			cust_pricelist_ids = self.pricelist_id.search([('name_partner','=',customer.id)],order="create_date desc")
			if len(cust_pricelist_ids) >= 1:
				customer_pricelist = cust_pricelist_ids[0]
				cust_pricelist= customer_pricelist.id
				# cust_pricelist_code = [(x.default_code,x.rate) for x in customer_pricelist.pricelist_line_id]
			else:
				raise ValidationError('Kindly Create a Customer PriceList For Customer " %s "' % (customer.name))
		else:
			customer_pricelist = self.pricelist_id
			cust_pricelist = self.pricelist_id.id
		
		if customer_pricelist:
			for record in customer_pricelist.pricelist_line_id:
				customer_pricelist_dict[record.default_code] = record.rate or 0.0
		
#--------------------- Pricelist ---------------------------#

		sale_values = {
			'partner_id':customer.id,
			'import_text':True,
			'payment_term_id':payment_term.id,
			'note':"",
			'type_order':'sale',
			'pricelist_id':cust_pricelist if cust_pricelist else False,
			'warehouse_id':warehouse.id,
		}
		
		sale_line_values = {
			'sequence':10,
			'customer_lead':7,
			'variant_amount':0.0,
			'dummy':True,
		}
		
		elements_to_fetch = ["Date:","PO number/Group","VAT TIN:", "CST TIN:",
							 "Delivery date:","Sales order", "Commision",
							 'VAT TIN','CST TIN','Service Tax Code No','Incoterms',
							 "Central Sales" ,"Integrated G","Central GST","State GST",
							 "Excise Duty","GSTN Number:","Supplier number:"]
		
		lines_to_neglect = ["Deco Ceiling ID","Flooring ID"]
		
		field_elements_dict = {
			"Date:":"po_date",
			"PO number/Group":"po_order",
			"Delivery date:":"delivery_date",
			"Sales order:":"name",
		}
		
		#------------------- Neglected Products -------------------#
		neg = str(self.neglected_products)
		nec_rec = neg.replace("\n", ",").strip()
		neglected_list = nec_rec.split(',')
		#------------------- Neglected Products -------------------#

		filetxt="/tmp/new"+str(self.create_uid.id)+".txt"
		with(open(filetxt,'wb')) as  u:
			u.write(base64.decodestring(self.import_file))
			u.close()

		fp = open("/tmp/new"+str(self.create_uid.id)+".txt")
		
		sale_note = "\
Following products need to be added in products master\n\
Product code:\n\
"
		
#------------------Neglecting Lines (Deco Ceiling ID and Flooring ID---------------------#
		for txt_lines in fp:
			loop_skip = False
			cgst = False
			sgst = False
			igst = False
			for neglect_record in lines_to_neglect:
				if neglect_record in txt_lines:
					neglected_lines.append(txt_lines)
					loop_skip = True
			
			if loop_skip:
				continue

#------------------Neglecting Lines (Deco Ceiling ID and Flooring ID---------------------#
			
#--------------------------------------- Tax --------------------------------------#
			
			if "Integrated G" in elements_to_fetch and "Integrated G" in txt_lines: 
				line_gst =txt_lines.split('Integrated G')
				line_gst1 = ''.join(line_gst[1].strip())
				line_gst2 = line_gst1.split("%")
				line_gst3 = ''.join(line_gst2[0].strip())
				
				gst_tax_id = self.env['account.tax'].search([
										('type_tax_use','=','sale'),
										('name','ilike','Integrated G'),
										('name','ilike',line_gst3)],order="create_date desc")
				# print "KKKKKKKKKKKKKKKKKKKK" ,gst_tax_id
				
				if len(gst_tax_id):
					line_tax_id = gst_tax_id[0]
				else:
					raise ValidationError('Kindly Create an GST Tax')
				for record in order_line_vals:
					if record['dummy'] == True and 'tax_id' not in record:
						record['tax_id'] = [(4,line_tax_id.id)]
						record['dummy'] == False
				
			if "Excise Duty" in elements_to_fetch and "Excise Duty" in txt_lines: 
				line_excise =txt_lines.split('Excise Duty')
				line_excise1 = ''.join(line_excise[1].strip())
				line_excise2 = line_excise1.split("%")
				line_excise3 = ''.join(line_excise2[0].strip())
				
				excise_tax_id = self.env['account.tax'].search([
										('type_tax_use','=','sale'),
										('name','ilike','Excise Duty'),
										('name','ilike',line_excise3)],order="create_date desc")
				
				if len(excise_tax_id):
					line_tax_id = excise_tax_id[0]
				else:
					raise ValidationError('Kindly Create an Excise Tax')
				# sale_line_values['tax_id'] = [(4,line_tax_id.id)]
				for record in order_line_vals:
					if record['dummy'] == True and 'tax_id' not in record:
						record['tax_id'] = [(4,line_tax_id.id)]
						record['dummy'] == False
						
			if "Central GST" in elements_to_fetch and "Central GST" in txt_lines:
				print "11111111111111111111111111111111111111111111111111"
				line_cgst =txt_lines.split('Central GST')
				line_cgst1 = ''.join(line_cgst[1].strip())
				line_cgst2 = line_cgst1.split("%")
				line_cgst3 = ''.join(line_cgst2[0].strip())
				
				cgst_tax_id = self.env['account.tax'].search([
										('type_tax_use','=','sale'),
										('name','ilike','Central GST'),
										('name','ilike',line_cgst3)],order="create_date desc")
				
				if len(cgst_tax_id):
					line_tax_id = cgst_tax_id[0]
				else:
					raise ValidationError('Kindly Create an CGST Tax')
				# sale_line_values['tax_id'] = [(4,line_tax_id.id)]
				for record in order_line_vals:
					if record['dummy'] == True:
						if 'tax_id' in record:
							record['tax_id'] += [(4,line_tax_id.id)]
						else:
							record['tax_id'] = [(4,line_tax_id.id)]
						if cgst:
							record['dummy'] == False
							cgst = True
						
			if "State GST" in elements_to_fetch and "State GST" in txt_lines:
				print "22222222222222222222222222222222222222222222222222222"
				line_sgst =txt_lines.split('State GST')
				line_sgst1 = ''.join(line_sgst[1].strip())
				line_sgst2 = line_sgst1.split("%")
				line_sgst3 = ''.join(line_sgst2[0].strip())
				
				sgst_tax_id = self.env['account.tax'].search([
										('type_tax_use','=','sale'),
										('name','ilike','State GST'),
										('name','ilike',line_sgst3)],order="create_date desc")
				
				if len(sgst_tax_id):
					line_tax_id = sgst_tax_id[0]
				else:
					raise ValidationError('Kindly Create an SGST Tax')
				# sale_line_values['tax_id'] = [(4,line_tax_id.id)]
				for record in order_line_vals:
					if record['dummy'] == True:
						if 'tax_id' in record:
							record['tax_id'] += [(4,line_tax_id.id)]
						else:
							record['tax_id'] = [(4,line_tax_id.id)]
						if sgst:
							record['dummy'] == False
							sgst = True
				
				
			if "Central Sales" in elements_to_fetch and "Central Sales" in txt_lines: 
				line_central =txt_lines.split('Central Sales')
				line_cent = ''.join(line_central[1].strip())
				line_percent = line_cent.split("%")
				line_per = ''.join(line_percent[0].strip())
				line_number = line_per.split("Ta")
				line_num = ''.join(line_number[1].strip())
				
				central_taxes_id = self.env['account.tax'].search([
										('type_tax_use','=','sale'),
										('name','ilike','Central Sales'),
										('name','ilike',line_num)],order="create_date desc")
				if len(central_taxes_id):
					central_tax_id = central_taxes_id[0]
				else:
					raise ValidationError('Kindly Create an Central Sales Tax')
				
				tax_line_values = {
					'tax_id':central_tax_id.id,
					'name':central_tax_id.name,
					'account_id':central_tax_id.account_id.id,
				}
				
#--------------------------------------- Tax --------------------------------------#
				
#---------------------------------------Packaging Box --------------------------------------#

			if "_____________________________" in txt_lines:
				underscore_detected = True
			
			if underscore_detected == True:
				
				if "000" in txt_lines: # For extracting PO box code
					line_bx_code=txt_lines.split('000')
					line_bx = ''.join(line_bx_code[1].strip())
					line_lbx =  line_bx.replace(line_bx[:2], '')
					line_bx_error=line_bx.split(' ')
					line_bx_cod=line_lbx.split(' ')
					
					line_bx_middle_error = filter(None, line_bx_error)
					if len(line_bx_middle_error) > 4:
						line_lbxo2 = line_bx_middle_error[2]
						boxes_error2.append(line_lbxo2)
						line_hsn = ''.join(line_lbxo2.strip())    #HSN NO. OF BOXES
					# line_lbxo = ''.join(line_lbx[0:10].strip())
					if len(line_bx_cod) > 2:
						line_lbxo = line_bx_cod[1]
						# abxo = len(line_lbxo)
						
						if len(line_lbxo) >= 6 and line_lbxo[0:1].isdigit():
							if line_lbxo not in box_codes:
								boxes_error.append(line_lbxo)
				
				for box_code in prod_package:
					bx_code = box_code.code.encode("utf-8")
					if bx_code in txt_lines:
						current_box = box_code
						current_box_code = box_code.code
						# if current_box_code in txt_lines: # For current_box_code
						line_current_box_code = txt_lines.split(current_box_code)
						line_box_code = ''.join(line_current_box_code[0].strip())
							
			else:
				underscore_detected = False
				
#---------------------------------------Packaging Box --------------------------------------#
				
#---------------------------------------Products --------------------------------------#

			if "/1 " in txt_lines and 'Piece' in txt_lines: # For Inserting In Sale order Line
				if any(ext in txt_lines for ext in code):
					line_list = txt_lines.split('/1')
					line_prod = txt_lines.split('1.00')
					line_default_code = ''.join(line_prod[0].strip())
					line_default_code_ids.append(line_default_code)
					
					line_tot = ''.join(line_list[1].strip())
					line_d = ''.join(line_list[0].strip())
					line_l = line_d.split('Piece')
					line_unit = line_l[1].strip()
					
					line_price_subtotal = float(line_tot.replace(',', ''))
					line_price_unit = float(line_unit.replace(',', ''))
					line_product_uom_qty = line_price_subtotal / line_price_unit
					
					if customer_pricelist:
						if line_default_code not in customer_pricelist_dict:
							error_price_lines.append((line_default_code or '',line_unit or ''))
						elif line_default_code in customer_pricelist_dict and customer_pricelist_dict[line_default_code] and customer_pricelist_dict[line_default_code] != line_price_unit:
							error_lines.append((line_default_code or '',line_unit or '',customer_pricelist_dict[line_default_code] or ''))
					
					prod_temp = self.product_id.search([('default_code','=',line_default_code)])
					
					if prod_temp.name:
						sale_line_values['name'] = prod_temp.name
						sale_line_values['product_uom'] = prod_temp.product_tmpl_id.uom_id.id
						sale_line_values['default_code'] = line_default_code
						sale_line_values['product_id'] = prod_temp.id
						sale_line_values['price_unit'] = line_price_unit
						sale_line_values['product_uom_qty'] = line_product_uom_qty
						sale_line_values['price_subtotal'] = line_price_subtotal
						sale_line_values['box_code'] = current_box.id if current_box else False
						sale_line_values['box_code_name'] = line_box_code if line_box_code else False
						sale_line_values['hsn_no'] = line_hsn if line_hsn else False
						
						order_line_vals.append(sale_line_values.copy())
						validation_line_ids.append(line_default_code)
					else:
						
						line_code = line_default_code[:-1]
						is_variant = False
						for idx, record in enumerate(order_line_vals):
							if line_code == record['default_code']:
								is_variant = True
								variant_list.append(line_default_code)
								order_line_vals[idx]['variant_amount'] = line_price_unit

				else:
					line_list_error = txt_lines.split('/1')
					line_prod_error = txt_lines.split('1.00')
					line_pro_error = ''.join(line_prod_error[0].strip())
					# line_pro_error_ids.append(line_pro_error)
					product_error.append(line_pro_error)
					
#---------------------------------------Products --------------------------------------#

			if "Date:" in elements_to_fetch and "Date:" in txt_lines: # For extracting PO Date
				line_list=txt_lines.split('Date:')
				line_d = ''.join(line_list[1].strip())
				line_l = line_d[0:10]
				d = datetime.datetime.strptime(line_l, "%d.%m.%Y")
				temp = d.strftime("%Y-%m-%d")
				self.po_date = temp
				sale_values['po_date'] = temp
				elements_fetched.append("Date:")
				elements_to_fetch.pop(elements_to_fetch.index("Date:"))
				
			if "SD- Variant condition" in txt_lines:
				line_sd_variant = txt_lines.split('SD- Variant condition')
				line_sd = ''.join(line_sd_variant[1].strip())
				sd_error.append(line_sd)
			
			if "PO number/Group" in elements_to_fetch and "PO number/Group" in txt_lines: # For extracting PO number/Group
				line_list=txt_lines.split(':')
				self.po_order =  line_list[1]
				sale_values['po_order'] = line_list[1]
				elements_fetched.append("PO number/Group")
				elements_to_fetch.pop(elements_to_fetch.index("PO number/Group"))
				
			if "Sales order" in elements_to_fetch and "Sales order" in txt_lines: # For extracting SO no.
				line_list=txt_lines.split(':')
				line_d = ''.join(line_list[1].strip())
				line_l = line_d[0:10]
				line_l = line_l.strip()
				line_sale.append(line_l)
				sale_values['client_order_ref'] = line_l
				
			if "Delivery date:" in elements_to_fetch and "Delivery date:" in txt_lines: # For extracting Delivery date
				line_list=txt_lines.split('Delivery date:')
				line_d = ''.join(line_list[1].strip())
				line_l = line_d[0:10]
				if line_l:
					d = datetime.datetime.strptime(line_l, "%d.%m.%Y")
					temp = d.strftime("%Y-%m-%d")
					self.delivery_date = temp
					sale_values['delivery_date'] = temp
					elements_fetched.append("Delivery date:")
					elements_to_fetch.pop(elements_to_fetch.index("Delivery date:"))
				
				
			if "Commision" in elements_to_fetch and "Commision" in txt_lines: # For extracting SO no.
				line_sale_name =txt_lines.split('Commision')
				line_d = ''.join(line_sale_name[1].strip())
				line_sale_name2 =line_d.split(':')
				line_d = ''.join(line_sale_name2[1].strip())
				self.name = line_d
				
				sale_order_list = self.env['sale.order'].search([])
				sale_order_code = [x.name.encode('utf-8') for x in sale_order_list]
				if str(self.name) not in sale_order_code:
					sale_values['name'] = line_d
				else:
					print "SSSSSSSSSSSSSSSSSSSSSSSSS Commissions number"
					raise ValidationError('Sale Order %s already present in the System '% (self.name))
				
				elements_fetched.append("Commision")
				elements_to_fetch.pop(elements_to_fetch.index("Commision"))
			
			
			if "Maharashtra" in txt_lines and "India" in txt_lines:
				for cust_address in customer.child_ids:
					if cust_address.state_id.name == 'Maharashtra':
						sale_values['partner_shipping_id'] = cust_address.id
						
			elif "Harayana" in txt_lines and "India" in txt_lines:
				for cust_address in customer.child_ids:
					if cust_address.state_id.name == 'Harayana':
						sale_values['partner_shipping_id'] = cust_address.id
						
			if "VAT TIN" in elements_to_fetch and "VAT TIN" in txt_lines: 
				line_list=txt_lines.split('VAT TIN: ')
				line_vat = ''.join(line_list[1].strip())
				sale_values['vat_no'] = line_vat
				
			# if "GSTN Number:" in elements_to_fetch and "GSTN Number:" in txt_lines: # For extracting SO no.
			# 	line_list_gst=txt_lines.split('GSTN Number:')
			# 	line_gstn = ''.join(line_list_gst[1].strip())
			# 	sale_values['delivery_gstin_no'] = line_gstn
				
			if "CST TIN" in elements_to_fetch and "CST TIN" in txt_lines: 
				line_list=txt_lines.split('CST TIN:')
				line_cst = ''.join(line_list[1].strip())
				sale_values['cst_no'] = line_cst
				
			if "Service Tax Code No" in elements_to_fetch and "Service Tax Code No" in txt_lines:
				line_list=txt_lines.split('Service Tax Code No :')
				line_cst = ''.join(line_list[1].strip())
				line_st = line_cst.split("Quotation number:")
				line_service = ''.join(line_st[0].strip())
				sale_values['service_tax_no'] = line_service
				
			if "Total net value excl. TAX INR" in txt_lines:
				line_total=txt_lines.split('Total net value excl. TAX INR')
				line_tl = ''.join(line_total[1].strip())
				
				if 'Page' not in line_tl:
					print "111111111111111111111111111111111111" , line_tl
					line_amount_untaxed = float(line_tl.replace(',', ''))
				else:
					line_tl2=line_tl.split('Page')
					line_tl3 = ''.join(line_tl2[0].strip())
					line_amount_untaxed = float(line_tl3.replace(',', ''))
					print "22222222222222222222222222222222222" , line_tl , line_tl2 , line_tl3
				
			if "SD- Variant condition" in txt_lines:
				line_sd_variant=txt_lines.split('SD- Variant condition')
				line_sd = ''.join(line_sd_variant[1].strip())
				line_sd_var = str(line_sd.replace(',', ''))
				line_sd_var_list.append(line_sd_var)
				
			if "Supplier number:" in elements_to_fetch and "Supplier number:" in txt_lines: # For extracting SO no.
				line_list_supp=txt_lines.split('Supplier number:')
				line_suppno = ''.join(line_list_supp[1].strip())
				sale_values['supplier_no'] = line_suppno
			
			# for val_rec in validation_line_ids:
			# 	if val_rec in txt_lines:
			# 		print "DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD" , val_rec
			# 		validation_line_ids.remove(val_rec)
					
		
		## --------------- For Last Validation -------------------##
		fp2 =open("/tmp/new"+str(self.create_uid.id)+".txt")
		general_expression = re.findall(r"\s\d{8}[A-Z]{3}\s|\s\d{8}[A-Z]{2}\s|\s\d{8}[A-Z]{1}\s|\s\d{8}\s", fp2.read())
		general_expression_rec = [x.strip() for x in general_expression]
		
		
		for var_rec in variant_list:
			if var_rec in validation_line_ids:
				validation_line_ids.remove(var_rec)
				general_expression_rec.remove(var_rec)
				
		for sd_var in line_sd_var_list:
			if sd_var in general_expression_rec:
				# validation_line_ids.remove(sd_var)
				general_expression_rec.remove(sd_var)
		
		test_case1 = []
		for idx, var_rec in enumerate(general_expression_rec):
			count_var = general_expression_rec.count(var_rec)
			if count_var < 2:
				test_case1.append(var_rec)
		
		test_case2 = []
		for var_rec in test_case1:
			if var_rec not in box_codes:
				test_case2.append(var_rec)
		
		test_case3 = []
		for case3 in test_case2:
			if case3 not in variant_list:
				test_case3.append(case3)
		
		for case4 in line_sale:
			if case4 in test_case3:
				test_case3.remove(case4)
				
		for case5 in boxes_error:
			if case5 in test_case3:
				test_case3.remove(case5)
				
		if len(neglected_list):
			for case6 in neglected_list:
				str_case6 = case6.strip() 
				if str_case6 in test_case3:
					test_case3.remove(str_case6)
					
		boxes_middle_error = filter(None, boxes_error2)
		for case7 in boxes_middle_error:
			if case7 in test_case3:
				test_case3.remove(case7)
				
		for case8 in sd_error:
			if case8 in test_case3:
				test_case3.remove(case8)
		
		
		for neg_rec in neglected_lines:
			for case9 in test_case3:
				if case9 in neg_rec:
					test_case3.remove(case9)
		
		# for var_rec2 in variant_list:
		# 	if var_rec2 in test_case3:
		# 		test_case3.remove(var_rec2)
		
		if len(product_error):
			error_product = "\
Product(s) is not present in the System with code\
				"
			for error in product_error:
				error_product += "\n %s " % ( error)
			print "XXXXXXXXXXXXXXXXXXXXXXXXXXXX Product Mismatch "
			raise ValidationError(error_product)
		
		print "JJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJ" , variant_list , sd_error , boxes_middle_error , neglected_list , boxes_error , line_sale , box_codes , test_case2
		if len(test_case3):
			missing_string = "\
Kindly Check The PO \n\
Product(s) with following code are missing from the Line Items :\n\
Product code :\n\
				   "
			for missing_line in test_case3:
				missing_string += "\n%s " % (missing_line)
			print "XXXXXXXXXXXXXXXXXXXXXXXXXXXX  missing from the Line Items "
			raise ValidationError(missing_string)
		
		
		if len(error_lines):
			error_string = "\
				  Product(s) with following code have different rate in the System:\n\
Product code --- Value in PO --- Pricelist value \
				"
			for error in error_lines:
				error_string += "\n%s -- -- -- %s -- -- -- %s" % ( error[0],error[1],error[2])
			print "XXXXXXXXXXXXXXXXXXXXXXXXXXXX Pricelist Mismatch "
			raise ValidationError(error_string)
		

		for normal_list in variant_list:
			for tuple_list in error_price_lines:
				if tuple_list[0] == normal_list:
					error_price_lines.remove(tuple_list)
		
		if len(error_price_lines):
			error_price_string = "\
Product(s) with following code are not present in the Pricelist:\n\
Product code --- Value in PO  \
				"
			for error_price in list(set(error_price_lines)):
				error_price_string += "\n%s -- --  -- %s " % ( error_price[0],error_price[1])
			print "XXXXXXXXXXXXXXXXXXXXXXXXXXXX Pricelist Product Mismatch "
			raise ValidationError(error_price_string)
		

		if len(boxes_error):
			error_boxes = "\
Box not present in the System with code\
				"
			for error_boxs in boxes_error:
				error_boxes += "\n %s " % (error_boxs)
			print "XXXXXXXXXXXXXXXXXXXXXXXXXXXX Boxes Mismatch " , error_boxes
			raise ValidationError(error_boxes)
		
		if len(variant_list):
			sale_note = sale_note + "\n".join(variant_list)
			sale_values['note'] = sale_note
		
		
		sale_obj = self.env['sale.order'].create(sale_values)
		# print "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA Sale Object Created" , sale_obj
		for line in order_line_vals:
			#------------------ Updating Singular Tax to All products---------------------#
			# sale_line_values['tax_id'] = [(4,line_tax_id.id)]
			# if 'tax_id' not in line and line_tax_id:
			# 	line['tax_id'] = [(4,line_tax_id.id)]
			#------------------ Updating Singular Tax to All products---------------------#
			line['order_id'] = sale_obj.id
			sale_line_obj = self.env['sale.order.line'].create(line)
			self.state = 'done'
			
		if not sale_obj.carrier_id:
			carrier_state = sale_obj.carrier_id.search([("state_ids","=",sale_obj.partner_shipping_id.state_id.id)])
			if carrier_state and len(carrier_state):
				carrier_state_rec = carrier_state[0]
				sale_obj.carrier_id = carrier_state_rec.id
				sale_obj.delivery_price = carrier_state_rec.amount
			
		amount_untaxed = sale_obj['amount_untaxed']
		amount_tax = sale_obj['amount_tax']
		if str(amount_untaxed) != str(line_amount_untaxed):
			print "XXXXXXXXXXXXXXXXXXXXXXXXXXXX Amount Mismatch " , amount_untaxed , line_amount_untaxed
			raise ValidationError('Amount Mismatch \n Total net value excl. TAX INR in PO is %s and Untaxed Amount calculated is %s'% (line_amount_untaxed ,amount_untaxed))
		
		tax_line_values['sale_id'] = sale_obj.id
		tax_line_values['amount'] = ((amount_untaxed + amount_tax) * (central_tax_id.amount if central_tax_id else False))
		tax_line_vals.append(tax_line_values.copy())
		
		for line in tax_line_vals:
			if central_tax_id:
				tax_line_obj = self.env['account.invoice.tax'].create(line)
		
		#---------- New preview ------------ #
		# fp123 = open("/tmp/new"+str(self.create_uid.id)+".txt")
		# self.note = "<pre>" + fp123.read() + "</pre>"
		# fp123.close()
		#---------- New preview ------------ #
		
		# print error45343
		sale_obj.onchange_order_line()
		
	@api.multi
	def count_docs(self):
		so_ids = self.env['sale.order'].search([("po_order","=",self.po_order)])
		if len(so_ids):
			self.attach_doc_count = len(so_ids) or 0
	
	@api.multi
	def get_attached_docs(self):
		so_ids = self.env['sale.order'].search([("po_order","=",self.po_order)])
		imd = self.env['ir.model.data']
		action = imd.xmlid_to_object('sale.action_quotations')
		list_view_id = imd.xmlid_to_res_id('sale.view_quotation_tree')
		form_view_id = imd.xmlid_to_res_id('sale.view_order_form')
		result = {
			'name': action.name,
			'help': action.help,
			'type': action.type,
			'views': [[list_view_id, 'tree'], [form_view_id, 'form'],
				[False, 'graph'], [False, 'kanban'], [False, 'calendar'], [False, 'pivot']],
			'target': action.target,
			'context': action.context,
			'res_model': action.res_model,
		}
		if len(so_ids) > 1:
			result['domain'] = "[('id','in',%s)]" % so_ids.ids
		elif len(so_ids) == 1:
			result['views'] = [(form_view_id, 'form')]
			result['res_id'] = so_ids.ids[0]
		else:
			result = {'type': 'ir.actions.act_window_close'}
		return result
