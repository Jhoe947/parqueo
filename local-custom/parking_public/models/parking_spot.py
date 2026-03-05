# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ParkingSpot(models.Model):
    _name = 'parking.spot'
    _description = 'Espacio de Parqueo'
    _order = 'name asc'

    name = fields.Char(
        string='Número de Espacio',
        required=True,
        help='Identificador del espacio. Ej: A-01, B-12'
    )
    description = fields.Char(string='Descripción', help='Descripción adicional del espacio')
    floor = fields.Char(string='Nivel/Piso', default='1')
    zone = fields.Char(string='Zona', help='Zona del parqueo. Ej: A, B, VIP')

    spot_type = fields.Selection([
        ('standard', 'Estándar'),
        ('handicapped', 'Discapacitados'),
        ('motorcycle', 'Motocicleta'),
        ('large', 'Vehículo Grande'),
        ('vip', 'VIP'),
    ], string='Tipo de Espacio', default='standard', required=True)

    state = fields.Selection([
        ('available', 'Disponible'),
        ('occupied', 'Ocupado'),
        ('reserved', 'Reservado'),
        ('maintenance', 'Mantenimiento'),
    ], string='Estado', default='available', required=True, tracking=True)

    current_ticket_id = fields.Many2one(
        'parking.ticket',
        string='Ticket Activo',
        readonly=True
    )

    active = fields.Boolean(default=True)
    notes = fields.Text(string='Observaciones')

    # Estadísticas
    ticket_count = fields.Integer(
        string='Total Tickets',
        compute='_compute_ticket_count'
    )

    @api.depends('name')
    def _compute_ticket_count(self):
        for spot in self:
            spot.ticket_count = self.env['parking.ticket'].search_count([
                ('spot_id', '=', spot.id)
            ])

    def action_set_maintenance(self):
        for spot in self:
            if spot.state == 'occupied':
                raise ValidationError(_('No puede poner en mantenimiento un espacio ocupado.'))
            spot.state = 'maintenance'

    def action_set_available(self):
        for spot in self:
            spot.state = 'available'
            spot.current_ticket_id = False

    def action_view_tickets(self):
        return {
            'name': _('Tickets del Espacio %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'parking.ticket',
            'view_mode': 'list,form',
            'domain': [('spot_id', '=', self.id)],
            'context': {'default_spot_id': self.id},
        }

    @api.constrains('name')
    def _check_unique_name(self):
        for spot in self:
            duplicate = self.search([
                ('name', '=', spot.name),
                ('id', '!=', spot.id)
            ])
            if duplicate:
                raise ValidationError(_('Ya existe un espacio con el nombre "%s".') % spot.name)

    def _get_state_color(self):
        colors = {
            'available': 'success',
            'occupied': 'danger',
            'reserved': 'warning',
            'maintenance': 'secondary',
        }
        return colors.get(self.state, 'primary')
