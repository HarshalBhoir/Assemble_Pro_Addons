#
# Web Debranding by Aqua-Giraffe
#

{
	'name': "Web Debranding",
	'version': '1.0',
	'author': 'Vinay Gharat (Aqua-Giraffe - An MSP1 Company)',
	'category': 'Custom Development',
	'website': 'http://www.aqua-giraffe.com',
	# 'license': 'LGPL-3',
	# 'price': 3999.00,
	# 'currency': 'INR',
	'depends': [
		'web',
		'mail',
		'web_planner',
	],
	'data': [
		'security/web_debranding_security.xml',
		'security/ir.model.access.csv',
		'views/web_debranding.xml',
		'views/debranding_settings.xml',
		],
	'qweb': [
		'static/src/xml/web_debranding.xml',
	],
	'auto_install': False,
	# 'uninstall_hook': 'uninstall_hook',
	'application': True,
	'installable': True,
}
