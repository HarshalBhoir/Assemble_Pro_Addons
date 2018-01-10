# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
from datetime import datetime
from datetime import timedelta
from dateutil import relativedelta
from openerp.tools.translate import _
from openerp.exceptions import UserError
from openerp import fields, models, exceptions, api,tools, _
import base64
import csv
import cStringIO


class hr_all_attendance(models.Model):
    _name = "hr.all.attendance"
    _description = "Attendance"
    _order = 'name desc'

    def _employee_get(self):
        ids = self.env['hr.employee'].search([('user_id', '=', self._uid)])
        return ids and ids[0] or False
    
    name = fields.Datetime('Date', required=True, select=1, default=lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'))
    
    employee_id = fields.Many2one('hr.employee', "Employee", required=True, select=True, default=_employee_get)
    department_id = fields.Many2one('hr.department', "Department", related="employee_id.department_id")
    status = fields.Char('Status')
    duration = fields.Char('Duration')
    overtime = fields.Float('Overtime')
    # action = fields.Selection([('sign_in', 'Sign In'), ('sign_out', 'Sign Out'), ('action','Action')], 'Action', required=True)
    # action_desc = fields.Many2one("hr.action.reason", "Action Reason", domain="[('action_type', '=', action)]", help='Specifies the reason for Signing In/Signing Out in case of extra hours.')
    # worked_hours = fields.function(_worked_hours_compute, type='float', string='Worked Hours', store=True)
    
    # def _altern_si_so(self, cr, uid, ids, context=None):
    #     """ Alternance sign_in/sign_out check.
    #         Previous (if exists) must be of opposite action.
    #         Next (if exists) must be of opposite action.
    #     """
    #     for att in self.browse(cr, uid, ids, context=context):
    #         # search and browse for first previous and first next records
    #         prev_att_ids = self.search(cr, uid, [('employee_id', '=', att.employee_id.id), ('name', '<', att.name), ('action', 'in', ('sign_in', 'sign_out'))], limit=1, order='name DESC')
    #         next_add_ids = self.search(cr, uid, [('employee_id', '=', att.employee_id.id), ('name', '>', att.name), ('action', 'in', ('sign_in', 'sign_out'))], limit=1, order='name ASC')
    #         prev_atts = self.browse(cr, uid, prev_att_ids, context=context)
    #         next_atts = self.browse(cr, uid, next_add_ids, context=context)
    #         # check for alternance, return False if at least one condition is not satisfied
    #         if prev_atts and prev_atts[0].action == att.action: # previous exists and is same action
    #             return False
    #         if next_atts and next_atts[0].action == att.action: # next exists and is same action
    #             return False
    #         if (not prev_atts) and (not next_atts) and att.action != 'sign_in': # first attendance must be sign_in
    #             return False
    #     return True
    # 
    # _constraints = [(_altern_si_so, 'Error ! Sign in (resp. Sign out) must follow Sign out (resp. Sign in)', ['action'])]
    
    
    
    
    
class attendance_import(models.Model):
    _name = "attendance.import"
    _description = "Import Attendance"
    _inherit = ['mail.thread']
    _order = 'create_date desc'
    
    
    name = fields.Char('Name',size=120)
    file_name = fields.Char('File Name',size=120)
    import_file = fields.Binary(string="Import File" ,attachment=True , required=True)
    import_csv = fields.Boolean(String="Import Trough CSV File")
    delimeter = fields.Char('Delimeter', default=',',
                            help='Default delimeter is ","')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Imported'),
        ('cancel', 'Cancelled'),
        ], string='Status', readonly=True,
        copy=False, index=True, track_visibility='always', default='draft')
    
    
    @api.multi
    def action_import(self):
        """Load Attendance data from the CSV file."""
        ctx = self.env.context
        att_imp_obj = self.env['attendance.import']
        hr_all_obj = self.env['hr.all.attendance']
        employee_obj = self.env['hr.employee']
        att_imp = att_imp_obj
        if 'active_id' in ctx:
            att_imp = att_imp_obj.browse(ctx['active_id'])
        # Decode the file data
        data = base64.b64decode(self.import_file)
        file_input = cStringIO.StringIO(data)
        file_input.seek(0)
        # location = self.location
        reader_info = []
        if self.delimeter:
            delimeter = str(self.delimeter)
        else:
            delimeter = ','
        reader = csv.reader(file_input, delimiter=delimeter,
                            lineterminator='\r\n')
        try:
            reader_info.extend(reader)
        except Exception:
            raise exceptions.Warning(_("Not a valid file!"))
        keys = reader_info[0]
        # check if keys exist
        if not isinstance(keys, list) or ('Date' not in keys or
                                          'Employee Code' not in keys or
                                          'In Time' not in keys or
                                          'Out Time' not in keys or
                                          'Status' not in keys or
                                          'TotalDuration' not in keys or
                                          'Overtime' not in keys):
            raise exceptions.Warning(
                _("Not 'Date' or 'Employee Code' or 'In Time' or 'Out Time' or 'Status' keys found"))
        del reader_info[0]
        values = {}
        for i in range(len(reader_info)):
            val = {}
            field = reader_info[i]
            values = dict(zip(keys, field))
           
            if (('Absent' or 'On WeeklyOff')  in values['Status']):
                pass
            else:
                empl_lst = employee_obj.search([('emp_code', '=',values['Employee Code'])])
                if empl_lst:
                    val['employee_id'] = empl_lst[0].id
                    val['duration'] = values['TotalDuration']
                    val['overtime'] = values['Overtime']
                    val['status'] = values['Status']
                    date_string = values['Date'] #30-Apr-2017
                    if values['In Time'] !='00:00':
                        time_string = values['In Time'] #30-Apr-2017
                        time_string1 = time_string.split(':')
                        if len(time_string1) > 2:
                            a=  datetime.combine(datetime.strptime(date_string, "%d-%b-%Y") ,datetime.strptime(time_string,"%H:%M:%S").time()) 
        
                            b= a -  timedelta(hours=5) - timedelta(minutes=30)
                            b_str = str(b)
                            val['name'] = b
                            
                            hr = hr_all_obj.search([])
                            if b_str not in [x.name for x in hr]:
                                hr_all_obj.create(val)
                            
                    if values['Out Time'] !='00:00':
                        time_string = values['Out Time'] #30-Apr-2017
                        time_string1 = time_string.split(':')
                        if len(time_string1) > 2:
                            c=  datetime.combine(datetime.strptime(date_string, "%d-%b-%Y") ,datetime.strptime(time_string,"%H:%M:%S").time()) 
        
                            d= c -  timedelta(hours=5) - timedelta(minutes=30)
                            d_str = str(b)
                            val['name'] = d
                            if d_str not in [x.name for x in hr]:
                                hr_all_obj.create(val)
                                self.state = 'done'
                            # hr_all_obj.create(val)
