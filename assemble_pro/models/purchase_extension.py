# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from openerp.exceptions import UserError, MissingError, ValidationError
from datetime import datetime
import datetime
import time
from dateutil.relativedelta import relativedelta
from openerp import api, fields, models, _, SUPERUSER_ID
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.translate import _
from openerp.tools.float_utils import float_is_zero, float_compare
import openerp.addons.decimal_precision as dp
from lxml import etree
from openerp.tools import amount_to_text_en

class purchase_order_extension(models.Model):
    _inherit = "purchase.order"
    
    advance_rm_material_id = fields.Many2one('advance.rm.material', string="RM ID" ,  track_visibility='always')
    purchase_type = fields.Selection([
        ('import', 'Import'),
        ('local', 'Local'),
        ], string='Purchase Type', track_visibility='always' )
    supplier_pricelist_id = fields.Many2one('product.supplierinfo', string="Pricelist" ,  track_visibility='always')
    transporter = fields.Char("Transporter")
    freight = fields.Char("Freight")
    packing = fields.Char("Packing & Forwarding")
    supplier_ref = fields.Char("Supplier Ref")
    sap_no = fields.Char("SAP No")
    delivery_terms = fields.Text("Delivery Terms")
    gstin_no = fields.Char(string='Vendor GSTIN No', store=True, related="partner_id.gstin_no")
    company_gstin_no = fields.Char(string='Company GSTIN No', store=True, related="company_id.gstin_no")
    tax_class = fields.Many2many('account.tax.class',string='Tax Class', related="partner_id.tax_class")

    
    def total_amount_in_words(self):
        return self.amount_total and  amount_to_text_en.amount_to_text_in(self.amount_total, 'Rupees') or ""
    
    
    # @api.depends('date_planned')
    # def _compute_date_planned(self):
    #     for order in self:
    #         min_date = False
    #         if not order.date_planned:
    #             print "AAAAAAAAAAAAAAAAAAAAAAAAAAAAA" , self.id , self.name
    #             for line in order.order_line:
    #                 if not min_date or line.date_planned < min_date:
    #                     min_date = line.date_planned
    #             if min_date:
    #                 order.date_planned = min_date
    #         else:
    #             print "BBBBBBBBBBBBBBBBBBBBBBBBB"
    #             if order.date_planned < order.date_order:
    #                 raise UserError(_('Kindly enter Correct Schedule date'))
    #             else:
    #                 for line2 in order.order_line:
    #                     line2.date_planned = order.date_planned
    #                     # if not min_date or line.date_planned < min_date:
    #                     #     min_date = line.date_planned
    
    @api.onchange('partner_id','date_order')
    def onchange_partner_date(self):
        dt = datetime.datetime.strptime(self.date_order,'%Y-%m-%d %H:%M:%S')
        dd = dt.date()
        if not self.partner_id:
            self.supplier_pricelist_id = False
        else:
            prod_sup = self.env['product.supplierinfo'].search([('name','=',self.partner_id.id),('date_start','<=',dd),('date_end','>=',dd)],order="create_date desc")
            if len(prod_sup):
                self.supplier_pricelist_id = prod_sup[0].id
            else:
                self.supplier_pricelist_id = False
            
        return {}
    
    @api.model
    def fields_view_get(self, view_id=None, view_type=False, toolbar=False, submenu=False):
        res = super(purchase_order_extension, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        doc = etree.XML(res['arch'])
        for node in doc.xpath("//field[@name='supplier_pricelist_id']"):
            node.set('domain', "[('name', '=',partner_id )]")
        
        res['arch'] = etree.tostring(doc)
        return res
    
    @api.multi
    def button_confirm(self):
        print "SSSSSSSSSSSSSSSSSSSSSSSS"
        for order in self:
            # order._add_supplier_to_product() # commented due to new creation of supplier pricelist
            # Deal with double validation process
            if order.company_id.po_double_validation == 'one_step'\
                    or (order.company_id.po_double_validation == 'two_step'\
                        and order.amount_total < self.env.user.company_id.currency_id.compute(order.company_id.po_double_validation_amount, order.currency_id))\
                    or order.user_has_groups('purchase.group_purchase_manager'):
                order.button_approve()
            else:
                order.write({'state': 'to approve'})
        # ----------- ModVAT code -------------------#
        modvat_dict = {}
        for modvat in self.order_line:
            modvat_dict[modvat.product_id.id] = modvat.modvat_applicable
        
        for record in self.picking_ids:
            for rec in record.pack_operation_product_ids:
                if rec.product_id.id in modvat_dict.keys():
                    rec.modvat_applicable = modvat_dict[rec.product_id.id]
                    
        # for record_po in self:
        #     for rec_po in record_po.order_line:
        #         for record in record_po.picking_ids:
        #             for rec in record.pack_operation_product_ids:
        #                 if rec.product_id.id == rec_po.product_id.id:
        #                     rec.modvat_applicable = rec_po.modvat_applicable
        
        # ----------- ModVAT code -------------------#
                    
        return {}


class purchase_order_line_extension(models.Model):
    _inherit = 'purchase.order.line'
    _description = 'Purchase Order Line'
    
    
    packing = fields.Float(string="Packing", track_visibility='always')
    no_of_packing = fields.Float(string="Nos/Packing", track_visibility='always')
    default_code = fields.Char('code' , related="product_id.default_code")
    modvat_applicable = fields.Boolean(string="ModVAT")
    hsn_code = fields.Char(string='HSN',related="product_id.product_tmpl_id.hsn_code")
    
    @api.onchange('product_id')
    def onchange_product_id(self):
        result = super(purchase_order_line_extension, self).onchange_product_id()
        supplier_pricelist = self.order_id.supplier_pricelist_id
        if len(supplier_pricelist):
            for price in supplier_pricelist[0]:
                for line in price.supplierinfo_id:
                    if self.product_id.product_tmpl_id.id == line.product_tmpl_id.id:
                        if self.order_id.type_order == 'purchase':
                            self.modvat_applicable = line.modvat_applicable
                        self.price_unit = line.rate or 0

        else:
            self.price_unit = 0.0
            if self.order_id.type_order == 'work':
                raise ValidationError("No PriceList available for Vendor  '%s' " % (self.order_id.partner_id.name))
        print "EEEEEEEEEE _onchange_quantity" , self.price_unit
        
        part = self.order_id.partner_id
        
        if not part:
            warning = {
                    'title': _('Warning!'),
                    'message': _('You must first select a partner!'),
                }
            return {'warning': warning}
        
        
        return result
    
    
    @api.onchange('product_qty', 'product_uom')
    def _onchange_quantity(self):
        result = super(purchase_order_line_extension, self)._onchange_quantity()
        supplier_pricelist = self.order_id.supplier_pricelist_id
        if len(supplier_pricelist):
            for price in supplier_pricelist[0]:
                for line in price.supplierinfo_id:
                    if self.product_id.product_tmpl_id.id == line.product_tmpl_id.id:
                        self.price_unit = line.rate or 0
        else:
            self.price_unit = 0.0
            if self.order_id.type_order == 'work':
                raise ValidationError("No PriceList available for Vendor  '%s' " % (self.order_id.partner_id.name))
        print "FFFFFFFFF _onchange_quantity" , self.price_unit
        return result