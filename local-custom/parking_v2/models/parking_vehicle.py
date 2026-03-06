# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ParkingVehicle(models.Model):
    _name = 'parking2.vehicle'
    _description = 'Vehiculo Registrado'
    _order = 'plate asc'
    _rec_name = 'plate'

    plate = fields.Char(string='Placa', required=True)
    owner_name = fields.Char(string='Nombre del Propietario', required=True)
    owner_phone = fields.Char(string='Telefono del Propietario')
    owner_id_number = fields.Char(string='DPI / Cedula')

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
        'parking2.rate', string='Tarifa Mensual',
        domain=[('rate_type', '=', 'monthly')],
    )
    monthly_expiry = fields.Date(string='Vence Mensualidad')

    active = fields.Boolean(default=True)
    notes = fields.Text(string='Observaciones')

    # ─── Estadisticas (compute sin store, solo para mostrar) ──────────────────
    ticket_count = fields.Integer(string='Total Visitas', compute='_compute_stats')
    completed_visits = fields.Integer(string='Visitas Completadas', compute='_compute_stats')
    last_visit = fields.Datetime(string='Ultima Visita', compute='_compute_stats')
    is_currently_parked = fields.Boolean(string='En Parqueo Ahora', compute='_compute_stats')

    # ─── Cliente Frecuente ────────────────────────────────────────────────────
    # Categorias segun visitas completadas (tickets con state='done'):
    #   Nuevo     0-4   visitas  → 0% descuento
    #   Regular   5-19  visitas  → 5% descuento
    #   Frecuente 20-49 visitas  → 10% descuento
    #   VIP       50+   visitas  → 15% descuento
    customer_category = fields.Selection([
        ('new', 'Nuevo'),
        ('regular', 'Regular'),
        ('frequent', 'Frecuente'),
        ('vip', 'VIP'),
    ], string='Categoria', compute='_compute_customer_category')

    discount_percent = fields.Float(
        string='Descuento (%)',
        compute='_compute_customer_category'
    )

    def _compute_stats(self):
        for vehicle in self:
            if not vehicle.id:
                vehicle.ticket_count = 0
                vehicle.completed_visits = 0
                vehicle.last_visit = False
                vehicle.is_currently_parked = False
                continue
            tickets = self.env['parking2.ticket'].search([('vehicle_id', '=', vehicle.id)])
            vehicle.ticket_count = len(tickets)
            done = tickets.filtered(lambda t: t.state == 'done')
            vehicle.completed_visits = len(done)
            vehicle.last_visit = max(done.mapped('exit_time')) if done else False
            vehicle.is_currently_parked = any(t.state == 'open' for t in tickets)

    def _compute_customer_category(self):
        for vehicle in self:
            count = self.env['parking2.ticket'].search_count([
                ('vehicle_id', '=', vehicle.id),
                ('state', '=', 'done'),
            ])
            if count >= 50:
                vehicle.customer_category = 'vip'
                vehicle.discount_percent = 15.0
            elif count >= 20:
                vehicle.customer_category = 'frequent'
                vehicle.discount_percent = 10.0
            elif count >= 5:
                vehicle.customer_category = 'regular'
                vehicle.discount_percent = 5.0
            else:
                vehicle.customer_category = 'new'
                vehicle.discount_percent = 0.0

    def name_get(self):
        result = []
        for v in self:
            name = v.plate or ''
            if v.owner_name:
                name += ' - ' + v.owner_name
            if v.brand:
                name += ' (' + v.brand + ((' ' + v.model) if v.model else '') + ')'
            result.append((v.id, name))
        return result

    @api.constrains('plate')
    def _check_unique_plate(self):
        for vehicle in self:
            if self.search([('plate', '=ilike', vehicle.plate), ('id', '!=', vehicle.id)]):
                raise ValidationError(
                    'Ya existe un vehiculo con la placa "%s".' % vehicle.plate
                )

    def action_view_tickets(self):
        return {
            'name': 'Historial de %s' % self.plate,
            'type': 'ir.actions.act_window',
            'res_model': 'parking2.ticket',
            'view_mode': 'tree,form',
            'domain': [('vehicle_id', '=', self.id)],
        }
