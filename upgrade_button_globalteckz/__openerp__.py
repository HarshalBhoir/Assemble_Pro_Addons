 # -*- coding: utf-8 -*-
##############################################################################
#
#    Globalteckz Pvt Ltd
#    Copyright (C) 2013-Today(www.globalteckz.com).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    'name': 'Upgrade button from kanban view',
    'version': '1.0',
    'category': 'Extra Tools',
    'sequence': 2,
    'summary': 'Upgrade your module using Kanban view without going in form view',
    'images': ['static/description/upgrade_banner.png'],
    'description': '''
Set Upgrade Button in kanban view if app is installed

''',
    'author': 'Globalteckz',
    'website': 'http://www.globalteckz.com/',
    'depends': ['base','web'],
    'data': [
        'upgrade_button_view.xml',
            ],
    'demo': [],
    'test': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
