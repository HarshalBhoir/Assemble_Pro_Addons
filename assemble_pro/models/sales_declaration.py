from openerp.exceptions import UserError, MissingError, ValidationError
import csv
import base64
import decimal
import openerp
from openerp import models, fields, api, _, tools
from datetime import datetime
# import datetime
import time
import logging
from openerp.tools import float_is_zero,openerp,image_colorize, image_resize_image_big
import re , collections
from openerp import http
from openerp.addons.web.controllers.main import serialize_exception,content_disposition
from openerp.http import request, serialize_exception as _serialize_exception
from cStringIO import StringIO
import xlwt
import pytz
from collections import Counter
import openerp.addons.decimal_precision as dp

class Binary(http.Controller):
	
	@http.route('/web/binary/download_document', type='http', auth="public")
	@serialize_exception
	def download_document(self,model,field,id,filename=None, **kw):
		""" Download link for files stored as binary fields.
		:param str model: name of the model to fetch the binary from
		:param str field: binary field
		:param str id: id of the record from which to fetch the binary
		:param str filename: field holding the file's name, if any
		:returns: :class:`werkzeug.wrappers.Response`
		"""
		Model = request.registry[model]
		cr, uid, context = request.cr, request.uid, request.context
		fields = [field]
		res = Model.read(cr, uid, [int(id)], fields, context)[0]
		filecontent = base64.b64decode(res.get(field) or '')
		if not filecontent:
			 return request.not_found()
		else:
			if not filename:
				filename = '%s_%s' % (model.replace('.', '_'), id)
			return request.make_response(filecontent,[
					('Content-Disposition', content_disposition(filename)),
					# ('Content-Type', 'application/vnd.ms-excel'),
					('Content-Type', 'application/octet-stream'),
					('Content-Length', len(filecontent))
			])


class sales_declaration(models.Model):
	_name = 'sales.declaration'
	_description = "Sales Declaration"
	_inherit = ['mail.thread', 'ir.needaction_mixin']
	_order = 'create_date desc'
	
	name = fields.Char(string = "Export No.")
	partner_id = fields.Many2one('res.partner',string="Customer"  ,track_visibility='always')
	data = fields.Binary(string="Unit 1 File")
	date_start = fields.Date(string="From Date")
	date_end = fields.Date(string="To Date")
	# data_path = fields.Char(string="Data Path")
	user_id = fields.Many2one('res.users', string='User', default=lambda self: self._uid, track_visibility='always')
	state = fields.Selection([
		('draft', 'Draft'),
		('done', 'Done'),
		('cancel', 'Cancelled'),
		], string='Status', readonly=True,
		copy=False, index=True, track_visibility='always', default='draft')
	# company_id = fields.Many2one('res.company', string='Company')
	company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('sales.declaration'))
	transporter = fields.Char(string = "Transporter")
	lr_no = fields.Char(string = "LR no.")
	lr_date = fields.Date(string="LR Date")
	vehicle_no = fields.Char(string = "Vehicle no.")

	attachment_id = fields.Many2one( 'ir.attachment', string="Attachment", ondelete='cascade')
	datas = fields.Binary(string="XLS Report", related="attachment_id.datas")
	# display_address = fields.Char(string="Name", compute="_name_get" , store=True)
	
	sales_declaration_line_one2many = fields.One2many('sales.declaration.line','sales_declaration_id',string="Sales Declaration Line")
	
	
	@api.multi
	def unlink(self):
		for order in self:
			if order.state != 'draft':
				raise UserError(_('You can only delete Draft Entries'))
		return super(sales_declaration, self).unlink()
	

	@api.model
	def create(self, vals):
		vals['name'] = self.env['ir.sequence'].next_by_code('sales.declaration')
		result = super(sales_declaration, self).create(vals)
		return result
	

	@api.multi
	def _sales_unset(self):
		self.env['sales.declaration.line'].search([('sales_declaration_id', 'in', self.ids)]).unlink()
		
		
	@api.multi
	def select_all(self):
		for record in self.sales_declaration_line_one2many:
			record.selection = True
			
	@api.constrains('date_start','date_end')
	def constraints_check(self):
		if not self.date_start and  not self.date_end or self.date_start > self.date_end:
			raise UserError("Please select a valid date range")
		
		
	@api.multi
	def search_sales(self):
		result = []
		sale_name = invoice_number = dc_no = location = ''
		self._sales_unset()

		if self.date_start and self.date_end:
			if self.partner_id:
				search_boolean = True
				inv_ids = self.env['account.invoice'].sudo().search([
					('date_invoice','>=',self.date_start),
					('date_invoice','<=',self.date_end),
					('type','=','out_invoice'),
					('partner_id','=',self.partner_id.id)])
				
				if (not inv_ids ):
					raise ValidationError('No Sale Invoice on this day ')
				
				file_name = self.name
				if inv_ids:
					amount = 0
					for record in inv_ids:
						invoice_date = datetime.strptime(record.date_invoice, '%Y-%m-%d').strftime('%d-%b-%y')
						quot_ids = self.env['sale.order'].search([('name','=',record.origin)])
						for rec in quot_ids:
							sale_name = rec.name
							invoice_number = record.number
							amount = record.amount_total
							partner = rec.partner_id
							
						stock_id = self.env['stock.picking'].search([('origin','=',record.origin)])
						if stock_id:
							for quant in stock_id:
								dc_no = quant.name
								location = quant.partner_id.city
						vals = {
							'invoice_no':invoice_number,
							'date':invoice_date,
							'dc_no':dc_no,
							'name':sale_name,
							'amount':amount,
							'partner_id':partner,
							'location':location
						}
						result.append(vals)
				self.state = 'done'
				self.sales_declaration_line_one2many = result
			else:
				search_boolean = True
				inv_ids = self.env['account.invoice'].sudo().search([('date_invoice','>=',self.date_start),('date_invoice','<=',self.date_end),('type','=','out_invoice')])
				
				
				if (not inv_ids ):
					raise ValidationError('No Sale Invoice on this day ')
				
				file_name = self.name
				
				if inv_ids:
					sale_name = invoice_number = dc = ''
					amount = 0
					for record in inv_ids:
						invoice_date = datetime.strptime(record.date_invoice, '%Y-%m-%d').strftime('%d-%b-%y')
						quot_ids = self.env['sale.order'].search([('name','=',record.origin)])
						for rec in quot_ids:
							sale_name = rec.name
							invoice_number = record.number
							amount = record.amount_total
							partner = rec.partner_id
							
						stock_id = self.env['stock.picking'].search([('origin','=',record.origin)])
						if stock_id:
							for quant in stock_id:
								dc_no = quant.name
								location = quant.partner_id.city
						vals = {
							'invoice_no':invoice_number,
							'date':invoice_date,
							'dc_no':dc_no,
							'name':sale_name,
							'amount':amount,
							'partner_id':partner,
							'location':location
						}
						result.append(vals)
				self.state = 'done'
				self.sales_declaration_line_one2many = result
		
			
	@api.multi
	def sales_declaration_report(self):
		selection_list =[]
		for record in self.sales_declaration_line_one2many:
			if record.selection:
				selection_list.append(record)
				
		for record in self:
			if not self.company_id.partner_id.child_ids:
				raise ValidationError('No Contact person found for %s ' %(self.company_id.name))
		if not len(selection_list):
			raise ValidationError('No record Selected for Printing ')
		return self.env['report'].get_action(self, 'assemble_pro.sales_declaration_template')
		
class sales_declaration_line(models.Model):
	_name = 'sales.declaration.line'
	_description = "Sales Declaration Line"
	
	selection = fields.Boolean(string = "", nolabel="1")
	invoice_no = fields.Char(string = "Invoice No")
	partner_id = fields.Many2one('res.partner',string="Customer"  ,track_visibility='always')
	date = fields.Char(string = "Date")
	dc_no = fields.Char(string = "DC No.")
	name = fields.Char(string = "Order No.")
	amount = fields.Char(string = "Amount")
	location = fields.Char(string = "Location")
	sales_declaration_id  = fields.Many2one('sales.declaration')
	
	# @api.multi
	# @api.depends('name','company_id')
	# def _name_get(self):
	# 	address = str(self.company_id.street)  + str(self.company_id.street) +","+ str(self.company_id.city) +","+  str(self.company_id.state_id.name)+","+  str(self.company_id.zip)
	# 	self.display_address = address
	# 
	# 
	# @api.model
	# def create(self, vals):
	# 	vals['name'] = self.env['ir.sequence'].next_by_code('tally.export')
	# 	result = super(tally_export, self).create(vals)
	# 	return result
	# 
	# @api.constrains('date_start','date_end','company_id','voucher_type')
	# def constraints_check(self):
	# 	if self.date_start and self.date_end and self.date_start > self.date_end:
	# 		print "PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP"
	# 		raise UserError("Please select a valid date range")
	# 	if not self.company_id:
	# 		raise UserError("Please select a Company")
	# 	if not self.voucher_type:
	# 		raise UserError("Please select Type Of Voucher")
	# 	
	# 
