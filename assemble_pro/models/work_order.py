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

class work_order(models.Model):
	_inherit = ['purchase.order']
	
	READONLY_STATES = {
		'purchase': [('readonly', True)],
		'done': [('readonly', True)],
		'cancel': [('readonly', True)],
	}
	
	# @api.model
	# def _default_picking_type(self):
	# 	type_obj = self.env['stock.picking.type']
	# 	company_id = self.env.context.get('company_id') or self.env.user.company_id.id
	# 	types = type_obj.search([('code', '=', 'incoming'), ('warehouse_id.company_id', '=', company_id)])
	# 	print "HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH" , types , types.name , types.code
	# 	if not types:
	# 		types = type_obj.search([('code', '=', 'dc'),('warehouse_id.company_id', '=', company_id)])
	# 		print "MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM" , types , types[:1] , types[:1].name , types[:1].code #, types[:2] , types[:2].name , types[:2].code
	# 	
	# 	return types[:1]

	type_order = fields.Selection([
		('purchase', 'Purchase Order'),
		('work', 'Work Order'),
		# ('claim', 'Claim order'),
		], string='Type of Order', store=True)
	attach_doc_count = fields.Integer(string="Number of documents attached", compute='count_docs')
	service = fields.Char(String="Service")
	partner_id = fields.Many2one('res.partner', string='Vendor', states=READONLY_STATES, change_default=True, track_visibility='always')
	dc_type = fields.Selection([('returnable', 'Returnable'), ('non_returnable', 'Non-Returnable')], 'Type of DC')
	payment = fields.Selection([('billable', 'Billable'), ('non_billable', 'Non-Billable')], 'Payment')
	sac_code = fields.Char(string='SAC Code', related="company_id.sac_code")

	@api.multi
	def button_approve(self):
		self.write({'state': 'purchase'})
		if self.type_order == 'purchase' or (self.type_order == 'work' and self.dc_type == 'returnable'):
			self._create_picking()
		return {}


	@api.multi
	def count_docs(self):
		sp_ids = self.env['stock.picking'].search([("work_order_id","=",self.id)])
		if len(sp_ids):
			self.attach_doc_count = len(sp_ids) or 0

	@api.multi
	def get_attached_docs(self):
		if self.type_order == 'work' :
			type_obj = self.env['stock.picking.type']
			company_id = self.env.context.get('company_id') or self.env.user.company_id.id
			types = type_obj.search([('code', '=', 'dc'), ('warehouse_id.company_id', '=', company_id)])
			

		ctx = self._context.copy()
		sp_ids = self.env['stock.picking'].search([("work_order_id","=",self.id)])
		imd = self.env['ir.model.data']
		action = imd.xmlid_to_object('stock.action_picking_tree_ready')
		tree_view_id = imd.xmlid_to_res_id('stock.vpicktree')
		form_view_id = imd.xmlid_to_res_id('stock.view_picking_form')
		if sp_ids:
			result = {
				'name': action.name,
				'help': action.help,
				'type': action.type,
				'views': [[form_view_id,'form'],[tree_view_id, 'tree']],
				'target': action.target,
				'res_model': action.res_model,
			}
			if len(sp_ids) > 1:
				result['domain'] = "[('id','in',%s)]" % sp_ids.ids
				
			elif len(sp_ids) == 1:
				result['views'] = [(form_view_id, 'form')]
				result['res_id'] = sp_ids.ids[0]
			else:
				result = {'type': 'ir.actions.act_window_close'}
			self.attach_doc_count = len(sp_ids) or 0
			return result
		
		if not sp_ids:
			ctx.update({
				'default_picking_type_code' : 'dc',
				'default_partner_id':self.partner_id.id,
				'default_work_order_id':self.id,
				'default_picking_type_id' : types[:1].id,
				'default_origin': self.name,
				'default_service': self.service,
				'default_dc_type': self.dc_type,
				'default_payment': self.payment,
			})
			result = {
				'name': action.name,
				'help': action.help,
				'type': action.type,
				'views': [[form_view_id, 'form'],[tree_view_id, 'tree']],
				'target': action.target,
				'domain': [('picking_type_code','=', 'dc')],
				'context': ctx,
				'res_model': action.res_model,
			}
		return result
	
	@api.model
	def create(self, vals):
		
		if ('name' not in vals and vals['type_order'] == 'work')\
		or ('name' in vals and vals.get('name') == 'New' and vals['type_order'] == 'work'):
			vals['name'] = self.env['ir.sequence'].next_by_code('work.order')
		result = super(work_order, self).create(vals)
		return result
	
# class work_order_line(models.Model):
# 	_inherit = ['purchase.order.line']
	
	# @api.onchange('product_id')
	# def onchange_product_id(self):
	# 	result = super(work_order_line, self).onchange_product_id()
	# 	
	# 	if self.order_id.type_order == 'work':
	# 		dt = datetime.datetime.strptime(self.order_id.date_order,'%Y-%m-%d %H:%M:%S')
	# 		dd = dt.date()
	# 		supplier_pricelist = self.env['product.supplierinfo'].search([('name','=',self.order_id.partner_id.id),('date_start','<=',dd),('date_end','>=',dd)],order="create_date desc")
	# 		if len(supplier_pricelist):
	# 			for price in supplier_pricelist[0]:
	# 				for line in price.supplierinfo_id:
	# 					if self.product_id.product_tmpl_id.id == line.product_tmpl_id.id:
	# 						self.price_unit = line.rate or 0
	# 						# print "AAAAAAAAAAAAAAAAAAAAAAAAAAAA" , self.price_unit
	# 						# result['value'] = {'price_unit': line.rate or 0}
	# 		else:
	# 			raise ValidationError("No PriceList available for Vendor  '%s' " % (self.order_id.partner_id.name))
	# 	# {'domain': {'product_uom': [('category_id', '=', 1)]}}
	# 	# print "UUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUU" , result
	# 	
	# 	return result
	
	# @api.onchange('product_qty', 'product_uom')
	# def _onchange_quantity(self):
	# 	result = super(work_order_line, self)._onchange_quantity()
	# 	# if self.order_id.type_order == 'work':
	# 	dt = datetime.datetime.strptime(self.order_id.date_order,'%Y-%m-%d %H:%M:%S')
	# 	dd = dt.date()
	# 	supplier_pricelist = self.env['product.supplierinfo'].search([('name','=',self.order_id.partner_id.id),('date_start','<=',dd),('date_end','>=',dd)],order="create_date desc")
	# 	if len(supplier_pricelist):
	# 		for price in supplier_pricelist[0]:
	# 			for line in price.supplierinfo_id:
	# 				if self.product_id.product_tmpl_id.id == line.product_tmpl_id.id:
	# 					self.price_unit = line.rate or 0
	# 					# print "AAAAAAAAAAAAAAAAAAAAAAAAAAAA" , self.price_unit
	# 					# result['value'] = {'price_unit': line.rate or 0}
	# 	else:
	# 		raise ValidationError("No PriceList available for Vendor  '%s' " % (self.order_id.partner_id.name))
	# 	# {'domain': {'product_uom': [('category_id', '=', 1)]}}
	# 	# print "UUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUU" , result
	# 	return result
