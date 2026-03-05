# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ParkingRate(models.Model):
    _name = 'parking.rate'
    _description = 'Tarifa de Parqueo'
    _order = 'name asc'

    name = fields.Char(string='Nombre de Tarifa', required=True)
    rate_type = fields.Selection([
        ('hourly', 'Por Hora'),
        ('daily', 'Por Día'),
        ('monthly', 'Por Mes'),
        ('event', 'Evento Especial'),
    ], string='Tipo de Tarifa', required=True, default='hourly')

    price = fields.Float(string='Precio', required=True, digits=(10, 2))
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id
    )

    vehicle_type = fields.Selection([
        ('car', 'Automóvil'),
        ('motorcycle', 'Motocicleta'),
        ('truck', 'Camión/Bus'),
        ('all', 'Todos'),
    ], string='Tipo de Vehículo', default='all', required=True)

    # Para tarifa por hora: precio de las primeras N horas (fracción)
    min_minutes = fields.Integer(
        string='Minutos Mínimos a Cobrar',
        default=60,
        help='Tiempo mínimo de cobro. Ej: 60 min = cobrar mínimo 1 hora aunque salga antes.'
    )
    grace_minutes = fields.Integer(
        string='Minutos de Gracia',
        default=10,
        help='Minutos de tolerancia al ingresar sin cobro. Ej: 10 minutos gratis.'
    )

    active = fields.Boolean(default=True)
    description = fields.Text(string='Descripción / Condiciones')

    @api.constrains('price')
    def _check_price(self):
        for rate in self:
            if rate.price <= 0:
                raise ValidationError(_('El precio de la tarifa debe ser mayor a 0.'))

    def get_display_price(self):
        labels = {
            'hourly': 'hora',
            'daily': 'día',
            'monthly': 'mes',
            'event': 'evento',
        }
        return f"{self.currency_id.symbol}{self.price:.2f} / {labels.get(self.rate_type, '')}"
