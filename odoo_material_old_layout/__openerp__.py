{
    'name': 'Odoo Material Theme with Old Layout by AQUAGiraffe',
    'version': '1.0',
    'author': 'Vinay Gharat (AQUAGiraffe - An MSP1 Company)',
    'sequence': 1,
    'category': 'UI',
    'description': """
Odoo Material Theme with Old Layout
""",
    'depends': ['web'],
    'data': [
        'views/odoo_material_old_layout.xml',
        'views/design_material.xml',
    ],
    'bootstrap': True,
    'installable' : True,
    'application' : True,
}