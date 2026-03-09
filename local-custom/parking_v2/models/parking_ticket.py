# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import math
from datetime import datetime


class ParkingTicket(models.Model):
    _name = 'parking2.ticket'
    _description = 'Ticket de Parqueo'
    _order = 'entry_time desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Numero de Ticket', readonly=True, copy=False, default='Nuevo')

    spot_id = fields.Many2one(
        'parking2.spot', string='Espacio de Parqueo', required=True, tracking=True,
        domain=[('state', 'in', ['available', 'reserved'])]
    )
    rate_id = fields.Many2one('parking2.rate', string='Tarifa', required=True, tracking=True)
    vehicle_id = fields.Many2one('parking2.vehicle', string='Vehiculo', tracking=True)
    owner_name = fields.Char(string='Propietario', related='vehicle_id.owner_name', store=True)
    plate = fields.Char(string='Placa', related='vehicle_id.plate', store=True)

    # Campos temporales para registrar vehiculo nuevo desde el ticket
    input_plate = fields.Char(string='Placa')
    is_new_vehicle = fields.Boolean(string='Vehiculo Nuevo', default=False)
    new_owner_name = fields.Char(string='Nombre del Propietario')
    new_owner_phone = fields.Char(string='Telefono')
    new_owner_id_number = fields.Char(string='DPI / Cedula')
    new_vehicle_type = fields.Selection([
        ('car', 'Automovil'), ('motorcycle', 'Motocicleta'), ('truck', 'Camion/Bus'),
    ], string='Tipo de Vehiculo', default='car')
    new_brand = fields.Char(string='Marca')
    new_color = fields.Char(string='Color')

    entry_time = fields.Datetime(
        string='Hora de Entrada', required=True, default=fields.Datetime.now, tracking=True
    )
    exit_time = fields.Datetime(string='Hora de Salida', readonly=True, tracking=True)

    # siempre se recalcula en tiempo real
    duration_hours = fields.Float(
        string='Duracion (horas)',
        compute='_compute_duration',
        store=False,
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
        store=False,
        digits=(10, 2),
        tracking=True
    )
    # Monto final guardado al cerrar el ticket
    amount_final = fields.Float(
        string='Total Cobrado',
        digits=(10, 2),
        readonly=True
    )
    amount_paid = fields.Float(string='Monto Pagado', digits=(10, 2), tracking=True, readonly=True)
    currency_id = fields.Many2one('res.currency', related='rate_id.currency_id')
    discount_applied = fields.Float(string='Descuento (%)', default=0.0, readonly=True)

    tariff_info = fields.Char(
        string='Resumen de Cobro',
        compute='_compute_tariff_info',
        store=False
    )

    state = fields.Selection([
        ('open', 'Activo / En Parqueo'),
        ('done', 'Cerrado / Salio'),
        ('cancelled', 'Anulado'),
    ], string='Estado', default='open', required=True, tracking=True)

    user_id = fields.Many2one('res.users', string='Registrado por',
                               default=lambda self: self.env.user, readonly=True)
    cashier_exit_id = fields.Many2one('res.users', string='Cajero de Salida', readonly=True)
    notes = fields.Text(string='Observaciones')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, readonly=True)

    # ONCHANGE: busca la placa mientras el cajero escribe
    @api.onchange('input_plate')
    def _onchange_input_plate(self):
        self.vehicle_id = False
        self.is_new_vehicle = False
        self.new_owner_name = False
        self.new_owner_phone = False
        self.new_owner_id_number = False
        self.new_brand = False
        self.new_color = False
        self.new_vehicle_type = 'car'

        if not self.input_plate:
            return

        plate = self.input_plate.strip().upper()
        vehicle = self.env['parking2.vehicle'].search([('plate', '=ilike', plate)], limit=1)

        if vehicle:
            self.vehicle_id = vehicle.id
            self.is_new_vehicle = False
            active = self.env['parking2.ticket'].search([
                ('vehicle_id', '=', vehicle.id), ('state', '=', 'open'),
            ], limit=1)
            if active:
                return {'warning': {
                    'title': 'Vehiculo ya en parqueo',
                    'message': 'La placa %s ya esta en el espacio %s (Ticket %s).' % (
                        plate, active.spot_id.name, active.name
                    )
                }}
        else:
            self.is_new_vehicle = True


    # COMPUTOS — store=False para que siempre reflejen el tiempo real
    @api.depends('entry_time', 'exit_time', 'state')
    def _compute_duration(self):
        """
        Calcula duracion desde entry_time hasta ahora (si abierto) o exit_time (si cerrado).
        store=False garantiza que cada vez que se consulta el registro se recalcula.
        """
        now = fields.Datetime.now()
        for t in self:
            if not t.entry_time:
                t.duration_hours = 0.0
                t.duration_display = '0h 00min'
                continue
            # Si ya salio usar exit_time, si sigue adentro usar hora actual
            end = t.exit_time if (t.state == 'done' and t.exit_time) else now
            secs = max(0, (end - t.entry_time).total_seconds())
            t.duration_hours = round(secs / 3600, 4)
            t.duration_display = '%dh %02dmin' % (int(secs // 3600), int((secs % 3600) // 60))

    def _calc_amount(self, rate, hours):

        if not rate or hours < 0:
            return 0.0

        if rate.rate_type == 'hourly':
            grace = rate.grace_minutes / 60.0
            if hours <= grace:
                return 0.0
            # Calcular bloques completos (ceil al siguiente bloque)
            block = rate.min_minutes / 60.0
            blocks = math.ceil(hours / block)
            return round(blocks * block * rate.price, 2)

        elif rate.rate_type == 'daily':
            days = math.ceil(hours / 24) if hours > 0 else 1
            return round(days * rate.price, 2)

        elif rate.rate_type in ('monthly', 'event'):
            return round(rate.price, 2)

        return 0.0

    def _get_discount(self):
        if not self.vehicle_id:
            return 0.0
        return {'vip': 15.0, 'frequent': 10.0, 'regular': 5.0}.get(
            self.vehicle_id.customer_category, 0.0
        )

    @api.depends('duration_hours', 'rate_id', 'vehicle_id', 'entry_time', 'exit_time', 'state')
    def _compute_amount(self):
        for t in self:
            base = t._calc_amount(t.rate_id, t.duration_hours)
            disc = t._get_discount()
            t.amount_total = round(base * (1 - disc / 100), 2)

    @api.depends('rate_id', 'duration_hours', 'duration_display', 'amount_total',
                 'vehicle_id', 'discount_applied')
    def _compute_tariff_info(self):
        labels = {'hourly': 'hora', 'daily': 'dia', 'monthly': 'mes', 'event': 'evento'}
        for t in self:
            if not t.rate_id:
                t.tariff_info = 'Seleccione una tarifa'
                continue
            r = t.rate_id
            sym = t.currency_id.symbol if t.currency_id else 'Q'
            parts = ['%s%.2f/%s' % (sym, r.price, labels.get(r.rate_type, ''))]
            if r.rate_type == 'hourly':
                if r.grace_minutes:
                    parts.append('Gracia: %dmin' % r.grace_minutes)
                parts.append('Min: %dmin' % r.min_minutes)
            if t.duration_display and t.duration_display != '0h 00min':
                parts.append('Tiempo: %s' % t.duration_display)
            parts.append('A pagar: %s%.2f' % (sym, t.amount_total))
            if t.discount_applied:
                parts.append('Descuento: %.0f%%' % t.discount_applied)
            t.tariff_info = '  |  '.join(parts)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('parking2.ticket') or 'Nuevo'

            if vals.get('is_new_vehicle') and vals.get('input_plate'):
                plate = vals['input_plate'].strip().upper()
                existing = self.env['parking2.vehicle'].search([('plate', '=ilike', plate)], limit=1)
                if existing:
                    vals['vehicle_id'] = existing.id
                else:
                    new_v = self.env['parking2.vehicle'].create({
                        'plate': plate,
                        'owner_name': vals.get('new_owner_name') or plate,
                        'owner_phone': vals.get('new_owner_phone') or '',
                        'owner_id_number': vals.get('new_owner_id_number') or '',
                        'vehicle_type': vals.get('new_vehicle_type') or 'car',
                        'brand': vals.get('new_brand') or '',
                        'color': vals.get('new_color') or '',
                    })
                    vals['vehicle_id'] = new_v.id

            for f in ['is_new_vehicle', 'input_plate', 'new_owner_name', 'new_owner_phone',
                      'new_owner_id_number', 'new_vehicle_type', 'new_brand', 'new_color']:
                vals.pop(f, None)

        tickets = super().create(vals_list)
        for ticket in tickets:
            ticket.spot_id.write({'state': 'occupied', 'current_ticket_id': ticket.id})
        return tickets

    def write(self, vals):

        chatter_only = {'message_ids', 'activity_ids', 'message_follower_ids'}
        for ticket in self:
            if ticket.state == 'done' and ticket.exit_time:
                # Ticket completamente cerrado: solo chatter permitido
                blocked = set(vals.keys()) - chatter_only
                if blocked:
                    raise UserError(
                        'El ticket %s ya esta cerrado. No se puede modificar.' % ticket.name
                    )
            if ticket.state == 'cancelled':
                blocked = set(vals.keys()) - chatter_only
                if blocked:
                    raise UserError(
                        'El ticket %s esta anulado. No se puede modificar.' % ticket.name
                    )
        return super().write(vals)


    # VALIDACIONES

    @api.constrains('spot_id', 'vehicle_id', 'state')
    def _check_business_rules(self):
        for t in self:
            if t.state != 'open':
                continue
            other_spot = self.search([
                ('spot_id', '=', t.spot_id.id), ('state', '=', 'open'), ('id', '!=', t.id),
            ])
            if other_spot:
                raise ValidationError(
                    'El espacio "%s" ya esta ocupado por ticket %s.' % (
                        t.spot_id.name, other_spot[0].name)
                )
            if t.vehicle_id:
                other_veh = self.search([
                    ('vehicle_id', '=', t.vehicle_id.id), ('state', '=', 'open'), ('id', '!=', t.id),
                ])
                if other_veh:
                    raise ValidationError(
                        'El vehiculo "%s" ya esta en el espacio "%s".' % (
                            t.vehicle_id.plate, other_veh[0].spot_id.name)
                    )
            if t.spot_id.state == 'maintenance':
                raise ValidationError('El espacio "%s" esta en mantenimiento.' % t.spot_id.name)

    @api.constrains('vehicle_id')
    def _check_vehicle_required(self):
        for t in self:
            if t.state == 'open' and not t.vehicle_id:
                raise ValidationError('Debe seleccionar o registrar un vehiculo.')


    # ACCIONES

    def action_checkout(self):
        self.ensure_one()
        if self.state != 'open':
            raise UserError('Este ticket ya fue cerrado o anulado.')
        return {
            'name': 'Registrar Salida - %s' % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'parking2.checkout.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_ticket_id': self.id},
        }

    def action_do_checkout(self, amount_paid):
        """
        Cierra el ticket. Se llama desde el wizard.
        1. Calcula el monto final con la hora exacta de salida
        2. Escribe todos los campos de cierre en una sola llamada (ticket aun es 'open')
        3. Libera el espacio
        """
        self.ensure_one()
        if self.state != 'open':
            raise UserError('Este ticket ya fue cerrado.')

        exit_now = fields.Datetime.now()
        secs = max(0, (exit_now - self.entry_time).total_seconds())
        final_hours = round(secs / 3600, 4)
        base = self._calc_amount(self.rate_id, final_hours)
        disc = self._get_discount()
        final_total = round(base * (1 - disc / 100), 2)

        # El ticket aun esta 'open' aqui, por eso el write no esta bloqueado
        # Cambiamos state a 'done' y exit_time en la misma llamada
        super(ParkingTicket, self).write({
            'exit_time': exit_now,
            'state': 'done',
            'amount_final': final_total,
            'amount_paid': amount_paid,
            'discount_applied': disc,
            'cashier_exit_id': self.env.user.id,
        })

        self.spot_id.write({'state': 'available', 'current_ticket_id': False})

        super(ParkingTicket, self).message_post(body=(
            '<b>Salida registrada</b><br/>'
            'Hora: %s | Duracion: %dh %02dmin<br/>'
            'Total: %.2f | Pagado: %.2f | Vuelto: %.2f'
        ) % (
            exit_now.strftime('%d/%m/%Y %H:%M'),
            int(secs // 3600), int((secs % 3600) // 60),
            final_total, amount_paid, max(0, amount_paid - final_total)
        ))
        return True

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'done':
            raise UserError('No puede anular un ticket ya cerrado.')
        self.state = 'cancelled'
        if self.spot_id.current_ticket_id == self:
            self.spot_id.write({'state': 'available', 'current_ticket_id': False})

    def action_print_ticket(self):
        return self.env.ref('parking_v2.action_report_parking2_ticket').report_action(self)
