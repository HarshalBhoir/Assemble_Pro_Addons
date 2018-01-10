from openerp.exceptions import UserError, MissingError, ValidationError
import csv
import base64
import decimal
import openerp

from openerp import models, fields, api, _, tools
from openerp.exceptions import UserError
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

class otd_calculation(models.Model):
	_name = 'otd.calculation'
	_description = "OTD Calculation"
	_inherit = ['mail.thread', 'ir.needaction_mixin']
	_order = 'create_date desc'

	
	name = fields.Char(string = "OTD No.")
	partner_id = fields.Many2one('res.partner',string="Supplier"  ,track_visibility='always')
	date_start = fields.Date(string="From Date")
	date_end = fields.Date(string="To Date")
	user_id = fields.Many2one('res.users', string='User', default=lambda self: self._uid, track_visibility='always')
	state = fields.Selection([
		('draft', 'Draft'),
		('done', 'Done'),
		], string='Status', readonly=True,
		copy=False, index=True, track_visibility='always', default='draft')
	company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('sales.declaration'))

	attachment_id = fields.Many2one( 'ir.attachment', string="Attachment", ondelete='cascade')
	datas = fields.Binary(string="XLS Report", related="attachment_id.datas")
	
	otd_line_one2many = fields.One2many('otd.calculation.line','otd_calculation_id',string="OTD Calculation Line")
	
	
	@api.multi
	def unlink(self):
		for order in self:
			if order.state != 'draft':
				raise UserError(_('You can only delete Draft Entries'))
		return super(otd_calculation, self).unlink()
	

	@api.model
	def create(self, vals):
		vals['name'] = self.env['ir.sequence'].next_by_code('otd.calculation')
		result = super(otd_calculation, self).create(vals)
		return result
	

	@api.multi
	def _po_unset(self):
		self.env['otd.calculation.line'].search([('otd_calculation_id', 'in', self.ids)]).unlink()
		
		
	@api.constrains('date_start','date_end')
	def constraints_check(self):
		if not self.date_start and  not self.date_end or self.date_start > self.date_end:
			raise UserError("Please select a valid date range")
		
	@api.multi
	def search_po(self):
		result = []
		self._po_unset()
		temp_dict = {}

		if self.date_start and self.date_end:
			if self.partner_id:
				po_ids = self.env['purchase.order'].sudo().search([('date_order','>=',self.date_start),('date_order','<=',self.date_end),('type_order','=','purchase'),('partner_id','=',self.partner_id.id)])

				if (not po_ids ):
					raise ValidationError('No Purchases in this date range')

				if po_ids:
					for record in po_ids:
						po_raise_date = purchase_product = ''
						purchase_id = record.id
						purchase_date = datetime.strptime(record.date_order, '%Y-%m-%d %H:%M:%S').strftime('%d-%b-%y')
						for rec in record.order_line:
							purchase_product =  rec.product_id.name
							purchase_product_id =  rec.product_id.id
							dt = datetime.strptime(rec.date_planned,'%Y-%m-%d %H:%M:%S')
							po_schedule_date = dt.date()
							po_schedule_date_rec = datetime.strptime(rec.date_planned, '%Y-%m-%d %H:%M:%S').strftime('%d-%b-%y')
							
						stock_ids = self.env['stock.picking'].sudo().search([('origin','=',record.name),('partner_id','=',self.partner_id.id),('state','=','done')])
						for rec_stock in stock_ids:
							for record_pack in rec_stock.pack_operation_product_ids:
								if record_pack.product_id.name == purchase_product:
									grn_no = rec_stock.name
									ct = datetime.strptime(rec_stock.date_done,'%Y-%m-%d %H:%M:%S')
									completion_date = ct.date()
									completion_date_rec = datetime.strptime(rec_stock.date_done, '%Y-%m-%d %H:%M:%S').strftime('%d-%b-%y')
									
									date_format = "%Y-%m-%d"
									a = datetime.strptime(str(po_schedule_date), date_format)
									b = datetime.strptime(str(completion_date), date_format)
									delta = b - a
									delay_record = int(delta.days)
									delay = 0
									if delay_record <= 0:
										delay = int(delta.days)
									elif delay_record > 0:
										delay = int(delta.days) - int(self.env['otd.delay'].search([],order="create_date desc")[0].name)
									
									# otd_po = delay = 0
									if delay >= 20:
										otd_po = 0
									elif delay <=20 and delay > 0 :
										otd_po = 100 - (delay * 5)
									elif delay <= 0:
										otd_po = 100
									
									vals = {
										'purchase_id':purchase_id,
										'product_id':purchase_product_id,
										'po_date':purchase_date,
										'po_due_date':po_schedule_date_rec,
										'po_completion_date':completion_date_rec,
										'grn_no':grn_no,
										'delay':delay,
										'item_otd': otd_po,
										'otd_calculation_id':self.id
									}
									if purchase_id in temp_dict:
										if temp_dict[purchase_id] > otd_po:
											temp_dict[purchase_id] = otd_po
									else:
										temp_dict[purchase_id] = otd_po
							result.append(vals)
				
				for line in result:
					line['otd_po'] = temp_dict[line['purchase_id']]
					
				self.state = 'done'
				self.otd_line_one2many = result
									

		
class otd_calculation_line(models.Model):
	_name = 'otd.calculation.line'
	_description = "OTD Calculation Line"
	_rec_name = "purchase_id"
	
	purchase_id = fields.Many2one('purchase.order',string="PO No.")
	product_id = fields.Many2one('product.product',string="Product")
	po_date = fields.Char(string = "Raised date")
	po_due_date = fields.Char(string = "Due date")
	po_completion_date = fields.Char(string = "Completion date")
	grn_no = fields.Char(string = "GRN NO.")
	delay = fields.Integer(string = "Delay")
	otd_po = fields.Float(string = "OTD for PO")
	item_otd = fields.Float(string = "Item wise OTD (in %)")
	otd_calculation_id  = fields.Many2one('otd.calculation')
	

class otd_delay(models.Model):
	_name = 'otd.delay'
	_description = "OTD Delay"
	_order= "create_date desc"

	name = fields.Float(string = "Delay")