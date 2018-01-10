from datetime import datetime, timedelta, date
from openerp.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT
from dateutil.relativedelta import relativedelta
from openerp import models, fields, api, tools, _
from openerp.exceptions import UserError, AccessError , ValidationError

class product_template_extension(models.Model):
	_inherit = 'product.template'
	
	show_in_rm_report = fields.Boolean('Show in RM Report')
	rm_batch = fields.Boolean('RM Batch',)
	hide_stockitem = fields.Boolean('Hide Stockitem')
	rm_product_batch = fields.Boolean('RM Product Batch')
	serial_no = fields.Boolean('Can be Rented')
	component_utilization = fields.Boolean('Component Utilization')
	cst_applicable = fields.Boolean('CST Applicable')
	finished_goods = fields.Boolean('Finished Goods')
	
	batch_length = fields.Float(string="Batch Length", track_visibility='always')
	length = fields.Float(string="Length", track_visibility='always')
	gross_weight = fields.Float(string="Gross Weight", track_visibility='always')
	monthly_quantity = fields.Float(string="Monthly Quantity", track_visibility='always')
	mol = fields.Char(string="MOL")
	moq = fields.Char(string="MOQ")
	ratio = fields.Float(string="Ratio", track_visibility='always')
	shelf_no = fields.Char(string="Rack/Shelf no.")
	
	product_packaging_id = fields.Many2one('product.packaging', track_visibility='always')
	main_box = fields.Char(string="Main Box")
	sub_box = fields.Char(string="Sub Box")
	product_packaging_one2many = fields.One2many('packaging.extension','product_temp_id',string="Packages")
	level1 = fields.Selection([
		('sa', 'SA'),
		('sac', 'SAC'),
		], string='Level 1', track_visibility='always')
	level2 = fields.Selection([
		('sa', 'SA'),
		('sac', 'SAC'),
		], string='Level 2', track_visibility='always')
	raw_material = fields.Boolean('Raw Material')
	stock_id = fields.Integer(string="Stock ID", track_visibility='always')
	opening_value = fields.Float(string="Opening Value", track_visibility='always')
	closing_value = fields.Float(string="Closing Value", track_visibility='always')
	opening_qty = fields.Integer(string="Opening Quantity", track_visibility='always')
	closing_qty = fields.Integer(string="Closing Quantity", track_visibility='always')
	# product_pricelist_id = fields.Many2one('product.pricelist', string='Products Pricelist',)
	product_tmpl_id = fields.Many2one('product.pricelist.line', string='Products Pricelist Line',)
	safety_stock_days = fields.Integer(string="Safety Stock Days", track_visibility='always')
	length_material = fields.Boolean('Length Material')
	product_supplier_one2many = fields.One2many('product.supplier.extension','product_supplier_id',string="Vendors")
	last_updated_qty = fields.Float(string="Last Updated Qty", track_visibility='always')
	pcb_material = fields.Boolean('PCB Material')
	hsn_code = fields.Char(string='HSN')
	
	_sql_constraints = [
		('product_name_uniq', 'unique(name)', 'Name already exists and violates unique field constraint'),
	]
			
	# @api.constrains('name')
	# def constraints_name_check(self):
	# 	if len(self.search(['name', '=', self.name])) > 1:
	# 		print "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW"
	# 		raise UserError("Name already exists and violates unique field constraint")
		
		
class product_custom_barcode(models.Model):
	_name = "product.custom.barcode"
	
	barcode_id = fields.Many2one('product.product', string='Product', ondelete='cascade', index=True)
	default_code = fields.Char(string="Code", related="barcode_id.default_code")
	barcode_scanned = fields.Char(string="Scanned Barcode")
	barcode_dot = fields.Char(string="Dot Barcode")

class product_supplier_extension(models.Model):
	_name = 'product.supplier.extension'
	
	name = fields.Many2one('res.partner', string='Supplier')
	city = fields.Char(string="Location", related="name.city")
	rate = fields.Float(string = "Rate")
	product_supplier_id = fields.Many2one('product.template', string='Product Master')

class product_product_extension(models.Model):
	_inherit = 'product.product'
	
	finished_goods = fields.Boolean('Finished Goods')
	print_no = fields.Integer(string="No. of Print")
	sequence = fields.Char(string="Serial No")
	barcode_ids = fields.One2many('product.custom.barcode', 'barcode_id', string='Barcodes')
	
	_sql_constraints = [
		('product_default_code_uniq', 'unique(default_code)', 'Product Code already exists and violates unique field constraint'),
	]
	
	@api.model
	def create(self, vals):
		vals['sequence'] = self.env['ir.sequence'].next_by_code('product.product')
		result = super(product_product_extension, self).create(vals)
		return result
	
	
	@api.multi
	def get_sequence_serial(self):
		day_month = datetime.today().strftime('%y.%m')
		result = []
		i = 0
		while i < self.print_no:
			new_val =  str(int(self.sequence) + i).zfill(5)+"."+ day_month #str(self.default_code) +
			result.append(new_val)
			i += 1
		# self.sequence = str(int(self.sequence) + self.print_no).zfill(5)
		
		return result
	
	@api.multi
	def get_sequence_barcode(self):
		day = datetime.today().strftime('%y')
		result = str(self.default_code) +str("-"+str(self.sequence).zfill(5)+ day)
		self.record_barcode(result,self.sequence)
		self.sequence = str(int(self.sequence) + 1).zfill(5)
		return result
	
	@api.multi
	def record_barcode(self, barcode, sequence):
		year_month = datetime.today().strftime('%y.%m')
		dotcode =  str(sequence).zfill(5)+"."+ year_month
		custom_barcode = self.env['product.custom.barcode']
		vals = {
			'barcode_id':self.id,
			'barcode_scanned':barcode,
			'barcode_dot':dotcode,
		}
		
		result2 = []
		for rec in self.barcode_ids:
			line_prod = rec.barcode_dot.split('.')
			line_pro = ''.join(line_prod[0].strip())
			result2.append(line_pro)
		
		if  self.sequence not in result2:
			self.env['product.custom.barcode'].create(vals)
	
	@api.onchange('product_packaging_id')
	def onchange_package_box(self):
		result = []
		box = self.product_packaging_id
		vals = {
			'name':box.id,
			'code':box.code,
			'qty':box.qty,
			'rate':box.rate,
			'amount':box.amount
		}
		result.append(vals)
		self.product_packaging_one2many = result