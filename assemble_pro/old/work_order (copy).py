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
	

	type_order = fields.Selection([
		('purchase', 'Purchase Order'),
		('work', 'Work Order'),
		# ('claim', 'Claim order'),
		], string='Type of Order', store=True)
	attach_doc_count = fields.Integer(string="Number of documents attached", compute='count_docs')
	service = fields.Char(String="Service")
	

	@api.multi
	def count_docs(self):
		so_ids = self.env['stock.picking'].search([("work_order_id","=",self.id)])
		if len(so_ids):
			self.attach_doc_count = len(so_ids) or 0
			
	@api.multi
	def get_attached_docs(self):

		if self.type_order == 'work' :
			type_obj = self.env['stock.picking.type']
			company_id = self.env.context.get('company_id') or self.env.user.company_id.id
			types = type_obj.search([('code', '=', 'dc'), ('warehouse_id.company_id', '=', company_id)])
			if not types:
				types = type_obj.search([('code', '=', 'dc'), ('warehouse_id', '=', False)])
		
		sp_ids = self.env['stock.picking'].search([("work_order_id","=",self.id)])
		if sp_ids:
			
			imd = self.env['ir.model.data']
			action = imd.xmlid_to_object('stock.action_picking_tree_ready')
			form_view_id = imd.xmlid_to_res_id('stock.view_picking_form')
			result = {
				'name': action.name,
				'help': action.help,
				'type': action.type,
				'views': [form_view_id,'form'],
				'target': action.target,
				'context': action.context,
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
			# return result
		
		if not sp_ids:
			
			ctx = self._context.copy()
			ctx.update({
					'default_picking_type_code' : 'dc',
					'default_partner_id':self.partner_id.id,
					'default_work_order_id':self.id,
					'default_picking_type_id' : types[:1].id,
				})
	
			imd = self.env['ir.model.data']
			action = imd.xmlid_to_object('stock.action_picking_tree_ready')
			tree_view_id = imd.xmlid_to_res_id('stock.vpicktree')
			form_view_id = imd.xmlid_to_res_id('stock.view_picking_form')
			

			result = {
				'name' : action.name,
				'help' : action.help,
				'type' : action.type,
				'views' : [[tree_view_id, 'tree'], [form_view_id, 'form']],
				'view_mode' : 'tree,form',   
				'target' : action.target,
				'domain': [('picking_type_code','=', 'dc')],
				# 'context':
				'context' : ctx,
				'res_model' : action.res_model,
			}
		return result
	
	@api.model
	def create(self, vals):
		
		if ('name' not in vals and vals['type_order'] == 'work')\
		or ('name' in vals and vals.get('name') == 'New' and vals['type_order'] == 'work'):
			vals['name'] = self.env['ir.sequence'].next_by_code('work.order')
		result = super(work_order, self).create(vals)
		return result