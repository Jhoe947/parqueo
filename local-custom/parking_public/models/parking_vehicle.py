# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ParkingVehicle(models.Model):
    _name = 'parking.vehicle'
    _description = 'Vehiculo Registrado'
    _order = 'plate asc'
    _rec_name = 'plate'

    plate = fields.Char(string='Placa', required=True)
    owner_name = fields.Char(string='Nombre del Propietario', required=True)
    owner_phone = fields.Char(string='Telefono del Propietario')
    owner_id_number = fields.Char(string='DPI / Cedula del Propietario')

    vehicle_type = fields.Selection([
        ('car', 'Automovil'),
        ('motorcycle', 'Motocicleta'),
        ('truck', 'Camion/Bus'),
    ], string='Tipo de Vehiculo', required=True, default='car')

    brand = fields.Char(string='Marca')
    model = fields.Char(string='Modelo')
    color = fields.Char(string='Color')
    year = fields.Integer(string='Anio')

    is_monthly = fields.Boolean(string='Suscripcion Mensual', default=False)
    monthly_rate_id = fields.Many2one(
        'parking.rate',
        string='Tarifa Mensual',
        domain=[('rate_type', '=', 'monthly')],
    )
    monthly_expiry = fields.Date(string='Vence Mensualidad')

    active = fields.Boolean(default=True)
    notes = fields.Text(string='Observaciones')

    ticket_count = fields.Integer(
        string='Total de Visitas',
        compute='_compute_ticket_count',
        store=False
    )

    # store=False porque depende de tickets externos — solo para mostrar en form/list
    is_currently_parked = fields.Boolean(
        string='En Parqueo Ahora',
        compute='_compute_is_parked',
        store=False
    )

    @api.depends('plate')
    def _compute_ticket_count(self):
        for vehicle in self:
            vehicle.ticket_count = self.env['parking.ticket'].search_count([
                ('vehicle_id', '=', vehicle.id)
            ])

    def _compute_is_parked(self):
        for vehicle in self:
            if not vehicle.id:
                vehicle.is_currently_parked = False
                continue
            active_ticket = self.env['parking.ticket'].search([
                ('vehicle_id', '=', vehicle.id),
                ('state', '=', 'open'),
            ], limit=1)
            vehicle.is_currently_parked = bool(active_ticket)

    def name_get(self):
        result = []
        for vehicle in self:
            name = vehicle.plate or ''
            if vehicle.owner_name:
                name += ' - ' + vehicle.owner_name
            if vehicle.brand:
                name += ' (' + vehicle.brand
                if vehicle.model:
                    name += ' ' + vehicle.model
                name += ')'
            result.append((vehicle.id, name))
        return result

    @api.constrains('plate')
    def _check_unique_plate(self):
        for vehicle in self:
            duplicate = self.search([
                ('plate', '=ilike', vehicle.plate),
                ('id', '!=', vehicle.id)
            ])
            if duplicate:
                raise ValidationError(
                    'Ya existe un vehiculo registrado con la placa "%s".' % vehicle.plate
                )

    def action_view_tickets(self):
        return {
            'name': 'Historial de %s' % self.plate,
            'type': 'ir.actions.act_window',
            'res_model': 'parking.ticket',
            'view_mode': 'tree,form',
            'domain': [('vehicle_id', '=', self.id)],
        }
