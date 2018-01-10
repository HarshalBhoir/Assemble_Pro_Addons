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

class rm_serial_search_report(models.TransientModel):
    _name = 'rm.serial.search.report'
    _description = "RM Serial Search Report"
    
    name = fields.Char(string="RMSerialSearchReport", compute="_get_name")
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
        rep_name = "RM_Serial_Search_Report"
        if self.date_from and self.date_to:
            date_from = datetime.datetime.strptime(self.date_from, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
            date_to = datetime.datetime.strptime(self.date_to, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
            if self.date_from == self.date_to:
                rep_name = "RM Serial Search Report(%s)" % (date_from,)
            else:
                rep_name = "RM Serial Search Report(%s|%s)" % (date_from, date_to)
        self.name = rep_name

    @api.multi
    def print_report(self):
        if self.date_from and self.date_to:
            if not self.attachment_id:
                pending_order_ids = []
                stock_list = []
                internal_stock_list = []
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
                
                worksheet.write_merge(0, 1, 0, 6, file_name, main_style)
                row_index = 2
                
                worksheet.col(0).width = 8000
                worksheet.col(1).width = 8000
                worksheet.col(2).width = 14000
                worksheet.col(3).width = 8000
                worksheet.col(4).width = 8000
                worksheet.col(5).width = 8000
                worksheet.col(6).width = 8000
                worksheet.col(7).width = 8000
                worksheet.col(8).width = 8000
                
                
                # Headers
                header_fields = ['Item Code','HSN','Product Name','Tax Slab','Product Serial No.','GRN No','GRN Date','Issue No','Issue Date']
                row_index += 1
                
                # https://github.com/python-excel/xlwt/blob/master/xlwt/Style.py
                
                for index, value in enumerate(header_fields):
                    worksheet.write(row_index, index, value, header_style)
                row_index += 1
                
                stock_ids = self.env['stock.picking'].sudo().search([('picking_type_code','=','incoming')])
                internal_stock_ids = self.env['stock.picking'].sudo().search([('picking_type_code','=','internal')])
                
                for stock_id in stock_ids:
                    if stock_id.date_done:
                        date_done = datetime.datetime.strptime(stock_id.date_done, tools.DEFAULT_SERVER_DATETIME_FORMAT).date().strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
                        if date_done >= self.date_from and date_done <= self.date_to:
                            for operation_id in stock_id.pack_operation_product_ids:
                                stock_list.append(operation_id)
                
                for internal_stock_id in internal_stock_ids:
                    for operation_id in internal_stock_id.pack_operation_product_ids:
                        internal_stock_list.append(operation_id)
                
                count = 0
                for picking_id in stock_list:
                    for lot_id in picking_id.pack_lot_ids:   
                        for internal_picking_id in internal_stock_list:
                            for internal_lot_id in internal_picking_id.pack_lot_ids:
                                if lot_id.lot_id == internal_lot_id.lot_id:
                                    worksheet.write(row_index, 0,picking_id.product_id.default_code, base_style)
                                    worksheet.write(row_index, 1,picking_id.product_id.hsn_code or '', base_style)
                                    worksheet.write(row_index, 2,picking_id.product_id.name or '', base_style)
                                    worksheet.write(row_index, 3,', '.join(map(lambda x: x.description, picking_id.product_id.taxes_id)) or '', base_style)
                                    worksheet.write(row_index, 4,lot_id.lot_id.name or '', base_style)
                                    worksheet.write(row_index, 5,picking_id.picking_id.name, base_style)
                                    worksheet.write(row_index, 6,picking_id.picking_id.date_done or '', base_style)
                                    worksheet.write(row_index, 7,internal_picking_id.picking_id.name or '', base_style)
                                    worksheet.write(row_index, 8,internal_picking_id.picking_id.date_done or '', base_style)
                                    row_index += 1
                                    count += 1
                
                if count == 0: # not order_ids
                    raise Warning(_('Record Not Found'))
                
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
                    'res_model':'rm.serial.search.report',
                }
                doc_id = self.env['ir.attachment'].create(attach_vals)
                self.attachment_id = doc_id.id
            return {
                'type' : 'ir.actions.act_url',
                'url': '/web/binary/download_document?model=%s&field=%s&id=%s&filename=%s.xls' % (self.attachment_id.res_model,'datas',self.id,self.attachment_id.name),
                'target': 'self',
                }