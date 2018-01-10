from openerp.exceptions import UserError, MissingError, ValidationError
import csv
import base64
import decimal
import openerp
from datetime import datetime, timedelta, date
from openerp import models, fields, api, _, tools
from openerp.exceptions import UserError
from openerp.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT
from dateutil.relativedelta import relativedelta
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


def get_date(freq, date):
    
    rec_date = datetime.strptime(date, tools.DEFAULT_SERVER_DATE_FORMAT)
    print " dDDDDDDDDDDDDDDDDDDDD", date , freq , rec_date 
    if freq == 'monthly':
        print "AAAAAAAAAAAAAAAAAAAAAAAAAAA monthly" , rec_date ,relativedelta(months=1)
        return rec_date + relativedelta(months=1)
        
    elif freq == 'quarterly':
        return rec_date + relativedelta(months=3)
    elif freq == 'half_yearly':
        return rec_date + relativedelta(months=6)
    elif freq == 'annually':
        return (rec_date - relativedelta(years=1)) + relativedelta(years=1) #- relativedelta(years=1)
    
class legal_compliance(models.Model):
    _name = "legal.compliance"
    
    _description = "Legal Compliance"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    
    name = fields.Char(string = "Compliance Details.")
    acts = fields.Char(string = "Acts")
    form_no = fields.Char(string = "Form No.")
    date_due = fields.Date(string="Due date for Compliance")
    date = fields.Date(string="Date of Completion")
    schedule_period = fields.Selection([
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('twice_year', 'Twice in Year'),
            ('half_yearly', 'Half Yearly'),
            ('annually', 'Annually'),
            ('as&when', 'As & When'),
            ], 'Periodicity', select=True)
    user_id = fields.Many2one('res.users', string='User', track_visibility='always')
    prepare_user_id = fields.Many2one('res.users', string='Challan/Return prepared by', track_visibility='always')
    performed_user_id = fields.Many2one('res.users', string='Task (Deposite Challan)Performed by', track_visibility='always')
    note = fields.Text(string="Remark if Any")
    notify_day = fields.Integer(string = "Reminder to be received before:")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
        ], string='Status', readonly=True,
        copy=False, index=True, track_visibility='always', default='draft')
    due_date = fields.Date(string="Date for Compliance")              
    
                    
    @api.model
    @api.multi
    def send_mail(self):
        legal_compliance_ids = self.search([])
        template = False
        try:
            template = self.env['ir.model.data'].get_object('assemble_pro', 'legal_compliance_template')
        except ValueError:
            pass
        
        ##### ---=== Email Recepients ===--- #####
        email_list = []
        
        manager_group = self.env['ir.model.data'].get_object('assemble_pro', 'group_assemble_pro_manager')
        if manager_group and manager_group.users:
            for user in manager_group.users:
                email_list.append(user.email)
        else:
            raise UserError("Assemble Manager not Defined!")
        
        emails = ",".join([str(x) for x in email_list])
        # emails.append(performed_user_id)
        
        if template:
            template.email_to = emails
        record = False
        for rec in self.search([]) :
            if rec.due_date and rec.schedule_period:
                print "RRRRRRRRRRRRRRRRRRRRRRRRRR", rec, rec.schedule_period
                date_notify = get_date(rec.schedule_period, rec.due_date) - timedelta(days=rec.notify_day)
                date_compliance = get_date(rec.schedule_period, rec.due_date)
                print "DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD", date_notify, datetime.now()
                print "JJJJJJJJJJJJJJJJJJJJJJJJ" , date_notify.date() , date.today()
                if date_notify.date() == date.today():
                    print "PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP", rec.performed_user_id.email
                    if rec.performed_user_id.email :
                        print "LLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL"
                        template.email_to = emails + "," + rec.performed_user_id.email
                        mail_values = template.generate_email(rec.id)
                        mail_values['email_from'] = rec.prepare_user_id.email
                        print "TTTTTTTTTTTTTTTTTTTTTT"
                        mail_obj = self.env['mail.mail'].create(mail_values)
                        print "Mail sentt================"
                        mail = mail_obj.send()
                        print "SSSSSSSSSSSSSSSS" , mail , rec.due_date , date_notify , date_compliance
                        if rec.schedule_period == 'annually' and mail:
                            rec.write({'due_date': (date_compliance + relativedelta(years=1))})
                            print "ATA tari ho KKKKKKKKKKKKKKKKKKKKKKKKKKKKK" , rec.due_date 




            # date_notify = get_date(record.frequency, record.date)
            # if date_notify < datetime.now():
            #         template_id = self.env['ir.model.data'].get_object_reference('assemble_pro','legal_compliance_template')[1]
            #         email_template_obj = self.env['mail.template'].browse(template_id)
            #         if template_id:
            #             values = email_template_obj.generate_email(rec.id, fields=None)
            #             for user in users:
            #                 if user.has_group('it_process.it_process_it_technician') and not user.has_group('it_process.it_process_vpit'):
            #                     tech_user.append(user)
            #             tech_partners = [x.partner_id.email for x in tech_user]
            #             values['email_from'] = legal_compliance_id.prepare_user_id.email
            #             values['email_to'] = tech_partners
            #             values['res_id'] = False
            #             mail_mail_obj = self.env['mail.mail']
            #             msg_id = mail_mail_obj.create(values)
            #             if msg_id:
            #                 mail_mail_obj.send([msg_id])







    