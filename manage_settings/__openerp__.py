{
    'name': 'Adds Manage / Hide Settings & Apps',
    'version': '1.0',
    'author': 'Vinay Gharat',
    'sequence': 1,
    'category': 'Administration',
    'description': """
Adds Manage menu and make Settings & Apps menu visible to SuperAdmin only
""",
    'depends': [
        'web',
        'base',
        'mail',
        'fetchmail',
    ],
    'data': [
        'security/security.xml',
        'views/actions.xml',
        'views/menus.xml',
    ],
    'qweb': [
    ],
    'installable' : True,
    'application' : False,
    'auto_install' : True,
}