# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


import time
from openerp.exceptions import UserError, MissingError, ValidationError
from openerp import api, fields as fields_new, models, _
import openerp.addons.decimal_precision as dp
from openerp.exceptions import UserError
from openerp.osv import fields, osv
import json


class mrp_product_produce_lot(osv.osv_memory):
    _name="mrp.product.produce.lot"
    _description = "Product Produce Consume Lots"
    
    _columns = {
        'name' :fields.char( string='Lot'),
        'lot_id': fields.many2one('stock.production.lot', string='Produce'),
        'ref': fields.char( string='Ref'),
        'serial_id': fields.many2one('mrp.product.produce.new', string='Produce'),
        'mrp_id': fields.many2one('mrp.production', string='Production'),
        'product_id':fields.many2one('product.product', string='Product'), #, related='serial_id.product_id' , store=True
        'product_qty': fields.float(string="Quantity"),
    }

class mrp_product_produce_extension(models.TransientModel):
    _inherit = "mrp.product.produce"

    @api.multi
    def do_produce(self):
        res = super(mrp_product_produce_extension, self).do_produce()
        result = []
        
        for box in self.consume_lines:
            vals = {
                'product_id':box.product_id.id,
                'product_qty':box.product_qty ,
                'lot_id':box.lot_id.id,
                'stock_lot_id':self.lot_id.id,
            }
            result.append(vals)
        self.lot_id.stock_lot_line_ids = result
        return res

    
class mrp_product_produce_line_new(osv.osv_memory):
    _name="mrp.product.produce.line.new"
    _description = "Product Produce Consume lines"

    _columns = {
        'product_id': fields.many2one('product.product', string='Product'),
        'product_qty': fields.float('Quantity (in default UoM)', digits_compute=dp.get_precision('Product Unit of Measure')),
        'lot_id': fields.many2one('stock.production.lot', string='Lot'),
        'produce_id': fields.many2one('mrp.product.produce.new', string="Produce"),
    }

class mrp_product_produce_new(osv.osv_memory):
    _name = "mrp.product.produce.new"
    _description = "Product Produce"

    _columns = {
        'product_id': fields.many2one('product.product', type='many2one'),
        'product_qty': fields.float('Select Quantity', digits_compute=dp.get_precision('Product Unit of Measure'), required=True),
        'mode': fields.selection([('consume_produce', 'Consume & Produce'),
                                  ('consume', 'Consume Only')], 'Mode', required=True,
                                  help="'Consume only' mode will only consume the products with the quantity selected.\n"
                                        "'Consume & Produce' mode will consume as well as produce the products with the quantity selected "
                                        "and it will finish the production order when total ordered quantities are produced."),
        'lot_id': fields.many2one('stock.production.lot', 'Lot'), #Should only be visible when it is consume and produce mode
        'consume_lines': fields.one2many('mrp.product.produce.line.new', 'produce_id', 'Products Consumed'),
        'tracking': fields.related('product_id', 'tracking', type='selection',
                                   selection=[('serial', 'By Unique Serial Number'), ('lot', 'By Lots'), ('none', 'No Tracking')]),
        
        'lot_lines' :  fields.one2many('mrp.product.produce.lot', 'serial_id', 'Lots to be Produced'),
        'barcode_scanned': fields.char(string="Barcodes")
    }
    
    
    def on_change_qty(self, cr, uid, ids, product_qty, consume_lines, context=None):
        """ 
            When changing the quantity of products to be produced it will 
            recalculate the number of raw materials needed according
            to the scheduled products and the already consumed/produced products
            It will return the consume lines needed for the products to be produced
            which the user can still adapt
        """
        prod_obj = self.pool.get("mrp.production")
        uom_obj = self.pool.get("product.uom")
        production = prod_obj.browse(cr, uid, context['active_id'], context=context)
        consume_lines = []
        new_consume_lines = []
        if product_qty > 0.0:
            product_uom_qty = uom_obj._compute_qty(cr, uid, production.product_uom.id, product_qty, production.product_id.uom_id.id)
            consume_lines = prod_obj._calculate_qty(cr, uid, production, product_qty=product_uom_qty, context=context)
        
        for consume in consume_lines:
            new_consume_lines.append([0, False, consume])
        return {'value': {'consume_lines': new_consume_lines}}


    def _get_product_qty(self, cr, uid, context=None):
        """ To obtain product quantity
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param context: A standard dictionary
        @return: Quantity
        """
        if context is None:
            context = {}
        prod = self.pool.get('mrp.production').browse(cr, uid,
                                context['active_id'], context=context)
        done = 0.0
        for move in prod.move_created_ids2:
            if move.product_id == prod.product_id:
                if not move.scrapped:
                    done += move.product_uom_qty # As uom of produced products and production order should correspond
        return prod.product_qty - done

    def _get_product_id(self, cr, uid, context=None):
        """ To obtain product id
        @return: id
        """
        prod=False
        if context and context.get("active_id"):
            prod = self.pool.get('mrp.production').browse(cr, uid,
                                    context['active_id'], context=context)
        return prod and prod.product_id.id or False
    
    def _get_track(self, cr, uid, context=None):
        prod = self._get_product_id(cr, uid, context=context)
        prod_obj = self.pool.get("product.product")
        return prod and prod_obj.browse(cr, uid, prod, context=context).tracking or 'none'

    _defaults = {
         'product_qty': _get_product_qty,
         'mode': lambda *x: 'consume_produce',
         'product_id': _get_product_id,
         'tracking': _get_track,
    }
    
    
    def do_produce(self, cr, uid, ids, context=None):
        production_id = context.get('active_id', False)
        assert production_id, "Production Id should be specified in context as a Active ID."
        data = self.browse(cr, uid, ids[0], context=context)
        production_lot_obj = self.pool.get('stock.production.lot')
        product_wizard_obj = self.pool.get('mrp.product.produce')
        
        quantity = data.product_qty or 1
        
        consume_lines_list = []
        for consume_record in data.consume_lines:
            quant = (consume_record.product_qty / data.product_qty) or 1
            consume_lines_list.append([0, 0, {'lot_id': consume_record.lot_id.id,
                                              'product_id': consume_record.product_id.id,
                                              'product_qty': quant}])
            

        for lot_record in data.lot_lines:
            lot_vals = {
                'name': lot_record.name,
                'product_id':lot_record.product_id.id,
            }
            lot_id = production_lot_obj.create(cr, uid, lot_vals, context)
            lot_obj = production_lot_obj.browse(cr, uid, lot_id)
            lot_obj.onchange_internal_reference()
            recal_data = self.on_change_qty(cr, uid, ids, 1, data.consume_lines, context)
            
            vals = {
                'mode': data.mode,
                'product_qty': 1,
                'lot_id':lot_id,
                'consume_lines': consume_lines_list,
            }
            wiz_id = product_wizard_obj.create(cr, uid, vals, context)
            wiz_obj = product_wizard_obj.browse(cr, uid, wiz_id)
            wiz_obj.with_context(context).do_produce()
            

        if not len(data.lot_lines):
            raise ValidationError("Kindly Scan the Product Barcodes")
            
        
        return {}