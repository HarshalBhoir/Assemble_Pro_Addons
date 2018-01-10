from openerp import models, fields, api, tools, _
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
from openerp.exceptions import UserError, MissingError, ValidationError
from openerp.tools import amount_to_text_en

class account_invoice_line_extension(models.Model):
	_inherit = 'account.invoice.line'
	
	@api.multi
	def get_tax(self):
		value = {'SGST':('',''),'CGST':('',''),'IGST':('','')}
		for tax in self.invoice_line_tax_ids:
			if "CGST" in tax.name:
				value['CGST'] = (tax.description,float(self.price_subtotal)*float(tax.amount)/100)
			if "SGST" in tax.name:
				value['SGST'] = (tax.description,float(self.price_subtotal)*float(tax.amount)/100)
			if "IGST" in tax.name:
				value['IGST'] = (tax.description,float(self.price_subtotal)*float(tax.amount)/100)
		
		return value

	
