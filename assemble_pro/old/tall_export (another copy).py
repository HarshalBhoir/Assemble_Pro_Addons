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

# from datetime import date
# import pandas
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


class tally_export(models.Model):
	_name = 'tally.export'
	_description = "Tally Export"
	_inherit = ['mail.thread', 'ir.needaction_mixin']
	
	name = fields.Char(string = "Export No.")
	data = fields.Binary(string="Unit 1 File")
	date_start = fields.Date(string="From Date")
	date_end = fields.Date(string="To Date")
	data_path = fields.Char(string="Data Path")
	user_id = fields.Many2one('res.users', string='User', default=lambda self: self._uid, track_visibility='always')
	state = fields.Selection([
		('draft', 'Draft'),
		('done', 'Exported'),
		('cancel', 'Cancelled'),
		], string='Status', readonly=True,
		copy=False, index=True, track_visibility='always', default='draft')
	company_id = fields.Many2one('res.company', string='Company')
	voucher_type = fields.Selection([
		('SO', 'Sale'),
		('PO', 'Purchase'),
		], string='Type Of Voucher')
	attachment_id = fields.Many2one( 'ir.attachment', string="Attachment", ondelete='cascade')
	datas = fields.Binary(string="XLS Report", related="attachment_id.datas")
	display_address = fields.Char(string="Name", compute="_name_get" , store=True)
	
	
	@api.multi
	@api.depends('name','company_id')
	def _name_get(self):
		address = str(self.company_id.street)  + str(self.company_id.street) +","+ str(self.company_id.city) +","+  str(self.company_id.state_id.name)+","+  str(self.company_id.zip)
		self.display_address = address
	

	@api.model
	def create(self, vals):
		vals['name'] = self.env['ir.sequence'].next_by_code('tally.export')
		result = super(tally_export, self).create(vals)
		return result
	
	@api.constrains('date_start','date_end','company_id','voucher_type')
	def constraints_check(self):
		if self.date_start and self.date_end and self.date_start > self.date_end:
			print "PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP"
			raise UserError("Please select a valid date range")
		if not self.company_id:
			raise UserError("Please select a Company")
		if not self.voucher_type:
			raise UserError("Please select Type Of Voucher")
		

	@api.multi
	def export_data(self):

		main_string2 = file_name = ""
		invoice_ids = self.env['account.invoice'].search([('date_invoice','>=',self.date_start),('date_invoice','<=',self.date_end)])
		
		if invoice_ids:
			for invoices in invoice_ids:
				if self.company_id.id == invoices.company_id.id:
					if invoices.company_id.id == 1:
						file_name ='LIFTUNIT1'
					else:
						file_name ='LIFTUNIT2'
						
					invoice_date = datetime.strptime(invoices.date_invoice, '%Y-%m-%d').strftime('%d-%b-%y')
					if invoices.type == "out_invoice" and self.voucher_type=="SO": #"in_refund","out_refund"
						
						move_ids = self.env['account.move'].search([('ref','=',invoices.origin)])
						# print "AAAAAAAAAAAAAAAAAAAAAAAA" ,invoices.origin , move_ids
						for move_line in move_ids:
							print "DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD" , move_line.ref , move_line.amount , move_line.name , move_line.journal_id.name
							if 'Customer Invoices' in move_line.journal_id.name:
								print "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB" , move_line.id , move_line.name
						tax_string = ""
						freight_string = ""
						if invoices.carrier_id:
							freight_string = "|"+ str(invoices.carrier_id)+";"+";"+";"+str(invoices.amount_freight)

						for taxes in invoices.tax_line_ids:
							if taxes.name and taxes.amount:
								tax_string = tax_string + "|"+str(taxes.name)+";"+";"+";"+str(taxes.amount)
		
						sale_string = "Sales|"+str(invoice_date)+"|"+str(invoices.number)+"|"+str(invoices.partner_id.name)+"|:"+str(invoices.partner_id.name)+";"+";"+";"+"-"+str(invoices.amount_total) + '|Inter-State Sales'+";"+";"+";"+str(invoices.amount_untaxed)
						main_string = sale_string + tax_string + freight_string + "\n"
						main_string2 = main_string2 +  main_string
						
					if invoices.type == "in_invoice"  and self.voucher_type=="PO":
						tax_string = ""
						for taxes in invoices.tax_line_ids:
							if taxes.name and taxes.amount:
								tax_string = tax_string + "|"+str(taxes.name)+";"+";"+";"+str(taxes.amount)
		
						purchase_string = "Purchase|"+str(invoices.number)+"|"+str(invoices.partner_id.name)+"|:"+str(invoices.partner_id.name)+";"+";"+";"+"-"+str(invoices.amount_total) + '|Inter-State Sales'+";"+";"+";"+str(invoices.amount_untaxed)
						main_string = purchase_string + tax_string +"\n"
						main_string2 = main_string2 +  main_string

		if main_string2:
			encoded_data = base64.encodestring(main_string2)
		else:
			raise ValidationError('%s is not present in the System '% (self.voucher_type))
		attach_vals = {
			# 'name':'LIFTUNIT1'+" ("+self.create_date+")"+"("+self.voucher_type+")",
			'name':file_name,
			'datas':encoded_data,
			'datas_fname':'LIFTUNIT1.ETF',
			'res_model':'ir.attachment',
		}
		doc_id = self.env['ir.attachment'].create(attach_vals)
		self.state ='done'
		return {
			'type' : 'ir.actions.act_url',
			'url': '/web/binary/download_document?model=%s&field=%s&id=%s&filename=%s.ETF' % (doc_id.res_model,'datas',doc_id.id,doc_id.name),
			'target': 'self',
			}


	@api.multi
	def sales_register_export(self):
		if self.date_start and self.date_end:
			if not self.attachment_id:
				inv_ids = self.env['account.invoice'].sudo().search([('date_invoice','>=',self.date_start),('date_invoice','<=',self.date_end),('type','=','out_invoice')])
				
				if (not inv_ids and not quot_ids ):
					return False
				
				# File Name
				file_name = self.name
				
				# Created Excel Workbook and Sheet
				workbook = xlwt.Workbook()
				worksheet = workbook.add_sheet('Sheet 1')
				
				main_style = xlwt.easyxf('font: bold on, height 400; align: wrap 1, vert centre, horiz center; borders: bottom thick, top thick, left thick, right thick')
				sp_style = xlwt.easyxf('font: bold on, height 350;')
				header_style = xlwt.easyxf('font: bold on; align: wrap 1,  horiz center; borders: bottom thin, top thin, left thin, right thin')
				base_style = xlwt.easyxf('align: wrap 1; borders: bottom thin, top thin, left thin, right thin')
				
				worksheet.write_merge(0, 1, 0, 7, file_name, main_style)
				row_index = 2
				
				worksheet.col(0).width = 4000
				worksheet.col(1).width = 6000
				worksheet.col(2).width = 16000
				worksheet.col(3).width = 6000
				worksheet.col(4).width = 6000
				worksheet.col(5).width = 5000
				worksheet.col(6).width = 6000
						
				if inv_ids:
					# Headers
					header_fields = ['Date','Doc No','Customer','Order No','Amount','Location Name','PONO']

					sp_updates = []
					for index, value in enumerate(header_fields):
						worksheet.write(row_index, index, value, header_style)
					row_index += 1
					sn = 1
					for record in inv_ids:
						invoice_date = datetime.strptime(record.date_invoice, '%Y-%m-%d').strftime('%d-%b-%y')
						quot_ids = self.env['sale.order'].search([('name','=',record.origin)])
						for rec in quot_ids:
							worksheet.write(row_index, 0, invoice_date, base_style)
							worksheet.write(row_index, 1, record.number, base_style)
							worksheet.write(row_index, 2, rec.partner_id.name, base_style)
							worksheet.write(row_index, 3, rec.name, base_style)
							worksheet.write(row_index, 4, record.amount_total, base_style)
							worksheet.write(row_index, 5, rec.partner_shipping_id.city, base_style)
							worksheet.write(row_index, 6, rec.po_order, base_style)
	
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
					'res_model':'tally.export',
				}
				doc_id = self.env['ir.attachment'].create(attach_vals)
				self.attachment_id = doc_id.id
			
			return {
				'type' : 'ir.actions.act_url',
				'url': '/web/binary/download_document?model=%s&field=%s&id=%s&filename=%s.xls' % (self.attachment_id.res_model,'datas',self.id,self.attachment_id.name),
				'target': 'self',
				}
		
		
	@api.multi
	def rg_export(self):
		if self.date_start and self.date_end:
			
			# if not self.attachment_id:
			inv_ids = self.env['account.invoice'].sudo().search([('date_invoice','>=',self.date_start),('date_invoice','<=',self.date_end)]) #,('type','=','out_invoice')
			
			if (not inv_ids):
				return False
			
			# File Name
			# file_name = self.name
			
			# Created Excel Workbook and Sheet
			workbook = xlwt.Workbook()
			worksheet = workbook.add_sheet('Sheet 1')
			
			main_style = xlwt.easyxf('font: bold on, height 400; align: wrap 1, vert centre, horiz center; borders: bottom thick, top thick, left thick, right thick')
			sp_style = xlwt.easyxf('font: bold on, height 350;')
			header_style = xlwt.easyxf('font: bold on; align: wrap 1,  horiz center; borders: bottom thin, top thin, left thin, right thin')
			base_style = xlwt.easyxf('align: wrap 1; borders: bottom thin, top thin, left thin, right thin')
			
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
			worksheet.col(9).width = 16000
			worksheet.col(10).width = 4000
			
			# print "CCCCCCCCCCCCCCCCC",self.company_id._get_address_data
			
			worksheet.write(row_index, 0, "R.G. - 1 DAILY STOCK ACCOUNT :", base_style)
			worksheet.write(row_index, 1, "Name of Unit :", base_style)
			worksheet.write(row_index, 2, self.company_id.name, base_style)
			worksheet.write(row_index, 3, "Address :", base_style)
			worksheet.write(row_index, 4, self.display_address, base_style)
			worksheet.write(row_index, 5, "C.Ex. Regn No :", base_style)
			worksheet.write(row_index, 6, self.company_id.company_registry, base_style)
			worksheet.write(row_index, 7, "Name of Comodity :", base_style)
			worksheet.write(row_index, 8, "LIFT CONTROLS BOXES/UNITS", base_style)
			worksheet.write(row_index, 9, "Unit of Quanity :", base_style)
			worksheet.write(row_index, 10, "NOS", base_style)
			
			
			if inv_ids:
				# Headers
				header_fields = ['Invoice Date','Qty of Boxes','Untaxed Invoice Amount','Excise Tax Rate %','Excise Tax Value','Freight Charges','Invoice Number','Total Invoice Amount','Location','Customer','PO NO']
				# row_index += 1
				# worksheet.write_merge(row_index, row_index, 0, 4, "Name of Comodity :", sp_style)
				worksheet.row(row_index).height = 400
				row_index += 1

				sp_updates = []
				for index, value in enumerate(header_fields):
					worksheet.write(row_index, index, value, header_style)
				row_index += 1
				sn = 1
				for record in inv_ids:
					
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
							for rec in quot_ids:
								worksheet.write(row_index, 0, invoice_date, base_style)
								worksheet.write(row_index, 1, box_qty, base_style)
								worksheet.write(row_index, 2, record.amount_untaxed, base_style)
								worksheet.write(row_index, 3, record.invoice_line_ids[0].invoice_line_tax_ids.amount, base_style)
								worksheet.write(row_index, 4, record.amount_tax, base_style)
								worksheet.write(row_index, 5, record.amount_freight, base_style)
								worksheet.write(row_index, 6, record.number, base_style)
								worksheet.write(row_index, 7, record.amount_total, base_style)
								worksheet.write(row_index, 8, rec.partner_shipping_id.city, base_style)
								worksheet.write(row_index, 9, record.partner_id.name, base_style)
								worksheet.write(row_index, 10, rec.name, base_style)
								
								sn +=1
								row_index += 1
								
						if record.type == "in_invoice" and self.voucher_type=="PO":
							rfq_ids = self.env['purchase.order'].search([('name','=',record.origin)])
							for rec in rfq_ids:
								worksheet.write(row_index, 0, invoice_date, base_style)
								worksheet.write(row_index, 1, 0, base_style)
								worksheet.write(row_index, 2, record.amount_untaxed, base_style)
								worksheet.write(row_index, 3, record.invoice_line_ids[0].invoice_line_tax_ids.amount, base_style)
								worksheet.write(row_index, 4, record.amount_tax, base_style)
								worksheet.write(row_index, 5, record.amount_freight, base_style)
								worksheet.write(row_index, 6, record.number, base_style)
								worksheet.write(row_index, 7, record.amount_total, base_style)
								worksheet.write(row_index, 8, rec.partner_id.city, base_style)
								worksheet.write(row_index, 9, record.partner_id.name, base_style)
								worksheet.write(row_index, 10, rec.name, base_style)
	
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
				'res_model':'tally.export',
			}
			doc_id = self.env['ir.attachment'].create(attach_vals)
			self.attachment_id = doc_id.id
		
		return {
			'type' : 'ir.actions.act_url',
			'url': '/web/binary/download_document?model=%s&field=%s&id=%s&filename=%s.xls' % (self.attachment_id.res_model,'datas',self.id,self.attachment_id.name),
			'target': 'self',
			}