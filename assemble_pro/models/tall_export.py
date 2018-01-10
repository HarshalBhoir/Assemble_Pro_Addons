from openerp.exceptions import UserError, MissingError, ValidationError
import csv
import base64
import decimal
import openerp

from openerp import models, fields, api, _, tools
from openerp.exceptions import UserError
from datetime import datetime
# import datetime
import time
import logging
from openerp.tools import float_is_zero,openerp,image_colorize, image_resize_image_big
import re , collections
from openerp import http
from openerp.addons.web.controllers.main import serialize_exception,content_disposition
from openerp.http import request, serialize_exception as _serialize_exception
from cStringIO import StringIO
import xlwt

import pytz

# from datetime import date
# import pandas
from collections import Counter
import openerp.addons.decimal_precision as dp

class Binary(http.Controller):
	
	@http.route('/web/binary/download_document', type='http', auth="public")
	@serialize_exception
	def download_document(self,model,field,id,filename=None, **kw):
		""" Download link for files stored as binary fields.
		:param str model: name of the model to fetch the binary from
		:param str field: binary field
		:param str id: id of the record from which to fetch the binary
		:param str filename: field holding the file's name, if any
		:returns: :class:`werkzeug.wrappers.Response`
		"""
		Model = request.registry[model]
		cr, uid, context = request.cr, request.uid, request.context
		fields = [field]
		res = Model.read(cr, uid, [int(id)], fields, context)[0]
		filecontent = base64.b64decode(res.get(field) or '')
		if not filecontent:
			 return request.not_found()
		else:
			if not filename:
				filename = '%s_%s' % (model.replace('.', '_'), id)
			return request.make_response(filecontent,[
					('Content-Disposition', content_disposition(filename)),
					# ('Content-Type', 'application/vnd.ms-excel'),
					('Content-Type', 'application/octet-stream'),
					('Content-Length', len(filecontent))
			])


class tally_export(models.Model):
	_name = 'tally.export'
	_description = "Tally Export"
	_inherit = ['mail.thread', 'ir.needaction_mixin']
	_order = 'create_date desc'
	
	name = fields.Char(string = "Export No.")
	data = fields.Binary(string="Unit 1 File")
	date_start = fields.Date(string="From Date")
	date_end = fields.Date(string="To Date")
	data_path = fields.Char(string="Data Path")
	user_id = fields.Many2one('res.users', string='User', default=lambda self: self._uid, track_visibility='always')
	state = fields.Selection([
		('draft', 'Draft'),
		('done', 'Exported'),
		('cancel', 'Cancelled'),
		], string='Status', readonly=True,
		copy=False, index=True, track_visibility='always', default='draft')
	company_id = fields.Many2one('res.company', string='Company', track_visibility='always')
	voucher_type = fields.Selection([
		('SO', 'Sale'),
		('PO', 'Purchase'),
		], string='Type Of Voucher', track_visibility='always')
	attachment_id = fields.Many2one( 'ir.attachment', string="Attachment", ondelete='cascade')
	datas = fields.Binary(string="XLS Report", related="attachment_id.datas")
	display_address = fields.Char(string="Name", compute="_name_get" , store=True)
	
	@api.multi
	def unlink(self):
		for order in self:
			if order.state != 'draft':
				raise UserError(_('You can only delete Draft Entries'))
		return super(tally_export, self).unlink()
	

	@api.multi
	@api.depends('name','company_id')
	def _name_get(self):
		address = str(self.company_id.street)  + str(self.company_id.street) +","+ str(self.company_id.city) +","+  str(self.company_id.state_id.name)+","+  str(self.company_id.zip)
		self.display_address = address
	

	@api.model
	def create(self, vals):
		vals['name'] = self.env['ir.sequence'].next_by_code('tally.export')
		result = super(tally_export, self).create(vals)
		return result
	
	@api.constrains('date_start','date_end','company_id','voucher_type')
	def constraints_check(self):
		if self.date_start and self.date_end and self.date_start > self.date_end:
			raise UserError("Please select a valid date range")
		if not self.company_id:
			raise UserError("Please select a Company")
		if not self.voucher_type:
			raise UserError("Please select Type Of Voucher")
		

	@api.multi
	def export_data(self):

		main_string2 = file_name = ""
		invoice_ids = self.env['account.invoice'].search([('date_invoice','>=',self.date_start),('date_invoice','<=',self.date_end)])
		
		if invoice_ids:
			for invoices in invoice_ids:
				if self.company_id.id == invoices.company_id.id:
					if invoices.company_id.id == 1:
						file_name ='LIFTUNIT1'
					else:
						file_name ='LIFTUNIT2'
						
					invoice_date = datetime.strptime(invoices.date_invoice, '%Y-%m-%d').strftime('%d-%m-%Y')
					if invoices.type == "out_invoice" and self.voucher_type=="SO": #"in_refund","out_refund"
						
						# move_ids = self.env['account.move'].search([('ref','=',invoices.origin)])
						# print "OOOOOOOOOOOOOOOOOOOOO" , move_ids
						# # print "AAAAAAAAAAAAAAAAAAAAAAAA" ,invoices.origin , move_ids
						# customer_amt = payment_amt = 0
						# for move_line in move_ids:
						# 	print "OOOOOOOOOOOOOOOOOOOOO" , move_ids , move_line.name , invoices.origin
						# 	# print "DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD" , move_line.ref , move_line.amount , move_line.name , move_line.journal_id.name
						# 	if 'Customer Invoices' in move_line.journal_id.name:
						# 		# print "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB" , move_line.id , move_line.name
						# 		customer_amt = move_line.amount
						# 	else:
						# 		payment_amt = move_line.amount
						# 		
						# roundoff_amt = payment_amt - customer_amt
						# roundoff_string = ""
						# if roundoff_amt:
						# 	roundoff_string = "|Round off"+";"+";"+";"+str(roundoff_amt)
						# print "UUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUU" , roundoff_amt , move_ids , move_line.name , invoices.origin
						tax_string = ""
						freight_string = ""
						
						if invoices.carrier_id:
							freight_string = "|FREIGHT ON SALE;NO;NO;"+str(invoices.amount_freight)

						for taxes in invoices.tax_line_ids:
							if taxes.name and taxes.amount:
								tax_string = tax_string + "|"+str(taxes.tax_id.tally_acc)+";NO;NO;"+str(taxes.amount)
								
						roundoff_amt = round(invoices.amount_total) - invoices.amount_total
						roundoff_string = ""
						if roundoff_amt:
							factor =""
							if roundoff_amt < 0:
								factor = "YES"
							else:
								factor ="NO"
							roundoff_string = "|Round off"+";"+factor+";NO;"+str(round(roundoff_amt,2))
						
		
						sale_string = "Sales|"+str(invoice_date)+"|"+str(invoices.number)+"|"+str(invoices.partner_id.name)+"|:"+str(invoices.partner_id.name)+";YES;YES;"+"-"+str(round(invoices.amount_total)) + '|Inter-State Sales'+";NO;NO;"+str(invoices.amount_untaxed)
						main_string = sale_string + tax_string + freight_string + roundoff_string + "\n" #
						main_string2 = main_string2 +  main_string
						
					if invoices.type == "in_invoice"  and self.voucher_type=="PO":
						tax_string = ""
						for taxes in invoices.tax_line_ids:
							if taxes.name and taxes.amount:
								tax_string = tax_string + "|"+str(taxes.tax_id.tally_acc)+";NO;NO;"+str(taxes.amount)
						
						roundoff_amt = round(invoices.amount_total) - invoices.amount_total
						roundoff_string = ""
						if roundoff_amt:
							factor =""
							if roundoff_amt < 0:
								factor = "YES"
							else:
								factor ="NO"
							roundoff_string = "|Round off"+";"+factor+";NO;"+str(round(roundoff_amt,2))
		
						purchase_string = "Purchase|"+str(invoice_date)+"|"+str(invoices.number)+"|"+str(invoices.partner_id.name)+"|:"+str(invoices.partner_id.name)+";"+";"+";"+"-"+str(invoices.amount_total) + '|Purchase Against  Form C'+";"+";"+";"+str(invoices.amount_untaxed)
						main_string = purchase_string + tax_string + roundoff_string + "\n"
						main_string2 = main_string2 +  main_string
		print "LLLLLLLLLLLLLLLLLLL" , main_string2
		if main_string2:
			encoded_data = base64.encodestring(main_string2)
		else:
			raise ValidationError('%s is not present in the System '% (self.voucher_type))
		attach_vals = {
			# 'name':'LIFTUNIT1'+" ("+self.create_date+")"+"("+self.voucher_type+")",
			'name':file_name,
			'datas':encoded_data,
			'datas_fname':'LIFTUNIT1.ETF',
			'res_model':'ir.attachment',
		}
		doc_id = self.env['ir.attachment'].create(attach_vals)
		self.state ='done'
		print "OOOOOOOOOOOOOOOOOOOOOOOOOOOO" , self.state
		# print eree
		return {
			'type' : 'ir.actions.act_url',
			'url': '/web/binary/download_document?model=%s&field=%s&id=%s&filename=%s.ETF' % (doc_id.res_model,'datas',doc_id.id,doc_id.name),
			'target': 'self',
			}