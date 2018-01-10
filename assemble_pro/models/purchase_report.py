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
import pytz

class purchase_order_report(models.TransientModel):
	_name = 'purchase.order.report'
	_description = "All Purchase Order Report"
	
	name = fields.Char(string="PurchaseOrderReport", compute="_get_name")
	date_from = fields.Date(string="Date From", default=lambda self: fields.datetime.now())
	date_to = fields.Date(string="Date To", default=lambda self: fields.datetime.now())
	partner_id = fields.Many2one( 'res.partner', string="Vendor")
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
		rep_name = "Purchase_Order_Report"
		if self.date_from and self.date_to:
			date_from = datetime.datetime.strptime(self.date_from, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
			date_to = datetime.datetime.strptime(self.date_to, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
			if self.date_from == self.date_to:
				rep_name = "Purchase Order Report(%s)" % (date_from,)
			else:
				rep_name = "Purchase Order Report(%s|%s)" % (date_from, date_to)
		self.name = rep_name
	
	@api.multi
	def print_report(self):
		if self.date_from and self.date_to:
			if not self.attachment_id:
				pending_order_ids = []
				order_list = []
				file_name = self.name
				# Created Excel Workbook and Sheet
				workbook = xlwt.Workbook()
				worksheet = workbook.add_sheet('Sheet 1')
				
				main_style = xlwt.easyxf('font: bold on, height 400; align: wrap 1, vert centre, horiz center; borders: bottom thick, top thick, left thick, right thick')
				sp_style = xlwt.easyxf('font: bold on, height 350;')
				header_style = xlwt.easyxf('font: bold on, height 220; align: wrap 1,  horiz center; borders: bottom thin, top thin, left thin, right thin')
				base_style = xlwt.easyxf('align: wrap 1; borders: bottom thin, top thin, left thin, right thin')
				base_style_gray = xlwt.easyxf('align: wrap 1; borders: bottom thin, top thin, left thin, right thin; pattern: pattern fine_dots, fore_color white, back_color gray_ega;')
				base_style_yellow = xlwt.easyxf('align: wrap 1; borders: bottom thin, top thin, left thin, right thin; pattern: pattern fine_dots, fore_color white, back_color yellow;')
				
				worksheet.write_merge(0, 1, 0, 9, file_name, main_style)
				row_index = 2
				
				worksheet.col(0).width = 4000
				worksheet.col(1).width = 8000
				worksheet.col(2).width = 6000
				worksheet.col(3).width = 6000
				worksheet.col(4).width = 16000
				worksheet.col(5).width = 4000
				worksheet.col(6).width = 4000
				worksheet.col(7).width = 4000
				worksheet.col(8).width = 6000
				worksheet.col(9).width = 4000
				worksheet.col(10).width = 4000
				worksheet.col(10).width = 4000
				
				# Headers
				header_fields = ['Date','Doc No','GSTIN NO.','HSN','Particulars','Order Qty','Pending Qty','UOM','Rate','Amount','Due Date','Status']
				row_index += 1
				
				# https://github.com/python-excel/xlwt/blob/master/xlwt/Style.py
				
				for index, value in enumerate(header_fields):
					worksheet.write(row_index, index, value, header_style)
				row_index += 1
				if self.partner_id:
					order_ids = self.env['purchase.order'].sudo().search([('partner_id','=',self.partner_id.id)])
				else:
					order_ids = self.env['purchase.order'].sudo().search([])

				if self._context.get('default_state') == 'pending':
					status = ''
					for rec in order_ids:
						if rec.picking_ids:
							date_order = datetime.datetime.strptime(rec.date_order, tools.DEFAULT_SERVER_DATETIME_FORMAT).date().strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
							if rec.picking_ids[0].state != 'done' and date_order >= self.date_from and date_order <= self.date_to:		
								pending_order_ids.append(rec)

					if (not pending_order_ids): # not enquiry_ids
						raise Warning(_('Record Not Found'))
					
					if pending_order_ids:
						for order_id in pending_order_ids:
							due_date = ''
							status = 'Pending'
							date = datetime.datetime.strptime(order_id.date_order, tools.DEFAULT_SERVER_DATETIME_FORMAT).date().strftime('%d %b %Y')
							if order_id.date_planned:
								due_date = datetime.datetime.strptime(order_id.date_planned, tools.DEFAULT_SERVER_DATETIME_FORMAT).date().strftime('%d %b %Y')
							worksheet.write(row_index, 0,date, base_style_yellow)
							worksheet.write_merge(row_index, row_index+len(order_id.order_line), 1, 1, order_id.name.strip(), base_style_yellow)
							worksheet.write(row_index, 2, order_id.partner_id.gstin_no or '', base_style_yellow)
							worksheet.write(row_index, 3,'', base_style_yellow)
							worksheet.write(row_index, 4, order_id.partner_id.name, base_style_yellow)
							worksheet.write(row_index, 5,'', base_style_yellow)
							worksheet.write(row_index, 6,'', base_style_yellow)
							worksheet.write(row_index, 7,'', base_style_yellow)
							worksheet.write(row_index, 8,'', base_style_yellow)
							worksheet.write(row_index, 9,'', base_style_yellow)
							worksheet.write(row_index, 10,due_date, base_style_yellow)
							worksheet.write(row_index, 11,status, base_style_yellow)
							row_index += 1
							for line in order_id.order_line:
								worksheet.write(row_index, 0,'', base_style)
								worksheet.write(row_index, 3,line.hsn_code or '', base_style)
								worksheet.write(row_index, 4,line.name, base_style)
								worksheet.write(row_index, 5,line.product_qty, base_style)
								worksheet.write(row_index, 6,'', base_style)
								worksheet.write(row_index, 7,line.product_uom.name or '', base_style)
								worksheet.write(row_index, 8,line.price_unit, base_style)
								worksheet.write(row_index, 9,line.price_subtotal, base_style)
								worksheet.write(row_index, 10,'', base_style)
								worksheet.write(row_index, 11,'', base_style)
								row_index += 1
				else:		
					if order_ids:
						for rec in order_ids:
							date_order = datetime.datetime.strptime(rec.date_order, tools.DEFAULT_SERVER_DATETIME_FORMAT).date().strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
							if date_order >= self.date_from and date_order <= self.date_to:
								order_list.append(rec)
								
						if (not order_list): # not order_list
							raise Warning(_('Record Not Found'))
						for order_id in order_list:
							due_date = ''
							date = datetime.datetime.strptime(order_id.date_order, tools.DEFAULT_SERVER_DATETIME_FORMAT).date().strftime('%d %b %Y')
							if order_id.date_planned:
								due_date = datetime.datetime.strptime(order_id.date_planned, tools.DEFAULT_SERVER_DATETIME_FORMAT).date().strftime('%d %b %Y')
							if order_id.picking_ids:
								if order_id.picking_ids[0].state == 'done':
									status = 'Received'
								else:
									status = 'Pending'
								if order_id.picking_ids[0].min_date:
									dispatch_date = datetime.datetime.strptime(order_id.picking_ids[0].min_date, tools.DEFAULT_SERVER_DATETIME_FORMAT).strftime('%d %b %Y')
							
	
							worksheet.write(row_index, 0,date, base_style_gray if status=='Received' else base_style_yellow)
							worksheet.write_merge(row_index, row_index+len(order_id.order_line), 1, 1, order_id.name.strip(), base_style_gray if status=='Received' else base_style_yellow)
							worksheet.write(row_index, 2, order_id.partner_id.gstin_no or '', base_style_gray if status=='Received' else base_style_yellow)
							worksheet.write(row_index, 3,'', base_style_gray if status=='Received' else base_style_yellow)
							worksheet.write(row_index, 4, order_id.partner_id.name, base_style_gray if status=='Received' else base_style_yellow)
							worksheet.write(row_index, 5,'', base_style_gray if status=='Received' else base_style_yellow)
							worksheet.write(row_index, 6,'', base_style_gray if status=='Received' else base_style_yellow)
							worksheet.write(row_index, 7,'', base_style_gray if status=='Received' else base_style_yellow)
							worksheet.write(row_index, 8,'', base_style_gray if status=='Received' else base_style_yellow)
							worksheet.write(row_index, 9,'', base_style_gray if status=='Received' else base_style_yellow)
							worksheet.write(row_index, 10,due_date, base_style_gray if status=='Received' else base_style_yellow)
							worksheet.write(row_index, 11,status, base_style_gray if status=='Received' else base_style_yellow)
							row_index += 1
							for line in order_id.order_line:
								worksheet.write(row_index, 0,'', base_style)
								worksheet.write(row_index, 3,line.hsn_code or '', base_style)
								worksheet.write(row_index, 4,line.name, base_style)
								worksheet.write(row_index, 5,line.product_qty, base_style)
								worksheet.write(row_index, 6,'', base_style)
								worksheet.write(row_index, 7,line.product_uom.name or '', base_style)
								worksheet.write(row_index, 8,line.price_unit, base_style)
								worksheet.write(row_index, 9,line.price_subtotal, base_style)
								worksheet.write(row_index, 10,'', base_style)
								worksheet.write(row_index, 11,'', base_style)
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
					'res_model':'purchase.order.report',
				}
				doc_id = self.env['ir.attachment'].create(attach_vals)
				self.attachment_id = doc_id.id
			return {
				'type' : 'ir.actions.act_url',
				'url': '/web/binary/download_document?model=%s&field=%s&id=%s&filename=%s.xls' % (self.attachment_id.res_model,'datas',self.id,self.attachment_id.name),
				'target': 'self',
				}