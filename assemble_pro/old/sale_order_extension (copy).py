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
import openerp.addons.decimal_precision as dp

class sale_order_line_entension(models.Model):
	_inherit = ['sale.order.line']
	
	length = fields.Float(string="Length", track_visibility='always')
	default_code = fields.Char('code' , related="product_id.default_code")
	# box_code = fields.Char('Box code' , related="product_id.product_packaging_id.name" ,store= True)
	claim_selection=fields.Boolean()
	box_code = fields.Many2one('product.packaging', string='Box code')

	stops = fields.Integer(string="Stops", track_visibility='always')
	variant_amount = fields.Float(string="Variant Amount", default=0.0)
	
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


	

class sale_order_entension(models.Model):
	_inherit = ['sale.order']
	
	import_text = fields.Boolean(String="Import Trough Text File")
	po_order = fields.Char('PO number/Group',size=120)
	po_date = fields.Date(string="PO Date" )
	vat_no = fields.Char(String='VAT TIN')
	cst_no = fields.Char(String='CST TIN')
	service_tax_no = fields.Char(String='Service Tax Code No')
	delivery_date = fields.Date(string="Delivery date" )
	
	# product_packaging_id = fields.Many2one('packaging.extension',string="Box Details")
	product_packaging_one2many = fields.One2many('packaging.extension','packaging_id',string="Box Details")
	amount_package = fields.Monetary(string='Package Amount', store=True, readonly=True, compute='_amount_all', track_visibility='always')
	
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
	# 	super(sale_order_entension, self)._amount_all()
	# 	for res in self:
	# 		amount_pkg = 0.0
	# 		for line in res.product_packaging_one2many:
	# 			amount_pkg += line.amount
	# 		res.update({
	# 			'amount_package': res.pricelist_id.currency_id.round(amount_pkg),
	# 			'amount_total': res.amount_untaxed + res.amount_tax + amount_pkg,
	# 		})
	
	@api.depends('carrier_id', 'partner_id', 'order_line')
	def _compute_delivery_price(self):
		for order in self:
			if order.state != 'draft':
				# We do not want to recompute the shipping price of an already validated/done SO
				continue
			elif order.carrier_id.delivery_type != 'grid' and not order.order_line:
				# Prevent SOAP call to external shipping provider when SO has no lines yet
				continue
			else:
				continue # as per LCPL Condition
				# order.delivery_price = order.carrier_id.with_context(order_id=order.id).price

	@api.multi
	def delivery_set(self):
	
		# Remove delivery products from the sale order
		# self._delivery_unset() # as per LCPL Condition
	
		for order in self:
			print "LLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLVVVVVVVVVVVVVVVV"
			carrier = order.carrier_id
			if carrier:
				if order.state not in ('draft', 'sent'):
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
		inv_obj = self.env['account.invoice']
		if self.type_order == 'claim':
			res = []
			for inv in self:
				inv_res = super(sale_order_entension, inv).action_invoice_create(grouped=grouped, final=final)
				result_obj = inv_obj.search([('id','in',inv_res)])
				for result in result_obj:
					result.type_order = 'claim'
					if result.company_id.id == 1:
						result.carrier_id = inv.carrier_id.name
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
				order_res = super(sale_order_entension, order).action_invoice_create(grouped=grouped, final=final)
				res.append(order_res)
				inv_rec = inv_obj.search([('id','in',order_res)])
				
				
				for invoice in inv_rec:
					if order.import_text:
						invoice.invoice_lines_boolean = order.import_text
					if invoice.company_id.id == 1:
						invoice.carrier_id = order.carrier_id.name
						invoice.amount_freight = order.delivery_price
						
					for box_line in order.product_packaging_one2many:
						box_vals = {
							'name': box_line.name.id,
							'code': box_line.code,
							'amount': box_line.amount,
							'rate': box_line.rate,
							'qty': box_line.qty,
							'account_packaging_id': invoice.id
						}
						self.env['packaging.extension'].create(box_vals)
						
						
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
									inv_data['carrier_id'] = order.carrier_id.name
									inv_data['amount_freight'] = order.delivery_price
								invoice = inv_obj.create(inv_data)
								invoices[group_key] = invoice
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
								'account_packaging_id': invoice.id
							}
							self.env['packaging.extension'].create(box_vals)
			
			
			for invoice in invoices.values():
				# If invoice is negative, do a refund invoice instead
				if invoice.amount_untaxed < 0:
					invoice.type = 'out_refund'
					for line in invoice.invoice_line_ids:
						line.quantity = -line.quantity
				# Necessary to force computation of taxes. In account_invoice, they are triggered
				# by onchanges, which are not triggered when doing a create.
				invoice.compute_taxes()
	
			return [inv.id for inv in invoices.values()]

	@api.model
	def create(self, vals):
		result = super(sale_order_entension, self).create(vals)
		return result
			
	@api.onchange('order_line')
	def onchange_order_line(self):
		result = {}
		box_dict = {}
		saved_dict = {}
		final_result = []

		for line in self.product_packaging_one2many:
			result[line.code] = []
			box_dict[line.code] = line.name.id
			saved_dict[line.code] = line
		
		for record in self.order_line:
			if record.box_code:
				box_code = record.box_code.code.encode("utf-8")
				if box_code in result:
					result[box_code].append(record.price_subtotal)
				else:
					box_dict[box_code] = record.box_code.id
					result[box_code] = [record.price_subtotal]
				
		for key,value in result.items():
			total_amount = sum(value)
			vals = {
				'name':box_dict[key],
				'code':key,
				'qty':1,
				'rate':total_amount,
				'amount':total_amount
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
		res = super(sale_order_entension, self).action_confirm()
		
		if self.picking_ids:
			for record in self.picking_ids:
				record.import_text = self.import_text
				# record.carrier_id = self.carrier_id
		
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
	po_order = fields.Char('PO number/Group',size=120)
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
	
	
	@api.one
	def import_csv_file(self):
		code = []
		box_codes = []
		order_line_ids = []
		order_line_vals = []
		absent_products = []
		default_code_ids = []
		def_code_ids = []
		error_lines = []
		variant_list = []
		line_pro_ids = []
		validation_line_ids = []
		new_ids = []
		line_sale = []
		line_sd_var_list = []
		line_tt = 0.0
		underscore_detected = False
		current_box = False
		
		prod_package = self.env['product.packaging'].search([])
		for pro_p in prod_package:
			box_codes.append(pro_p.code.encode('utf-8').strip())
		customer = self.env['res.partner'].search([('name','=','Schindler India Private Limited')])
		if len(customer) > 1:
			customer = customer[0]
		tax_id = self.env['account.tax'].search([('name','=','Excise Duty (Non12.50 %')])
		payment_term = self.env['account.payment.term'].search([('name','=','Immediate Payment')])
		prod = self.product_id.search([])
		prod_code = [x.default_code for x in prod]
		for pro in prod_code:
			if pro != False:
				code.append(pro.encode('utf-8').strip())
		# incoterm = self.env['stock.incoterms'].search([('name','=','EXW Ponda')])
		# prod_global = self.product_id.search([])
		# cust_pricelist = self.env['product.pricelist'].search([('name','=',customer.name)],order="create_date desc")
		# if len(cust_pricelist) > 1:
		# 	cust_pricelist = cust_pricelist[0]
		
				
		if not self.pricelist_id:
			cust_pricelist = self.pricelist_id.search([('name','=',customer.name)],order="create_date desc")
			if len(cust_pricelist) > 1:
				customer_pricelist = cust_pricelist[0]
				cust_pricelist= customer_pricelist.id
		else:
			customer_pricelist = self.pricelist_id
			cust_pricelist = self.pricelist_id.id
			
		sale_values = {
			'partner_id':customer.id,
			'import_text':True,
			'payment_term_id':payment_term.id,
			'note':"",
			'type_order':'sale',
			'pricelist_id':cust_pricelist,
			# 'incoterm':incoterm.id,
			# 'vat_no':customer.vat_no,
			# 'cst_no':customer.cst_no,
			# 'service_tax_no':customer.service_tax_no,
		}
		
		sale_line_values = {
			'sequence':10,
			'product_uom':1,
			'customer_lead':7,
			'variant_amount':0.0,
			'tax_id':[(4,tax_id.id)],
		}
		
		elements_to_fetch = ["Date:","PO number/Group","VAT TIN:", "CST TIN:",
							 "Delivery date:","Sales order", "Commissions number",
							 'VAT TIN','CST TIN','Service Tax Code No','Incoterms']
		elements_fetched = []
		field_elements_dict = {
			"Date:":"po_date",
			"PO number/Group":"po_order",
			"Delivery date:":"delivery_date",
			"Sales order:":"name",
		}

		filetxt="/opt/odoo/openerp/new"+str(self.create_uid.id)+".txt"
		with(open(filetxt,'wb')) as  u:
			u.write(base64.decodestring(self.import_file))
			u.close()

		fp =open("/opt/odoo/openerp/new"+str(self.create_uid.id)+".txt")
		
		
		sale_note = "\
Following products need to be added in products master\n\
Product code:\n\
"
		
		for line_date in fp:
				
			if "_____________________________" in line_date:
				underscore_detected = True
			
			if underscore_detected == True:
				for box_code in prod_package:
					bx_code = box_code.code.encode("utf-8")
					if bx_code in line_date:
						current_box = box_code
			else:
				underscore_detected = False

			
			if "/1 " in line_date and 'Piece' in line_date: # For Inserting In Sale order Line
				if any(ext in line_date for ext in code):
					line_list = line_date.split('/1')
					line_prod = line_date.split('1.00')
					line_pro = ''.join(line_prod[0].strip())
					line_pro_ids.append(line_pro)
					
					line_tot = ''.join(line_list[1].strip())
					line_d = ''.join(line_list[0].strip())
					line_l = line_d.split('Piece')
					line_unit = line_l[1].strip()
					
					i = float(line_tot.replace(',', ''))
					j = float(line_unit.replace(',', ''))
					h = i / j
					
					for cp in customer_pricelist.pricelist_line_id:
						if cp.default_code == line_pro and cp.rate != j:
							error_lines.append((line_pro,line_unit,cp.rate))
					
					prod_temp = self.product_id.search([('default_code','=',line_pro)])
					if prod_temp.name:
						sale_line_values['name'] = prod_temp.name
						sale_line_values['default_code'] = line_pro
						sale_line_values['product_id'] = prod_temp.id
						sale_line_values['price_unit'] = j
						sale_line_values['product_uom_qty'] = h
						sale_line_values['price_subtotal'] = i
						sale_line_values['box_code'] = current_box.id
						order_line_vals.append(sale_line_values.copy())
						validation_line_ids.append(line_pro)
					else:
						line_code = line_pro[:-1]
						
						is_variant = False
						for idx, record in enumerate(order_line_vals):
							if line_code == record['default_code']:
								is_variant = True
								variant_list.append(line_pro)
								
								order_line_vals[idx]['variant_amount'] = j
						if not is_variant:
							print "OOOOOOOOOOOOOOOOOOOOOOOOOOOOO Product not present"
							raise ValidationError('Product(s) with code %s is not present in the System' % (line_pro))
						

			if "Date:" in elements_to_fetch and "Date:" in line_date: # For extracting PO Date
				line_list=line_date.split('Date:')
				line_d = ''.join(line_list[1].strip())
				line_l = line_d[0:10]
				d = datetime.datetime.strptime(line_l, "%d.%m.%Y")
				temp = d.strftime("%Y-%m-%d")
				self.po_date = temp
				sale_values['po_date'] = temp
				elements_fetched.append("Date:")
				elements_to_fetch.pop(elements_to_fetch.index("Date:"))
			
			if "PO number/Group" in elements_to_fetch and "PO number/Group" in line_date: # For extracting PO number/Group
				line_list=line_date.split(':')
				self.po_order =  line_list[1]
				
				sale_values['po_order'] = line_list[1]
				elements_fetched.append("PO number/Group")
				elements_to_fetch.pop(elements_to_fetch.index("PO number/Group"))
				
			if "Sales order" in elements_to_fetch and "Sales order" in line_date: # For extracting SO no.
				line_list=line_date.split(':')
				line_d = ''.join(line_list[1].strip())
				line_l = line_d[0:10]
				line_l = line_l.strip()
				line_sale.append(line_l)
				
			if "Delivery date:" in elements_to_fetch and "Delivery date:" in line_date: # For extracting Delivery date
				line_list=line_date.split('Delivery date:')
				line_d = ''.join(line_list[1].strip())
				line_l = line_d[0:10]
				d = datetime.datetime.strptime(line_l, "%d.%m.%Y")
				temp = d.strftime("%Y-%m-%d")
				self.delivery_date = temp
				sale_values['delivery_date'] = temp
				elements_fetched.append("Delivery date:")
				elements_to_fetch.pop(elements_to_fetch.index("Delivery date:"))
				
				
			if "Commissions number" in elements_to_fetch and "Commissions number" in line_date: # For extracting SO no.
				line_list=line_date.split('Commissions number')
				line_d = ''.join(line_list[1].strip())
				self.name = line_d
				
				sale_order_list = self.env['sale.order'].search([])
				sale_order_code = [x.name.encode('utf-8') for x in sale_order_list]
				if str(self.name) not in sale_order_code:
					sale_values['name'] = line_d
				else:
					print "SSSSSSSSSSSSSSSSSSSSSSSSS Commissions number"
					raise ValidationError('Sale Order %s already present in the System '% (self.name))
				
				elements_fetched.append("Commissions number")
				elements_to_fetch.pop(elements_to_fetch.index("Commissions number"))
			
			
			if "Maharashtra" in line_date and "India" in line_date:
				for cust_address in customer.child_ids:
					if cust_address.state_id.name == 'Maharashtra':
						sale_values['partner_shipping_id'] = cust_address.id
						
			if "Harayana" in line_date and "India" in line_date:
				for cust_address in customer.child_ids:
					if cust_address.state_id.name == 'Harayana':
						sale_values['partner_shipping_id'] = cust_address.id
						
			if "VAT TIN" in elements_to_fetch and "VAT TIN" in line_date: 
				line_list=line_date.split('VAT TIN: ')
				line_vat = ''.join(line_list[1].strip())
				sale_values['vat_no'] = line_vat
				
			if "CST TIN" in elements_to_fetch and "CST TIN" in line_date: 
				line_list=line_date.split('CST TIN:')
				line_cst = ''.join(line_list[1].strip())
				sale_values['cst_no'] = line_cst
				
			if "Service Tax Code No" in elements_to_fetch and "Service Tax Code No" in line_date:
				line_list=line_date.split('Service Tax Code No :')
				line_cst = ''.join(line_list[1].strip())
				line_st = line_cst.split("Quotation number:")
				line_service = ''.join(line_st[0].strip())
				sale_values['service_tax_no'] = line_service
				
			if "Total net value excl. TAX INR" in line_date:
				line_total=line_date.split('Total net value excl. TAX INR')
				line_tl = ''.join(line_total[1].strip())
				line_tt = float(line_tl.replace(',', ''))
				
			if "SD- Variant condition" in line_date:
				line_sd_variant=line_date.split('SD- Variant condition')
				line_sd = ''.join(line_sd_variant[1].strip())
				line_sd_var = str(line_sd.replace(',', ''))
				line_sd_var_list.append(line_sd_var)

			# if "Incoterms" in elements_to_fetch and "Incoterms" in line_date:
			# 	line_list=line_date.split('Incoterms:')
			# 	line_term = ''.join(line_list[1].strip())
			# 	line_st = line_term.split("Our")
			# 	line_inco = ''.join(line_st[0].strip())
			# 	inco = self.env['stock.incoterms'].search([('name','ilike',line_inco)])
			# 	if inco and len(inco):
			# 		sale_values['incoterm'] = inco.id
			# 	else:
			# 		raise ValidationError('Incoterm(s) with name %s is not present in the System' % (line_inco,))
			
			# for val_rec in validation_line_ids:
			# 	if val_rec in line_date:
			# 		print "DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD" , val_rec
			# 		validation_line_ids.remove(val_rec)
					
		
		
		
		fp2 =open("/opt/odoo/openerp/new"+str(self.create_uid.id)+".txt")
		test123 = re.findall(r"\s\d{8}[A-Z]{3}\s|\s\d{8}[A-Z]{2}\s|\s\d{8}[A-Z]{1}\s|\s\d{8}\s", fp2.read())
		test456 = [x.strip() for x in test123]
		
		for var_rec in variant_list:
			if var_rec in validation_line_ids:
				validation_line_ids.remove(var_rec)
				test456.remove(var_rec)
				
		for sd_var in line_sd_var_list:
			if sd_var in test456:
				# validation_line_ids.remove(sd_var)
				test456.remove(sd_var)
		
		test_arr = []
		for idx, var_rec in enumerate(test456):
			count_var = test456.count(var_rec)
			if count_var < 2:
				test_arr.append(var_rec)
		
		test_arr2 = []
		for var_rec in test_arr:
			if var_rec not in box_codes:
				test_arr2.append(var_rec)
				
		test_arr3 = []
		for tinng in test_arr2:
			if tinng not in variant_list:
				test_arr3.append(tinng)
		
		for toonng in line_sale:
			if toonng in test_arr3:
				test_arr3.remove(toonng)

		if len(test_arr3):
			missing_string = "\
Kindly Check The PO \n\
Product(s) with following code are missing from the Line Items :\n\
Product code :\n\
				   "
			for missing_line in test_arr3:
				# if missing_line in 
				missing_string += "\n%s " % (missing_line)
			print "XXXXXXXXXXXXXXXXXXXXXXXXXXXX  missing from the Line Items "
			raise ValidationError(missing_string)
		
		if len(error_lines):
			error_string = "\
Product(s) with following code have different rate in the System:\n\
Product code --- Pricelist value  --- Value in PO\
				"
			for error in error_lines:
				error_string += "\n%s -- --  -- %s  -- -- -- -- --  %s" % ( error[0],error[1],error[2])
			print "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX Pricelist Mismatch "
			raise ValidationError(error_string)
		
		if len(variant_list):
			sale_note = sale_note + "\n".join(variant_list)
			sale_values['note'] = sale_note
		
		sale_obj = self.env['sale.order'].create(sale_values)
		
		for line in order_line_vals:
			line['order_id']= sale_obj.id
			sale_line_obj = self.env['sale.order.line'].create(line)
			self.state = 'done'
			
		if not sale_obj.carrier_id:
			a = sale_obj.carrier_id.search([("state_ids","=",sale_obj.partner_shipping_id.state_id.id)])
			if a and len(a):
				a_rec = a[0]
				sale_obj.carrier_id = a_rec.id
				sale_obj.delivery_price = a_rec.amount
			# print AAi
			
		amount_untaxed = sale_obj['amount_untaxed']
		if str(amount_untaxed) != str(line_tt):
			print "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX Amount Mismatch "
			raise ValidationError('Amount Mismatch \n Total net value excl. TAX INR in PO is %s and Untaxed Amount calculated is %s'% (line_tt ,amount_untaxed))
		
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
			'views': [[list_view_id, 'tree'], [form_view_id, 'form'], [False, 'graph'], [False, 'kanban'], [False, 'calendar'], [False, 'pivot']],
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