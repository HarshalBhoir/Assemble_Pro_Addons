odoo.define('assemble_pro.assemble_pro', function (require) {
"use strict";

//var instance = openerp;
var core = require('web.core');
var Model = require('web.Model');

var PickingBarcodeHandler = core.form_widget_registry.get('picking_barcode_handler');

PickingBarcodeHandler.include({
    
    pre_onchange_hook: function(barcode) {
        var self = this;
        var deferred = $.Deferred();
        this.mrp_wiz_model = new Model("mrp.product.produce.new");
        console.log("BBBBBBBBBBBBBB",this.form_view.model,this.form_view.datarecord);
        if (this.form_view.model === "mrp.product.produce.new") {
            //return self.mrp_wiz_model.call('on_barcode_scanned', [[self.form_view.datarecord.id], barcode]);
            var mrp_field = this.form_view.fields.lot_lines;
            var mrp_records = mrp_field.viewmanager.active_view.controller.records;
            console.log("MMMMMMMMMMMMMM",mrp_field, mrp_records);
            //var mrp_candidate = mrp_records.find(function(po) { return is_suitable(po) && po.get('qty_done') < po.get('product_qty') })
            //    || mrp_records.find(function(po) { return is_suitable(po) });
            if (mrp_records) {
                return mrp_field.data_update({'product_id': this.form_view.datarecord.get('product_id'), 'name': barcode}).then(function() {
                    return mrp_field.viewmanager.active_view.controller.reload_record(mrp_records);
                });
            } else {
                return $.Deferred().reject();
            }
        }
        else{
            var state = this.form_view.datarecord.state;
            if (state === 'cancel' || state === 'done') {
                this.do_warn(_.str.sprintf(_t('Picking %s'), state), _.str.sprintf(_t('The picking is %s and cannot be edited.'), state));
                return true;
            }
            self.try_increasing_po_qty(barcode).fail(function() {
                self.try_lot_splitting_wizard(barcode).fail(function() {
                    deferred.resolve(true);
                }).done(function() { deferred.resolve(false); });
            }).done(function() { deferred.resolve(false); });
            return deferred;
        }
    },
    
    try_lot_splitting_wizard: function(barcode) {
        function is_suitable(pack_operation) {
            var barcode_str=String(barcode).split('-');
            
            barcode = barcode_str[0];
            alert(barcode);
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