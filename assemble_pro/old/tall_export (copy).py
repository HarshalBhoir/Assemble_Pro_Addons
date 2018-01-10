from openerp.exceptions import UserError, MissingError, ValidationError
import csv
import base64
import decimal
import openerp

from openerp import models, fields, api, _, tools
from openerp.exceptions import UserError
from datetime import datetime
import datetime
import time
import logging
from openerp.tools import float_is_zero,openerp,image_colorize, image_resize_image_big
import re , collections
from openerp import http
from openerp.addons.web.controllers.main import serialize_exception,content_disposition
from openerp.http import request, serialize_exception as _serialize_exception
from cStringIO import StringIO
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
	
	
	@api.model
	def create(self, vals):
		vals['name'] = self.env['ir.sequence'].next_by_code('tally.export')
		# vals['state'] = 'done'
		result = super(tally_export, self).create(vals)
		return result
	

	@api.multi
	def export_data(self):
		# con_cat ='LIFTUNIT1.ETF'
		text_file = open("LIFTUNIT1.ETF", "w")
		main_string = ""
		invoice_ids = self.env['account.invoice'].search([('date_invoice','<=',self.date_start),('date_invoice','>=',self.date_end)])
		for invoices in invoice_ids:
			if 'SO' in invoices.origin:
				tax_string = ""
				for taxes in invoices.tax_line_ids:
					# print "SSSSSSSSSSSSSSSS" , taxes.name ,  taxes.amount
					if taxes.name and taxes.amount:
						tax_string = tax_string + "|"+str(taxes.name)+";"+";"+str(taxes.amount)
						# print "bbbbbbbbbbbbbbb taxes" ,tax_string # taxes.name ,  taxes.amount
		# self.state = 'done'
				sale_string = "Sales|"+str(invoices.number)+"|"+str(invoices.company_id.name)+"|:"+str(invoices.company_id.name)+";"+";"+str(invoices.amount_untaxed)
				main_string = sale_string + tax_string
		text_file.write(main_string)
		text_file.close()
		print 'AAAAAAAAAAAAAAAAAAAAAA \n ' , main_string , text_file
		
		# fp = StringIO()
		# main_string.save(fp)
		# fp.seek(0)
		# data = fp.read()
		# fp.close()
		encoded_data = base64.encodestring(main_string)
		# local_tz = pytz.timezone(self._context.get('tz') or 'UTC')
		attach_vals = {
			'name':'LIFTUNIT1',
			'datas':encoded_data,
			'datas_fname':'LIFTUNIT1.ETF',
			'res_model':'ir.attachment',
		}
		doc_id = self.env['ir.attachment'].create(attach_vals)
		# self.attachment_id = doc_id.id
		
		return {
			'type' : 'ir.actions.act_url',
			'url': '/web/binary/download_document?model=%s&field=%s&id=%s&filename=%s.ETF' % (doc_id.res_model,'datas',doc_id.id,doc_id.name),
			'target': 'self',
			}
				
				# print "AAAAAAAiiiiii" , invoices , invoices.partner_id.name , invoices.origin , invoices.company_id.name ,invoices.number
		# rm_ids = self.mapped('advance_rm_material_id')
		# if len(rm_ids):
		# 	self.attach_doc_count = len(rm_ids) or 0
			
	@api.multi
	def cancel(self):
		print "BBBBBBBAAAAAAAAAABBBBBBBBBBBAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
		# rm_ids = self.mapped('advance_rm_material_id')
		# if len(rm_ids):
		# 	self.attach_doc_count = len(rm_ids) or 0