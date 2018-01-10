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

class issue_note_register_report(models.TransientModel):
    _name = 'issue.note.register.report'
    _description = "Issue Note Register Report"
    
    name = fields.Char(string="IssueNoteRegisterReport", compute="_get_name")
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
        rep_name = "Issue_Note_Register_Report"
        if self.date_from and self.date_to:
            date_from = datetime.datetime.strptime(self.date_from, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
            date_to = datetime.datetime.strptime(self.date_to, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
            if self.date_from == self.date_to:
                rep_name = "Issue Note Register Report(%s)" % (date_from,)
            else:
                rep_name = "Issue Note Register Report(%s|%s)" % (date_from, date_to)
        self.name = rep_name

    @api.multi
    def print_report(self):
        if self.date_from and self.date_to:
            if not self.attachment_id:
                stock_list = []
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
                
                worksheet.write_merge(0, 1, 0, 4, file_name, main_style)
                row_index = 2
                
                worksheet.col(0).width = 8000
                worksheet.col(1).width = 8000
                worksheet.col(2).width = 4000
                worksheet.col(3).width = 4000
                worksheet.col(4).width = 12000
                worksheet.col(5).width = 4000
      
                # Headers
                header_fields = ['Date','Doc No.','Order No.','HSN','Particulars','Qty']
                row_index += 1
                
                # https://github.com/python-excel/xlwt/blob/master/xlwt/Style.py
                
                for index, value in enumerate(header_fields):
                    worksheet.write(row_index, index, value, header_style)
                row_index += 1

                stock_ids = self.env['stock.picking'].sudo().search([('state','=','done'),('picking_type_code','=','internal')])

                for stock_id in stock_ids:
                    if stock_id.date_done:
                        date_done = datetime.datetime.strptime(stock_id.date_done, tools.DEFAULT_SERVER_DATETIME_FORMAT).date().strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
                        if date_done >= self.date_from and date_done <= self.date_to:
                            stock_list.append(stock_id)
                
                if not stock_list: # not stock_list
                    raise Warning(_('Record Not Found'))
                
                for picking_id in stock_list:
                    worksheet.write(row_index, 0,picking_id.date_done or '', base_style)
                    worksheet.write(row_index, 1,picking_id.name, base_style)
                    worksheet.write(row_index, 2,'', base_style)
                    worksheet.write(row_index, 3,'', base_style)
                    worksheet.write(row_index, 4,picking_id.location_dest_id.name, base_style)
                    worksheet.write(row_index, 5,'', base_style)
                    row_index += 1
                    for res in picking_id.pack_operation_product_ids:
                        worksheet.write(row_index, 0,'', base_style_yellow)
                        worksheet.write(row_index, 1,'', base_style_yellow)
                        worksheet.write(row_index, 2,'', base_style_yellow)
                        worksheet.write(row_index, 3,res.product_id.hsn_code or '', base_style_yellow)
                        worksheet.write(row_index, 4,res.product_id.name, base_style_yellow)
                        worksheet.write(row_index, 5,res.qty_done, base_style_yellow)    
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
                    'res_model':'issue.note.register.report',
                }
                doc_id = self.env['ir.attachment'].create(attach_vals)
                self.attachment_id = doc_id.id
            return {
                'type' : 'ir.actions.act_url',
                'url': '/web/binary/download_document?model=%s&field=%s&id=%s&filename=%s.xls' % (self.attachment_id.res_model,'datas',self.id,self.attachment_id.name),
                'target': 'self',
                }