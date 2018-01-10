odoo.define('assemble_pro.assemble_pro', function (require) {
"use strict";

//var instance = openerp;
var core = require('web.core');
var Model = require('web.Model');

var PickingBarcodeHandler = core.form_widget_registry.get('picking_barcode_handler');

PickingBarcodeHandler.include({

    try_lot_splitting_wizard: function(barcode) {
        function is_suitable(pack_operation) {
            var barcode_str=String(barcode).split('-');
            
            barcode = barcode_str[0];
            //alert(barcode);
            //alert(pack_operation.get('product_barcode'));
            return pack_operation.get('product_barcode') === barcode
                && pack_operation.get('lots_visible')
                && ! pack_operation.get('location_processed')
                && ! pack_operation.get('result_package_id');
        }
        var po_field = this.form_view.fields.pack_operation_product_ids;
        var po_records = po_field.viewmanager.active_view.controller.records;
        var candidate = po_records.find(function(po) { return is_suitable(po) && po.get('qty_done') < po.get('product_qty') })
            || po_records.find(function(po) { return is_suitable(po) });
        if (candidate) {
            var self = this;
            return self.form_view.save().done(function() {
                return self.form_view.reload().done(function() {
                    return self.picking_model.call('get_po_to_split_from_barcode', [[self.form_view.datarecord.id], barcode]).done(function(id) {
                        return self.po_model.call("split_lot", [[id]]).done(function(result) {
                            self.open_wizard(result);
                        });
                    });
                });
            });
        } else {
            return $.Deferred().reject();
        }
    },
    
});

//core.form_widget_registry.add('picking_barcode_handler', PickingBarcodeHandler);

});
