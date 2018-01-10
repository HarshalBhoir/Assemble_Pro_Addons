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


class handeling_unit_barcode(models.Model):
	_name = 'handeling.unit.barcode'
	_description = "Handeling Unit Barcode"
	_inherit = ['mail.thread', 'ir.needaction_mixin']
	_order = 'create_date desc'
	
	@api.model
	def _get_sequence(self):
		return self.env['ir.sequence'].search([('code','=','handeling.unit.barcode')]) or False

	name = fields.Char(string = "Handeling Unit Barcode No.")
	sale_id = fields.Many2one('sale.order',string="Contract No."  ,track_visibility='always')
	sequence_id = fields.Many2one('ir.sequence',string="Sequ ", default=_get_sequence)
	user_id = fields.Many2one('res.users', string='User', default=lambda self: self._uid, track_visibility='always')
	state = fields.Selection([
		('draft', 'Draft'),
		('done', 'Done'),
		], string='Status', readonly=True,
		copy=False, index=True, track_visibility='always', default='draft')
	sequence = fields.Char(string="Serial No")
	company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('sales.declaration'))

	attachment_id = fields.Many2one( 'ir.attachment', string="Attachment", ondelete='cascade')
	
	hlcp_no = fields.Char(string = "")
	hlcp_barcode = fields.Char(string = "")
	commission_no = fields.Char(string = "")
	box_name = fields.Char(string = "")
	box_code_name = fields.Char(string = "")
	po_no = fields.Char(string = "")
	sup_po_no = fields.Char(string = "")
	purchase_order_no = fields.Char(string = "")
	purchase_order_barcode = fields.Char(string = "")
	supplier_ref_no = fields.Char(string = "")
	
	@api.multi
	def unlink(self):
		for order in self:
			if order.state != 'draft':
				raise UserError(_('You can only delete Draft Entries'))
		return super(handeling_unit_barcode, self).unlink()
	
	@api.onchange('sequence_id')
	def onchange_sequence_id(self):
		self.sequence = self.sequence_id and self.sequence_id.number_next
	
	@api.model
	def create(self, vals):
		vals['name'] = self.env['ir.sequence'].next_by_code('handeling.unit.barcode.name')
		result = super(handeling_unit_barcode, self).create(vals)
		return result
	
	@api.multi
	def get_sequence_barcode(self):
		curr_sequence = str(self.sequence).zfill(10)
		self.sequence = str(int(self.sequence) + 1).zfill(10)
		self.sequence_id.sudo().number_next = int(self.sequence)
		return curr_sequence
	
	@api.multi
	def print_handeling_unit_barcode(self):
		day = datetime.today().strftime('%y')
		self.hlcp_no = "HLCP"+str(self.sequence).zfill(10)
		self.hlcp_barcode = "H-HLCP"+str(self.sequence).zfill(10)
		box_code_name = box_name = ''
		for record in self.sale_id.product_packaging_one2many:
			box_code_name = record.code_name
			self.box_name = record.name.name
			
		po_no = str(self.sale_id.po_order).split('/')
		sup_po_no = ''.join(po_no[0].strip())
		self.purchase_order_no = sup_po_no
		if box_code_name:
			self.purchase_order_barcode = "P"+sup_po_no+box_code_name
		else:
			raise UserError(_('Box Code is Missing in this Sale Order'))
		self.commission_no = self.sale_id.name
		self.supplier_ref_no = self.sale_id.client_order_ref
		self.state ='done'
		return self.env['report'].get_action(self, 'assemble_pro.handeling_unit_barcode_template')
