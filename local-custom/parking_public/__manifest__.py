# -*- coding: utf-8 -*-
{
    'name': 'Parqueo Público',
    'version': '17.0.1.0.0',
    'summary': 'Gestión de Parqueo Público - Control de espacios, vehículos y tarifas',
    'description': """
        Módulo completo para la gestión de un parqueo público:
        - Control de espacios (disponible, ocupado, reservado, mantenimiento)
        - Registro de vehículos con datos del propietario
        - Tarifas por hora, día y mes
        - Tickets de entrada/salida con cálculo automático
        - Validaciones de negocio reales
        - Reportes de ocupación
    """,
    'category': 'Services',
    'author': 'jo',
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
    'images': [],
}
