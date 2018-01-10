from openerp import models, fields, api, tools, _
import datetime
import time
from datetime import timedelta,datetime
from zklib import zklib
from openerp.exceptions import UserError, Warning

class biometric_machine(models.Model):
	_name= 'biometric.machine'
	
	name = fields.Char(string="Machine Name")
	location = fields.Char(string="Location")
	ip_address = fields.Char(string="Machine IP",size=15)
	port = fields.Integer(string="Machine Port", size=4)
	in_machine = fields.Integer(string="Entry Machine Code")
	out_machine = fields.Integer(string="Exit Machine Code")
	
	@api.model
	def download_schedular(self):
		###--- Uncomment on final build ---###
		machine = self.search([('ip_address','not in',['',False])])
		if machine:
			machine.download_attendance()
		return True
	
	@api.multi
	def download_attendance(self):
		date_yesterday = datetime.today().date() - timedelta(days=+1)
		# date_yesterday = datetime.datetime.strptime('2016-02-02','%Y-%m-%d').date()
		if self.ip_address and self.port:
			in_machine = self.in_machine or 0
			out_machine = self.out_machine or 0
			# Uncomment after completion
			zk = zklib.ZKLib(self.ip_address, int(self.port))
			res = zk.connect()
			print "kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk", date_yesterday , zk
			
			# res = True # To be removed
			if res == True:
				zk.enableDevice()
				zk.disableDevice()
				attendance = zk.getAttendance()
				print "hhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh", attendance
				time.sleep(2)
				
				zk.enableDevice()
				zk.disconnect()
				# print "####################",attendance
				# if (attendance):
				# 	self.env["hr.employee"].emp_attendance_fetcher(attendance, date_yesterday, in_machine, out_machine)
				for lattendance in attendance:
					print "GGGGGGGGGGGGGGG lattendance " , lattendance
					time_att = str(lattendance[2].date()) + ' ' +str(lattendance[2].time())
					atten_time1 = datetime.strptime(str(time_att), '%Y-%m-%d %H:%M:%S')
					atten_time = atten_time1 - timedelta(hours=5,minutes=30)
					atten_time = datetime.strftime(atten_time,'%Y-%m-%d %H:%M:%S')
					atten_time1 = datetime.strftime(atten_time1,'%Y-%m-%d %H:%M:%S')
					in_time = datetime.strptime(atten_time1,'%Y-%m-%d %H:%M:%S').time()
					employee_id = self.env["hr.employee"].search([("emp_code", "=", str(lattendance[0]))])
					address_id = False
					category = False
					if employee_id:
					    address_id = self.env["hr.employee"].browse(employee_id[0].id).address_id
					    # category = self.env["hr.employee"].browse(employee_id[0].id).category
					
					try:
					    hr_attendance =  self.env["hr.all.attendance"]
					    atten_ids = hr_attendance.search([('employee_id','=',employee_id[0].id),('name','=',atten_time)])
					    print "pppppppppppppppppppppppppppppppppppppppp", atten_ids
					    if atten_ids:
					        continue
					    else:
					        # print "Date %s, Name %s: %s" % ( lattendance[2].date(), lattendance[2].time(), lattendance[0] )
					        atten_id = hr_attendance.create({'name':atten_time,'address_id':address_id.id,'day':str(lattendance[2].date()),'employee_id':employee_id[0].id})
					        # print atten_id
					except Exception,e:
					    pass
					    # print "Exception..Attendance creation======", e.args
				return True
			else:
				raise Warning(_("Unable to connect, please check the Biometrics Machine parameters and network connections."))
			# raise UserError(_('Warning !'),_("Unable to connect, please check the Biometrics Machine parameters and network connections."))
	
	def clear_attendance(self, cr, uid, ids, context=None):
		# machine_ip = self.browse(cr,uid,ids).name
		# port = self.browse(cr,uid,ids).port
		# zk = zklib.ZKLib(machine_ip, int(port))
		# res = zk.connect()
		# if res == True:
		#     zk.enableDevice()
		#     zk.disableDevice()
		#     res = zk.clearAttendance()
		#     print res
		#     zk.enableDevice()
		#     zk.disconnect()
		#     return True
		# else:
		#     raise osv.except_osv(_('Warning !'),_("Unable to connect, please check the parameters and network connections."))
		return True