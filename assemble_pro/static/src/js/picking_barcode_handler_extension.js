odoo.define('stock_barcode.PickingBarcodeHandler', function (require) {
"use strict";

var core = require('web.core');
var Model = require('web.Model');
var FormViewBarcodeHandler = require('barcodes.FormViewBarcodeHandler');

var _t = core._t;

var PickingBarcodeHandler = FormViewBarcodeHandler.extend({
    init: function(parent, context) {
        this.form_view_initial_mode = parent.ViewManager.action.context.form_view_initial_mode;
        return this._super.apply(this, arguments);
    },

    start: function() {
        this._super();
        this.po_model = new Model("stock.pack.operation");
        this.picking_model = new Model("stock.picking");
        this.map_barcode_method['O-CMD.MAIN-MENU'] = _.bind(this.do_action, this, 'stock_barcode.stock_barcode_action_main_menu', {clear_breadcrumbs: true});
        // FIXME: start is not a reliable place to do this.
        this.form_view.options.disable_autofocus = 'true';
        if (this.form_view_initial_mode) {
            this.form_view.options.initial_mode = this.form_view_initial_mode;
        }
    },
	
	pre_onchange_hook: function(barcode) {
        var self = this;
        var deferred = $.Deferred();
        this.mrp_wiz_model = new Model("mrp.production");
        //console.log("BBBBBBBBBBBBBB",this.form_view.model,this.form_view.datarecord);
        if (this.form_view.model === "mrp.production") {
            return self.mrp_wiz_model.call('on_barcode_scanned', [[self.form_view.datarecord.id], barcode]);
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

    try_increasing_po_qty: function(barcode) {
        function is_suitable(pack_operation) {
            return pack_operation.get('product_barcode') === barcode
                && ! pack_operation.get('lots_visible')
                && ! pack_operation.get('location_processed')
                && ! pack_operation.get('result_package_id');
        }
        var po_field = this.form_view.fields.pack_operation_product_ids;
        var po_records = po_field.viewmanager.active_view.controller.records;
        var candidate = po_records.find(function(po) { return is_suitable(po) && po.get('qty_done') < po.get('product_qty') })
            || po_records.find(function(po) { return is_suitable(po) });
        if (candidate) {
            return po_field.data_update(candidate.get('id'), {'qty_done': candidate.get('qty_done') + 1}).then(function() {
                return po_field.viewmanager.active_view.controller.reload_record(candidate);
            });
        } else {
            return $.Deferred().reject();
        }
    },

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

    open_wizard: function(action) {
        var self = this;
        this.form_view.trigger('detached');
        this.do_action(action, {
            on_close: function() {
                self.form_view.trigger('attached');
                self.form_view.reload();
            }
        });
    },
});

core.form_widget_registry.add('picking_barcode_handler', PickingBarcodeHandler);

});