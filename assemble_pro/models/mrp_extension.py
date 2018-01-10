from datetime import datetime
from openerp import models, fields, api, tools, _
from openerp.exceptions import UserError
import openerp.addons.decimal_precision as dp
from openerp.exceptions import UserError, MissingError, ValidationError ,AccessError
from collections import OrderedDict
from openerp.tools import float_compare, float_is_zero

class mrp_bom_extension(models.Model):
	_inherit = 'mrp.bom'
	
	stock_id = fields.Integer(string="Stock ID", track_visibility='always' , related="product_tmpl_id.stock_id")
	default_code = fields.Char(string="Product Code" , related="product_tmpl_id.default_code") 
	product_tmpl_id = fields.Many2one('product.template', 'Product', domain="[('type', 'in', ['product', 'consu'])]")
	
	# @api.onchange('default_code')
	# def onchange_name(self):
	# 	if self.default_code:
	# 		self.product_tmpl_id = self.product_tmpl_id.default_code
	
	@api.constrains('code')
	def check_bom_no(self):
		result = self.search([('code','=',self.code),('id','!=',self.id)])
		if len(result):
			raise UserError('BOM No. has to be Unique')
		
	@api.model
	def create(self, vals):
		vals['code'] = self.env['ir.sequence'].next_by_code('mrp.bom')
		result = super(mrp_bom_extension, self).create(vals)
		return result
	

class mrp_production_product_line_extension(models.Model):
	_inherit = 'mrp.production.product.line'
	_description = 'Production Scheduled Product'

	serial_no = fields.Many2one('stock.production.lot', string="Serial No", track_visibility='always')
	
class stock_move_extension(models.Model):
	_inherit = "stock.move"
	_description = "Stock Move"
	
	serial_no = fields.Many2one('stock.production.lot', string="Serial No", track_visibility='always')

	
class mrp_bom_line_extension(models.Model):
	_inherit = 'mrp.bom.line'
	
	level1 = fields.Selection([
		('sa', 'SA'),('sac', 'SAC'),], string='Level 1', track_visibility='always')
	level2 = fields.Selection([
		('sa', 'SA'),('sac', 'SAC'),], string='Level 2', track_visibility='always')
	default_code = fields.Char(string="Code", related="product_id.default_code")
	stock_id = fields.Integer(string="Stock ID", track_visibility='always' , related="product_id.stock_id")
	
	
class mrp_production_extension(models.Model):
	_inherit = 'mrp.production'
	
	assemble_work_id = fields.Many2one('assemble.work',string="Assemble Work", track_visibility='always')
	product_id = fields.Many2one('product.product',string= 'Product')
	employee_id = fields.Many2one('hr.employee', string='Employee', track_visibility='always')
	mrp_produce_ids = fields.One2many('mrp.product.produce.lot', 'mrp_id', string='Scanned Products' )
	barcode_scanned = fields.Char(string="Barcodes")
	qty_scanned = fields.Float(string="Qty Scanned")
	hsn_code = fields.Char(string='HSN',related="product_id.product_tmpl_id.hsn_code")
	
	@api.multi
	def button_dummy(self):
		return True
	
	def _src_id_default(self, cr, uid, ids, context=None):
		return self.pool.get('stock.location').search(cr, uid, [('name','ilike','wip')])[0]
	
	def _dest_id_default(self, cr, uid, ids, context=None):
		return self.pool.get('stock.location').search(cr, uid, [('name','ilike','finished')])[0]
	
	def location_id_change(self, cr, uid, ids, src, dest, context=None):
		""" Changes destination location if source location is changed.
		@param src: Source location id.
		@param dest: Destination location id.
		@return: Dictionary of values.
		"""
		if dest:
			return {}
		if src:
			return {'value': {'location_dest_id': src}}
		return {}
	
	_defaults = {
		'location_src_id': _src_id_default,
		'location_dest_id': _dest_id_default
	}
	
	@api.multi
	# @api.onchange('barcode_scanned')
	def on_barcode_scanned(self, barcode):
		if self.state in ('ready','in_production'):
			default_code = self.product_id.default_code
			mrp_produce_ids = self.env['mrp.production']
			og_barcode = str(barcode)
			line_list = og_barcode.split('-')
			line_tot = ''.join(line_list[0].strip())
			barcode =  line_tot
			
			if str(default_code) != barcode:
				
				print "HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH Barcode scanned " , default_code , barcode , type(default_code) , type(barcode) , len(barcode) , len(default_code)
				raise UserError("You have scanned a wrong serial Number")
					
			vals = {'name': og_barcode,'mrp_id':self.id,'product_id':self.product_id.id}
			# result = [[0,0,vals]]
			if og_barcode in [x.name for x in self.mrp_produce_ids]:
				raise UserError("You have already scanned this serial number")
			else:
				self.mrp_produce_ids += self.mrp_produce_ids.new(vals)
				self.qty_scanned += 1
		else:
			raise UserError("Kindly Confirm the Production")

	@api.model
	def create(self, vals):
		res = super(mrp_production_extension, self).create(vals)
		if res.assemble_work_id:
			res.assemble_work_id.mrp_production_id = res.id
		return res
	
	@api.multi
	def test_production_done(self):
		""" Tests whether production is done or not.
		@return: True or False
		"""
		res = super(mrp_production_extension, self).test_production_done()
		if self.assemble_work_id :
			if res:
				self.assemble_work_id.state = 'done'
		return res
	
		
	def _make_consume_line_from_data(self, cr, uid, production, product, uom_id, qty,serial_no=False, context=None):
		stock_move = self.pool.get('stock.move')
		loc_obj = self.pool.get('stock.location')
		# Internal shipment is created for Stockable and Consumer Products
		if product.type not in ('product', 'consu'):
			return False
		# Take routing location as a Source Location.
		source_location_id = production.location_src_id.id
		prod_location_id = source_location_id
		prev_move= False
		if production.bom_id.routing_id and production.bom_id.routing_id.location_id and production.bom_id.routing_id.location_id.id != source_location_id:
			source_location_id = production.bom_id.routing_id.location_id.id
			prev_move = True
	
		destination_location_id = production.product_id.property_stock_production.id
		print "KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKIIIIIIIIIIII" , serial_no
		move_id = stock_move.create(cr, uid, {
			'name': production.name,
			'date': production.date_planned,
			'product_id': product.id,
			'product_uom_qty': qty,
			'product_uom': uom_id,
			'location_id': source_location_id,
			'location_dest_id': destination_location_id,
			'company_id': production.company_id.id,
			'procure_method': prev_move and 'make_to_stock' or self._get_raw_material_procure_method(cr, uid, product, location_id=source_location_id, location_dest_id=destination_location_id, context=context), #Make_to_stock avoids creating procurement
			'raw_material_production_id': production.id,
			#this saves us a browse in create()
			'price_unit': product.standard_price,
			'origin': production.name,
			'warehouse_id': loc_obj.get_warehouse(cr, uid, production.location_src_id, context=context),
			'group_id': production.move_prod_id.group_id.id,
			'serial_no': serial_no.id or False,
		}, context=context)
		
		if prev_move:
			prev_move = self._create_previous_move(cr, uid, move_id, product, prod_location_id, source_location_id, context=context)
			stock_move.action_confirm(cr, uid, [prev_move], context=context)
		return move_id

	def _make_production_consume_line(self, cr, uid, line, context=None):
		return self._make_consume_line_from_data(cr, uid, line.production_id, line.product_id, line.product_uom.id, line.product_qty ,line.serial_no, context=context)
		
	def _prepare_lines(self, cr, uid, production, properties=None, context=None):
		if not production.assemble_work_id:
			return super(mrp_production_extension, self)._prepare_lines(cr, uid, production, properties=properties, context=context)
			
		else:
			assemble_work_id =production.assemble_work_id.assemble_work_mrp_one2many
			result = ([],[])
			
			for record in assemble_work_id:
				product_id = False
				product_obj = self.pool.get('product.product').search(cr, uid, [('product_tmpl_id','=',record.product_id.id)])
				if product_obj:
					product_id = product_obj[0]
					vals = {
						'product_qty': record.product_qty,
						'name': record.product_id.name,
						'product_uom': record.product_id.uom_id.id,
						'product_id': product_id,
						'serial_no': record.serial_no.id,
					}
					result[0].append(vals)
			return result
		
	@api.multi
	def action_assign(self):
			
			quants_dict = {}
			raise_error = False
		# if self.assemble_work_id:
			quant = self.env['stock.quant'].search([('location_id','=',self.location_src_id.id)])
			
			for record in self.move_lines:
				if len(quant):
					quant_found = False
					for quant_id in quant:
						# print "AAAAAAAAAAAAAA" , record.product_id , quant_id.product_id
						if record.product_id.id == quant_id.product_id.id:
							
							quant_found = True
							if record.product_id.name in quants_dict:
							   quants_dict[record.product_id.name] = quants_dict[record.product_id.name] + quant_id.qty
							else:
							   quants_dict[record.product_id.name] = quant_id.qty
					if not quant_found:
						quants_dict[record.product_id.name] = 0
				else:
						raise ValidationError("No stock available for any Product(s)")
			quant_string = "\
	Stock Not Available for the following Product(s) in the System:\n\
	Product --- Quantity \
	"
			for quant_name, value in quants_dict.iteritems():
				if value <= 0:
					raise_error = True
					quant_string += "\n%s -- -- -- ( %s ) " % (quant_name,value)
					
			print "KKKKKKKKKKKKKKKKKKKKKKKKKKKKKK" , quants_dict
			if raise_error:
				print "IIIIIIIIIIIIIIIIIIIIII Stock Not Available"
				raise ValidationError(quant_string)
			res = super(mrp_production_extension,self).action_assign()
			return res
	
	@api.multi
	def force_production(self):
		res = super(mrp_production_extension,self).force_production()
		
		quants_dict = {}
		raise_error = False
	# if self.assemble_work_id:
		quant = self.env['stock.quant'].search([('location_id','=',self.location_src_id.id)])
		
		for record in self.move_lines:
			if len(quant):
				quant_found = False
				for quant_id in quant:
					# print "AAAAAAAAAAAAAA" , record.product_id , quant_id.product_id
					if record.product_id.id == quant_id.product_id.id:
						
						quant_found = True
						if record.product_id.name in quants_dict:
						   quants_dict[record.product_id.name] = quants_dict[record.product_id.name] + quant_id.qty
						else:
						   quants_dict[record.product_id.name] = quant_id.qty
				if not quant_found:
					quants_dict[record.product_id.name] = 0
			else:
					raise ValidationError("No stock available for any Product(s)")
		quant_string = "\
Stock Not Available for the following Product(s) in the System:\n\
Product --- Quantity \
"
		for quant_name, value in quants_dict.iteritems():
			if value <= 0:
				raise_error = True
				quant_string += "\n%s -- -- -- ( %s ) " % (quant_name,value)
				
		# print "KKKKKKKKKKKKKKKKKKKKKKKKKKKKKK" , quants_dict
		if raise_error:
			# print "IIIIIIIIIIIIIIIIIIIIII Stock Not Available"
			raise ValidationError(quant_string)
			
		return res

	def _calculate_qty(self, cr, uid, production, product_qty=0.0, context=None):
		if not production.assemble_work_id:
			return super(mrp_production_extension, self)._calculate_qty(cr, uid, production, product_qty=0.0, context=context)
		
		else:
			"""
				Calculates the quantity still needed to produce an extra number of products
				product_qty is in the uom of the product
			"""
			quant_obj = self.pool.get("stock.quant")
			uom_obj = self.pool.get("product.uom")
			produced_qty = self._get_produced_qty(cr, uid, production, context=context)
			consumed_data = self._get_consumed_data(cr, uid, production, context=context)
			#In case no product_qty is given, take the remaining qty to produce for the given production
			if not product_qty:
				product_qty = uom_obj._compute_qty(cr, uid, production.product_uom.id, production.product_qty, production.product_id.uom_id.id) - produced_qty
			production_qty = uom_obj._compute_qty(cr, uid, production.product_uom.id, production.product_qty, production.product_id.uom_id.id)
		
			scheduled_qty = OrderedDict()
			for scheduled in production.product_lines:
				if scheduled.product_id.type not in ['product', 'consu']:
					continue
				qty = uom_obj._compute_qty(cr, uid, scheduled.product_uom.id, scheduled.product_qty, scheduled.product_id.uom_id.id)
				if scheduled_qty.get(scheduled.product_id.id):
					scheduled_qty[scheduled.product_id.id] += qty
				else:
					scheduled_qty[scheduled.product_id.id] = qty
			dicts = OrderedDict()
			# Find product qty to be consumed and consume it
			for product_id in scheduled_qty.keys():
		
				consumed_qty = consumed_data.get(product_id, 0.0)
				
				# qty available for consume and produce
				sched_product_qty = scheduled_qty[product_id]
				qty_avail = sched_product_qty - consumed_qty
				if qty_avail <= 0.0:
					# there will be nothing to consume for this raw material
					continue
		
				if not dicts.get(product_id):
					dicts[product_id] = {}
		
				# total qty of consumed product we need after this consumption
				if product_qty + produced_qty <= production_qty:
					total_consume = ((product_qty + produced_qty) * sched_product_qty / production_qty)
				else:
					total_consume = sched_product_qty
				qty = total_consume - consumed_qty
		
				# Search for quants related to this related move
				for move in production.move_lines:
					if qty <= 0.0:
						break
					if move.product_id.id != product_id:
						continue
		
					q = min(move.product_qty, qty)
					quants = quant_obj.quants_get_preferred_domain(cr, uid, q, move, domain=[('qty', '>', 0.0)], preferred_domain_list=[[('reservation_id', '=', move.id)]], context=context)
					for quant, quant_qty in quants:
						if quant:
							lot_id = move.serial_no.id
							if not product_id in dicts.keys():
								dicts[product_id] = {lot_id: quant_qty}
							elif lot_id in dicts[product_id].keys():
								dicts[product_id][lot_id] += quant_qty
							else:
								dicts[product_id][lot_id] = quant_qty
							qty -= quant_qty
				if float_compare(qty, 0, self.pool['decimal.precision'].precision_get(cr, uid, 'Product Unit of Measure')) == 1:
					if dicts[product_id].get(False):
						dicts[product_id][False] += qty
					else:
						dicts[product_id][False] = qty
		
			consume_lines = []
			for prod in dicts.keys():
				for lot, qty in dicts[prod].items():
					consume_lines.append({'product_id': prod, 'product_qty': qty, 'lot_id': lot})
			return consume_lines
		
		
	# def action_produce(self, cr, uid, production_id, production_qty, production_mode, wiz=False, lot_id=False,context=None):
	# 	""" To produce final product based on production mode (consume/consume&produce).
	# 	If Production mode is consume, all stock move lines of raw materials will be done/consumed.
	# 	If Production mode is consume & produce, all stock move lines of raw materials will be done/consumed
	# 	and stock move lines of final product will be also done/produced.
	# 	@param production_id: the ID of mrp.production object
	# 	@param production_qty: specify qty to produce in the uom of the production order
	# 	@param production_mode: specify production mode (consume/consume&produce).
	# 	@param wiz: the mrp produce product wizard, which will tell the amount of consumed products needed
	# 	@return: True
	# 	"""
	# 	stock_mov_obj = self.pool.get('stock.move')
	# 	uom_obj = self.pool.get("product.uom")
	# 	production = self.browse(cr, uid, production_id, context=context)
	# 	production_qty_uom = uom_obj._compute_qty(cr, uid, production.product_uom.id, production_qty, production.product_id.uom_id.id)
	# 	precision = self.pool['decimal.precision'].precision_get(cr, uid, 'Product Unit of Measure')
	# 
	# 	main_production_move = False
	# 	if production_mode == 'consume_produce':
	# 		# To produce remaining qty of final product
	# 		produced_products = {}
	# 		for produced_product in production.move_created_ids2:
	# 			if produced_product.scrapped:
	# 				continue
	# 			if not produced_products.get(produced_product.product_id.id, False):
	# 				produced_products[produced_product.product_id.id] = 0
	# 			produced_products[produced_product.product_id.id] += produced_product.product_qty
	# 		for produce_product in production.move_created_ids:
	# 			subproduct_factor = self._get_subproduct_factor(cr, uid, production.id, produce_product.id, context=context)
	# 			# lot_id = False
	# 			# if wiz:
	# 			# 	lot_id = wiz.lot_id.id
	# 			qty = min(subproduct_factor * production_qty_uom, produce_product.product_qty) #Needed when producing more than maximum quantity
	# 			new_moves = stock_mov_obj.action_consume(cr, uid, [produce_product.id], qty,
	# 													 location_id=produce_product.location_id.id, restrict_lot_id=lot_id, context=context)
	# 			stock_mov_obj.write(cr, uid, new_moves, {'production_id': production_id}, context=context)
	# 			remaining_qty = subproduct_factor * production_qty_uom - qty
	# 			if not float_is_zero(remaining_qty, precision_digits=precision):
	# 				# In case you need to make more than planned
	# 				#consumed more in wizard than previously planned
	# 				extra_move_id = stock_mov_obj.copy(cr, uid, produce_product.id, default={'product_uom_qty': remaining_qty,
	# 																						 'production_id': production_id}, context=context)
	# 				stock_mov_obj.action_confirm(cr, uid, [extra_move_id], context=context)
	# 				stock_mov_obj.action_done(cr, uid, [extra_move_id], context=context)
	# 
	# 			if produce_product.product_id.id == production.product_id.id:
	# 				main_production_move = produce_product.id
	# 
	# 	if production_mode in ['consume', 'consume_produce']:
	# 		if wiz:
	# 			consume_lines = []
	# 			for cons in wiz.consume_lines:
	# 				consume_lines.append({'product_id': cons.product_id.id, 'lot_id': cons.lot_id.id, 'lot_name': cons.lot_id.name, 'product_qty': cons.product_qty})
	# 		else:
	# 			consume_lines = self._calculate_qty(cr, uid, production, production_qty_uom, context=context)
	# 		for consume in consume_lines:
	# 			remaining_qty = consume['product_qty']
	# 			for raw_material_line in production.move_lines:
	# 				if raw_material_line.state in ('done', 'cancel'):
	# 					continue
	# 				if remaining_qty <= 0:
	# 					break
	# 				if consume['product_id'] != raw_material_line.product_id.id:
	# 					continue
	# 				consumed_qty = min(remaining_qty, raw_material_line.product_qty)
	# 				stock_mov_obj.action_consume(cr, uid, [raw_material_line.id], consumed_qty, raw_material_line.location_id.id,
	# 											 restrict_lot_id=consume['lot_id'], consumed_for=main_production_move, context=context)
	# 				remaining_qty -= consumed_qty
	# 			if not float_is_zero(remaining_qty, precision_digits=precision):
	# 				#consumed more in wizard than previously planned
	# 				product = self.pool.get('product.product').browse(cr, uid, consume['product_id'], context=context)
	# 				extra_move_id = self._make_consume_line_from_data(cr, uid, production, product, product.uom_id.id, remaining_qty, consume.get('lot_id'), context=context)
	# 				stock_mov_obj.write(cr, uid, [extra_move_id], {'restrict_lot_id': consume['lot_id'],
	# 																'consumed_for': main_production_move}, context=context)
	# 				stock_mov_obj.action_done(cr, uid, [extra_move_id], context=context)
	# 
	# 	self.message_post(cr, uid, production_id, body=_("%s produced") % self._description, context=context)
	# 
	# 	# Remove remaining products to consume if no more products to produce
	# 	if not production.move_created_ids and production.move_lines:
	# 		stock_mov_obj.action_cancel(cr, uid, [x.id for x in production.move_lines], context=context)
	# 
	# 	self.signal_workflow(cr, uid, [production_id], 'button_produce_done')
	# 	return True


