from openerp import models, fields, api, _, tools
from openerp.exceptions import UserError, MissingError, ValidationError


class stock_production_lot_extension(models.Model):
    _inherit = "stock.production.lot"
    
    stock_lot_line_ids = fields.One2many('stock.lot.line.extension', 'stock_lot_id', string='Stock Quant Line' )

class stock_lot_line_extension(models.Model):
    _name="stock.lot.line.extension"
    
    product_id = fields.Many2one('product.product', string='Product')
    product_qty= fields.Float('Quantity (in default UoM)')
    lot_id= fields.Many2one('stock.production.lot', string='Lot')
    # produce_id= fields.Many2one('mrp.product.produce', string="Produce")
    stock_lot_id = fields.Many2one('stock.production.lot', string="Stock lot")


class stock_location_extension(models.Model):
    _inherit =  "stock.location"
    
    days = fields.Integer(String="Days")
    
class stock_picking_type_extension(models.Model):
    _inherit = "stock.picking.type"
    
    code= fields.Selection([('incoming', 'Suppliers'), ('outgoing', 'Customers'), ('internal', 'Internal'), ('dc', 'Delivery Challan')], 'Type of Operation', required=True)
    
    
class stock_pack_operation_lot_extension(models.Model):
    _inherit = "stock.pack.operation.lot"
    
    start_length = fields.Float(string="Start Length", track_visibility='always' )
    end_length = fields.Float(string="End Length", track_visibility='always' )
    uom_id = fields.Char('Unit of Measure',related="operation_id.product_uom_id.name") # , default='Unit(s)'
    
    # @api.model
    # def default_get(self, fields):
    #     print "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" , self , fields, self.operation_id
    #     res = super(stock_pack_operation_lot_extension, self).default_get(fields)
    #     print "JJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJ" , res , "KKKKKKKKKKKK" , self.uom_id
    #     res['uom_id'] = self.operation_id.product_uom_id.name
    #     print "KDDDDDDDDDDDDDDDDDDDDDDDDDDDD" , self.uom_id
    #     # ids = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)])
    #     # if not ids:
    #     #     raise UserError("Employee is not created. Please contact Administrator.")
    #     return res
    
    # @api.model
    # def default_get(self, fields):
    #     res = super(stock_pack_operation_lot_extension, self).default_get(fields)
    #     receivable_id = [rec.id for rec in self.env['account.account.type'].sudo().search([('type','=','receivable')])]
    #     account_receivable = self.env['account.account'].search([('user_type_id','in',receivable_id)])
    #     if account_receivable:
    #         res['property_account_receivable_id'] = account_receivable.id
    #     payable_id = [rec.id for rec in self.env['account.account.type'].sudo().search([('type','=','payable')])]
    #     account_payable = self.env['account.account'].search([('user_type_id','in',payable_id)])
    #     if account_payable:
    #         res['property_account_payable_id'] = account_payable.id
    #     term = self.env['ir.model.data'].get_object('equipment_rental', 'account_payment_term_cash_in_advance')
    #     res['property_payment_term_id'] = term.id
    #     res['user_id'] = self._uid
    #     return res

    @api.multi
    @api.onchange('start_length','end_length')
    def onchange_length(self):
        if self.start_length and  self.end_length:
            self.qty = self.end_length - self.start_length
            
            if self.qty != self.qty_todo:
                raise ValidationError("Inputed quantity is incorrect \n Correct Quantity is %s" % (self.qty_todo))
            else:
                self.operation_id.product_id.product_tmpl_id.last_updated_qty = self.end_length
                a = self.env['product.template'].search([('id', '=', self.operation_id.product_id.product_tmpl_id.id)]).write({'last_updated_qty': self.end_length})
        
class stock_barcode_list(models.Model):
    _name = "stock.barcode.list"
    
    name = fields.Char(string="Barcode")
    picking_id = fields.Many2one('stock.picking', string='Stock Picking', track_visibility='always')
    pack_operation_id = fields.Many2one('stock.pack.operation', string='Stock Pack Operation', track_visibility='always')
    
class stock_move_extension(models.Model):
    _inherit =  "stock.move"
    
    @api.multi
    def get_total_rate(self):
        for i in self.picking_id.work_order_id.order_line:
            if self.product_id.default_code == i.product_id.default_code:
                amount = tot_amt = 0.0
                for tax in i.taxes_id:
                    if tax.amount_type == "group":
                        for tax_line in tax.children_tax_ids:
                            amount += ((tax_line.amount) / 100)
                    elif tax.amount_type == "percent":
                        amount = tax.amount
                    tot_amt +=amount
                qty_price = float(float(i.price_unit) * float(i.product_qty)) 
                tax_price = qty_price + tot_amt
        return tax_price

class stock_picking_extension(models.Model):
    _inherit = "stock.picking"
    
    import_text = fields.Boolean(String="Import Through Text File")
    picking_type_code = fields.Selection([('incoming', 'Suppliers'), ('outgoing', 'Customers'), ('internal', 'Internal'),('dc','=','DC')], 'Type of Operation' ,related="picking_type_id.code" , store=True )
    remark = fields.Char(String="Remark")
    invoice_no = fields.Char(String="DC/Invoice Number")
    material_checker = fields.Many2one('hr.employee', string='Material Checked By', track_visibility='always')
    gate_pass = fields.Selection([('yes', 'YES'), ('no', 'NO')], 'Excise Gate Pass Received', track_visibility='always')
    test_certificate = fields.Selection([('yes', 'YES'), ('no', 'NO')], 'Test Certificate Received', track_visibility='always')
    work_order_id = fields.Many2one('purchase.order', string='Work Order', track_visibility='always')
    service = fields.Char(String="Service")
    dc_type = fields.Selection([('returnable', 'Returnable'), ('non_returnable', 'Non-Returnable')], 'Type of DC')
    payment = fields.Selection([('billable', 'Billable'), ('non_billable', 'Non-Billable')], 'Payment')
    color = fields.Char(String="Color")
    barcode_product = fields.Text(String="Barcode List" )
    barcode_list_ids = fields.One2many('stock.barcode.list', 'picking_id', string='Barcode List' )#, compute="add_barcode"
        
    @api.multi
    @api.onchange('partner_id')
    def onchange_partner_id(self):
        result = {'domain': {'work_order_id': []}}
        work_ids = []
        if self.partner_id :
            srch = self.env['purchase.order'].search([('partner_id','=',self.partner_id.id),('state','!=','done')])
            for srch1 in srch :
                if 'PO' not in srch1.name:
                    work_ids.append(srch1.id)
            result = {'domain': {'work_order_id': [('id','in',work_ids)]}}
        return result
    
    @api.multi
    @api.onchange('work_order_id')
    def onchange_work_order_id(self):
        result = []
        if self.work_order_id:
            for i in self.work_order_id.order_line:
                vals = {
                        'product_id':i.product_id,
                        'name':i.name,
                        'price_unit':i.price_unit,
                        'product_uom_qty':i.product_qty,
                        'state':'draft',
                        'date':i.date_order,
                         'date_expected':i.date_planned,
                         'product_uom':1,
                         'location_id':self.location_id.id,
                         'location_dest_id':self.location_dest_id.id,
                        }
                result.append(vals)
            self.move_lines = result

    @api.multi
    def _add_delivery_cost_to_so(self):
        pass # changes made for restricting stock module to create a line in sale order line

    @api.multi
    def action_assign(self):                
                    
        res = super(stock_picking_extension, self).action_assign()
        quants_dict = {}
        raise_error = False
        if self.import_text==True:
            quant = self.env['stock.quant'].search([('location_id','=',self.location_id.id)])
            for record in self.move_lines:
                if len(quant):
                    quant_found = False
                    for quant_id in quant:
                        if record.product_id.id == quant_id.product_id.product_tmpl_id.id:
                            quant_found = True
                            if record.product_id.name in quants_dict:
                                quants_dict[record.product_id.name] = quants_dict[record.product_id.name] + quant_id.qty
                            else:
                                quants_dict[record.product_id.name] = quant_id.qty
                    if not quant_found:
                        quants_dict[record.product_id.name] = 0
    
                else:
                    raise ValidationError("No stock available for any Product(s)")
                    
            quant_string = "\
Stock Not Available for the following Product(s) in the System:\n\
Product --- Quantity \
"
            for quant_name, value in quants_dict.iteritems():
                if value <= 0:
                    raise_error = True
                    quant_string += "\n%s -- -- -- ( %s ) " % (quant_name,value)
            if raise_error:
                print "IIIIIIIIIIIIIIIIIIIIII Stock Not Available"
                raise ValidationError(quant_string)
                    
        return res
    
    @api.multi
    def do_new_transfer(self):
        quants_dict = {}
        raise_error = False
        if self.import_text==True:
            quant = self.env['stock.quant'].search([('location_id','=',self.location_id.id)])
            for record in self.move_lines:
                if len(quant):
                    quant_found = False
                    for quant_id in quant:
                        if record.product_id.id == quant_id.product_id.product_tmpl_id.id:
                            quant_found = True
                            if record.product_id.name in quants_dict:
                                quants_dict[record.product_id.name] = quants_dict[record.product_id.name] + quant_id.qty
                            else:
                                quants_dict[record.product_id.name] = quant_id.qty
                    if not quant_found:
                        quants_dict[record.product_id.name] = 0
    
                else:
                    raise ValidationError("No stock available for any Product(s)")
            quant_string = "\
Stock Not Available for the following Product(s) in the System:\n\
Product --- Quantity \
"
            for quant_name, value in quants_dict.iteritems():
                if value <= 0:
                    raise_error = True
                    quant_string += "\n%s -- -- -- ( %s ) " % (quant_name,value)
            if raise_error:
                print "IIIIIIIIIIIIIIIIIIIIII Stock Not Available"
                raise ValidationError(quant_string)
            
            if self.state == 'assigned':
                for rec in self.pack_operation_product_ids:
                    if rec.product_qty != rec.qty_done:
                        raise ValidationError("Some products require lots, so you need to specify those first!")
                    
        if self.work_order_id and self.picking_type_code == 'dc' and self.state == 'assigned':
            for rec in self.pack_operation_product_ids:
                if rec.product_qty == rec.qty_done:
                    # self.work_order_id.state = 'done'
                    pass
                    # if self.dc_type == 'returnable':
                    #     self.work_order_id._create_picking()
                else:
                    raise ValidationError("Some products require lots, so you need to specify those first!")
            
        res = super(stock_picking_extension, self).do_new_transfer()
        return res
    
    @api.multi
    def write(self ,vals):
        res = super(stock_picking_extension, self).write(vals)
        if self.barcode_product:
            my_list = str(self.barcode_product).split(",")
            for barcode in my_list:
                self.barcode_list_ids.create({'name':barcode,'picking_id':self.id})
        return res
        
    
    @api.multi
    def get_po_to_split_from_barcode(self, barcode):
            print "SSSSSSSSSSSSSSSSSSSSSSSSSSS get_po_to_split_from_barcode stock picking" , self , self.env.context
        # if self.picking_type_code in ['outgoing','dc']:
            line_list = barcode.split('-')
            line_tot = ''.join(line_list[0].strip())
            barcode =  line_tot
            product_code = []
            for i in self.move_lines_related:
                product_code.append(str(i.product_id.default_code))
                
            if str(barcode) not in product_code:
                return { 'warning': {
                'title': _('You have entered this serial number already'),
                'message': _('You have already scanned this serial number'),
                }}
            else:
                ''' Returns the ID of the next PO that needs splitting '''
                candidates = self.env['stock.pack.operation'].search([
                    ('picking_id', 'in', self.ids),
                    ('product_barcode', '=', barcode),
                    ('location_processed', '=', False),
                    ('result_package_id', '=', False),
                ]).filtered(lambda r: r.lots_visible)
                candidates_todo = candidates.filtered(lambda r: r.qty_done < r.product_qty)
                return candidates_todo and candidates_todo[0].id or candidates[0].id
        # else:
        #     raise UserError("This Facility is only available for Packing")
    
    @api.multi
    def _check_product(self, product, og_barcode, qty=1.0):
        
        # if self.picking_type_id.code == 'incoming':
        #     raise  UserError("Kindly Open the Product Wizard for Adding Product Quantity")
        
        print "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC _check_product"
        barcode_product = []
        barcode_product = str(self.barcode_product).split(',')
        
        og_barcode = str(og_barcode)
        existing_barcodes = self.env['stock.barcode.list'].search([])
        for ex_barcode in existing_barcodes:
            if og_barcode == ex_barcode.name:
                raise UserError("You have already scanned this serial number 1")
            
        if og_barcode  in barcode_product and self.picking_type_id.code != 'incoming':
            raise UserError("You have already scanned this serial number 2")
        elif og_barcode  in barcode_product or self.picking_type_id.code == 'incoming':
            raise UserError("Kindly Open the Product Wizard for Adding Product Quantity")
        else:
            barcode_product.append(og_barcode)
            self.barcode_product = og_barcode if not self.barcode_product else ",".join(barcode_product)
            
        corresponding_po = self.pack_operation_product_ids.filtered(lambda r: r.product_id.id == product.id and not r.result_package_id and not r.location_processed)
        if corresponding_po:
            if not corresponding_po.lots_visible:#product.tracking=='none':
                new_po = False
                last_po = False
                for po in corresponding_po:
                    last_po = po
                    if po.product_qty > po.qty_done:
                        new_po = po
                        break
                corresponding_po = new_po or last_po
                corresponding_po.qty_done += qty
        else:
            picking_type_lots = (self.picking_type_id.use_create_lots or self.picking_type_id.use_existing_lots)
            self.pack_operation_product_ids += self.pack_operation_product_ids.new({
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'location_id': self.location_id.id,
                'location_dest_id': self.location_dest_id.id,
                'qty_done': (product.tracking == 'none' and picking_type_lots) and qty or 0.0,
                'product_qty': 0.0,
                'from_loc': self.location_id.name,
                'to_loc': self.location_dest_id.name,
                'fresh_record': False,
                'state':'assigned',
                'lots_visible': product.tracking != 'none' and picking_type_lots,
            })
        # ctx = self.env.context.get('params')
        # self.barcode_list_ids.create({'name': og_barcode,'picking_id':ctx.get('id')})
        return True
    
    
    
    def on_barcode_scanned(self, barcode):
        print "IIIIIIIIIIIIIIIIIIIIIIIIIIIIIII stock picking on_barcode_scanned"
        og_barcode = barcode
        line_list = barcode.split('-')
        line_tot = ''.join(line_list[0].strip())
        barcode =  line_tot
        
        
        
        for i in self.move_lines_related:
            print "RRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRgela"
            if i.product_id.default_code != barcode and self.picking_type_code != 'incoming':
                return { 'warning': {
                'title': _('You have entered a wrong serial number'),
                'message': _('You have scanned a serial number which is not present in this packlist'),
                }}
            else:
                if not self.picking_type_id.barcode_nomenclature_id:
                    # Logic for products
                    product = self.env['product.product'].search(['|', ('barcode', '=', barcode), ('default_code', '=', barcode)], limit=1)
                    if product:
                        if self._check_product(product):
                            return
        
                    # Logic for packages in source location
                    if self.pack_operation_pack_ids:
                        package_source = self.env['stock.quant.package'].search([('name', '=', barcode), ('location_id', 'child_of', self.location_id.id)], limit=1)
                        if package_source:
                            if self._check_source_package(package_source):
                                return
        
                    # Logic for packages in destination location
                    package = self.env['stock.quant.package'].search([('name', '=', barcode), '|', ('location_id', '=', False), ('location_id','child_of', self.location_dest_id.id)], limit=1)
                    if package:
                        if self._check_destination_package(package):
                            return
        
                    # Logic only for destination location
                    location = self.env['stock.location'].search(['|', ('name', '=', barcode), ('barcode', '=', barcode)], limit=1)
                    if location and location.parent_left < self.location_dest_id.parent_right and location.parent_left >= self.location_dest_id.parent_left:
                        if self._check_destination_location(location):
                            return
                else:
                    parsed_result = self.picking_type_id.barcode_nomenclature_id.parse_barcode(barcode)
                    product_barcode = ''
                    if parsed_result['type'] in ['weight', 'product','lot']:
                        if parsed_result['type'] == 'weight':
                            product_barcode = parsed_result['base_code']
                            qty = parsed_result['value']
                        else: #product
                            product_barcode = parsed_result['code']
                            qty = 1.0
                        product = self.env['product.product'].search(['|', ('barcode', '=', product_barcode), ('default_code', '=', product_barcode)], limit=1)

                        if product:
                            if self._check_product(product , og_barcode):
                                return
        
                    if parsed_result['type'] == 'package':
                        if self.pack_operation_pack_ids:
                            package_source = self.env['stock.quant.package'].search([('name', '=', parsed_result['code']), ('location_id', 'child_of', self.location_id.id)], limit=1)
                            if package_source:
                                if self._check_source_package(package_source):
                                    return
                        package = self.env['stock.quant.package'].search([('name', '=', parsed_result['code']), '|', ('location_id', '=', False), ('location_id','child_of', self.location_dest_id.id)], limit=1)
                        if package:
                            if self._check_destination_package(package):
                                return
        
                    if parsed_result['type'] == 'location':
                        location = self.env['stock.location'].search(['|', ('name', '=', parsed_result['code']), ('barcode', '=', parsed_result['code'])], limit=1)
                        if location and location.parent_left < self.location_dest_id.parent_right and location.parent_left >= self.location_dest_id.parent_left:
                            if self._check_destination_location(location):
                                return
        if self.picking_type_code != 'incoming':
            return {'warning': {
                'title': _('Wrong barcode'),
                'message': _('The barcode "%(barcode)s" doesn\'t correspond to a proper product, package or location.') % {'barcode': barcode}
            }}
        # else:
        #     print "LOLITAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


    def do_print_picking(self, cr, uid, ids, context=None):
        '''This function prints the picking list'''
        context = dict(context or {}, active_ids=ids)
        self.write(cr, uid, ids, {'printed': True}, context=context)
        return self.pool.get("report").get_action(cr, uid, ids, 'assemble_pro.assemble_pro_report_picking2', context=context)
    
    @api.model
    @api.multi
    def reminder_mail(self):
        template = False
        try:
            template = self.env['ir.model.data'].get_object('assemble_pro', 'modvat_template')
        except ValueError:
            pass
        
        ##### ---=== Email Recepients ===--- #####
        email_list = []
        modvat_list  = []
        
        ac_billing_group = self.env['ir.model.data'].get_object('account', 'group_account_invoice')
        ac_user_group = self.env['ir.model.data'].get_object('account', 'group_account_user')
        ac_manager_group = self.env['ir.model.data'].get_object('account', 'group_account_manager')
        if ac_user_group  and ac_user_group.users \
            or (ac_billing_group and ac_billing_group.users) \
            or (ac_manager_group and ac_manager_group.users):
            for user1 in ac_user_group.users:
                email_list.append(user1.email)
            for user2 in ac_billing_group.users:
                email_list.append(user2.email)
            for user3 in ac_manager_group.users:
                email_list.append(user3.email)
        else:
            raise UserError("Account Manager not Defined!")
        
        emails = ",".join([str(x) for x in email_list])
        print "DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD" , emails
        # emails.append(performed_user_id)
        
        if template:
            template.email_to = emails
        # record = False
        for rec in self.search([('picking_type_code', '=', 'incoming'),('state', '=', 'done')]) :
            for record in rec.pack_operation_product_ids:
                # modvat_flag = False
                if record.modvat_applicable:
                    modvat_list.append(record)
                    
            if modvat_list and rec.gate_pass == 'no':
                
                print "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" , record , rec.picking_type_code , record.modvat_applicable , rec.gate_pass , rec.name ,rec.origin , rec.partner_id.name

                template.email_to = emails
                mail_values = template.generate_email(rec.id)
                mail_values['email_from'] = rec.write_uid.email
                mail_obj = self.env['mail.mail'].create(mail_values)
                # msg_obj = self.env['mail.message'].create(mail_values)
                print "Mail sentt================" , mail_obj
                mail = mail_obj.send()
                # msg = msg_obj.send()



    @api.multi
    def packlist_report(self):
        result = []
        box_dict = {}
        subbox_dict = {}
        for rec in self.pack_operation_product_ids:
            print "AAAAAAAAAA" ,rec.product_id.name , rec.product_id.main_box , rec.product_id.sub_box
            rec_line = [rec.product_id.default_code,rec.product_id.name,rec.barcode_list,0,rec.qty_done,rec.product_uom_id.name,""]
            if rec.product_id.main_box:
                if rec.product_id.sub_box:
                    if rec.product_id.sub_box in subbox_dict.keys():
                        subbox_dict[rec.product_id.sub_box].append((rec.product_id.main_box,rec_line))
                    else:
                        subbox_dict[rec.product_id.sub_box] = [(rec.product_id.main_box,rec_line)]
                else:
                    if rec.product_id.main_box in box_dict.keys():
                        box_dict[rec.product_id.main_box].append(rec_line)
                    else:
                        box_dict[rec.product_id.main_box] = [
                            ["PO No.","Test PO","","","","","font-weight:bold;border-top:1px solid black;"],
                            ["Contract No.",self.origin,"","","","","font-weight:bold"],
                            ["Main Box:",rec.product_id.main_box,"","","","","font-weight:bold; border-bottom:1px solid black;"],
                            rec_line
                        ]
        
        sub_dict = {}
        used_keys = []
        
        for key,value in subbox_dict.iteritems():
            print "VVVVVVVVVVVv",key,value,type(value)
            for value_rec in value:
                sub_key = value_rec[0]+"."+key
                # if value_rec[0] in sub_dict.keys():
                if sub_key not in used_keys:
                    used_keys.append(sub_key)
                    if value_rec[0] in box_dict.keys():
                        box_dict[value_rec[0]].append(["Sub Box : ",key,"","","","",""])
                    else:
                        box_dict[value_rec[0]] = [["Sub Box : ",key,"","","","",""]]
                box_dict[value_rec[0]].append(value_rec[1])
                # else:
                #     sub_dict[value_rec[0]] = [["Sub Box : ",key,"","","",""],value_rec[1]]
        
        # result = [value for key,value in box_dict.iteritems()]
        for rec_key, rec_value in box_dict.iteritems():
            result = result + rec_value
        
        # print "MMMMMMMMMMMMM",box_dict,sub_dict
        # print "SSSSSSSSSSSSS",used_keys
        
        print "RRRRRRRRRRRRRRR",result
        return result
        # return """<span style='font-weight:bold'>Test</span>"""
            

    
class stock_pack_operation_extension(models.Model):
    _name= 'stock.pack.operation'
    _inherit = ['stock.pack.operation', 'barcodes.barcode_events_mixin']

    product_barcode = fields.Char(related='product_id.default_code')
    location_processed = fields.Boolean()
    barcode_list = fields.Text(string="Barcode List")
    barcode_list_ids = fields.One2many('stock.barcode.list', 'pack_operation_id', string='Barcode List' )#, compute="add_barcode"
    batch_length = fields.Float(string="Batch Length", track_visibility='always' ,related="product_id.product_tmpl_id.batch_length" )
    picking_type_code = fields.Selection([('incoming', 'Suppliers'), ('outgoing', 'Customers'), ('internal', 'Internal'),('dc','=','DC')], 'Type of Operation' ,related="picking_id.picking_type_code" , store=True )
    uom_id_name = fields.Char('Unit of Measure',related="product_uom_id.name" )
    modvat_applicable = fields.Boolean(string="ModVAT")
    
    
    @api.multi
    def button_dummy(self):
        return self.split_lot()
    
    @api.multi
    def write(self ,vals):
        res = super(stock_pack_operation_extension, self).write(vals)
        if self.barcode_list:
            my_list = str(self.barcode_list).split(",")
            for barcode in my_list:
                if self.picking_id:
                    self.barcode_list_ids.create({'name':barcode,'pack_operation_id':self.id,'picking_id':self.picking_id.id})
                
        return res

    def on_barcode_scanned(self, barcode):
        barcode_list = []
        barcode_list = str(self.barcode_list).split(',')
        
        og_barcode = str(barcode)
        
        print "LLLLLLLLLLLLLLLL" , len(barcode) , self.batch_length , self.id , self.picking_id.picking_type_code , self.picking_id , self.picking_type_code
        
        if len(barcode) != int(self.batch_length) and self.picking_type_code == 'incoming':
            raise ValidationError("You have scanned a serial number whose batch length doesnot match with this product " )
        
        existing_barcodes = self.env['stock.barcode.list'].search([])
        for ex_barcode in existing_barcodes:
            if og_barcode == ex_barcode.name:
                raise UserError("You have already scanned this serial number 3")
        
        
        print "KKKKKKKKKKKKKKKKKKKKKKKKK stock_pack_operation_extension on_barcode_scanned",barcode, barcode_list 
        if barcode in barcode_list:
            return { 'warning': {
                'title': _('You have entered this serial number already'),
                'message': _('You have already scanned this serial number 4'),
            }}
        else:
            barcode_list.append(barcode)
            self.barcode_list = barcode if not self.barcode_list else ",".join(barcode_list)
        
        line_list = barcode.split('-')
        line_tot = ''.join(line_list[0].strip())
        barcode = line_tot
        context=dict(self.env.context)
        # As there is no quantity, just add the quantity
        if context.get('only_create') and context.get('serial'):
            if barcode in [x.lot_name for x in self.pack_lot_ids]:
                return { 'warning': {
                            'title': _('You have entered this serial number already'),
                            'message': _('You have already scanned the serial number "%(barcode)s"') % {'barcode': barcode},
                        }}
            else:
                self.pack_lot_ids += self.pack_lot_ids.new({'qty': 1.0, 'lot_name': barcode})
        elif context.get('only_create') and not context.get('serial'):
            corresponding_pl = self.pack_lot_ids.filtered(lambda r: r.lot_name == barcode)
            if corresponding_pl:
                corresponding_pl[0].qty = corresponding_pl[0].qty + 1.0
            else:
                self.pack_lot_ids += self.pack_lot_ids.new({'qty': 1.0, 'lot_name': barcode})
        elif not context.get('only_create'):
            corresponding_pl = self.pack_lot_ids.filtered(lambda r: r.lot_id.name == barcode)
            if corresponding_pl:
                if context.get('serial') and corresponding_pl[0].qty == 1.0:
                    return {'warning': {'title': _('You have entered this serial number already'),
                            'message': _('You have already scanned the serial number "%(barcode)s"') % {'barcode': barcode},}}
                else:
                    corresponding_pl[0].qty = corresponding_pl[0].qty + 1.0
                    corresponding_pl[0].plus_visible = (corresponding_pl[0].qty_todo == 0.0) or (corresponding_pl[0].qty < corresponding_pl[0].qty_todo)
            else:
                # Search lot with correct name
                lots = self.env['stock.production.lot'].search(['|',('product_id', '=', self.product_id.id), ('name', '=', barcode)])
                # print "MAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" , lots
                if lots:
                    # if context.get('serial'):
                    raise_exception = True
                    skip_loop = False
                    for lot_record in self.pack_lot_ids:
                        print "JJJJJJJJJJJJJJJJJJJJJJJ SERIAL NUMBER" , barcode , lot_record.lot_id.product_id.default_code, lot_record.lot_id
                        if lot_record.qty_todo != lot_record.qty and barcode == lot_record.lot_id.product_id.default_code and skip_loop == False:
                            lot_record.do_plus()
                            raise_exception = False
                            skip_loop = True
                            
                    # if barcode in [x.lot_name for x in self.pack_lot_ids]:
                    if raise_exception:
                        # self.pack_lot_ids += self.pack_lot_ids.new({'qty': 1.0, 'lot_name': barcode})
                        return { 'warning': {
                                    'title': _('You have entered a wrong Serial Number of product'),
                                    'message': _('You have scanned the serial number which doesnot belong to this product'),
                                }}
                    
                    # else:
                    #     self.pack_lot_ids += self.pack_lot_ids.new({'qty': 1.0, 'lot_id': lots[0].id, 'plus_visible': False})
                else:
                    # If picking type allows for creating
                    if context.get('create_lots'):
                        lot_id = self.env['stock.production.lot'].with_context({'mail_create_nosubscribe': True}).create({'name': barcode, 'product_id': self.product_id.id})
                        self.pack_lot_ids += self.pack_lot_ids.new({'qty': 1.0, 'lot_id': lot_id.id, 'plus_visible': not context.get('serial')})
                    else:
                        return { 'warning': {
                            'title': _('No lot found'),
                            'message': _('There is no production lot for "%(product)s" corresponding to "%(barcode)s"') % {'product': self.product_id.name, 'barcode': barcode},
                        }}