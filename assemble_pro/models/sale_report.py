from openerp import models, fields, api, _, tools
from openerp.exceptions import UserError, Warning, ValidationError
from dateutil.relativedelta import relativedelta
import datetime
from datetime import timedelta
import time
from dateutil import relativedelta
from cStringIO import StringIO
import xlwt
import re
import base64
from openerp import http
from openerp.addons.web.controllers.main import serialize_exception,content_disposition
from openerp.http import request, serialize_exception as _serialize_exception
import pytz


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
					('Content-Type', 'application/vnd.ms-excel'),
					# ('Content-Type', 'application/octet-stream'),
					('Content-Length', len(filecontent))
			])

class sale_order_report(models.TransientModel):
	_name = 'sale.order.report'
	_description = "All Sale Order Report"
	
	name = fields.Char(string="SaleOrderReport", compute="_get_name")
	date_from = fields.Date(string="Date From", default=lambda self: fields.datetime.now())
	date_to = fields.Date(string="Date To", default=lambda self: fields.datetime.now())
	partner_id = fields.Many2one('res.partner', string="Customer")
	attachment_id = fields.Many2one('ir.attachment', string="Attachment", ondelete='cascade')
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
		rep_name = "Sale_Order_Report"
		if self.date_from and self.date_to:
			date_from = datetime.datetime.strptime(self.date_from, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
			date_to = datetime.datetime.strptime(self.date_to, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
			if self.date_from == self.date_to:
				rep_name = "Sale Order Report(%s)" % (date_from,)
			else:
				rep_name = "Sale Order Report(%s|%s)" % (date_from, date_to)
		self.name = rep_name
	
	@api.multi
	def print_report(self):
		if self.date_from and self.date_to:
			if not self.attachment_id:
				pending_order_ids = []
				
				# Created Excel Workbook and Sheet
				workbook = xlwt.Workbook()
				worksheet = workbook.add_sheet('Sheet 1')
				
				main_style = xlwt.easyxf('font: bold on, height 400; align: wrap 1, vert centre, horiz center; borders: bottom thick, top thick, left thick, right thick')
				sp_style = xlwt.easyxf('font: bold on, height 350;')
				header_style = xlwt.easyxf('font: bold on, height 220; align: wrap 1,  horiz center; borders: bottom thin, top thin, left thin, right thin')
				base_style = xlwt.easyxf('align: wrap 1; borders: bottom thin, top thin, left thin, right thin')

				worksheet.col(0).width = 4000
				worksheet.col(1).width = 8000
				worksheet.col(2).width = 8000
				worksheet.col(3).width = 8000
				worksheet.col(4).width = 4000
				worksheet.col(5).width = 6000
				worksheet.col(6).width = 4000
				worksheet.col(7).width = 4000
				worksheet.col(8).width = 6000
				worksheet.col(9).width = 4000
				
				if self.partner_id:
					order_ids = self.env['sale.order'].sudo().search([('partner_id','=',self.partner_id.id),('po_date','>=',self.date_from),('po_date','<=',self.date_to)])
				else:
					order_ids = self.env['sale.order'].sudo().search([('po_date','>=',self.date_from),('po_date','<=',self.date_to)])
				
				if self._context.get('default_state') == 'pending':
					file_name = 'Pending ' + self.name
					worksheet.write_merge(0, 1, 0, 8, file_name, main_style)
					row_index = 2
					# Headers
					header_fields = ['Date','Customer','GSTIN No.','Order Ref','Due Date','Location','Type','Status','PO NO','Boxes']
					row_index += 1
					
					for index, value in enumerate(header_fields):
						worksheet.write(row_index, index, value, header_style)
					row_index += 1
					for order_id in order_ids:
						if order_id.picking_ids:
							if order_id.picking_ids[0].state != 'done':
								pending_order_ids.append(order_id)
					if (not pending_order_ids): # not enquiry_ids
						raise Warning(_('Record Not Found'))
					
					if pending_order_ids:
						for order_id in pending_order_ids:
							delivery_date = po_date = status = box_type = ''
	
							if order_id.delivery_date:
								delivery_date = datetime.datetime.strptime(order_id.delivery_date, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d %b %Y')
							if order_id.po_date:
								po_date = datetime.datetime.strptime(order_id.po_date, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d %b %Y')
							if order_id.picking_ids:
								if order_id.picking_ids[0].state == 'done':
									status = 'Dispatched'
								else:
									status = 'Pending'

							box_qty = 0
							
							for box in  order_id.product_packaging_one2many:
								box_qty += box.qty
								if box.code == '57909466':
									box_type = '3100'
								elif box.code == '57909411':
									box_type = '3300'
	
							worksheet.write(row_index, 0,po_date, base_style)
							worksheet.write(row_index, 1,order_id.partner_id.name, base_style)
							worksheet.write(row_index, 2,order_id.partner_id.gstin_no or '', base_style)
							worksheet.write(row_index, 3, order_id.name, base_style)
							worksheet.write(row_index, 4,delivery_date, base_style)
							worksheet.write(row_index, 5,order_id.partner_id.city, base_style)
							worksheet.write(row_index, 6,box_type, base_style)
							worksheet.write(row_index, 7,status, base_style)
							worksheet.write(row_index, 8,order_id.po_order.strip() if order_id.po_order else '', base_style)
							worksheet.write(row_index, 9,box_qty, base_style)
	
							row_index += 1
				else:
					file_name = self.name
					worksheet.write_merge(0, 1, 0, 9, file_name, main_style)
					row_index = 2
					# Headers
					header_fields = ['Date','Customer','GSTIN No.','Order Ref','Due Date','Dispatch Date','Location','Type','Status','PO NO','Boxes']
					row_index += 1
					
					for index, value in enumerate(header_fields):
						worksheet.write(row_index, index, value, header_style)
					row_index += 1
					
					if (not order_ids): # not enquiry_ids
						raise Warning(_('Record Not Found'))
					
					if order_ids:
						for order_id in order_ids:
							delivery_date = po_date = dispatch_date = status = box_type = ''
	
							if order_id.delivery_date:
								delivery_date = datetime.datetime.strptime(order_id.delivery_date, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d %b %Y')
							if order_id.po_date:
								po_date = datetime.datetime.strptime(order_id.po_date, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d %b %Y')
							if order_id.picking_ids:
								if order_id.picking_ids[0].state == 'done':
									status = 'Dispatched'
								else:
									status = 'Pending'
								if order_id.picking_ids[0].min_date:
									dispatch_date = datetime.datetime.strptime(order_id.picking_ids[0].min_date, tools.DEFAULT_SERVER_DATETIME_FORMAT).strftime('%d %b %Y')
							
							box_qty = 0
							
							for box in  order_id.product_packaging_one2many:
								box_qty += box.qty
								if box.code == '57909466':
									box_type = '3100'
								elif box.code == '57909411':
									box_type = '3300'
	
							worksheet.write(row_index, 0,po_date, base_style)
							worksheet.write(row_index, 1,order_id.partner_id.name, base_style)
							worksheet.write(row_index, 2,order_id.partner_id.gstin_no or '', base_style)
							worksheet.write(row_index, 3, order_id.name, base_style)
							worksheet.write(row_index, 4,delivery_date, base_style)
							worksheet.write(row_index, 5,dispatch_date, base_style)
							worksheet.write(row_index, 6,order_id.partner_id.city, base_style)
							worksheet.write(row_index, 7,box_type, base_style)
							worksheet.write(row_index, 8,status, base_style)
							worksheet.write(row_index, 9,order_id.po_order.strip() if order_id.po_order else '', base_style)
							worksheet.write(row_index, 10,box_qty, base_style)
	
							row_index += 1
		
				fp = StringIO()
				workbook.save(fp)
				fp.seek(0)
				data = fp.read()
				fp.close()
				encoded_data = base64.encodestring(data)
				local_tz = pytz.timezone(self._context.get('tz') or 'UTC')
				attach_vals = {
					'name':'%s' % ( file_name ),
					'datas':encoded_data,
					'datas_fname':'%s.xls' % ( file_name ),
					'res_model':'sale.order.report',
				}
				doc_id = self.env['ir.attachment'].create(attach_vals)
				self.attachment_id = doc_id.id
			return {
				'type' : 'ir.actions.act_url',
				'url': '/web/binary/download_document?model=%s&field=%s&id=%s&filename=%s.xls' % (self.attachment_id.res_model,'datas',self.id,self.attachment_id.name),
				'target': 'self',
				}

class sale_order_export_report(models.TransientModel):
	_name = 'sale.order.export.report'
	_description = "Sale Order Export Report"
	
	name = fields.Char(string="SaleOrderExportReport", compute="_get_name")
	date_from = fields.Date(string="Date From", default=lambda self: fields.datetime.now())
	date_to = fields.Date(string="Date To", default=lambda self: fields.datetime.now())
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
		rep_name = "Sale_Order_Export_Report"
		if self.date_from and self.date_to:
			date_from = datetime.datetime.strptime(self.date_from, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
			date_to = datetime.datetime.strptime(self.date_to, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
			if self.date_from == self.date_to:
				rep_name = "Sale Order Export Report(%s)" % (date_from,)
			else:
				rep_name = "Sale Order Export Report(%s|%s)" % (date_from, date_to)
		self.name = rep_name
	
	@api.multi
	def print_report(self):
		if self.date_from and self.date_to:
			if not self.attachment_id:
				pending_order_ids = []
				file_name = self.name
				# Created Excel Workbook and Sheet
				workbook = xlwt.Workbook()
				worksheet = workbook.add_sheet('Sheet 1')
				
				main_style = xlwt.easyxf('font: bold on, height 400; align: wrap 1, vert centre, horiz center; borders: bottom thick, top thick, left thick, right thick')
				sp_style = xlwt.easyxf('font: bold on, height 350;')
				header_style = xlwt.easyxf('font: bold on, height 220; align: wrap 1,  horiz center; borders: bottom thin, top thin, left thin, right thin')
				base_style = xlwt.easyxf('align: wrap 1; borders: bottom thin, top thin, left thin, right thin')
				
				worksheet.write_merge(0, 1, 0, 13, file_name, main_style)
				row_index = 2
				
				worksheet.col(0).width = 4000
				worksheet.col(1).width = 8000
				worksheet.col(2).width = 8000
				worksheet.col(3).width = 8000
				worksheet.col(4).width = 3000
				worksheet.col(5).width = 8000
				worksheet.col(6).width = 3000
				worksheet.col(7).width = 3000
				worksheet.col(8).width = 4000
				worksheet.col(9).width = 4000
				worksheet.col(10).width = 4000
				worksheet.col(11).width = 4000
				worksheet.col(12).width = 4000
				worksheet.col(13).width = 4000
				worksheet.col(14).width = 4000
				
				# Headers
				header_fields = ['PO NO','Job No','Box ID','Code','HSN','Description','Qty','Stops','No of Belts','UOM','Warehouse','PO Date','Due Date','Rate','Amount']
				row_index += 1
				
				for index, value in enumerate(header_fields):
					worksheet.write(row_index, index, value, header_style)
				row_index += 1

				order_ids = self.env['sale.order'].sudo().search([('po_date','>=',self.date_from),('po_date','<=',self.date_to)])

				
				if (not order_ids): # not enquiry_ids
					raise Warning(_('Record Not Found'))
				
				if order_ids:
					for order_id in order_ids:
						delivery_date = po_date = ''

						if order_id.delivery_date:
							delivery_date = datetime.datetime.strptime(order_id.delivery_date, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d %b %Y')
						if order_id.po_date:
							po_date = datetime.datetime.strptime(order_id.po_date, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d %b %Y')
						
						for line in order_id.order_line:
							worksheet.write(row_index, 0,order_id.po_order.strip() if order_id.po_order else '', base_style)
							worksheet.write(row_index, 1,order_id.name, base_style)
							worksheet.write(row_index, 2, line.box_code.name or '', base_style)
							worksheet.write(row_index, 3,line.box_code_name or '', base_style)
							worksheet.write(row_index, 4,line.hsn_code or '', base_style)
							worksheet.write(row_index, 5,line.name, base_style)
							worksheet.write(row_index, 6,line.product_uom_qty, base_style)
							worksheet.write(row_index, 7,line.stops, base_style)
							worksheet.write(row_index, 8,'', base_style)
							worksheet.write(row_index, 9,line.product_uom.name or '', base_style)
							worksheet.write(row_index, 10,order_id.partner_id.city or '', base_style)
							worksheet.write(row_index, 11,order_id.po_date, base_style)
							worksheet.write(row_index, 12,order_id.delivery_date, base_style)
							worksheet.write(row_index, 13,line.price_unit, base_style)
							worksheet.write(row_index, 14,line.price_subtotal, base_style)

							row_index += 1
		
				fp = StringIO()
				workbook.save(fp)
				fp.seek(0)
				data = fp.read()
				fp.close()
				encoded_data = base64.encodestring(data)
				local_tz = pytz.timezone(self._context.get('tz') or 'UTC')
				attach_vals = {
					'name':'%s' % ( file_name ),
					'datas':encoded_data,
					'datas_fname':'%s.xls' % ( file_name ),
					'res_model':'sale.order.export.report',
				}
				doc_id = self.env['ir.attachment'].create(attach_vals)
				self.attachment_id = doc_id.id
			return {
				'type' : 'ir.actions.act_url',
				'url': '/web/binary/download_document?model=%s&field=%s&id=%s&filename=%s.xls' % (self.attachment_id.res_model,'datas',self.id,self.attachment_id.name),
				'target': 'self',
				}


class sale_summary_report(models.TransientModel):
	_name = 'sale.summary.report'
	_description = "Sale Summary Report"
	
	name = fields.Char(string="SaleSummaryReport", compute="_get_name")
	date_from = fields.Date(string="Date From", default=lambda self: fields.datetime.now())
	date_to = fields.Date(string="Date To", default=lambda self: fields.datetime.now())
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
		rep_name = "Sale_Summary_Report"
		if self.date_from and self.date_to:
			date_from = datetime.datetime.strptime(self.date_from, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
			date_to = datetime.datetime.strptime(self.date_to, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
			if self.date_from == self.date_to:
				rep_name = "Sale Summary Report(%s)" % (date_from,)
			else:
				rep_name = "Sale Summary Report(%s|%s)" % (date_from, date_to)
		self.name = rep_name
	
	@api.multi
	def print_report(self):
		if self.date_from and self.date_to:
			if not self.attachment_id:
				pending_order_ids = []
				file_name = self.name
				# Created Excel Workbook and Sheet
				workbook = xlwt.Workbook()
				worksheet = workbook.add_sheet('Sheet 1')
				
				main_style = xlwt.easyxf('font: bold on, height 400; align: wrap 1, vert centre, horiz center; borders: bottom thick, top thick, left thick, right thick')
				sp_style = xlwt.easyxf('font: bold on, height 350;')
				header_style = xlwt.easyxf('font: bold on, height 220; align: wrap 1,  horiz center; borders: bottom thin, top thin, left thin, right thin')
				base_style = xlwt.easyxf('align: wrap 1; borders: bottom thin, top thin, left thin, right thin')
				
				worksheet.write_merge(0, 1, 0, 5, file_name, main_style)
				row_index = 2
				
				worksheet.col(0).width = 4000
				worksheet.col(1).width = 8000
				worksheet.col(2).width = 3000
				worksheet.col(3).width = 3000
				worksheet.col(4).width = 4000
				worksheet.col(5).width = 4000
				
				# Headers
				header_fields = ['Code','Particulars','Qty','Stops','Rate','Amount']
				row_index += 1
				
				for index, value in enumerate(header_fields):
					worksheet.write(row_index, index, value, header_style)
				row_index += 1
				
				packaging_ids = self.env['product.packaging'].sudo().search([])
				order_ids = self.env['sale.order'].sudo().search([('po_date','>=',self.date_from),('po_date','<=',self.date_to)])

				
				if (not order_ids): # not enquiry_ids
					raise Warning(_('Record Not Found'))
				for packaging_id in packaging_ids:
					qty = 0.0
					rate = 0.0
					for order_id in order_ids:
						for line in order_id.product_packaging_one2many:
							if line.name.name == packaging_id.name:
								qty += line.qty
								rate += line.rate
								print "kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk", qty, line.qty
					worksheet.write(row_index, 0,packaging_id.code, base_style)
					worksheet.write(row_index, 1,packaging_id.name, base_style)
					worksheet.write(row_index, 2, qty, base_style)
					worksheet.write(row_index, 3,'', base_style)
					worksheet.write(row_index, 4,rate, base_style)
					worksheet.write(row_index, 5,(qty * rate), base_style)

	
					row_index += 1
		
				fp = StringIO()
				workbook.save(fp)
				fp.seek(0)
				data = fp.read()
				fp.close()
				encoded_data = base64.encodestring(data)
				local_tz = pytz.timezone(self._context.get('tz') or 'UTC')
				attach_vals = {
					'name':'%s' % ( file_name ),
					'datas':encoded_data,
					'datas_fname':'%s.xls' % ( file_name ),
					'res_model':'sale.summary.report',
				}
				doc_id = self.env['ir.attachment'].create(attach_vals)
				self.attachment_id = doc_id.id
			return {
				'type' : 'ir.actions.act_url',
				'url': '/web/binary/download_document?model=%s&field=%s&id=%s&filename=%s.xls' % (self.attachment_id.res_model,'datas',self.id,self.attachment_id.name),
				'target': 'self',
				}		