from openerp.exceptions import UserError, MissingError, ValidationError,Warning
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

class sale_register_report(models.Model):
	_name = 'sale.register.report'
	_description = "Sale Register Report"
	
	name = fields.Char(string="SaleRegisterReport", compute="_get_name")
	date_from = fields.Date(string="Date From", default=lambda self: fields.datetime.now())
	date_to = fields.Date(string="Date To", default=lambda self: fields.datetime.now())
	company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env['res.company']._company_default_get('sale.register.report'))
	attachment_id = fields.Many2one( 'ir.attachment', string="Attachment", ondelete='cascade')
	datas = fields.Binary(string="XLS Report", related="attachment_id.datas")
	
	
	@api.constrains('date_from','date_to')
	@api.depends('date_from','date_to')
	def date_range_check(self):
		if self.date_from and self.date_to and self.date_from > self.date_to:
			raise ValidationError(_("Start Date should be before or be the same as End Date."))
		return True
	
	@api.depends('date_from','date_to')
	@api.multi
	def _get_name(self):
		rep_name = "Sale_Register_Report"
		if self.date_from and self.date_to:
			date_from = datetime.strptime(self.date_from, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
			date_to = datetime.strptime(self.date_to, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
			if self.date_from == self.date_to:
				rep_name = "Sale Register Report(%s)" % (date_from,)
			else:
				rep_name = "Sale Register Report(%s|%s)" % (date_from, date_to)
		self.name = rep_name
		

	@api.multi
	def sales_register_export(self):
		if self.date_from and self.date_to:
			# if not self.attachment_id:
			inv_ids = self.env['account.invoice'].sudo().search([('date_invoice','>=',self.date_from),('date_invoice','<=',self.date_to),('type','=','out_invoice')])
			
			if (not inv_ids ):
				raise ValidationError('No Sale Invoice on this day ')
			
			# File Name
			file_name = self.name
			
			# Created Excel Workbook and Sheet
			workbook = xlwt.Workbook()
			worksheet = workbook.add_sheet('Sheet 1')
			
			main_style = xlwt.easyxf('font: bold on, height 400; align: wrap 1, vert centre, horiz center; borders: bottom thick, top thick, left thick, right thick')
			sp_style = xlwt.easyxf('font: bold on, height 350;')
			header_style = xlwt.easyxf('font: bold on; align: wrap 1,  horiz center; borders: bottom thin, top thin, left thin, right thin')
			base_style = xlwt.easyxf('align: wrap 1; borders: bottom thin, top thin, left thin, right thin')
			merge_style = xlwt.easyxf('font: bold on,height 200; align: wrap 1,  horiz center; borders: bottom thin, top thin, left thin, right thin')
				
			info = (str(self.company_id.name) or '') +"\n Address: "+ (str(self.company_id.street) or '') +" "+ (str(self.company_id.street2) or '') +" "+ (str(self.company_id.state_id.name) or '') +" "+ (str(self.company_id.zip) or '')+ "\n Period: "+ (str(self.date_from) or '')+" To "+ (str(self.date_to) or '')
			worksheet.write_merge(0, 3, 0, 7, info,merge_style)
			# worksheet.write_merge(0, 1, 0, 7, file_name, main_style)
			row_index = 4
			
			# worksheet.write_merge(0, 1, 0, 7, file_name, main_style)
			# row_index = 2
			
			worksheet.col(0).width = 4000
			worksheet.col(1).width = 6000
			worksheet.col(2).width = 6000
			worksheet.col(3).width = 16000
			worksheet.col(4).width = 6000
			worksheet.col(5).width = 5000
			worksheet.col(6).width = 6000
			worksheet.col(7).width = 6000
					
			if inv_ids:
				# Headers
				header_fields = ['Date','Doc No','GSTIN No.','Customer','Order No','Amount','Location Name','PONO']

				sp_updates = []
				for index, value in enumerate(header_fields):
					worksheet.write(row_index, index, value, header_style)
				row_index += 1
				sn = 1
				for record in inv_ids:
					if self.company_id.id == record.company_id.id:
						
						invoice_date = datetime.strptime(record.date_invoice, '%Y-%m-%d').strftime('%d-%b-%y')
						quot_ids = self.env['sale.order'].search([('name','=',record.origin)])
						for rec in quot_ids:
							worksheet.write(row_index, 0, invoice_date, base_style)
							worksheet.write(row_index, 1, record.number, base_style)
							worksheet.write(row_index, 2, rec.partner_id.gstin_no or '', base_style)
							worksheet.write(row_index, 3, rec.partner_id.name, base_style)
							worksheet.write(row_index, 4, rec.name, base_style)
							worksheet.write(row_index, 5, record.amount_total, base_style)
							worksheet.write(row_index, 6, rec.partner_shipping_id.city, base_style)
							worksheet.write(row_index, 7, rec.po_order, base_style)
	
							sn +=1
							row_index += 1
			
			
			fp = StringIO()
			workbook.save(fp)
			fp.seek(0)
			data = fp.read()
			fp.close()
			encoded_data = base64.encodestring(data)
			local_tz = pytz.timezone(self._context.get('tz') or 'UTC')
			attach_vals = {
				'name':'SalesRegister',
				'datas':encoded_data,
				'datas_fname':'%s.xls' % ( file_name ),
				'res_model':'sale.register.report',
			}
			doc_id = self.env['ir.attachment'].create(attach_vals)
			self.attachment_id = doc_id.id
		
		return {
			'type' : 'ir.actions.act_url',
			'url': '/web/binary/download_document?model=%s&field=%s&id=%s&filename=%s.xls' % (self.attachment_id.res_model,'datas',self.id,self.attachment_id.name),
			'target': 'self',
			}
	