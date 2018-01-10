# # -*- coding: utf-8 -*-

from openerp import fields, models, exceptions, api, _
import base64
import csv
import cStringIO
from openerp.exceptions import UserError, MissingError, ValidationError


class WizardImport(models.TransientModel):
    _name = 'wizard.pricelist.import'
    _description = 'Import Pricelists Lines'

    data = fields.Binary('File', required=True)
    name = fields.Char('Filename')
    delimeter = fields.Char('Delimeter', default=',',
                            help='Default delimeter is ","')
    
    @api.multi
    def send_lines(self):
        """Load Sale Line data from the CSV file."""
        ctx = self.env.context
        cp_obj = self.env['product.pricelist']
        cp_line_obj = self.env['product.pricelist.line']
        product_obj = self.env['product.product']
        error_list = []
        raise_error = False

        cp = cp_obj
        if 'active_id' in ctx:
            cp = cp_obj.browse(ctx['active_id'])
        # Decode the file data
        data = base64.b64decode(self.data)
        file_input = cStringIO.StringIO(data)
        file_input.seek(0)
        reader_info = []
        if self.delimeter:
            delimeter = str(self.delimeter)
        else:
            delimeter = ','
        reader = csv.reader(file_input, delimiter=delimeter,lineterminator='\r\n')
        try:
            reader_info.extend(reader)
        except Exception:
            reader_info.extend(reader)
            raise exceptions.Warning(_("Not a valid file!"))
        keys = reader_info[0]
        # check if keys exist
        if not isinstance(keys, list) or ('Code' not in keys or
                                          'Rate' not in keys ):
            raise exceptions.Warning(
                _("Not 'Code' or 'Rate'  keys found"))
        del reader_info[0]
        values = {}
        
        for i in range(len(reader_info)):
            val = {}
            field = reader_info[i]
            values = dict(zip(keys, field))

            prod_lst = product_obj.search([('default_code', '=',values['Code'])])
            if prod_lst:
                if len(cp.pricelist_line_id):
                    prod_code = [x.default_code for x in cp.pricelist_line_id]
                    if  values['Code'] not in prod_code:
                        val['product_tmpl_id'] = prod_lst[0].product_tmpl_id.id
                        val['rate'] = values['Rate']
                        val['product_pricelist_id'] = cp.id
                else:
                    val['product_tmpl_id'] = prod_lst[0].product_tmpl_id.id
                    val['rate'] = values['Rate']
                    val['product_pricelist_id'] = cp.id
            else:
                error_list.append(values['Code'])
            
            # print errrorr
            cp_line_obj.create(val)
            
        quant_string = "\
Product(s) Not present in the System:\n\
Product \
"
            
        for error in error_list:
            raise_error = True
            quant_string += "\n%s " % (error)
            
        if raise_error:
            print "IIIIIIIIIIIIIIIIIIIIII Product Not present in the System"
            raise ValidationError(quant_string)
        
class WizardSupplierPricelistImport(models.TransientModel):
    _name = 'wizard.supplierpricelist.import'
    _description = 'Import Pricelists Lines'

    data = fields.Binary('File', required=True)
    name = fields.Char('Filename')
    delimeter = fields.Char('Delimeter', default=',',
                            help='Default delimeter is ","')    
    @api.multi
    def send_supplier_lines(self):
        """Load Supplier Pricelist Line data from the CSV file."""
        print "DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD"
        ctx = self.env.context
        sp_obj = self.env['product.supplierinfo']
        sp_line_obj = self.env['product.supplierinfo.line']
        product_obj = self.env['product.product']
        error_list = []
        raise_error = False

        sp = sp_obj
        if 'active_id' in ctx:
            sp = sp_obj.browse(ctx['active_id'])
        # Decode the file data
        
        
        data = base64.b64decode(self.data)
        file_input = cStringIO.StringIO(data)
        file_input.seek(0)
        reader_info = []
        if self.delimeter:
            delimeter = str(self.delimeter)
        else:
            delimeter = ','
        reader = csv.reader(file_input, delimiter=delimeter,lineterminator='\r\n')
        try:
            reader_info.extend(reader)
        except Exception:
            reader_info.extend(reader)
            raise exceptions.Warning(_("Not a valid file!"))
        keys = reader_info[0]
        # check if keys exist
        if not isinstance(keys, list) or ('Code' not in keys or
                                          'Rate' not in keys ):
            raise exceptions.Warning(
                _("Not 'Code' or 'Rate'  keys found"))
        del reader_info[0]
        values = {}
        
        for i in range(len(reader_info)):
            val = {}
            field = reader_info[i]
            values = dict(zip(keys, field))

            prod_lst = product_obj.search([('default_code', '=',values['Code'])])
            if prod_lst:
                if len(sp.supplierinfo_id):
                    prod_code = [x.default_code for x in sp.supplierinfo_id]
                    if  values['Code'] not in prod_code:
                        val['product_tmpl_id'] = prod_lst[0].product_tmpl_id.id
                        val['rate'] = values['Rate']
                        val['custom_lead_time'] = values['Custom LT']
                        val['delay'] = values['Delivery Lead Time']
                        val['moq'] = values['MOQ']
                        val['modvat_applicable'] = values['ModVAT'] 
                        val['product_supplierinfo_id'] = sp.id
                else:
                    val['product_tmpl_id'] = prod_lst[0].product_tmpl_id.id
                    val['rate'] = values['Rate']
                    val['custom_lead_time'] = values['Custom LT']
                    val['delay'] = values['Delivery Lead Time']
                    val['moq'] = values['MOQ']
                    val['modvat_applicable'] = values['ModVAT'] 
                    val['product_supplierinfo_id'] = sp.id
            else:
                error_list.append(values['Code'])
            
            # print errrorr
            sp_line_obj.create(val)
            
        quant_string = "\
Product(s) Not present in the System:\n\
Product \
"
            
        for error in error_list:
            raise_error = True
            quant_string += "\n%s " % (error)
            
        if raise_error:
            print "IIIIIIIIIIIIIIIIIIIIII Product Not present in the System"
            raise ValidationError(quant_string)
            
    
