# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import math


class ParkingTicket(models.Model):
    _name = 'parking.ticket'
    _description = 'Ticket de Parqueo'
    _order = 'entry_time desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ─── Identificación ───────────────────────────────────────────────────────
    name = fields.Char(
        string='Número de Ticket',
        readonly=True,
        copy=False,
        default='Nuevo'
    )

    # ─── Relaciones principales ───────────────────────────────────────────────
    spot_id = fields.Many2one(
        'parking.spot',
        string='Espacio de Parqueo',
        required=True,
        tracking=True,
        domain=[('state', 'in', ['available', 'reserved'])]
    )
    vehicle_id = fields.Many2one(
        'parking.vehicle',
        string='Vehículo',
        required=True,
        tracking=True
    )
    rate_id = fields.Many2one(
        'parking.rate',
        string='Tarifa Aplicada',
        required=True,
        tracking=True
    )

    # Campos de solo lectura del vehículo (para el ticket impreso)
    owner_name = fields.Char(
        string='Propietario',
        related='vehicle_id.owner_name',
        store=True
    )
    plate = fields.Char(
        string='Placa',
        related='vehicle_id.plate',
        store=True
    )

    # ─── Tiempos ──────────────────────────────────────────────────────────────
    entry_time = fields.Datetime(
        string='Hora de Entrada',
        required=True,
        default=fields.Datetime.now,
        tracking=True
    )
    exit_time = fields.Datetime(
        string='Hora de Salida',
        readonly=True,
        tracking=True
    )
    expected_exit = fields.Datetime(
        string='Salida Estimada',
        help='Fecha/hora estimada de salida (para reservas mensuales o por día)'
    )

    # ─── Duración y costos ────────────────────────────────────────────────────
    duration_hours = fields.Float(
        string='Duración (horas)',
        compute='_compute_duration',
        store=True,
        digits=(10, 2)
    )
    duration_display = fields.Char(
        string='Tiempo en Parqueo',
        compute='_compute_duration',
        store=False
    )
    amount_total = fields.Float(
        string='Total a Pagar',
        compute='_compute_amount',
        store=True,
        digits=(10, 2),
        tracking=True
    )
    amount_paid = fields.Float(
        string='Monto Pagado',
        digits=(10, 2),
        tracking=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='rate_id.currency_id',
        string='Moneda'
    )

    # ─── Estado ───────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('open', 'Activo / En Parqueo'),
        ('done', 'Cerrado / Salió'),
        ('cancelled', 'Anulado'),
    ], string='Estado', default='open', required=True, tracking=True)

    # ─── Info adicional ───────────────────────────────────────────────────────
    user_id = fields.Many2one(
        'res.users',
        string='Registrado por',
        default=lambda self: self.env.user,
        readonly=True
    )
    cashier_exit_id = fields.Many2one(
        'res.users',
        string='Cajero de Salida',
        readonly=True
    )
    notes = fields.Text(string='Observaciones')
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        readonly=True
    )

    # ─── Cómputos ─────────────────────────────────────────────────────────────
    @api.depends('entry_time', 'exit_time', 'state')
    def _compute_duration(self):
        now = fields.Datetime.now()
        for ticket in self:
            end = ticket.exit_time if ticket.exit_time else now
            if ticket.entry_time and end >= ticket.entry_time:
                delta = end - ticket.entry_time
                total_seconds = delta.total_seconds()
                hours = total_seconds / 3600
                ticket.duration_hours = round(hours, 4)

                # Formato legible: 2h 35min
                h = int(total_seconds // 3600)
                m = int((total_seconds % 3600) // 60)
                ticket.duration_display = f"{h}h {m:02d}min"
            else:
                ticket.duration_hours = 0.0
                ticket.duration_display = "0h 00min"

    @api.depends('duration_hours', 'rate_id', 'entry_time', 'exit_time', 'state')
    def _compute_amount(self):
        for ticket in self:
            if not ticket.rate_id:
                ticket.amount_total = 0.0
                continue

            rate = ticket.rate_id
            hours = ticket.duration_hours

            if rate.rate_type == 'hourly':
                # Aplicar minutos de gracia
                grace_hours = rate.grace_minutes / 60.0
                if hours <= grace_hours:
                    ticket.amount_total = 0.0
                    continue
                # Mínimo a cobrar
                min_hours = rate.min_minutes / 60.0
                billable_hours = max(hours, min_hours)
                # Redondear al siguiente bloque de hora
                billable_hours = math.ceil(billable_hours * (60 / rate.min_minutes)) / (60 / rate.min_minutes)
                ticket.amount_total = round(billable_hours * rate.price, 2)

            elif rate.rate_type == 'daily':
                days = math.ceil(hours / 24) if hours > 0 else 1
                ticket.amount_total = round(days * rate.price, 2)

            elif rate.rate_type == 'monthly':
                ticket.amount_total = rate.price

            elif rate.rate_type == 'event':
                ticket.amount_total = rate.price

            else:
                ticket.amount_total = 0.0

    # ─── ORM ──────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('parking.ticket') or 'Nuevo'
        tickets = super().create(vals_list)
        for ticket in tickets:
            # Marcar el espacio como ocupado
            ticket.spot_id.write({
                'state': 'occupied',
                'current_ticket_id': ticket.id,
            })
        return tickets

    def write(self, vals):
        # ─── PROTECCIÓN: no modificar tickets cerrados ─────────────────────────
        for ticket in self:
            if ticket.state == 'done':
                # Campos permitidos incluso en tickets cerrados
                allowed_fields = {'amount_paid', 'notes', 'message_ids', 'activity_ids'}
                restricted = set(vals.keys()) - allowed_fields
                if restricted:
                    raise UserError(_(
                        'El ticket %s ya está cerrado y no puede ser modificado.\n'
                        'Si necesita corregir algo, contacte al administrador.'
                    ) % ticket.name)

            if ticket.state == 'cancelled':
                raise UserError(_(
                    'El ticket %s está anulado y no puede ser modificado.'
                ) % ticket.name)

        return super().write(vals)

    # ─── Validaciones ─────────────────────────────────────────────────────────
    @api.constrains('spot_id', 'state')
    def _check_spot_available(self):
        for ticket in self:
            if ticket.state != 'open':
                continue
            # Buscar otro ticket abierto en el mismo espacio
            conflicting = self.search([
                ('spot_id', '=', ticket.spot_id.id),
                ('state', '=', 'open'),
                ('id', '!=', ticket.id),
            ])
            if conflicting:
                raise ValidationError(_(
                    'El espacio "%s" ya está ocupado por el ticket %s (Placa: %s).\n'
                    'No puede registrar otro vehículo en este espacio.'
                ) % (
                    ticket.spot_id.name,
                    conflicting[0].name,
                    conflicting[0].plate
                ))

    @api.constrains('vehicle_id', 'state')
    def _check_vehicle_not_parked(self):
        for ticket in self:
            if ticket.state != 'open':
                continue
            conflicting = self.search([
                ('vehicle_id', '=', ticket.vehicle_id.id),
                ('state', '=', 'open'),
                ('id', '!=', ticket.id),
            ])
            if conflicting:
                raise ValidationError(_(
                    'El vehículo con placa "%s" ya se encuentra estacionado en el espacio "%s" (Ticket: %s).\n'
                    'No puede registrar el mismo vehículo dos veces.'
                ) % (
                    ticket.vehicle_id.plate,
                    conflicting[0].spot_id.name,
                    conflicting[0].name
                ))

    @api.constrains('spot_id')
    def _check_spot_state(self):
        for ticket in self:
            if ticket.state != 'open':
                continue
            spot = ticket.spot_id
            if spot.state == 'maintenance':
                raise ValidationError(_(
                    'El espacio "%s" está en mantenimiento y no puede recibir vehículos.'
                ) % spot.name)

    # ─── Acciones ─────────────────────────────────────────────────────────────
    def action_checkout(self):
        """Registrar salida del vehículo"""
        self.ensure_one()
        if self.state != 'open':
            raise UserError(_('Este ticket ya fue cerrado o anulado.'))

        return {
            'name': _('Registrar Salida - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'parking.checkout.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ticket_id': self.id,
                'default_amount_total': self.amount_total,
            }
        }

    def action_do_checkout(self, amount_paid=None):
        """Ejecutar el cierre del ticket"""
        self.ensure_one()
        if self.state != 'open':
            raise UserError(_('Este ticket ya fue cerrado.'))

        exit_now = fields.Datetime.now()
        paid = amount_paid if amount_paid is not None else self.amount_total

        # Calcular monto final con la hora de salida real
        self.exit_time = exit_now
        self._compute_duration()
        self._compute_amount()

        self.write({
            'exit_time': exit_now,
            'state': 'done',
            'amount_paid': paid,
            'cashier_exit_id': self.env.user.id,
        })

        # Liberar el espacio
        self.spot_id.write({
            'state': 'available',
            'current_ticket_id': False,
        })

        self.message_post(
            body=_(
                '<b>Salida registrada</b><br/>'
                'Hora de salida: %s<br/>'
                'Duración: %s<br/>'
                'Total cobrado: %s'
            ) % (
                exit_now.strftime('%d/%m/%Y %H:%M'),
                self.duration_display,
                f"{self.currency_id.symbol}{paid:.2f}"
            )
        )
        return True

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'done':
            raise UserError(_('No puede anular un ticket ya cerrado.'))
        self.state = 'cancelled'
        # Liberar espacio si estaba ocupado por este ticket
        if self.spot_id.current_ticket_id == self:
            self.spot_id.write({
                'state': 'available',
                'current_ticket_id': False,
            })

    def action_print_ticket(self):
        return self.env.ref('parking_public.action_report_parking_ticket').report_action(self)

    # ─── Datos computados para la vista ───────────────────────────────────────
    def _get_amount_due(self):
        """Diferencia entre total y lo pagado"""
        return max(0, self.amount_total - self.amount_paid)
