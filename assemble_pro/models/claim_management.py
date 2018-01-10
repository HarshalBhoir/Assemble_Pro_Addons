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
from openerp.tools import openerp,image_colorize, image_resize_image_big
# from datetime import date


class claim_order(models.Model):
	_inherit = ['sale.order']
	# _table ="sale_order"
	# _name = "claim.management"
	
	claim_date = fields.Date(string="Claim Date" )
	claim_order_id = fields.Many2one('sale.order',string="Claim No." )
	type_order = fields.Selection([
		('sale', 'Sale Order'),
		# ('work', 'Work Order'),
		('claim', 'Claim order'),
		], string='Type of Order', store=True)
	state = fields.Selection([
		('draft', 'Quotation'),
		('sent', 'Quotation Sent'),
		('sale', 'Sale Order'),
		('done', 'Done'),
		('cancel', 'Cancelled'),
		], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')
	claim_state = fields.Selection([
		('draft', 'Quotation'),
		('sent', 'Quotation Sent'),
		('sale', 'Claim Order'),
		('done', 'Done'),
		('cancel', 'Cancelled'),
		], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')
	# claim_line = fields.One2many('claim.order.line', 'claim_id', string='Claim Lines', copy=True)
	# mrp_repair_id = fields.Many2one('mrp.repair', track_visibility='always' )
	
	@api.model
	def create(self, vals):
		if ('name' not in vals and vals['type_order'] == 'claim')\
		or ('name' in vals and vals.get('name') == 'New' and vals['type_order'] == 'claim'):
			vals['name'] = self.env['ir.sequence'].next_by_code('claim.order')
		result = super(claim_order, self).create(vals)
		return result
	
	@api.multi
	def write(self, vals):
		if 'state' in vals and vals.get('state'):
			vals['claim_state'] = vals.get('state')
		if 'claim_state' in vals and vals.get('claim_state'):
			vals['state'] = vals.get('claim_state')
		result = super(claim_order, self).write(vals)
		return result


	# @api.multi
	# @api.onchange('partner_id')
	# def onchange_partner_id(self):
	# 	super(claim_order, self).onchange_partner_id()
	# 	result = {'domain': {'claim_order_id': []}}
	# 	claim_ids = []
	# 	print "AAAAAAAAAAAAAAAAAAAAAAAA"
	# 	if self.partner_id and self.type_order == 'claim':
	# 		srch = self.env['sale.order'].search([('partner_id','=',self.partner_id.id)])
	# 		for srch1 in srch :
	# 			if 'CMO' not in srch1.name:
	# 				claim_ids.append(srch1.id)
	# 
	# 		result = {'domain': {'claim_order_id': [('id','in',claim_ids)]}}
	# 	return result
		
	
	# @api.multi
	# @api.onchange('claim_order_id')
	# def onchange_claim_id(self):
	# 	claim_line_ids = []
	# 	result = []
	# 	if self.claim_order_id:
	# 		for i in self.claim_order_id.order_line:
	# 			vals = {
	# 						'product_id':i.product_id,
	# 						'name':i.name,
	# 						'price_unit':i.price_unit,
	# 						'product_uom_qty':i.product_uom_qty,
	# 						'product_uom':i.product_uom
	# 					}
	# 			result.append(vals)
	# 
	# 		self.order_line = result
	# 		self.claim_line = result
	# 		
	# @api.multi
	# def claim_products(self):
	# 	# self._cr.execute('delete from claim_order_line where  claim_selection = False and claim_id = %d' % (self.id))
	# 	for i in self.claim_line:
	# 		if not i.claim_selection:
	# 			i.unlink()
	# 	self.state = 'claim'
	# 	
	# 	
	# @api.multi
	# def action_repair(self):
	# 	ctx = self._context.copy()
	# 	ctx.update({
	# 		'default_partner_id': self.partner_id.id,
	# 		'default_claim_order_id': self.id,
	# 	})
	# 	# self.state = 'done'
	# 	imd = self.env['ir.model.data']
	# 	action = imd.xmlid_to_object('mrp_repair.action_repair_order_tree')
	# 	form_view_id = imd.xmlid_to_res_id('mrp_repair.view_repair_order_form')
	# 	
	# 	result = {
	# 		'name': action.name,
	# 		'help': action.help,
	# 		'type': action.type,
	# 		'views': [[form_view_id, 'form']],
	# 		'target': action.target,
	# 		'context': ctx,
	# 		'res_model': action.res_model,
	# 	}
	# 	return result
		
			
# class claim_order_line(models.Model):
# 	_name = 'claim.order.line'
# 	
# 	name = fields.Text(string='Item Name')
# 	sequence = fields.Integer(string='Sequence',)
# 	state = fields.Selection([
# 		('draft', 'Quotation'),
# 		 ('sent', 'Quotation Sent'),
# 		 ('sale', 'Sale Order'),
# 		 ('claim', 'Claim Order'),
# 		 ('repair', 'Repair Order'),
# 		 ('done', 'Done'),
# 		 ('cancel', 'Cancelled'),
# 		], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')
# 	date = fields.Datetime(string='Order Date',  default=fields.Datetime.now)
# 	claim_id = fields.Many2one('sale.order', string='Claim Reference', ondelete='cascade', index=True, copy=False)
# 	claim_selection=fields.Boolean(string='select')
# 	
# 	# price_unit = fields.Float('Unit Price', digits=dp.get_precision('Product Price'), default=0.0)
# 	
# 	# price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', readonly=True, store=True)
# 	# price_tax = fields.Monetary(compute='_compute_amount', string='Taxes', readonly=True, store=True)
# 	# price_total = fields.Monetary(compute='_compute_amount', string='Total', readonly=True, store=True)
# 	# 
# 	# price_reduce = fields.Monetary(compute='_get_price_reduce', string='Price Reduce', readonly=True, store=True)
# 		
# 	product_id = fields.Many2one('product.product', string='Product', change_default=True, ondelete='restrict')
# 	product_uom_qty = fields.Float(string='Quantity', default=1.0)
# 	product_uom = fields.Many2one('product.uom', string='Unit of Measure')
# 	
# 	currency_id = fields.Many2one(related='claim_id.currency_id', store=True, string='Currency', readonly=True)
# 	company_id = fields.Many2one(related='claim_id.company_id', string='Company', store=True, readonly=True)
# 	order_partner_id = fields.Many2one(related='claim_id.partner_id', store=True, string='Customer')
# 	
# 	length = fields.Float(string="Length", track_visibility='always')
# 	default_code = fields.Char('code' , related="product_id.default_code")
# 	stops = fields.Integer(string="Stops", track_visibility='always')
# 	
# 	state = fields.Selection([
# 		('draft', 'Quotation'),
# 		('sent', 'Quotation Sent'),
# 		('sale', 'Sale Order'),
# 		('claim', 'Claim Order'),
# 		('repair', 'Repair Order'),
# 		('done', 'Done'),
# 		('cancel', 'Cancelled'),
# 	], related='claim_id.state', string='Claim Status', readonly=True, copy=False, store=True, default='draft')