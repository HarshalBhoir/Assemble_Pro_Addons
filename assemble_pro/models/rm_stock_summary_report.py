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

class rm_stock_summary_report(models.TransientModel):
    _name = 'rm.stock.summary.report'
    _description = "RM Stock Summary Report"
    
    @api.model
    def _get_default_location(self):
        location = self.env.ref('stock.stock_location_stock')
        return self.env['stock.location'].browse(location.id)

    
    name = fields.Char(string="RMStockSummaryReport", compute="_get_name")
    date_from = fields.Date(string="Date From", default=lambda self: fields.datetime.now())
    date_to = fields.Date(string="Date To", default=lambda self: fields.datetime.now())
    company_id = fields.Many2one('res.company', string="Company", ondelete='cascade', default=lambda self: self.env['res.company']._company_default_get('rm.stock.summary.report'))
    location_id = fields.Many2one('stock.location', string="Location", ondelete='cascade', default=_get_default_location)
    attachment_id = fields.Many2one('ir.attachment', string="Attachment", ondelete='cascade')
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
        rep_name = "RM_Stock_Summary_Report"
        if self.date_from and self.date_to:
            date_from = datetime.datetime.strptime(self.date_from, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
            date_to = datetime.datetime.strptime(self.date_to, tools.DEFAULT_SERVER_DATE_FORMAT).strftime('%d-%b-%Y')
            if self.date_from == self.date_to:
                rep_name = "Stock Summary Report(%s) - %s" % (date_from,self.location_id.name)
            else:
                rep_name = "Stock Summary Report(%s|%s) - %s" % (date_from, date_to,self.location_id.name)
        self.name = rep_name

    @api.multi
    def print_report(self):
        if self.date_from and self.date_to:
            if not self.attachment_id:
                quant_list = []
                file_name = self.name
                workbook = xlwt.Workbook()
                worksheet = workbook.add_sheet('Sheet 1')
                
                main_style = xlwt.easyxf('font: bold on, height 400; align: wrap 1, vert centre, horiz center; borders: bottom thick, top thick, left thick, right thick')
                sp_style = xlwt.easyxf('font: bold on, height 350;')
                header_style = xlwt.easyxf('font: bold on, height 220; align: wrap 1,  horiz center; borders: bottom thin, top thin, left thin, right thin')
                base_style = xlwt.easyxf('align: wrap 1; borders: bottom thin, top thin, left thin, right thin')
                
                worksheet.write_merge(0, 1, 0, 10, file_name, main_style)
                row_index = 2
                
                worksheet.col(0).width = 4000
                worksheet.col(1).width = 4000
                worksheet.col(2).width = 10000
                worksheet.col(3).width = 8000
                worksheet.col(4).width = 7000
                worksheet.col(5).width = 4000
                worksheet.col(6).width = 4000
                worksheet.col(7).width = 4000
                worksheet.col(8).width = 4000
                worksheet.col(9).width = 4000
                worksheet.col(10).width = 4000
                worksheet.col(11).width = 6000
                worksheet.col(12).width = 6000
                
                # Headers
                header_fields = ['Code','HSN','Particulars','Tax Slab','Rack Shelf No.','PO','Receipts','Issues','Rej Qty','Closing Bal','Rate PerUnit','Closing Value','Company']
                row_index += 1
                
                for index, value in enumerate(header_fields):
                    worksheet.write(row_index, index, value, header_style)
                row_index += 1
                
                product_ids = self.env['product.product'].search([])
                location = self.env.ref('stock.stock_location_stock')
                wip_location = self.env['stock.location'].search([('name','ilike','wip')])
                finished_location = self.env['stock.location'].search([('name','ilike','finished')])
                rej_location = self.env['stock.location'].search([('name','ilike','rejection')])
                
                
                quant_ids = self.env['stock.quant'].sudo().search([('company_id','=',1),('location_id','=',self.location_id.id)],order="product_id desc")
                for quant_id in quant_ids:
                    in_date = datetime.datetime.strptime(quant_id.in_date, tools.DEFAULT_SERVER_DATETIME_FORMAT).date().strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
                    if in_date <= self.date_to:
                        quant_list.append(quant_id)
                
                if (not quant_list): # not quant_ids
                    raise Warning(_('Record Not Found'))
                
                po_name = ''
                purchase_qty = issue_qty = rej_qty = 0
                if quant_list:
                    for rec in quant_list:
                        if self.company_id.id == rec.product_id.company_id.id:
                            for record_quants in rec:
                                for record_purchase in record_quants.history_ids:
                                    
                                    if (record_purchase.picking_type_id.code == 'incoming') \
                                    and ((record_purchase.origin) and ('PO' in record_purchase.origin)) \
                                    and (rec.product_id.id == record_purchase.product_id.id):
                                        purchase_qty = record_purchase.product_uom_qty
                                        po_name = record_purchase.origin
                                    else:
                                        purchase_qty = 0
                                        po_name = ''
                                        
                                        
                            issue_ids = self.env['stock.move'].search([('product_id','=',rec.product_id.id),('location_id','=',self.location_id.id),('location_dest_id','=',wip_location.id),('state','=','done'),('date','<=',self.date_to)])
    
                            if issue_ids:
                                for record_issue in issue_ids:
                                    if record_issue.quant_ids and (record_issue.quant_ids[0].lot_id.id == rec.lot_id.id):
                                        issue_qty = record_issue.product_uom_qty
                                    else:
                                        issue_qty = 0
                                        
                            rej_ids = self.env['stock.move'].search([('product_id','=',rec.product_id.id),('location_id','=',self.location_id.id),('location_dest_id','=',rej_location.id),('state','=','done'),('date','<=',self.date_to)])
    
                            if rej_ids:
                                for record_rej in rej_ids:
                                    if record_rej.quant_ids.lot_id.id == rec.lot_id.id:
                                        rej_qty = record_rej.product_uom_qty
                                    else:
                                        rej_qty = 0
                            
                            per_unit = (rec.inventory_value/rec.qty)
                            worksheet.write(row_index, 0,rec.product_id.default_code or '', base_style)
                            worksheet.write(row_index, 1,rec.product_id.hsn_code or '', base_style)
                            worksheet.write(row_index, 2,rec.product_id.name, base_style)
                            worksheet.write(row_index, 3,', '.join(map(lambda x: x.description, rec.product_id.taxes_id)) or '', base_style)
                            worksheet.write(row_index, 4,rec.lot_id.name or '', base_style)
                            worksheet.write(row_index, 5,po_name or '',base_style)
                            worksheet.write(row_index, 6,purchase_qty or 0, base_style) #issue_lines if issue_lines else 0
                            worksheet.write(row_index, 7,issue_qty or 0, base_style)
                            worksheet.write(row_index, 8,rej_qty or 0, base_style)
                            worksheet.write(row_index, 9,rec.qty or 0, base_style)
                            worksheet.write(row_index, 10,per_unit or 0, base_style)
                            worksheet.write(row_index, 11,rec.inventory_value or 0, base_style)
                            worksheet.write(row_index, 12,rec.product_id.company_id.name or '', base_style)
                            
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
                    'res_model':'rm.stock.summary.report',
                }
                doc_id = self.env['ir.attachment'].create(attach_vals)
                self.attachment_id = doc_id.id
            return {
                'type' : 'ir.actions.act_url',
                'url': '/web/binary/download_document?model=%s&field=%s&id=%s&filename=%s.xls' % (self.attachment_id.res_model,'datas',self.id,self.attachment_id.name),
                'target': 'self',
                }