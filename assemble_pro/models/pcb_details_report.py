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

class pcb_details_report(models.TransientModel):
    _name = 'pcb.details.report'
    _description = "PCB Details Report"
    
    name = fields.Char(string="PCBDetailsReport", compute="_get_name")
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
        rep_name = "PCB_Details_Report"
        if self.date_from and self.date_to:
            date_from = datetime.datetime.strptime(self.date_from, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
            date_to = datetime.datetime.strptime(self.date_to, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
            if self.date_from == self.date_to:
                rep_name = "PCB Details Report(%s)" % (date_from,)
            else:
                rep_name = "PCB Details Report(%s|%s)" % (date_from, date_to)
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
                
                worksheet.write_merge(0, 1, 0, 8, file_name, main_style)
                row_index = 2
                
                worksheet.col(0).width = 4000
                worksheet.col(1).width = 8000
                worksheet.col(2).width = 8000
                worksheet.col(3).width = 8000
                worksheet.col(4).width = 12000
                worksheet.col(5).width = 8000
                worksheet.col(6).width = 8000
                worksheet.col(7).width = 8000
                worksheet.col(8).width = 8000
                worksheet.col(9).width = 12000
                worksheet.col(10).width = 8000
                
                # Headers
                header_fields = ['Date','Contract No','FG Code','FG HSN','FG Desc','FG Serial No','FG Lot No.','PCB Code','PCB HSN','PCB Desc','PCB Serial No']
                row_index += 1
                
                # https://github.com/python-excel/xlwt/blob/master/xlwt/Style.py
                
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
                            count = 0
                            new_index = row_index
                            for line in order_id.picking_ids[0].pack_operation_product_ids:
                                # if line.product_id.pcb_material:#
                                for pack_lot_id in line.pack_lot_ids:
                                    for result in pack_lot_id.lot_id.stock_lot_line_ids:
                                        if result.product_id.pcb_material:
                                            count +=1
                                            worksheet.write(row_index, 0,po_date, base_style)
                                            worksheet.write(row_index, 2,line.product_id.default_code or '', base_style)
                                            worksheet.write(row_index, 3,line.product_id.hsn_code or '', base_style)
                                            worksheet.write(row_index, 4,line.product_id.name, base_style)
                                            worksheet.write(row_index, 5,line.barcode_list or '', base_style)
                                            worksheet.write(row_index, 6,pack_lot_id.lot_id.name or '', base_style)
                                            worksheet.write(row_index, 7,result.product_id.default_code or '', base_style)
                                            worksheet.write(row_index, 8,result.product_id.hsn_code or '', base_style)
                                            worksheet.write(row_index, 9,result.product_id.name, base_style)
                                            worksheet.write(row_index, 10,result.lot_id.name or '', base_style)
                                            row_index += 1

                            if count != 0:
                                worksheet.write_merge(new_index, new_index+count-1, 1, 1, order_id.name.strip(), base_style)
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
                    'res_model':'pcb.details.report',
                }
                doc_id = self.env['ir.attachment'].create(attach_vals)
                self.attachment_id = doc_id.id
            return {
                'type' : 'ir.actions.act_url',
                'url': '/web/binary/download_document?model=%s&field=%s&id=%s&filename=%s.xls' % (self.attachment_id.res_model,'datas',self.id,self.attachment_id.name),
                'target': 'self',
                }