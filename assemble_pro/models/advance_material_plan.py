from openerp.exceptions import UserError, MissingError, ValidationError
import csv
import base64
import decimal
import openerp
from openerp import models, fields, api, _, tools
from openerp.exceptions import UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import time
import logging
from openerp.tools import float_is_zero,openerp,image_colorize, image_resize_image_big
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
import re , collections
from collections import Counter
import openerp.addons.decimal_precision as dp
from lxml import etree

_logger = logging.getLogger(__name__)


class advance_fg_material(models.Model):
	_name = 'advance.fg.material'
	_description = "Advance Finished Goods Plan"
	_inherit = ['mail.thread', 'ir.needaction_mixin']
	_order = 'create_date desc'

	@api.multi
	def compute_fg(self):
		quants_dict = {}
		record_to_remove = []
		for record in self.advance_finishgoods_one2many:
			location = self.env['stock.location'].search([('name','ilike','finished')])
			# location = self.env.ref('stock.stock_location_stock')
			
			quant = self.env['stock.quant'].search([('location_id','=',location.id)])
			for quant_id in quant:
				if record.product_id.id == quant_id.product_id.product_tmpl_id.id:
					if record.product_id.name in quants_dict:
						quants_dict[record.product_id.name] = quants_dict[record.product_id.name] + quant_id.qty
					else:
						quants_dict[record.product_id.name] = quant_id.qty
						# quants_dict.update({record.product_id.name:quant_id.qty})
				
			for quant_name, value in quants_dict.iteritems():
				if quant_name == record.product_id.name:
					record.fg_balance = value
			
			if record.product_id:
				for rec in self.advance_finishgoods_one2many:
					if not ( rec.jan or  rec.feb or  rec.mar or   rec.apr or  rec.may or \
						  rec.jun or  rec.jul  or  rec.aug  or   rec.sep  or  rec.octo or \
						  rec.nov or  rec.dec):
						record_to_remove = rec if len(record_to_remove) == 0 else record_to_remove+rec
				
				record.req_qty = record.jan + record.feb +record.mar +record.apr+record.may+\
					 record.jun+record.jul +record.aug + record.sep +record.octo +record.nov+record.dec
				record.net_req_qty = record.req_qty - record.fg_balance

		if len(record_to_remove):
			record_to_remove.sudo().unlink()
		
		self.state ='inprogress'
	
	@api.multi
	def compute_rm_req(self):
		vals = []
		non_bom_list = []
		if not len(self.advance_finishgoods_one2many):
			raise ValidationError("No items Included")

		for record in self.advance_finishgoods_one2many:
			bom = self.env['mrp.bom'].search([('product_tmpl_id','=',record.product_id.id)],order="create_date desc")
			location = self.env.ref('stock.stock_location_stock')
			bom_product = False
			if len(bom):
				bom_product = True
				for bom_line in bom[0].bom_line_ids:
					for prod_id in bom_line.product_id.product_tmpl_id:
						prod_sup = False
						for supplier in prod_id.product_supplier_one2many:
							prod_sup = self.env['product.supplierinfo'].search([('name','=',supplier.name[0].id)])
					
						vals.append([0,0,{
							'product_id': bom_line.product_id.product_tmpl_id.id,
							'req_qty':(bom_line.product_qty * record.net_req_qty),
							'net_req_qty':(bom_line.product_qty),
							'supplier_id':prod_sup[0].name.id if prod_sup else False,
							# 'moq':bom_line.product_id.moq,
							'location_id': location and location.id or False,
						}])

			if not bom_product:
				non_bom_list.append(str(record.product_id.name))


		bom_string = "\
No BOM available for Following Product(s) :\n\n"
		if non_bom_list:
			print "IIIIIIIIIIIIIIIIIIIIII BOM Not Available"
			raise ValidationError(bom_string+"\n".join(non_bom_list))

		
		ctx = self._context.copy()
		ctx.update({
			'default_fg_plan':self.id,
			'default_date':self.date,
			'default_average_forecast':self.average_forecast,
			'default_advance_rawmaterial_one2many':vals
		})
		
		imd = self.env['ir.model.data']
		action = imd.xmlid_to_object('assemble_pro.action_advance_rm_material')
		form_view_id = imd.xmlid_to_res_id('assemble_pro.view_advance_rm_material_form')
		
		result = {
			'name': action.name,
			'help': action.help,
			'type': action.type,
			'views': [[form_view_id, 'form']],
			'target': action.target,
			'context': ctx,
			'res_model': action.res_model,
		}

		return result
	

	@api.multi
	@api.depends('advance_rm_material_id')
	def count_docs(self):
		for rec in self:
			rm_ids = rec.mapped('advance_rm_material_id')
			if len(rm_ids):
				rec.attach_doc_count = len(rm_ids) or 0
		
	@api.multi
	def get_attached_docs(self):
		rm_ids = self.mapped('advance_rm_material_id')
		imd = self.env['ir.model.data']
		action = imd.xmlid_to_object('assemble_pro.action_advance_rm_material')
		list_view_id = imd.xmlid_to_res_id('assemble_pro.view_advance_rm_material_tree')
		form_view_id = imd.xmlid_to_res_id('assemble_pro.view_advance_rm_material_form')
	
		result = {
			'name': action.name,
			'help': action.help,
			'type': action.type,
			'views': [[list_view_id, 'tree'], [form_view_id, 'form'], [False, 'graph'], [False, 'kanban'], [False, 'calendar'], [False, 'pivot']],
			'target': action.target,
			'context': action.context,
			'res_model': action.res_model,
		}
		if len(rm_ids) > 1:
			result['domain'] = "[('id','in',%s)]" % rm_ids.ids
		elif len(rm_ids) == 1:
			result['views'] = [(form_view_id, 'form')]
			result['res_id'] = rm_ids.ids[0]
		else:
			result = {'type': 'ir.actions.act_window_close'}
		return result

	# @api.depends('date','months')
	# def _compute_months(self):
	# 	for record in self:
	# 		if record.date and record.months:
	# 			month_list = []
	# 			month_future = int(sel_dict[record.months])
	# 			start_date = datetime.strptime(record.date, DEFAULT_SERVER_DATE_FORMAT).date().replace(day=1)
	# 			while month_future > 0:
	# 				mth = start_date.strftime('%b')
	# 				month_list.append(mth.lower())
	# 				start_date = start_date + relativedelta(months=+1)
	# 				month_future = month_future - 1
	# 		
	# 			record.visible_months = "['" + "','".join(month_list) + "']"
			
	name = fields.Char(string="Plan No.", track_visibility='always')
	date = fields.Date(string="Date")
	user_id = fields.Many2one('res.users', string='User', default=lambda self: self._uid, track_visibility='always')
	advance_finishgoods_one2many = fields.One2many('advance.finishgoods','advance_fg_material_id',string="Advance Finished Good")
	
	advance_rm_material_id = fields.Many2one('advance.rm.material', string="RM ID" ,  track_visibility='always')
	attach_doc_count = fields.Integer(string="Number of documents attached", compute='count_docs')
	average_forecast =  fields.Integer(string="Average Forecast", required=True)

	months = fields.Selection([
		('three', 'Three'),
		('six', 'Six'),
		('year', 'Year'),
		], string='Months', track_visibility='always', default='three')
	
	state = fields.Selection([
		('draft', 'Draft'),
		('inprogress','In Progress'),
		('done', 'Done'),
		('cancel', 'Cancelled'),
		], string='Status', readonly=True,
		copy=False, index=True, track_visibility='always', default='draft')
	
	@api.model
	def create(self, vals):
		vals['name'] = self.env['ir.sequence'].next_by_code('advance.fg.material')
		# vals['state'] = 'done'
		result = super(advance_fg_material, self).create(vals)

		if not len(result.advance_finishgoods_one2many):
			raise ValidationError("No items Included")
		return result
	
	@api.multi
	def name_get(self):
		result= []
		for ai in self:
			b = datetime.strptime(ai.date, '%Y-%m-%d').strftime('%d %B %Y')
			name = str(ai.name) + ' ( '+b+ ' )'
			result.append((ai.id,name))
		return result
	

class advance_finishgoods(models.Model):
	_name = 'advance.finishgoods'
	_description = "Advance Finished Good"
	_rec_name='product_id'
	
	# name = fields.Char(string="Description", track_visibility='always')
	sequence = fields.Integer(string="Seq", track_visibility='always')
	default_code = fields.Char(string="Code" , related="product_id.default_code")
	product_id = fields.Many2one('product.template',string="Product" , track_visibility='always')
	req_qty = fields.Float(string="Req Qty", store= True)
	net_req_qty = fields.Float(string="Net Req Qty"  )
	fg_balance = fields.Float(string="FG Balance")
	length = fields.Float(string="Req Length")
	stops = fields.Float(string="Req Stops")
	advance_fg_material_id = fields.Many2one('advance.fg.material', track_visibility='always')
	
	jan = fields.Float(string="Jan")
	feb = fields.Float(string="Feb")
	mar = fields.Float(string="Mar")
	apr = fields.Float(string="Apr")
	may = fields.Float(string="May")
	jun = fields.Float(string="Jun")
	jul = fields.Float(string="Jul")
	aug = fields.Float(string="Aug")
	sep = fields.Float(string="Sep")
	octo = fields.Float(string="Oct")
	nov = fields.Float(string="Nov")
	dec = fields.Float(string="Dec")
	

class advance_rm_material(models.Model):
	_name = 'advance.rm.material'
	_description = "Advance Raw Material Plan"
	_inherit = ['mail.thread', 'ir.needaction_mixin']
	_order = 'create_date desc'
	
	@api.multi
	def button_dummy(self):
		return True

	@api.multi
	def generate_po(self):
		# supplier_dict = {}
		product_list = []
		po_ids = []
		po_raise_list =[]
		supplier_name = False
		for record in self.advance_rawmaterial_one2many:
			if record.po_raise == True:
				po_raise_list.append(record)
		if po_raise_list:
			supplier_dict = {}
			for po in po_raise_list:
				
				product_product = self.env['product.product'].search([('product_tmpl_id', '=', po.product_id.id)])
				
				if po.supplier_id.id in supplier_dict:
					supplier_dict[po.supplier_id.id].append((product_product, po.po_qty, po.current_price))
				else:
					supplier_dict[po.supplier_id.id] = [(product_product , po.po_qty,po.current_price)]
		else:
			# print "Hai hi nahi koi PO raise"
			raise UserError('No PO raise is found ')
		for supplier_name, product_name in supplier_dict.iteritems():
			if supplier_name:
				
				vals = {
					'partner_id':supplier_name,
					'type_order':'purchase',
					'date_order':self.date,
					# 'date_planned':self.date,
					# 'currency_id':'INR'
					'advance_rm_material_id':self.id,
					'origin':self.fg_plan.name + " / " +  self.name
				}
				purchase_order = self.env['purchase.order'].create(vals)
				po_ids.append(purchase_order.id)
				for products in product_name:
					vals_line = {
						'product_id':products[0].id,
						# 'tax_id':[(4,products[0].supplier_taxes_id.id)],
						'taxes_id':[(4,x.id) for x in products[0].supplier_taxes_id],
						'date_planned':self.date,
						'order_id':purchase_order.id,
						'product_qty':products[1],
						'name':products[0].name,
						'product_uom':products[0].uom_po_id.id,
						'price_unit':products[2] if (products[2] > 0) else products[0].standard_price,
					}
					self.env['purchase.order.line'].create(vals_line)
	
			else:
				raise UserError('Please Select Supplier For all the Products')
		
		
		imd = self.env['ir.model.data']
		action = self.env.ref('purchase.purchase_rfq')
		result = action.read([])[0]
		result['domain'] = [('id','in',po_ids)]
		self.state = 'done'
		# print Error
		return result
	
		
	@api.multi
	def count_docs(self):
		po_ids = self.env['purchase.order'].search([("advance_rm_material_id","=",self.id)])
		if len(po_ids):
			self.attach_doc_count = len(po_ids) or 0
	
	@api.multi
	def get_attached_docs(self):
		po_ids = self.env['purchase.order'].search([("advance_rm_material_id","=",self.id)])
		imd = self.env['ir.model.data']
		action = imd.xmlid_to_object('purchase.purchase_rfq')
		list_view_id = imd.xmlid_to_res_id('purchase.purchase_order_tree')
		form_view_id = imd.xmlid_to_res_id('purchase.purchase_order_form')
		result = {
			'name': action.name,
			'help': action.help,
			'type': action.type,
			'views': [[list_view_id, 'tree'], [form_view_id, 'form'], [False, 'graph'], [False, 'kanban'], [False, 'calendar'], [False, 'pivot']],
			'target': action.target,
			'context': action.context,
			'res_model': action.res_model,
		}
		if len(po_ids) > 1:
			result['domain'] = "[('id','in',%s)]" % po_ids.ids
		elif len(po_ids) == 1:
			result['views'] = [(form_view_id, 'form')]
			result['res_id'] = po_ids.ids[0]
		else:
			result = {'type': 'ir.actions.act_window_close'}
		return result
	
	
	name = fields.Char(string="Plan No.", track_visibility='always')
	fg_plan = fields.Many2one('advance.fg.material' , string='FG Plan No.')
	date = fields.Date(string="Date")
	user_id = fields.Many2one('res.users', string='User', default=lambda self: self._uid, track_visibility='always')
	advance_rawmaterial_one2many = fields.One2many('advance.rawmaterial','advance_rm_material_id',string="Advance Raw Material")
	# purchase_order_id = fields.Many2one('purchase.order', track_visibility='always' )
	purchase_order_ids = fields.Many2many("purchase.order", string='Purchases', compute="get_attached_docs", readonly=True, copy=False)
	attach_doc_count = fields.Integer(string="Number of documents attached", compute='count_docs')
	
	average_forecast =  fields.Integer(string="Average Forecast", required=True)
	
	months = fields.Selection([
		('three', 'Three'),
		('six', 'Six'),
		('year', 'Year'),
		], string='Months', track_visibility='always', default='three')
	
	state = fields.Selection([
		('draft', 'Draft'),
		('done', 'Done'),
		('cancel', 'Cancelled'),
		], string='Status', readonly=True,
		copy=False, index=True, track_visibility='always', default='draft')
	
	@api.model
	def create(self, vals):
		vals['name'] = self.env['ir.sequence'].next_by_code('advance.rm.material')
		# vals['state'] = 'done'
		result = super(advance_rm_material, self).create(vals)
		if result.fg_plan:
			result.fg_plan.state = result.state
			result.fg_plan.advance_rm_material_id = result.id
		return result
	
	@api.multi
	def write(self, values):
		result = super(advance_rm_material, self).write(values)
		if self.fg_plan:
			self.fg_plan.state = self.state
			self.fg_plan.advance_rm_material_id = self.id
		return result

	@api.multi
	def name_get(self):
		result= []
		for ai in self:
			b = datetime.strptime(ai.date, '%Y-%m-%d').strftime('%d %B %Y')
			name = str(ai.name) + ' ( '+b+ ' )'
			result.append((ai.id,name))
		return result
	
	@api.constrains('average_forecast')
	def constraints_check(self):
		if self.average_forecast == 0 :
			print "OOOOOOOOOOOOOOOOOOOOOOO Please enter Average Forecast"
			raise UserError("Please enter Average Forecast")
	

class advance_rawmaterial(models.Model):
	_name = 'advance.rawmaterial'
	_description = "Advance Raw Material"
	# _rec_name='product_id'
	
	@api.multi
	@api.depends('req_qty')
	def _compute_net_req_qty(self):
		for record in self:
			record.net_req_qty = record.req_qty - (record.order_qty  + record.wip_stock + record.store_stock)
	
	# @api.model
	# def fields_view_get(self, view_id=None, view_type=False, toolbar=False, submenu=False):
	# 	print "lllllllllllllllllll",view_type
	# 	res = super(advance_rawmaterial, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
	# 	doc = etree.XML(res['arch'])
	# 	for node in doc.xpath("//field[@name='supplier_id']"):
	# 		print "ppppppppppppppppppppp", node, self
	# 		print "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",self.env.context.get('active_ids')
	# 		for record in self:
	# 			for prod_id in record.product_id:
	# 					for supplier in prod_id.product_supplier_one2many:
	# 						prod_sup = self.env['product.supplierinfo'].search([('name','=',supplier.name[0].id)])
	# 			node.set('domain',  "[('id', 'in',["+',' .join(map(str, self.product_id.product_supplier_one2many ))+"])]")
	# 	res['arch'] = etree.tostring(doc)
	# 	return res
				
	@api.multi
	@api.depends('product_id')
	def _compute_store_stock(self):
		for record in self:
			quants_dict = {}
			quant = self.env['stock.quant'].search([('location_id','=',record.location_id.id)])
			for quant_id in quant:
				if record.product_id.id == quant_id.product_id.product_tmpl_id.id:
					if record.product_id.name in quants_dict:
						quants_dict[record.product_id.name] = quants_dict[record.product_id.name] + quant_id.qty
					else:
						quants_dict[record.product_id.name] = quant_id.qty
						
				for quant_name, value in quants_dict.iteritems():
					if quant_name == record.product_id.name:
						record.store_stock = value

	@api.multi
	@api.depends('product_id')
	def _compute_wip_stock(self):
	
		for record in self:
			wip_location = self.env['stock.location'].search([('name','ilike','wip')])
			print "LLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL" , wip_location
			quants_dict = {}
			quant = self.env['stock.quant'].search([('location_id','=',wip_location.id)])
			for quant_id in quant:
				if record.product_id.id == quant_id.product_id.product_tmpl_id.id:
					if record.product_id.name in quants_dict:
						quants_dict[record.product_id.name] = quants_dict[record.product_id.name] + quant_id.qty
					else:
						quants_dict[record.product_id.name] = quant_id.qty
				else:
					quants_dict[record.product_id.name] = 0
		
				for quant_name, value in quants_dict.iteritems():
					if quant_name == record.product_id.name:
						record.wip_stock = value
						
						
	@api.multi
	@api.depends('product_id')
	def _compute_safety_stock(self):
		for record in self:
			safety_location = self.env['stock.location'].search([('name','ilike','safety')])
			quants_dict = {}
			quant = self.env['stock.quant'].search([('location_id','=',safety_location.id)])
			for quant_id in quant:
				if record.product_id.id == quant_id.product_id.product_tmpl_id.id:
					if record.product_id.name in quants_dict:
						quants_dict[record.product_id.name] = quants_dict[record.product_id.name] + quant_id.product_id.safety_stock_days
					else:
						quants_dict[record.product_id.name] = quant_id.product_id.safety_stock_days
						
				else:
					quants_dict[record.product_id.name] = 0
		
				for quant_name, value in quants_dict.iteritems():
					if quant_name == record.product_id.name:
						record.ss_days = value
						
						
						
	@api.multi
	@api.depends('product_id')
	def _compute_order_qty(self):
		for record in self:
			order_qty_dict = {}
			order_qty = self.env['stock.move'].search([('state','=','assigned')])
			for order_qty_id in order_qty:
				if order_qty_id.origin and ('PO' in order_qty_id.origin):
					if record.product_id.id == order_qty_id.product_id.product_tmpl_id.id:
						if record.product_id.name in order_qty_dict:
							order_qty_dict[record.product_id.name] = order_qty_dict[record.product_id.name] + order_qty_id.product_uom_qty
						else:
							order_qty_dict[record.product_id.name] = order_qty_id.product_uom_qty
	
					for order_name, value in order_qty_dict.iteritems():
						if order_name == record.product_id.name:
							record.order_qty = value
							
	@api.multi
	@api.depends('product_id','supplier_id')
	def _compute_price(self):
		for record in self:
			supplier_pricelist = self.env['product.supplierinfo'].search([('name','=',record.supplier_id.id)],order="create_date desc")
			
			
			for sp in supplier_pricelist:
				# if record.supplier_id == sp.name:
				for spl in sp.supplierinfo_id:
					if spl.product_tmpl_id == record.product_id:
						record.current_price = spl.rate
						record.lead_time = spl.delay
						record.custom_lead_time = spl.custom_lead_time
						record.moq = spl.moq
					
	
	@api.multi
	@api.depends('lead_time','custom_lead_time','req_qty','ss_days','piece_ratio','order_qty')
	def compute_function(self):
		
		for record in self:
			average_forecast = record.advance_rm_material_id.average_forecast
			
			record.total_lead_time = record.lead_time  + record.custom_lead_time
			
			if record.piece_ratio and average_forecast:
				record.monthly_consumption = average_forecast * record.piece_ratio
				
			if record.ss_days and record.piece_ratio:
				record.ss_qty = ( record.ss_days *record.monthly_consumption) / 30
			else:
				record.ss_qty = 0.0

			if record.piece_ratio and record.total_lead_time:
				record.rol = (record.ss_qty  + (record.total_lead_time * ( record.monthly_consumption / 30 )))
			else:
				record.rol = record.ss_qty
			
			if record.piece_ratio:
				if (record.rol < ( record.order_qty + record.wip_stock + record.store_stock )) or (record.rol == 0.0):
					record.po_raise = True
				else:
					record.po_raise = False
					
			if record.order_qty  and record.piece_ratio:
				record.oq_days = ( record.order_qty / (( record.monthly_consumption) / 30) )
			else:
				record.oq_days = 0.0
					
					
	@api.multi
	@api.depends('req_qty')
	def _compute_po_qty(self):
		for record in self:
			if record.moq > record.req_qty:
				record.po_qty = record.moq
			else:
				record.po_qty = record.req_qty
				
	@api.multi
	@api.depends('product_id')
	def _compute_piece_ratio(self):
		for record in self:
			purchase_qty = sale_qty = 0
			product_product = self.env['product.product'].search([('product_tmpl_id','=',record.product_id.id)])
			sale_lines = self.env['sale.order.line'].search([('product_id','=',product_product[0].id),('state','=','sale')])
			for sale_line in sale_lines:
				sale_qty +=   sale_line.product_uom_qty
			purchase_lines = self.env['purchase.order.line'].search([('product_id','=',product_product[0].id)])
			for lines in purchase_lines:
				purchase_qty += lines.product_qty
			
			record.piece_ratio = ((sale_qty - purchase_qty)/12) / 100  or 0.0
		
				
					
	# @api.multi
	# @api.depends('product_id')
	# def _compute_supplier(self):
	# 	for record in self:
	# 		print "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" , record.product_id.product_supplier_one2many.name
	# 		quants_dict = {}
	# 		supp_list = self.env['product.supplierinfo'].search([('location_id','=',record.location_id.id)])
	# 		for quant_id in quant:
	# 			if record.product_id.id == quant_id.product_id.id:
	# 				if record.product_id.name in quants_dict:
	# 					quants_dict[record.product_id.name] = quants_dict[record.product_id.name] + quant_id.qty
	# 				else:
	# 					quants_dict[record.product_id.name] = quant_id.qty
	# 					
	# 			else:
	# 				quants_dict[record.product_id.name] = 0
	# 
	# 			for quant_name, value in quants_dict.iteritems():
	# 				if quant_name == record.product_id.name:
	# 					record.store_stock = value
		
	# name = fields.Char(string="Description", track_visibility='always')
	sequence = fields.Integer(string="Seq", track_visibility='always')
	default_code = fields.Char(string="Code" , related="product_id.default_code")
	product_id = fields.Many2one('product.template',string="Product" , track_visibility='always')
	req_qty = fields.Float(string="OQ (Qty)",compute = "_compute_req_qty" , store= True)
	prev_qty = fields.Float(string="Previous Qty" )
	current_qty = fields.Float(string="Current Qty" )
	store_stock = fields.Float(string="ERP STOCK" ,compute = "_compute_store_stock" , store= True)
	wip_stock = fields.Float(string="WIP Stock" ,compute = "_compute_wip_stock" , store= True )
	order_qty = fields.Float(string="Open PO Qty" ,compute = "_compute_order_qty" , store= True)
	lead_time = fields.Integer(string="Supplier mfg. LT",compute = "_compute_price" , store= True)
	net_req_qty = fields.Float(string="Net Req Qty" ,compute = "compute_function" , store= True )
	fg_balance = fields.Float(string="FG Balance")
	moq = fields.Float(string="MOQ",compute = "_compute_price" , store= True)
	# supplier_id = fields.Many2one('res.partner',string="Supplier"  ,track_visibility='always')
	supplier_id = fields.Many2one('res.partner',string="Supplier"  ,track_visibility='always')
	location_id = fields.Many2one('stock.location', string='Location')
	advance_rm_material_id = fields.Many2one('advance.rm.material', track_visibility='always')
	
	supplier_location = fields.Char(string="Supplier Location" , related="supplier_id.city")
	# supplier_lead_time = fields.Integer(string="Supplier mfg. LT ")
	custom_lead_time = fields.Float(string="Custom LT",compute = "_compute_price" , store= True)
	total_lead_time = fields.Float(string=" Total LT" , compute='compute_function')
	monthly_consumption = fields.Float(string="Monthly Consumption" , compute='compute_function' , store = True)
	piece_ratio = fields.Float(string="Piece Ratio" , compute='_compute_piece_ratio')
	ss_days = fields.Float(string="SS (days)" ,compute = "_compute_safety_stock" , store= True)
	ss_qty = fields.Float(string="SS (Qty)" , compute='compute_function')
	oq_days = fields.Float(string="OQ (days)" , compute='compute_function')
	rol = fields.Float(string="ROL", compute='compute_function')
	po_raise  = fields.Boolean(string="PO raise?" , compute='compute_function')
	po_qty = fields.Float(string="PO Qty",compute = "_compute_po_qty" , store= True )
	landed_cost = fields.Float(string="Landed Cost")
	current_price = fields.Float(string="Current Price",compute = "_compute_price" , store= True)
	
	
	state = fields.Selection([
		('draft', 'Draft'),
		('done', 'RFQ'),
		], string='Status', readonly=True,
		copy=False, index=True, track_visibility='always', default='draft')
