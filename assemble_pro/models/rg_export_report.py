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

class rg_export_report(models.Model):
	_name = 'rg.export.report'
	_description = "RG Export Report"
	
	name = fields.Char(string="RGExportReport", compute="_get_name")
	date_from = fields.Date(string="Date From", default=lambda self: fields.datetime.now())
	date_to = fields.Date(string="Date To", default=lambda self: fields.datetime.now())
	company_id = fields.Many2one('res.company', string='Company')
	voucher_type = fields.Selection([
		('SO', 'Sale'),
		('PO', 'Purchase'),
		], string='Type Of Voucher')
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
		rep_name = "RG_Export_Report"
		if self.date_from and self.date_to:
			date_from = datetime.strptime(self.date_from, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
			date_to = datetime.strptime(self.date_to, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
			if self.date_from == self.date_to:
				rep_name = "RG Export Report(%s)" % (date_from,)
			else:
				rep_name = "RG Export Report(%s|%s)" % (date_from, date_to)
		self.name = rep_name
		
	
	@api.multi
	def rg_export(self):
		if self.date_from and self.date_to:
			
			# if not self.attachment_id:
			inv_ids = self.env['account.invoice'].sudo().search([('date_invoice','>=',self.date_from),('date_invoice','<=',self.date_to)]) #,('type','=','out_invoice')
			
			if (not inv_ids):
				raise ValidationError('No Sale Invoice on this day ')
			
			# File Name
			# file_name = self.name
			
			# Created Excel Workbook and Sheet
			workbook = xlwt.Workbook()
			worksheet = workbook.add_sheet('Sheet 1')
			
			main_style = xlwt.easyxf('font: bold on, height 400; align: wrap 1, vert centre, horiz center; borders: bottom thick, top thick, left thick, right thick')
			sp_style = xlwt.easyxf('font: bold on, height 350;')
			header_style = xlwt.easyxf('font: bold on; align: wrap 1,  horiz center; borders: bottom thin, top thin, left thin, right thin')
			base_style = xlwt.easyxf('align: wrap 1; borders: bottom thin, top thin, left thin, right thin')
			merge_style = xlwt.easyxf('font: bold on,height 200; align: wrap 1,  horiz center; borders: bottom thin, top thin, left thin, right thin')
			
			# worksheet.write_merge(0, 1, 0, 7, file_name, main_style)
			row_index = 0
			
			worksheet.col(0).width = 4000
			worksheet.col(1).width = 4000
			worksheet.col(2).width = 6000
			worksheet.col(3).width = 6000
			worksheet.col(4).width = 6000
			worksheet.col(5).width = 5000
			worksheet.col(6).width = 6000
			worksheet.col(7).width = 6000
			worksheet.col(8).width = 5000
			worksheet.col(9).width = 6000
			worksheet.col(10).width = 16000
			worksheet.col(11).width = 4000
			
			# print "CCCCCCCCCCCCCCCCC",self.company_id._get_address_data
			info = "R.G. - 1 DAILY STOCK ACCOUNT :" +"\n Name of Unit: "+ (str(self.company_id.name) or '') +"\n Address: "+ (str(self.company_id.street) or '') +" "+ (str(self.company_id.street2) or '') +" "+ (str(self.company_id.state_id.name) or '') +" "+ (str(self.company_id.zip) or '')+"\n"+ "C.Ex. Regn No: " + (str(self.company_id.company_registry) or '') + "\n"+ "Name of Comodity: "+ "\n"+ "LIFT CONTROLS BOXES/UNITS: " +"\n"+ "Unit of Quanity :"+"\n"+ "NOS:"
			worksheet.write_merge(0, 6, 0, 6, info,merge_style)
			
			# worksheet.write(row_index, 0, "R.G. - 1 DAILY STOCK ACCOUNT :", base_style)
			# worksheet.write(row_index, 1, "Name of Unit :", base_style)
			# worksheet.write(row_index, 2, self.company_id.name, base_style)
			# worksheet.write(row_index, 3, "Address :", base_style)
			# worksheet.write(row_index, 4, self.display_address, base_style)
			# worksheet.write(row_index, 5, "C.Ex. Regn No :", base_style)
			# worksheet.write(row_index, 6, self.company_id.company_registry, base_style)
			# worksheet.write(row_index, 7, "Name of Comodity :", base_style)
			# worksheet.write(row_index, 8, "LIFT CONTROLS BOXES/UNITS", base_style)
			# worksheet.write(row_index, 9, "Unit of Quanity :", base_style)
			# worksheet.write(row_index, 10, "NOS", base_style)
			
			
			if inv_ids:
				# Headers
				header_fields = ['Invoice Date','Qty of Boxes','Untaxed Invoice Amount','Excise Tax Rate %','Excise Tax Value','Freight Charges','Invoice Number','Total Invoice Amount','Location','GSTIN NO.','Customer','PO NO']
				# row_index += 1
				# worksheet.write_merge(row_index, row_index, 0, 4, "Name of Comodity :", sp_style)
				worksheet.row(row_index).height = 400
				row_index += 7
	
				sp_updates = []
				for index, value in enumerate(header_fields):
					worksheet.write(row_index, index, value, header_style)
				row_index += 1
				sn = 1
				for record in inv_ids:
					tax_ids = []
					taxes = ''
					if self.company_id.id == record.company_id.id:
						if record.company_id.id == 1:
							file_name ='RG1-U1'
						else:
							file_name ='RG1-U2'
						invoice_date = datetime.strptime(record.date_invoice, '%Y-%m-%d').strftime('%d-%b-%y')
						
						
						if record.type == "out_invoice" and self.voucher_type=="SO":
							box_qty = 0
							for box in  record.product_packaging_one2many:
								# if len(box):
									box_qty += box.qty
							quot_ids = self.env['sale.order'].search([('name','=',record.origin)])
							for tax_id in record.invoice_line_ids[0].invoice_line_tax_ids:
								tax_ids.append(str(tax_id.amount))
							taxes = ",".join(tax_ids)
							for rec in quot_ids:
								worksheet.write(row_index, 0, invoice_date, base_style)
								worksheet.write(row_index, 1, box_qty, base_style)
								worksheet.write(row_index, 2, record.amount_untaxed, base_style)
								worksheet.write(row_index, 3, taxes, base_style)
								worksheet.write(row_index, 4, record.amount_tax, base_style)
								worksheet.write(row_index, 5, record.amount_freight, base_style)
								worksheet.write(row_index, 6, record.number, base_style)
								worksheet.write(row_index, 7, record.amount_total, base_style)
								worksheet.write(row_index, 8, rec.partner_shipping_id.city, base_style)
								worksheet.write(row_index, 9, record.partner_id.gstin_no or '', base_style)
								worksheet.write(row_index, 10, record.partner_id.name, base_style)
								worksheet.write(row_index, 11, rec.name, base_style)
								
								sn +=1
								row_index += 1
								
						if record.type == "in_invoice" and self.voucher_type=="PO":
							rfq_ids = self.env['purchase.order'].search([('name','=',record.origin)])
							for rec in rfq_ids:
								worksheet.write(row_index, 0, invoice_date, base_style)
								worksheet.write(row_index, 1, 0, base_style)
								worksheet.write(row_index, 2, record.amount_untaxed, base_style)
								worksheet.write(row_index, 3, taxes, base_style)
								worksheet.write(row_index, 4, record.amount_tax, base_style)
								worksheet.write(row_index, 5, record.amount_freight, base_style)
								worksheet.write(row_index, 6, record.number, base_style)
								worksheet.write(row_index, 7, record.amount_total, base_style)
								worksheet.write(row_index, 8, rec.partner_id.city, base_style)
								worksheet.write(row_index, 9, record.partner_id.gstin_no or '', base_style)
								worksheet.write(row_index, 10, record.partner_id.name, base_style)
								worksheet.write(row_index, 11, rec.name, base_style)
	
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
				'name':file_name,
				'datas':encoded_data,
				'datas_fname':'%s.xls' % ( file_name ),
				'res_model':'rg.export.report',
			}
			doc_id = self.env['ir.attachment'].create(attach_vals)
			self.attachment_id = doc_id.id
		
		return {
			'type' : 'ir.actions.act_url',
			'url': '/web/binary/download_document?model=%s&field=%s&id=%s&filename=%s.xls' % (self.attachment_id.res_model,'datas',self.id,self.attachment_id.name),
			'target': 'self',
			}