
from openerp.exceptions import UserError, MissingError, ValidationError
import csv
import base64
import decimal
import openerp

from openerp import models, fields, api, _, tools
from openerp.exceptions import UserError
from datetime import datetime , timedelta
import calendar
import time
import logging
from openerp.tools import float_is_zero,openerp,image_colorize, image_resize_image_big
import re , collections
from openerp import http
from openerp.addons.web.controllers.main import serialize_exception,content_disposition
from openerp.http import request, serialize_exception as _serialize_exception
from cStringIO import StringIO
import xlwt
# from datetime import timedelta
from dateutil import relativedelta
import pytz

# from datetime import date
from collections import Counter
import openerp.addons.decimal_precision as dp

class hr_extension(models.Model):
	_inherit = 'hr.employee'
	
	display_name = fields.Char(string="Display Name", compute="_name_get")
	last_name = fields.Char(string="Last Name")
	middle_name = fields.Char(string="Middle Name")
	hr_employee_salary_one2many = fields.One2many('hr.employee.salary','hr_employee_id',string="Salary Details")
	
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


class hr_employee_salary(models.Model):
	_name = 'hr.employee.salary'
	_description = "Hr Employee Bonus"
	_inherit = ['mail.thread', 'ir.needaction_mixin']
	_rec_name = 'hr_employee_id'
	
	hr_employee_id = fields.Many2one('hr.employee' , string = "Employee Id")
	wage_paid =  fields.Float(string="Wage")
	days_worked = fields.Float(string="Conveyance")
	total_ot_hrs = fields.Float(string="OT hrs")
	month = fields.Char(string="Month")
	actual_basic = fields.Float(string="Basic")
	total_deduction = fields.Float(string="Deductions")
	
	
class hr_contract_extension(models.Model):
	_inherit = 'hr.contract'

	lwf = fields.Float(string="LWF" , default='10.00')
	conveyance = fields.Float(string="Conveyance")
	overtime = fields.Float(string="Total hrs. OT Worked")
	miscellaneous_deduction = fields.Float(string="Mis. Ded.")
	advance = fields.Float(string="Advance")
	ot_rates = fields.Float(string="Overtime Rates")
	


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
	
	# name = fields.Many2one('hr.employee' , string = "Export No.")
	name = fields.Char(string = "Export No.")
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
		
		today = datetime.today()
		m = datetime.strptime(self.date_start, "%Y-%m-%d")
		y = datetime.strptime(self.date_end, "%Y-%m-%d")
		days = (y - m).days + 1

		daygenerator = (m + timedelta(x + 1) for x in xrange((y - m).days))
		weekdays = sum(1 for day in daygenerator if day.weekday() < 6)
		sundays = days - weekdays - 1

		employee_values = {}
		if self.date_start and self.date_end:
			
			# Created Excel Workbook and Sheet
			workbook = xlwt.Workbook()
			worksheet = workbook.add_sheet('Sheet 1')
			
			main_style = xlwt.easyxf('font: bold on, height 400; align: wrap 1, vert centre, horiz center; borders: bottom thick, top thick, left thick, right thick')
			sp_style = xlwt.easyxf('font: bold on, height 350;')
			header_style = xlwt.easyxf('font: bold on; align: wrap 1,  horiz center; borders: bottom thin, top thin, left thin, right thin')
			base_style = xlwt.easyxf('align: wrap 1; borders: bottom thin, top thin, left thin, right thin')
			
			# worksheet.write_merge(0, 1, 0, 7, file_name, main_style)
			merge_style = xlwt.easyxf('font: bold on,height 200; align: wrap 1,  horiz center; borders: bottom thin, top thin, left thin, right thin')
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
			month_year =  datetime.strptime(self.date_start, '%Y-%m-%d').strftime('%B %Y')
			company = (str(self.company_id.name) or '') +"\n"+ (str(self.company_id.street) or '') +" "+ (str(self.company_id.street2) or '') +" "+ (str(self.company_id.state_id.name) or '') +" "+ (str(self.company_id.zip) or '')+"\n"+ "REGISTER OF WAGES FOR THE MONTH " + month_year + "\n"+ "Period: "+ (str(self.date_start) or '')+" To "+ (str(self.date_end) or '')
			worksheet.write_merge(0, 2, 0, 36, company,merge_style)
			file_name = 'HR Export '+str(month_year)

			# Headers
			header_fields = ['SR No.','Department','Name of the Employee',"Father's/Husband's Name",'Designation','Actual Rate of Wages','Gross Wages','Present days','Weekly Off','PL',"CL",'SL','Absent','Monthly Working days','Total days Paid For','Rate of Wages Actually Paid','Gross Wages earned','Rate of Overtime','Total hrs. OT Worked','Ovetime Wages','Total Wages Earned','Deductions','Total Deduction','Net Wages Paid','Signature of Employees','Bank A/c No','Remark']
			# row_index += 1
			# worksheet.write_merge(row_index, row_index, 0, 4, "Name of Comodity :", sp_style)
			worksheet.row(row_index).height = 400
			row_index += 1

			sp_updates = []
			new_index = 0
			for value in enumerate(header_fields):
				if new_index == 5 or new_index == 18:
					worksheet.write_merge(row_index,row_index,new_index,new_index+3, value[1], header_style)
					rate_wages = ['Basic','HRA','Conveyance','Special Allowances']
					rate_wage_index = new_index
					for value in enumerate(rate_wages):
						worksheet.write_merge(row_index+1,row_index+1,rate_wage_index,rate_wage_index, value[1], header_style)
						rate_wage_index += 1
					new_index += 4
				elif new_index == 27:
					worksheet.write_merge(row_index,row_index,new_index,new_index+4, value[1], header_style)
					deduction = ['P.F.','ESIC','LWF','Advance','Mis. Ded.']
					deduction_index = new_index
					for value in enumerate(deduction):
						worksheet.write_merge(row_index+1,row_index+1,deduction_index,deduction_index, value[1], header_style)
						deduction_index += 1
					new_index += 5
				else:
					worksheet.write_merge(row_index,row_index+1,new_index,new_index, value[1], header_style)
					new_index += 1
					
			row_index += 2
			sn = 1
			# if contract_ids:
			employee_ids = self.env['hr.employee'].search([('id','>',0)])
			# salary_details 
			for record in employee_ids:
				attendance_ids = self.env['hr.attendance'].search([('employee_id','=',record.id),('name','>=',self.date_start),('name','<=',self.date_end)])
				print "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" , attendance_ids
				len_attendance_ids = len(attendance_ids)
				attendance = len_attendance_ids / 2
				# if self.company_id.id == record.company_id.id:
				# 	invoice_date = datetime.strptime(record.date_invoice, '%Y-%m-%d').strftime('%d-%b-%y')
				overtime_hours = 0.0
				for overtime in record.overtime_ids:
					overtime_hours += overtime.number_of_hours
				
				contract_ids = self.env['hr.contract'].search([('employee_id','=',record.id)])
# 				,('date_start','>=',self.date_start),('date_end','<=',self.date_end)
				
				for contract in contract_ids:
					holiday_ids = self.env['hr.holidays'].search([('employee_id','=',record.id),('type','=','remove'),('date_from','>=',self.date_start),('date_to','<=',self.date_end)])
					pl = cl = sl = ul = 0
					for holiday in holiday_ids:
						
						if holiday.holiday_status_id.name =='Compensatory Days':
							cl += holiday.number_of_days_temp
							
						if  'Legal Leaves'  in holiday.holiday_status_id.name:
							pl += holiday.number_of_days_temp
							
						if holiday.holiday_status_id.name =='Sick Leaves':
							sl += holiday.number_of_days_temp
							
						if holiday.holiday_status_id.name =='Unpaid':
							ul += holiday.number_of_days_temp
						
					# Calculation -------------------------------
					father_name = (str(record.middle_name) or '') +" "+(str(record.last_name) or '')
					gross = contract.wage + contract.house_rent_allowance_metro_nonmetro + contract.conveyance + contract.supplementary_allowance
					
					absent = days - (attendance + pl + cl + sl + ul + sundays)
					paid_days = attendance + pl + cl + sl + sundays
					basic_actual = (contract.wage / days)* paid_days
					hra_actual = (contract.house_rent_allowance_metro_nonmetro / days)* paid_days
					conveyance_actual = (contract.conveyance / days)* paid_days
					special_actual = (contract.supplementary_allowance / days)* paid_days
					wages_earned = basic_actual + hra_actual + conveyance_actual + special_actual
					ot_rate = ((contract.wage / days)/8) * 2
					ot_wages = ot_rate * overtime_hours
					total_wages = wages_earned + ot_wages
					pf = basic_actual * 0.12
					esic = total_wages * (1.75/100)
					
					deduction = pf + esic + contract.lwf + contract.advance + contract.miscellaneous_deduction
					net_wages = wages_earned - deduction
					# Calculation -------------------------------
					
					worksheet.write(row_index, 0, str(sn), base_style) # SR No.
					worksheet.write(row_index, 1, record.department_id.name, base_style) # Dept
					worksheet.write(row_index, 2, record.display_name, base_style) # Employee
					worksheet.write(row_index, 3, father_name, base_style) # Employee father_name
					worksheet.write(row_index, 4, record.job_id.name or '' , base_style) # Title
					worksheet.write(row_index, 5, contract.wage, base_style) # Basic
					worksheet.write(row_index, 6, contract.house_rent_allowance_metro_nonmetro, base_style) # HRA
					worksheet.write(row_index, 7, contract.conveyance, base_style) # conveyance
					worksheet.write(row_index, 8, contract.supplementary_allowance, base_style) # Special Allowances
					worksheet.write(row_index, 9, gross, base_style) # Gross Wages
					worksheet.write(row_index, 10, attendance, base_style) # Present days
					worksheet.write(row_index, 11, sundays, base_style) # Weekly Off
					worksheet.write(row_index, 12, pl, base_style) # PL
					worksheet.write(row_index, 13, cl, base_style) # CL
					worksheet.write(row_index, 14, sl, base_style) # SL
					worksheet.write(row_index, 15, absent, base_style) # absent
					worksheet.write(row_index, 16, days, base_style) # Monthly Working days
					worksheet.write(row_index, 17, paid_days, base_style) # Total days Paid For
					worksheet.write(row_index, 18, round(basic_actual,2), base_style) # basic_actual
					worksheet.write(row_index, 19, round(hra_actual,2), base_style) # hra_actual
					worksheet.write(row_index, 20, round(conveyance_actual,2), base_style) # conveyance_actual
					worksheet.write(row_index, 21, round(special_actual,2), base_style) # special_actual
					worksheet.write(row_index, 22, round(wages_earned,2), base_style) # Gross Wages earned
					worksheet.write(row_index, 23, round(ot_rate,2), base_style) # Rate of Overtime
					worksheet.write(row_index, 24, round(overtime_hours,2), base_style) # Total hrs. OT Worked
					worksheet.write(row_index, 25, round(ot_wages,2), base_style) # Ovetime Wages
					worksheet.write(row_index, 26, round(total_wages,2), base_style) # Total Wages Earned
					worksheet.write(row_index, 27, round(pf,2), base_style) # PF
					worksheet.write(row_index, 28, round(esic,2), base_style) # ESIC
					worksheet.write(row_index, 29, contract.lwf, base_style) # LWF
					worksheet.write(row_index, 30, contract.advance, base_style) # ADVANCE
					worksheet.write(row_index, 31, contract.miscellaneous_deduction, base_style) # Mis. Ded.
					worksheet.write(row_index, 32, round(deduction,2), base_style) # Total Deduction
					worksheet.write(row_index, 33, round(net_wages,2), base_style) # Net Wages Paid
					worksheet.write(row_index, 34, '', base_style) # Signature
					worksheet.write(row_index, 35, record.bank_account_id.sanitized_acc_number, base_style)  # Bank A/c No
					worksheet.write(row_index, 36, '', base_style) # Remark
					
					sn +=1
					row_index += 1

					salary_ids=record.hr_employee_salary_one2many.search([('hr_employee_id','=',record.id),('month','ilike',month_year)])
					if not salary_ids and (days<= 31):
						record.hr_employee_salary_one2many.create({'hr_employee_id': record.id,'month':month_year,'days_worked':paid_days,'total_ot_hrs':overtime_hours,'actual_basic':basic_actual,'total_deduction':deduction,'wage_paid':net_wages})
					
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
		self.name = file_name
		self.state = 'done'
		
		
		return {
			'type' : 'ir.actions.act_url',
			'url': '/web/binary/download_document?model=%s&field=%s&id=%s&filename=%s.xls' % (self.attachment_id.res_model,'datas',self.id,self.attachment_id.name),
			'target': 'self',
			}
	
class hr_employee_bonus(models.Model):
	_name = 'hr.employee.bonus'
	_description = "Hr Employee Bonus"
	_inherit = ['mail.thread', 'ir.needaction_mixin']
	
	# name = fields.Many2one('hr.employee' , string = "Export No.")
	name = fields.Char(string = "No.") 
	date_start = fields.Date(string="From Date")
	date_end = fields.Date(string="To Date")
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
	
	@api.multi
	def bonus_export(self):
		

		today = datetime.today()
		m = datetime.strptime(self.date_start, "%Y-%m-%d")
		y = datetime.strptime(self.date_end, "%Y-%m-%d")
		days = (y - m).days + 1
		daygenerator = (m + timedelta(x + 1) for x in xrange((y - m).days))
		weekdays = sum(1 for day in daygenerator if day.weekday() < 6)
		sundays = days - weekdays - 1

		if self.date_start and self.date_end:
			workbook = xlwt.Workbook()
			worksheet = workbook.add_sheet('Sheet 1')
			main_style = xlwt.easyxf('font: bold on, height 400; align: wrap 1, vert centre, horiz center; borders: bottom thick, top thick, left thick, right thick')
			sp_style = xlwt.easyxf('font: bold on, height 350;')
			header_style = xlwt.easyxf('font: bold on; align: wrap 1,  horiz center; borders: bottom thin, top thin, left thin, right thin')
			base_style = xlwt.easyxf('align: wrap 1; borders: bottom thin, top thin, left thin, right thin')
			
			# worksheet.write_merge(0, 1, 0, 7, file_name, main_style)
			merge_style = xlwt.easyxf('font: bold on,height 200; align: wrap 1,  horiz left; borders: bottom thin, top thin, left thin, right thin')
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
			start_month_year =  datetime.strptime(self.date_start, '%Y-%m-%d').strftime('%B %Y')
			end_month_year =  datetime.strptime(self.date_end, '%Y-%m-%d').strftime('%B %Y')
			company = (str(self.company_id.name) or '') +"\n"+ "Bonus Calculation for the year " + start_month_year+ " To "+end_month_year
			worksheet.write_merge(0, 2, 0, 36, company,merge_style)
			file_name = 'Employee Bonus'+str(start_month_year)

			# Headers
			header_fields = ['SR No.','Department','Name of the Employee',"Father's/Husband's Name",'Designation','Actual Rate of Wages','Gross Wages','Present days','Weekly Off','PL',"CL",'SL','Absent','Monthly Working days','Total days Paid For','Rate of Wages Actually Paid','Gross Wages earned','Rate of Overtime','Total hrs. OT Worked','Ovetime Wages','Total Wages Earned','Deductions','Total Deduction','Net Wages Paid','Signature of Employees','Bank A/c No','Remark']
			# row_index += 1
			# worksheet.write_merge(row_index, row_index, 0, 4, "Name of Comodity :", sp_style)
			worksheet.row(row_index).height = 400
			row_index += 1

			sp_updates = []
			new_index = 0
			for value in enumerate(header_fields):
				if new_index == 5 or new_index == 18:
					worksheet.write_merge(row_index,row_index,new_index,new_index+3, value[1], header_style)
					rate_wages = ['Basic','HRA']
					rate_wage_index = new_index
					for value in enumerate(rate_wages):
						worksheet.write_merge(row_index+1,row_index+1,rate_wage_index,rate_wage_index, value[1], header_style)
						rate_wage_index += 1
					new_index += 4
				elif new_index == 27:
					worksheet.write_merge(row_index,row_index,new_index,new_index+4, value[1], header_style)
					deduction = ['P.F.','ESIC','LWF','Advance','Mis. Ded.']
					deduction_index = new_index
					for value in enumerate(deduction):
						worksheet.write_merge(row_index+1,row_index+1,deduction_index,deduction_index, value[1], header_style)
						deduction_index += 1
					new_index += 5
				else:
					worksheet.write_merge(row_index,row_index+1,new_index,new_index, value[1], header_style)
					new_index += 1
					
			row_index += 2
			sn = 1
			# if contract_ids:
			employee_ids = self.env['hr.employee'].search([('id','>',0)])
			for record in employee_ids:
				attendance_ids = self.env['hr.attendance'].search([('employee_id','=',record.id),('name','>=',self.date_start),('name','<=',self.date_end)])
				len_attendance_ids = len(attendance_ids)
				attendance = len_attendance_ids / 2
				# if self.company_id.id == record.company_id.id:
				# 	invoice_date = datetime.strptime(record.date_invoice, '%Y-%m-%d').strftime('%d-%b-%y')
				overtime_hours = 0.0
				for overtime in record.overtime_ids:
					overtime_hours += overtime.number_of_hours
				
				contract_ids = self.env['hr.contract'].search([('employee_id','=',record.id)])
# 				,('date_start','>=',self.date_start),('date_end','<=',self.date_end)
				
				for contract in contract_ids:
					holiday_ids = self.env['hr.holidays'].search([('employee_id','=',record.id),('type','=','remove')])
					pl = cl = sl = ul = 0
					for holiday in holiday_ids:
						
						if holiday.holiday_status_id.name =='Compensatory Days':
							cl += holiday.number_of_days_temp
							
						if  'Legal Leaves'  in holiday.holiday_status_id.name:
							pl += holiday.number_of_days_temp
							
						if holiday.holiday_status_id.name =='Sick Leaves':
							sl += holiday.number_of_days_temp
							
						if holiday.holiday_status_id.name =='Unpaid':
							ul += holiday.number_of_days_temp
						
					# Calculation -------------------------------
					father_name = (str(record.middle_name) or '') +" "+(str(record.last_name) or '')
					gross = contract.wage + contract.house_rent_allowance_metro_nonmetro + contract.conveyance + contract.supplementary_allowance
					
					absent = days - (attendance + pl + cl + sl + ul + sundays)
					paid_days = attendance + pl + cl + sl + sundays
					basic_actual = (contract.wage / days)* paid_days
					hra_actual = (contract.house_rent_allowance_metro_nonmetro / days)* paid_days
					conveyance_actual = (contract.conveyance / days)* paid_days
					special_actual = (contract.supplementary_allowance / days)* paid_days
					wages_earned = basic_actual + hra_actual + conveyance_actual + special_actual
					ot_rate = ((contract.wage / days)/8) * 2
					ot_wages = ot_rate * overtime_hours
					total_wages = wages_earned + ot_wages
					pf = basic_actual * 0.12
					esic = total_wages * (1.75/100)
					
					deduction = pf + esic + contract.lwf + contract.advance + contract.miscellaneous_deduction
					net_wages = wages_earned - deduction
					# Calculation -------------------------------
					
					worksheet.write(row_index, 0, str(sn), base_style) # SR No.
					worksheet.write(row_index, 1, record.department_id.name, base_style) # Dept
					worksheet.write(row_index, 2, record.display_name, base_style) # Employee
					worksheet.write(row_index, 3, father_name, base_style) # Employee father_name
					worksheet.write(row_index, 4, record.job_id.name or '' , base_style) # Title
					worksheet.write(row_index, 5, contract.wage, base_style) # Basic
					worksheet.write(row_index, 6, contract.house_rent_allowance_metro_nonmetro, base_style) # HRA
					worksheet.write(row_index, 7, contract.conveyance, base_style) # conveyance
					worksheet.write(row_index, 8, contract.supplementary_allowance, base_style) # Special Allowances
					worksheet.write(row_index, 9, gross, base_style) # Gross Wages
					worksheet.write(row_index, 10, attendance, base_style) # Present days
					worksheet.write(row_index, 11, sundays, base_style) # Weekly Off
					worksheet.write(row_index, 12, pl, base_style) # PL
					worksheet.write(row_index, 13, cl, base_style) # CL
					worksheet.write(row_index, 14, sl, base_style) # SL
					worksheet.write(row_index, 15, absent, base_style) # absent
					worksheet.write(row_index, 16, days, base_style) # Monthly Working days
					worksheet.write(row_index, 17, paid_days, base_style) # Total days Paid For
					worksheet.write(row_index, 18, round(basic_actual,2), base_style) # basic_actual
					worksheet.write(row_index, 19, round(hra_actual,2), base_style) # hra_actual
					worksheet.write(row_index, 20, round(conveyance_actual,2), base_style) # conveyance_actual
					worksheet.write(row_index, 21, round(special_actual,2), base_style) # special_actual
					worksheet.write(row_index, 22, round(wages_earned,2), base_style) # Gross Wages earned
					worksheet.write(row_index, 23, round(ot_rate,2), base_style) # Rate of Overtime
					worksheet.write(row_index, 24, round(overtime_hours,2), base_style) # Total hrs. OT Worked
					worksheet.write(row_index, 25, round(ot_wages,2), base_style) # Ovetime Wages
					worksheet.write(row_index, 26, round(total_wages,2), base_style) # Total Wages Earned
					worksheet.write(row_index, 27, round(pf,2), base_style) # PF
					worksheet.write(row_index, 28, round(esic,2), base_style) # ESIC
					worksheet.write(row_index, 29, contract.lwf, base_style) # LWF
					worksheet.write(row_index, 30, contract.advance, base_style) # ADVANCE
					worksheet.write(row_index, 31, contract.miscellaneous_deduction, base_style) # Mis. Ded.
					worksheet.write(row_index, 32, round(deduction,2), base_style) # Total Deduction
					worksheet.write(row_index, 33, round(net_wages,2), base_style) # Net Wages Paid
					worksheet.write(row_index, 34, '', base_style) # Signature
					worksheet.write(row_index, 35, record.bank_account_id.sanitized_acc_number, base_style)  # Bank A/c No
					worksheet.write(row_index, 36, '', base_style) # Remark
					
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
				'res_model':'hr.employee.bonus',
			}
			doc_id = self.env['ir.attachment'].create(attach_vals)
			self.attachment_id = doc_id.id
		self.name = file_name
		self.state = 'done'
		
		return {
			'type' : 'ir.actions.act_url',
			'url': '/web/binary/download_document?model=%s&field=%s&id=%s&filename=%s.xls' % (self.attachment_id.res_model,'datas',self.id,self.attachment_id.name),
			'target': 'self',
			}
