# -*- coding: utf-8 -*-
{
    'name': 'Parqueo V2',
    'version': '17.0.2.0.0',
    'summary': 'Gestion de Parqueo Publico - Version 2',
    'category': 'Services',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/parking_data.xml',
        'views/parking_spot_views.xml',
        'views/parking_rate_views.xml',
        'views/parking_vehicle_views.xml',
        'views/parking_ticket_views.xml',
        'views/parking_menu.xml',
        'report/parking_ticket_report.xml',
        'report/parking_ticket_template.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
