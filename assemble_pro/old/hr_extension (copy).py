
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
from datetime import timedelta
from dateutil import relativedelta
import pytz

# from datetime import date
# import pandas
from collections import Counter
import openerp.addons.decimal_precision as dp

class hr_extension(models.Model):
	_inherit = 'hr.employee'
	
	display_name = fields.Char(string="Display Name", compute="_name_get")
	last_name = fields.Char(string="Last Name")
	middle_name = fields.Char(string="Middle Name")
	
	@api.depends('name','middle_name','last_name')
	def _name_get(self):
		for hr in self:
			name = hr.name_get()
			hr.display_name = name[0][1]
			
	@api.multi
	def name_get(self):
		result= []
		for ai in self:
			name = (ai.name or '')+' '+(ai.middle_name or '')+' '+(ai.last_name or '')
			result.append((ai.id,name.strip()))
		return result

class hr_contract_extension(models.Model):
	_inherit = 'hr.contract'

	lwf = fields.Float(string="LWF" , default='10.00')
	conveyance = fields.Float(string="Conveyance")
	overtime = fields.Float(string="Total hrs. OT Worked")
	miscellaneous_deduction = fields.Float(string="Mis. Ded.")
	advance = fields.Float(string="Advance")


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


class hr_employee_export(models.Model):
	_name = 'hr.employee.export'
	_description = "Hr Employee Export"
	_inherit = ['mail.thread', 'ir.needaction_mixin']
	
	name = fields.Many2one('hr.employee' , string = "Export No.")
	date_start = fields.Date(string="From Date" , default= lambda *a: time.strftime('%Y-%m-01'))
	date_end = fields.Date(string="To Date",default= lambda *a: str(datetime.now() + relativedelta.relativedelta(months=+1, day=1, days=-1))[:10])
	user_id = fields.Many2one('res.users', string='User', default=lambda self: self._uid, track_visibility='always')
	state = fields.Selection([
		('draft', 'Draft'),
		('done', 'Exported'),
		('cancel', 'Cancelled'),
		], string='Status', readonly=True,
		copy=False, index=True, track_visibility='always', default='draft')
	company_id = fields.Many2one('res.company', string='Company')

	attachment_id = fields.Many2one( 'ir.attachment', string="Attachment", ondelete='cascade')
	datas = fields.Binary(string="XLS Report", related="attachment_id.datas")
	display_address = fields.Char(string="Name")
	
	
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
	@api.constrains('date_start','date_end','company_id')
	def constraints_check(self):
		if self.date_start and self.date_end and self.date_start > self.date_end:
			raise UserError("Please select a valid date range")
		if not self.company_id:
			raise UserError("Please select a Company")
		
	@api.multi
	def hr_export(self):
		if self.date_start and self.date_end:
			
			# if not self.attachment_id:
			# contract_ids = self.env['hr.contract'].sudo().search([('date_start','>=',self.date_start),('date_end','<=',self.date_end)]) #,('type','=','out_invoice')
			
			# if (not contract_ids):
			# 	return False
			
			# File Name
			file_name = 'HR_export'
			
			# Created Excel Workbook and Sheet
			workbook = xlwt.Workbook()
			worksheet = workbook.add_sheet('Sheet 1')
			
			main_style = xlwt.easyxf('font: bold on, height 400; align: wrap 1, vert centre, horiz center; borders: bottom thick, top thick, left thick, right thick')
			sp_style = xlwt.easyxf('font: bold on, height 350;')
			header_style = xlwt.easyxf('font: bold on; align: wrap 1,  horiz center; borders: bottom thin, top thin, left thin, right thin')
			base_style = xlwt.easyxf('align: wrap 1; borders: bottom thin, top thin, left thin, right thin')
			
			# worksheet.write_merge(0, 1, 0, 7, file_name, main_style)
			row_index = 2
			
			worksheet.col(0).width = 4000
			worksheet.col(1).width = 4000
			worksheet.col(2).width = 6000
			worksheet.col(3).width = 6000
			worksheet.col(4).width = 6000
			# worksheet.col(5).width = 5000
			# worksheet.col(6).width = 6000
			# worksheet.col(7).width = 6000
			# worksheet.col(8).width = 5000
			# worksheet.col(9).width = 16000
			# worksheet.col(10).width = 4000
			
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
			
			
			# if contract_ids:
			employee_ids = self.env['hr.employee'].search([('id','>',0)])
			# Headers
			header_fields = ['SR No.','Department','Name of the Employee',"Father's/Husband's Name",'Designation','Basic','HRA','Conveyance','Special Allowances','Gross Wages','Present days','Weekly Off','PL',"CL",'SL','Absent','Monthly Working days','Total days Paid For','Basic','HRA','Conveyance','Special Allowances','Gross Wages earned','Rate of Overtime','Total hrs. OT Worked','Ovetime Wages','Total Wages Earned','P.F.','ESIC','LWF','Advance','Mis. Ded.','Total Deduction','Net Wages Paid','Signature of Employees','Bank A/c No','Remark']
			# row_index += 1
			# worksheet.write_merge(row_index, row_index, 0, 4, "Name of Comodity :", sp_style)
			worksheet.row(row_index).height = 400
			row_index += 1

			sp_updates = []
			for index, value in enumerate(header_fields):
				worksheet.write(row_index, index, value, header_style)
			row_index += 1
			sn = 1
			for record in employee_ids:
				attendance_ids = self.env['hr.attendance'].search([('employee_id','=',record.id)])
				print "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA attendance " , attendance_ids , record.display_name
				len_attendance_ids = len(attendance_ids)
				attendance = len_attendance_ids / 2
				# if self.company_id.id == record.company_id.id:
				# 	invoice_date = datetime.strptime(record.date_invoice, '%Y-%m-%d').strftime('%d-%b-%y')
				
				contract_ids = self.env['hr.contract'].search([('employee_id','=',record.id)])
# 				,('date_start','>=',self.date_start),('date_end','<=',self.date_end)
				
				for contract in contract_ids:
					
					father_name = (str(record.middle_name) or '') +" "+(str(record.last_name) or '')
					gross = contract.wage + contract.house_rent_allowance_metro_nonmetro + contract.conveyance + contract.supplementary_allowance
					
					worksheet.write(row_index, 0, str(sn), base_style) # SR No.
					worksheet.write(row_index, 1, record.department_id.name, base_style) # SR No.
					worksheet.write(row_index, 2, record.display_name, base_style) # SR No.
					worksheet.write(row_index, 3, father_name, base_style) # SR No.
					worksheet.write(row_index, 4, record.job_id.name) # SR No.
					worksheet.write(row_index, 5, contract.wage, base_style) # SR No.
					worksheet.write(row_index, 6, contract.house_rent_allowance_metro_nonmetro, base_style) # SR No.
					worksheet.write(row_index, 7, contract.conveyance, base_style) # SR No.
					worksheet.write(row_index, 8, contract.supplementary_allowance, base_style) # SR No.
					worksheet.write(row_index, 9, gross, base_style) # SR No.
					
					worksheet.write(row_index, 10, attendance, base_style) # SR No.
					worksheet.write(row_index, 11, gross, base_style) # SR No.
					worksheet.write(row_index, 12, gross, base_style) # SR No.
					worksheet.write(row_index, 13, gross, base_style) # SR No.
					worksheet.write(row_index, 14, gross, base_style) # SR No.
					worksheet.write(row_index, 15, gross, base_style) # SR No.
					worksheet.write(row_index, 16, gross, base_style) # SR No.
					worksheet.write(row_index, 17, gross, base_style) # SR No.
					worksheet.write(row_index, 18, gross, base_style) # SR No.
					worksheet.write(row_index, 19, gross, base_style) # SR No.
					worksheet.write(row_index, 20, gross, base_style) # SR No.
					worksheet.write(row_index, 21, gross, base_style) # SR No.
					worksheet.write(row_index, 22, gross, base_style) # SR No.
					worksheet.write(row_index, 23, gross, base_style) # SR No.
					worksheet.write(row_index, 24, gross, base_style) # SR No.
					worksheet.write(row_index, 25, gross, base_style) # SR No.
					worksheet.write(row_index, 26, gross, base_style) # SR No.
					worksheet.write(row_index, 27, gross, base_style) # SR No.
					worksheet.write(row_index, 28, gross, base_style) # SR No.
					# worksheet.write(row_index, 10, rec.name, base_style)
					# worksheet.write(row_index, 29, gross, base_style) # SR No.
					worksheet.write(row_index, 29, contract.lwf, base_style) # SR No.
					worksheet.write(row_index, 30, contract.advance, base_style) # SR No.
					worksheet.write(row_index, 31, contract.miscellaneous_deduction, base_style) # SR No.
					worksheet.write(row_index, 32, gross, base_style) # SR No.
					worksheet.write(row_index, 33, gross, base_style) # SR No.
					worksheet.write(row_index, 34, gross, base_style) # SR No.
					worksheet.write(row_index, 35, record.bank_account_id.sanitized_acc_number, base_style)  # SR No.
					# worksheet.write(row_index, 36, record.bank_account_id.sanitized_acc_number, base_style) # Remark

					
					
					
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
				'res_model':'hr.employee.export',
			}
			doc_id = self.env['ir.attachment'].create(attach_vals)
			self.attachment_id = doc_id.id
		# print AAi
		return {
			'type' : 'ir.actions.act_url',
			'url': '/web/binary/download_document?model=%s&field=%s&id=%s&filename=%s.xls' % (self.attachment_id.res_model,'datas',self.id,self.attachment_id.name),
			'target': 'self',
			}