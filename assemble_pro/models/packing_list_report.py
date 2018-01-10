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


class packing_list_export_report(models.TransientModel):
	_name = 'packing.list.export.report'
	_description = "Packing List Export Report"
	
	name = fields.Char(string="PackingListExportReport", compute="_get_name")
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
		rep_name = "Packing_List_Export_Report"
		if self.date_from and self.date_to:
			date_from = datetime.datetime.strptime(self.date_from, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
			date_to = datetime.datetime.strptime(self.date_to, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
			if self.date_from == self.date_to:
				rep_name = "Packing List Export Report(%s)" % (date_from,)
			else:
				rep_name = "Packing List Export Report(%s|%s)" % (date_from, date_to)
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
				
				worksheet.write_merge(0, 1, 0, 9, file_name, main_style)
				row_index = 2
				
				worksheet.col(0).width = 4000
				worksheet.col(1).width = 5000
				worksheet.col(2).width = 5000
				worksheet.col(3).width = 5000
				worksheet.col(4).width = 10000
				worksheet.col(5).width = 3000
				worksheet.col(6).width = 3000
				worksheet.col(7).width = 8000
				worksheet.col(8).width = 4000
				worksheet.col(9).width = 4000
				worksheet.col(10).width = 4000
				
				# Headers
				header_fields = ['PO NO','Job No','Code','HSN','Description','Qty','Stops','UOM','Batch Nos','Warehouse','PO Date']
				row_index += 1
				
				for index, value in enumerate(header_fields):
					worksheet.write(row_index, index, value, header_style)
				row_index += 1
				
				order_ids = self.env['sale.order'].sudo().search([('po_date','>=',self.date_from),('po_date','<=',self.date_to)])
				
				
				if (not order_ids): # not order_ids
					raise Warning(_('Record Not Found'))
				
				if order_ids:
					for order_id in order_ids:
						po_date = ''
						if order_id.po_date:
							po_date = datetime.datetime.strptime(order_id.po_date, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d %b %Y')
						if order_id.picking_ids:
							for line in order_id.picking_ids[0].pack_operation_product_ids:
								lot_ids = []
								batch_nos = ''
								for lot_id in line.pack_lot_ids:
									lot_ids.append(lot_id.lot_id.name)
								batch_nos = ",".join(lot_ids)
							
								worksheet.write(row_index, 0,order_id.po_order.strip() if order_id.po_order else '', base_style)
								worksheet.write(row_index, 1,order_id.name, base_style)  
								worksheet.write(row_index, 2, line.product_id.default_code or '', base_style)
								worksheet.write(row_index, 3, line.product_id.hsn_code or '', base_style)
								worksheet.write(row_index, 4,line.product_id.name, base_style)
								worksheet.write(row_index, 5,line.qty_done, base_style)
								worksheet.write(row_index, 6,'', base_style)
								worksheet.write(row_index, 7,line.product_uom_id.name or '', base_style)
								worksheet.write(row_index, 8,batch_nos, base_style)
								worksheet.write(row_index, 9,order_id.partner_id.city or '', base_style)
								worksheet.write(row_index, 10,order_id.po_date, base_style)
								
								row_index += 1
				# print err    
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
					'res_model':'packing.list.export.report',
				}
				doc_id = self.env['ir.attachment'].create(attach_vals)
				self.attachment_id = doc_id.id
			return {
				'type' : 'ir.actions.act_url',
				'url': '/web/binary/download_document?model=%s&field=%s&id=%s&filename=%s.xls' % (self.attachment_id.res_model,'datas',self.id,self.attachment_id.name),
				'target': 'self',
				}
				