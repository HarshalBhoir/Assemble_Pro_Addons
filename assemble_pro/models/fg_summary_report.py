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
    
class fg_summary_report(models.TransientModel):
    _name = 'fg.summary.report'
    _description = "FG Batch Summary Report"
    
    name = fields.Char(string="FGSummaryReport", compute="_get_name")
    # date_from = fields.Date(string="Date From", default=lambda self: fields.datetime.now())
    # date_to = fields.Date(string="Date To", default=lambda self: fields.datetime.now())
    attachment_id = fields.Many2one( 'ir.attachment', string="Attachment", ondelete='cascade')
    datas = fields.Binary(string="XLS Report", related="attachment_id.datas")
    
    # @api.constrains('date_from','date_to')
    # @api.depends('date_from','date_to')
    # def date_range_check(self):
    #     if self.date_from and self.date_to and self.date_from > self.date_to:
    #         raise ValidationError(_("Start Date should be before or be the same as End Date."))
    #     return True
    
    # @api.depends('date_from','date_to')
    @api.multi
    def _get_name(self):
        rep_name = "FG_Batch_Summary_Report"
        # if self.date_from and self.date_to:
            # date_from = datetime.datetime.strptime(self.date_from, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
            # date_to = datetime.datetime.strptime(self.date_to, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
            # if self.date_from == self.date_to:
            # 	rep_name = "Packing List Export Report(%s)" % (date_from,)
            # else:
        rep_name = "FG Batch Summary Report"
        self.name = rep_name

    @api.multi
    def print_report(self):
        # if self.date_from and self.date_to:
        if not self.attachment_id:
            quant_ids = []
            file_name = self.name
            # Created Excel Workbook and Sheet
            workbook = xlwt.Workbook()
            worksheet = workbook.add_sheet('Sheet 1')
            
            main_style = xlwt.easyxf('font: bold on, height 400; align: wrap 1, vert centre, horiz center; borders: bottom thick, top thick, left thick, right thick')
            sp_style = xlwt.easyxf('font: bold on, height 350;')
            header_style = xlwt.easyxf('font: bold on, height 220; align: wrap 1,  horiz center; borders: bottom thin, top thin, left thin, right thin')
            base_style = xlwt.easyxf('align: wrap 1; borders: bottom thin, top thin, left thin, right thin')
            
            worksheet.write_merge(0, 1, 0, 3, file_name, main_style)
            row_index = 2
            
            worksheet.col(0).width = 4000
            worksheet.col(1).width = 4000
            worksheet.col(2).width = 16000
            worksheet.col(3).width = 6000
            
            # Headers
            header_fields = ['Code','HSN','Particulars','QtyInStock']
            row_index += 1
            
            for index, value in enumerate(header_fields):
                worksheet.write(row_index, index, value, header_style)
            row_index += 1
            finished_location = self.env['stock.location'].search([('name','ilike','finished')])
            if finished_location:
                quant_ids = self.env['stock.quant'].sudo().search([('location_id','=',finished_location[0].id)])
            
            if (not quant_ids): # not quant_ids
                raise Warning(_('Record Not Found'))
            
            product_ids = self.env['product.product'].sudo().search([])
            for prod in product_ids:
                inventory_qty = 0
                if quant_ids:
                    for quant_id in quant_ids:
                        if prod.id == quant_id.product_id.id:
                            inventory_qty += quant_id.qty
                if inventory_qty > 0:
                    worksheet.write(row_index, 0,prod.default_code or '', base_style)
                    worksheet.write(row_index, 1,prod.hsn_code or '', base_style)  
                    worksheet.write(row_index, 2,prod.name, base_style)  
                    worksheet.write(row_index, 3,inventory_qty, base_style)
           
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
                'res_model':'fg.summary.report',
            }
            doc_id = self.env['ir.attachment'].create(attach_vals)
            self.attachment_id = doc_id.id
        return {
            'type' : 'ir.actions.act_url',
            'url': '/web/binary/download_document?model=%s&field=%s&id=%s&filename=%s.xls' % (self.attachment_id.res_model,'datas',self.id,self.attachment_id.name),
            'target': 'self',
            }
                