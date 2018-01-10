from openerp import models, fields, api, _, tools
from openerp.exceptions import UserError
from openerp.exceptions import UserError, MissingError, ValidationError

from datetime import datetime
import time
import logging
from openerp.tools import openerp,image_colorize, image_resize_image_big
from datetime import date
from lxml import etree

_logger = logging.getLogger(__name__)

class assemble_instructions(models.Model):
	_name = 'assemble.instructions'
	_description = "Assembly Config Instructions"
	_inherit = ['mail.thread', 'ir.needaction_mixin']
	_rec_name = 'display_name'
	_order = 'create_date desc'

	# name = fields.Char(string="Description", track_visibility='always')
	start_date = fields.Date(string="Date" ,default=lambda self: datetime.now())
	user_id = fields.Many2one('res.users', string='User', default=lambda self: self._uid, track_visibility='always')
	employee_id = fields.Many2one('hr.employee', string='Employee', track_visibility='always')
	photo = fields.Binary(string="Image to upload")
	name = fields.Many2one('mrp.bom', track_visibility='always' )
	display_name = fields.Char(string="Name", compute="_name_get" , store=True)
	product_id = fields.Many2one('product.template', track_visibility='always',related="name.product_tmpl_id" )
	
	assemble_sub_one2many = fields.One2many('assemble.sub','assemble_instructions_id',string="Instructions")
	work_instruction_id = fields.Char(string="Work Instruction ID", track_visibility='always')
	default_code = fields.Char(string="Product Code" , related="name.default_code" )
	
	@api.model
	def create(self, vals):
		vals['work_instruction_id'] = self.env['ir.sequence'].next_by_code('assemble.instructions')
		result = super(assemble_instructions, self).create(vals)
		return result
	
	@api.multi
	def _instruction_unset(self):
		self.env['assemble.sub'].search([('assemble_instructions_id', 'in', self.ids)]).unlink()

	@api.onchange('name')
	def onchange_bom_lines(self):
		self._instruction_unset()
		result = []
		for rec in self:
			
			if rec.name  and rec.name.bom_line_ids:
				for box in rec.name.bom_line_ids:
					vals = {
						'sequence':box.sequence,
						'product_id':box.product_id.product_tmpl_id.id,
						'product_qty':box.product_qty,
					}
					result.append(vals)
		rec.assemble_sub_one2many = result
		
	# @api.multi
	# def name_get(self):
	# 	result= []
	# 	for ai in self:
	# 		name = '('+str(ai.work_instruction_id) + ') ' + ai.name.product_tmpl_id.name
	# 		result.append((ai.id,name))
	# 	return result
	
	@api.multi
	@api.depends('name','work_instruction_id')
	def _name_get(self):
		for ai in self:
			name = '('+str(ai.work_instruction_id) + ') ' + str(ai.name.product_tmpl_id.name)
			ai.display_name = name

class assemble_sub(models.Model):
	_name = 'assemble.sub'
	_description = "Assembly Sub Work Instructions "
	
	@api.model
	def default_get(self, fields_list):
		res = super(assemble_sub, self).default_get(fields_list)
		res.update({'sequence': len(self._context.get('assemble_sub', [])) + 1})
		return res
	
	sequence = fields.Integer(string="Seq", track_visibility='always')
	handler = fields.Char()
	name = fields.Char(string="Description", track_visibility='always')
	photo = fields.Binary(string="Image to upload")
	product_id = fields.Many2one('product.template', track_visibility='always')
	default_code = fields.Char(string="Product Code" , related="product_id.default_code")
	assemble_instructions_id = fields.Many2one('assemble.instructions', track_visibility='always')
	product_qty = fields.Float(string="Quantity")
	serial_no = fields.Many2one('stock.production.lot', string="Serial No", track_visibility='always')
	
class assemble_work(models.Model):
	_name = 'assemble.work'
	_description = "Assembly Work Instructions"
	_inherit = ['mail.thread', 'ir.needaction_mixin']
	_order = 'create_date desc'
	
	
	@api.multi
	def unlink(self):
		for order in self:
			if order.state != 'draft':
				raise UserError(_('You can only delete Draft Entries'))
		return super(assemble_work, self).unlink()

	# @api.multi 
	# def _get_attached_docs(self):
	# 	attachment = self.env['ir.attachment']
	# 	try:
	# 		for record in self:
	# 			company_attachments = attachment.search([('res_model', '=', str(self._model)), ('res_id', '=',  record.id)])
	# 			record.attach_doc_count = len(company_attachments) or 0
	# 	except:
	# 		pass
		
	@api.multi
	def get_attached_docs(self):
		for rec in self:
			aw_ids = self.env['mrp.production'].search([("origin","=",rec.assemble_no)])
			imd = self.env['ir.model.data']
			action = imd.xmlid_to_object('mrp.mrp_production_action')
			form_view_id = imd.xmlid_to_res_id('mrp.mrp_production_form_view')
			result = {
				'name': action.name,
				'help': action.help,
				'type': action.type,
				'views': [form_view_id,'form'],
				'target': action.target,
				'context': action.context,
				'res_model': action.res_model,
			}
			if len(aw_ids) > 1:
				result['domain'] = "[('id','in',%s)]" % aw_ids.ids
				
			elif len(aw_ids) == 1:
				result['views'] = [(form_view_id, 'form')]
				result['res_id'] = aw_ids.ids[0]
			else:
				result = {'type': 'ir.actions.act_window_close'}
			rec.attach_doc_count = len(aw_ids) or 0
			return result
	
	
	assemble_no = fields.Char(string="Assemble No.",default="New", copy=False, track_visibility='always')
	name = fields.Many2one('assemble.instructions',string="Description", track_visibility='always')
	date = fields.Date(string="Date",default=lambda self: datetime.now())
	product_id = fields.Many2one('product.template', track_visibility='always' , related="assemble_sub_id.product_id")
	product_template_id = fields.Many2one('product.template', track_visibility='always' , related="name.product_id")
	photo = fields.Binary(string="Photo", related="assemble_sub_id.photo")
	instruction = fields.Char("Instructions" ,related="assemble_sub_id.name")
	sequence = fields.Integer(string="Seq" ,related="assemble_sub_id.sequence")
	assemble_sub_id = fields.Many2one('assemble.sub')
	final_step = fields.Boolean(string="Final Step")
	user_id = fields.Many2one('res.users', string='User', default=lambda self: self._uid, track_visibility='always')
	employee_id = fields.Many2one('hr.employee', string='Employee', track_visibility='always')
	product_qty = fields.Float(string="Quantity",related="assemble_sub_id.product_qty") # ,related="assemble_sub_id.product_qty"
	qty = fields.Float(string="Quantity" , store=True) #compute="constraint_serial_no",
	qty_compute = fields.Float(string="Quantity" , related="qty")
	qty_manual = fields.Float(string="Quantity")
	state = fields.Selection([
		('draft', 'Draft'),
		('inprogress', 'Under Assembly'),
		('under_production', 'Under Production'),
		('done', 'Closed'),
		('cancel', 'Cancelled'),
		], string='Status', readonly=True, copy=False, index=True, track_visibility='always', default='draft')
	mrp_production_id = fields.Many2one('mrp.production', track_visibility='always' )
	serial_no = fields.Many2one('stock.production.lot', string="Serial No", track_visibility='always')
	quant_no = fields.Many2one('stock.quant', string="Quant No", track_visibility='always')
	attach_doc_count = fields.Integer(string="Number of documents attached", compute='get_attached_docs')
	assemble_work_mrp_one2many = fields.One2many('assemble.work.mrp','assemble_work_id',string="Product Details")
	tracking = fields.Selection([
		('serial', 'By Unique Serial Number'),
		('lot', 'By Lots'),
		('none', 'No Tracking')], string='Tracking' , related="product_id.tracking")
	serial_no_text = fields.Char("Serial No")
	# serial_list = fields.Integer("Serial List")
	

	@api.model
	def fields_view_get(self, view_id=None, view_type=False, toolbar=False, submenu=False):
		res = super(assemble_work, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
		doc = etree.XML(res['arch'])
		for node in doc.xpath("//field[@name='serial_no']"):
			node.set('domain', "[('product_id', '=',product_id )]")
		for node in doc.xpath("//field[@name='quant_no']"):
			node.set('domain', "[('product_id', '=',product_id )]")
		res['arch'] = etree.tostring(doc)
		return res
	
		
	@api.multi
	def button_dummy(self):
		return True

	@api.multi
	@api.onchange('serial_no_text')
	def constraint_serial_no(self):
		# print "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" , self.serial_no_text , self.qty
		# location = self.env.ref('stock.stock_location_stock')
		location = self.env['stock.location'].search([('name','ilike','wip')])
		# print "KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK location" , location
		code = []
		product_product = self.env['product.product'].search([('product_tmpl_id','=',self.product_id.id)])
		for rec in self:
			if rec.serial_no_text:
				quant = self.env['stock.quant'].search([('location_id','=',location.id),('product_id','=',product_product.id)])
				# print "KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK" , quant
				# product_lot = self.env['stock.production.lot'].search([('product_id','=',self.product_id.id)])
				prod_code = [x.lot_id.name for x in quant]
				for pro in prod_code:
					if pro != False:
						code.append(pro.encode('utf-8').strip())
				
				if rec.serial_no_text in code:
					rec.qty += 1
					# rec.serial_list += 1
					product_serial_no = self.env['stock.production.lot'].search([('name','=',rec.serial_no_text)])
					rec.serial_no = product_serial_no[0].id
					# rec.qty  = rec.serial_list
					# break
				else:
					print "SSSSSSSSSSSSSSSSSSSSSSSSs" , rec.serial_no_text , code , self.product_id.id , self.product_id.default_code ,location.name
					raise UserError("Kindly Enter the Serial Number assigned to this product")
	
	
	@api.one
	def action_start(self):
		if self.name and self.name.assemble_sub_one2many:
			if len(self.name.assemble_sub_one2many) == 1:
				self.final_step = True
			self.assemble_sub_id = self.name.assemble_sub_one2many[0].id
			self.state = 'inprogress'

	@api.one
	def action_next(self):
		result = []
		if  (self.qty or self.qty_manual ) != self.product_qty:
			print "KKKKKKKKKKKK Wrong Quantity Entered"
			raise ValidationError('Wrong Quantity Entered \n Right Quantity is  %s' % (self.product_qty))
		
		if self.qty <= 0 and self.tracking == 'serial':
			raise UserError("Kindly Enter the Serial Number assigned to this product")
		
		for box in self:
			vals = {
				'name':box.name,
				'product_id':box.product_id.id,
				'product_qty':box.qty if box.qty else box.qty_manual,
				'product_uom':box.product_id.uom_id.id,
				'serial_no':box.serial_no.id,
				'assemble_work_id':box.id,
			}
			result.append(vals)
		self.assemble_work_mrp_one2many = result
		
		self.qty = self.qty_manual = 0.00
		self.serial_no = self.serial_no_text = ''
		seq = self.assemble_sub_id.sequence
		asssemble_sub_recs = self.assemble_sub_id.search([('sequence','>',seq),
			('assemble_instructions_id','=',self.name.id)],order='sequence')
		if asssemble_sub_recs:
			if len(asssemble_sub_recs) == 1:
				self.final_step = True
			self.assemble_sub_id = asssemble_sub_recs[0].id
			
		

	@api.one
	def action_prev(self):
		seq = self.assemble_sub_id.sequence
		self.final_step = False
		asssemble_sub_recs = self.assemble_sub_id.search([('sequence','<',seq),
			('assemble_instructions_id','=',self.name.id)],order='sequence desc')
		if asssemble_sub_recs:
			self.assemble_sub_id = asssemble_sub_recs[0].id
			
	
	@api.model
	def create(self, vals):
		# if vals['assemble_no'] == 'New':
		vals['assemble_no'] = self.env['ir.sequence'].next_by_code('assemble.work')
		result = super(assemble_work, self).create(vals)
		return result
	
	@api.multi
	def action_final(self):
		result2=[]
		if  (self.qty or self.qty_manual ) != self.product_qty:
			print "JJJJJJJJJJJJJJJJ Wrong Quantity Entered"
			raise ValidationError('Wrong Quantity Entered \n Right Quantity is %s' % (self.product_qty))
		
		for box in self:
			vals = {
				'name':box.name,
				'product_id':box.product_id.id,
				'product_qty':box.qty if box.qty else box.qty_manual,
				'product_uom':box.product_id.uom_id.id,
				'serial_no':box.serial_no.id,
				'assemble_work_id':box.id,
			}
			result2.append(vals)
		self.assemble_work_mrp_one2many = result2
		
		self.qty = self.qty_manual =  0.00
		self.serial_no = self.serial_no_text = ''
		product_product = self.env['product.product'].search([('product_tmpl_id', '=', self.name.product_id.id)])
		ctx = self._context.copy()
		mrp_ids = self.env['mrp.production'].search([('origin', '=', self.assemble_no)])
		if mrp_ids:
			result = self.get_attached_docs()
		if not mrp_ids:
			ctx.update({
				'default_product_id': product_product.id,
				'default_assemble_work_id': self.id,
				'default_origin':self.assemble_no,
				'default_employee_id':self.employee_id.id,
			})
			# self.state = 'done'
			imd = self.env['ir.model.data']
			action = imd.xmlid_to_object('mrp.mrp_production_action')
			form_view_id = imd.xmlid_to_res_id('mrp.mrp_production_form_view')
			
			result = {
				'name': action.name,
				'help': action.help,
				'type': action.type,
				'views': [[form_view_id, 'form']],
				'target': action.target,
				'context': ctx,
				'res_model': action.res_model,
			}
		self.state = 'under_production'
		return result
	

class assemble_work_mrp(models.Model):
	_name = 'assemble.work.mrp'
	_description = "Assembly Work Instructions"


	name = fields.Char('Name')
	product_id = fields.Many2one('product.template', 'Product')
	product_qty = fields.Float('Product Quantity')
	product_uom = fields.Many2one('product.uom', 'Product Unit of Measure' )
	serial_no = fields.Many2one('stock.production.lot', string="Serial No", track_visibility='always')
	assemble_work_id =  fields.Many2one('assemble.work', 'Production Order')
