# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ParkingSpot(models.Model):
    _name = 'parking2.spot'
    _description = 'Espacio de Parqueo'
    _order = 'name asc'

    name = fields.Char(string='Numero de Espacio', required=True)
    description = fields.Char(string='Descripcion')
    floor = fields.Char(string='Nivel/Piso', default='1')
    zone = fields.Char(string='Zona')

    spot_type = fields.Selection([
        ('standard', 'Estandar'),
        ('handicapped', 'Discapacitados'),
        ('motorcycle', 'Motocicleta'),
        ('large', 'Vehiculo Grande'),
        ('vip', 'VIP'),
    ], string='Tipo de Espacio', default='standard', required=True)

    state = fields.Selection([
        ('available', 'Disponible'),
        ('occupied', 'Ocupado'),
        ('reserved', 'Reservado'),
        ('maintenance', 'Mantenimiento'),
    ], string='Estado', default='available', required=True)

    current_ticket_id = fields.Many2one('parking2.ticket', string='Ticket Activo', readonly=True)
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Observaciones')

    ticket_count = fields.Integer(string='Total Tickets', compute='_compute_ticket_count')

    def _compute_ticket_count(self):
        for spot in self:
            spot.ticket_count = self.env['parking2.ticket'].search_count([
                ('spot_id', '=', spot.id)
            ])

    def action_set_maintenance(self):
        for spot in self:
            if spot.state == 'occupied':
                raise ValidationError('No puede poner en mantenimiento un espacio ocupado.')
            spot.state = 'maintenance'

    def action_set_available(self):
        for spot in self:
            spot.state = 'available'
            spot.current_ticket_id = False

    def action_view_tickets(self):
        return {
            'name': 'Tickets del Espacio %s' % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'parking2.ticket',
            'view_mode': 'tree,form',
            'domain': [('spot_id', '=', self.id)],
        }

    @api.constrains('name')
    def _check_unique_name(self):
        for spot in self:
            if self.search([('name', '=', spot.name), ('id', '!=', spot.id)]):
                raise ValidationError('Ya existe un espacio con el nombre "%s".' % spot.name)
