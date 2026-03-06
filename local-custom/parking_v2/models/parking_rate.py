# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ParkingRate(models.Model):
    _name = 'parking2.rate'
    _description = 'Tarifa de Parqueo'
    _order = 'name asc'

    name = fields.Char(string='Nombre de Tarifa', required=True)
    rate_type = fields.Selection([
        ('hourly', 'Por Hora'),
        ('daily', 'Por Dia'),
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
        ('car', 'Automovil'),
        ('motorcycle', 'Motocicleta'),
        ('truck', 'Camion/Bus'),
        ('all', 'Todos'),
    ], string='Tipo de Vehiculo', default='all', required=True)

    # Minutos minimos a cobrar (ej: 60 = cobrar minimo 1 hora aunque salga antes)
    min_minutes = fields.Integer(string='Minutos Minimos a Cobrar', default=60)
    # Minutos de gracia: el carro puede salir en este tiempo sin pagar nada
    grace_minutes = fields.Integer(string='Minutos de Gracia', default=10)

    active = fields.Boolean(default=True)
    description = fields.Text(string='Descripcion / Condiciones')

    @api.constrains('price')
    def _check_price(self):
        for rate in self:
            if rate.price <= 0:
                raise ValidationError('El precio de la tarifa debe ser mayor a 0.')
