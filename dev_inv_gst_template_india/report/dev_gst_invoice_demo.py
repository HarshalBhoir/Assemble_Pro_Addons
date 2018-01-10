# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd. (<http://devintellecs.com>).
#
##############################################################################
from openerp.osv import  osv
from openerp.report import report_sxw
from openerp.tools import amount_to_text_en
from openerp import models,api

class dev_gst_invoice_rep(report_sxw.rml_parse): 
    def __init__(self, cr, uid, name, context):
        super(dev_gst_invoice_rep, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'convert' : self.convert,          
        }) 
    def convert(self, amount, obj):
        cur = obj
        var =  amount_to_text_en.amount_to_text(amount, 'en', cur).replace(cur, "")
        return var
    
    def total_amount_in_words(self):
        return self.amount_total and  amount_to_text_en.amount_to_text_in(self.amount_total, 'Rupees') or ""
    

class print_gst_invoice(osv.AbstractModel):
    _name = 'report.dev_inv_gst_template_india.gst_invoice_template' 
    _inherit = 'report.abstract_report'
    _template = 'dev_inv_gst_template_india.gst_invoice_template'
    _wrapped_report_class = dev_gst_invoice_rep
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
