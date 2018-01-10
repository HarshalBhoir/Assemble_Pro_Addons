from openerp import models, fields, api, _
from openerp.exceptions import UserError, MissingError, ValidationError
from datetime import datetime
import time

class product_supplierinfo_extension(models.Model):
	_inherit = 'product.supplierinfo'
	
	supplierinfo_id = fields.One2many('product.supplierinfo.line','product_supplierinfo_id',string="Products")
	custom_lead_time = fields.Integer(string="Custom LT")
	state = fields.Selection([
		('draft', 'Draft'),
		('done', 'Done'),
		], string='Status', readonly=True,
		copy=False, index=True, track_visibility='always', default='draft')
	
	@api.multi
	def name_get(self):
		result= []
		for pl in self:
			to = ' to '
			name = str(pl.name.name)  + \
				' ('+(str(pl.date_start) if  pl.date_start else '')+ \
				(to if pl.date_end else '')+ \
				(str(pl.date_end)  if  pl.date_end else '')  + ') ' 
			result.append((pl.id,name))
		return result
	
	# @api.model
	# def create(self, vals):
	# 	result = super(product_supplierinfo_extension, self).create(vals)
	# 	if not len(result.supplierinfo_id):
	# 		raise ValidationError("No items Included")
	# 	return result
	
	@api.multi
	def update_supplier(self):
		
		result = []
		result2 = []
		result3 =[]
		for res in self.supplierinfo_id:
			product_ids = self.env['product.template'].search([('id','=',res.product_tmpl_id.id)])
			for product in product_ids:
				val = {
					'name':self.name.id,
					'rate':res.rate,
					'product_supplier_id':res.product_tmpl_id.id,
				}
				result.append(val)
				if len(product.product_supplier_one2many):
					for supplier_id in product.product_supplier_one2many:
						if supplier_id.name.id == self.name.id and supplier_id.product_supplier_id.id == res.product_tmpl_id.id:
							result2.append(supplier_id)
				else:
					product.product_supplier_one2many = result
				
				for supplier in result2:
					if self.name.id == supplier.name.id and supplier.product_supplier_id.id == res.product_tmpl_id.id:
						supplier.rate = res.rate
					else:
						val2 = {
							'name':self.name.id,
							'rate':res.rate,
							'product_supplier_id':res.product_tmpl_id.id,
						}
						result3.append(val2)
						product.product_supplier_one2many = result3
							
		self.state = 'done'
		return True
	

class product_supplierinfo_line(models.Model):
	_name = 'product.supplierinfo.line'
	
	default_code = fields.Char(string="Code",related="product_tmpl_id.default_code")
	product_tmpl_id = fields.Many2one('product.template', string =  'Product Template')
	product_supplierinfo_id = fields.Many2one('product.supplierinfo', string =  'Supplier Pricelist')
	rate = fields.Float(string = "Rate")
	length_rate = fields.Float(string = "Length Rate")
	stops_rate = fields.Float(string = "Stops Rate")
	percentage = fields.Float(string = "Percentage")
	custom_lead_time = fields.Integer(string="Custom LT")
	delay = fields.Integer(string="Delivery Lead Time")
	moq = fields.Char(string="MOQ")
	modvat_applicable = fields.Boolean(string="ModVAT")
	hsn_code = fields.Char(string='HSN',related="product_tmpl_id.hsn_code")
	tax_class = fields.Many2many('account.tax.class',string='Tax Class')
	
class product_pricelist_extension(models.Model):
	_inherit = "product.pricelist"
	
	@api.multi
	@api.onchange('name_partner')
	def _compute_name(self):
		if self.name_partner:
			self.name = str(self.name_partner.name)
	
	name_partner = fields.Many2one('res.partner' , string = "Name Partner")
	pricelist_line_id = fields.One2many('product.pricelist.line','product_pricelist_id',string="Products")
	
	@api.multi
	def name_get(self):
		result= []
		if not all(self.ids):
			return result
		for pl in self:
			name = pl.name + ' ('+ pl.currency_id.name + ')' +' (' +pl.create_date+ ')'
			result.append((pl.id,name))
		return result
	
	@api.model
	def create(self, vals):
		result = super(product_pricelist_extension, self).create(vals)
		for res in self:
			if not len(result.pricelist_line_id):
				print "zsjkgzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"
				raise ValidationError("No items Included")
		return result

class product_pricelist_line(models.Model):
	_name = 'product.pricelist.line'
	
	default_code = fields.Char(string="Code",related="product_tmpl_id.default_code")
	product_tmpl_id = fields.Many2one('product.template', string =  'Product Template')
	product_pricelist_id = fields.Many2one('product.pricelist', string =  'Product Pricelist')
	rate = fields.Float(string = "Rate")
	length_rate = fields.Float(string = "Length Rate")
	stops_rate = fields.Float(string = "Stops Rate")
	percentage = fields.Float(string = "Percentage")
	hsn_code = fields.Char(string='HSN',related="product_tmpl_id.hsn_code")
	tax_class = fields.Many2many('account.tax.class',string='Tax Class')