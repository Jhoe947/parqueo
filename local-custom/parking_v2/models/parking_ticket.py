# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import math


class ParkingTicket(models.Model):
    _name = 'parking2.ticket'
    _description = 'Ticket de Parqueo'
    _order = 'entry_time desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ─── Identificacion ───────────────────────────────────────────────────────
    name = fields.Char(
        string='Numero de Ticket',
        readonly=True, copy=False, default='Nuevo'
    )

    # ─── Espacio y tarifa ─────────────────────────────────────────────────────
    spot_id = fields.Many2one(
        'parking2.spot', string='Espacio de Parqueo',
        required=True, tracking=True,
        domain=[('state', 'in', ['available', 'reserved'])]
    )
    rate_id = fields.Many2one(
        'parking2.rate', string='Tarifa',
        required=True, tracking=True
    )

    # ─── Vehiculo: puede venir de uno existente O registrarse nuevo aqui ──────
    vehicle_id = fields.Many2one(
        'parking2.vehicle', string='Vehiculo', tracking=True
    )
    # Campos relacionados del vehiculo (para mostrar info y para el ticket impreso)
    owner_name = fields.Char(string='Propietario', related='vehicle_id.owner_name', store=True)
    plate = fields.Char(string='Placa', related='vehicle_id.plate', store=True)

    # ─── Campos para registro rapido de vehiculo nuevo desde el ticket ────────
    # El cajero escribe la placa → si no existe aparecen estos campos
    # Al guardar se crea el vehiculo automaticamente
    input_plate = fields.Char(string='Placa')
    is_new_vehicle = fields.Boolean(string='Vehiculo Nuevo', default=False)
    new_owner_name = fields.Char(string='Nombre del Propietario')
    new_owner_phone = fields.Char(string='Telefono')
    new_owner_id_number = fields.Char(string='DPI / Cedula')
    new_vehicle_type = fields.Selection([
        ('car', 'Automovil'),
        ('motorcycle', 'Motocicleta'),
        ('truck', 'Camion/Bus'),
    ], string='Tipo de Vehiculo', default='car')
    new_brand = fields.Char(string='Marca')
    new_color = fields.Char(string='Color')

    # ─── Tiempos ──────────────────────────────────────────────────────────────
    entry_time = fields.Datetime(
        string='Hora de Entrada',
        required=True, default=fields.Datetime.now, tracking=True
    )
    exit_time = fields.Datetime(string='Hora de Salida', readonly=True, tracking=True)

    # ─── Duracion y cobro ─────────────────────────────────────────────────────
    duration_hours = fields.Float(
        string='Duracion (horas)',
        compute='_compute_duration', store=True, digits=(10, 2)
    )
    duration_display = fields.Char(
        string='Tiempo en Parqueo',
        compute='_compute_duration'
    )
    amount_total = fields.Float(
        string='Total a Pagar',
        compute='_compute_amount', store=True, digits=(10, 2), tracking=True
    )
    amount_paid = fields.Float(string='Monto Pagado', digits=(10, 2), tracking=True)
    currency_id = fields.Many2one('res.currency', related='rate_id.currency_id')
    discount_applied = fields.Float(string='Descuento (%)', default=0.0, readonly=True)

    # Campo informativo: muestra desglose de tarifa en tiempo real
    # Ejemplo: "Q5.00/hora  |  Gracia: 10min  |  Tiempo: 1h 23min  |  A pagar: Q10.00"
    tariff_info = fields.Char(
        string='Resumen de Cobro',
        compute='_compute_tariff_info'
    )

    # ─── Estado ───────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('open', 'Activo / En Parqueo'),
        ('done', 'Cerrado / Salio'),
        ('cancelled', 'Anulado'),
    ], string='Estado', default='open', required=True, tracking=True)

    # ─── Auditoria ────────────────────────────────────────────────────────────
    user_id = fields.Many2one(
        'res.users', string='Registrado por',
        default=lambda self: self.env.user, readonly=True
    )
    cashier_exit_id = fields.Many2one('res.users', string='Cajero de Salida', readonly=True)
    notes = fields.Text(string='Observaciones')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, readonly=True
    )

    # =========================================================================
    # ONCHANGE: busca la placa mientras el cajero escribe
    # =========================================================================
    @api.onchange('input_plate')
    def _onchange_input_plate(self):
        """
        Se dispara cada vez que el cajero escribe en el campo Placa.
        - Si la placa existe: carga el vehiculo automaticamente
        - Si no existe: muestra los campos para registrar el cliente nuevo
        - Si el vehiculo ya esta adentro: muestra una advertencia
        """
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
        vehicle = self.env['parking2.vehicle'].search(
            [('plate', '=ilike', plate)], limit=1
        )

        if vehicle:
            self.vehicle_id = vehicle.id
            self.is_new_vehicle = False
            # Avisar si ya esta adentro
            active = self.env['parking2.ticket'].search([
                ('vehicle_id', '=', vehicle.id),
                ('state', '=', 'open'),
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

    # =========================================================================
    # COMPUTOS
    # =========================================================================
    @api.depends('entry_time', 'exit_time', 'state')
    def _compute_duration(self):
        now = fields.Datetime.now()
        for t in self:
            end = t.exit_time if t.exit_time else now
            if t.entry_time and end >= t.entry_time:
                secs = (end - t.entry_time).total_seconds()
                t.duration_hours = round(secs / 3600, 4)
                t.duration_display = '%dh %02dmin' % (int(secs // 3600), int((secs % 3600) // 60))
            else:
                t.duration_hours = 0.0
                t.duration_display = '0h 00min'

    def _calc_amount(self, rate, hours):
        """
        Calcula el monto segun tarifa y horas.
        Por hora: cobra bloques completos (ceil). Gracia = primeros N min gratis.
        Por dia: ceil al proximo dia completo.
        Mensual/Evento: precio fijo.
        """
        if not rate or hours < 0:
            return 0.0

        if rate.rate_type == 'hourly':
            grace = rate.grace_minutes / 60.0
            if hours <= grace:
                return 0.0
            block = rate.min_minutes / 60.0  # tamano del bloque (ej: 1.0 hora)
            blocks = math.ceil(hours / block)
            return round(blocks * block * rate.price, 2)

        elif rate.rate_type == 'daily':
            days = math.ceil(hours / 24) if hours > 0 else 1
            return round(days * rate.price, 2)

        elif rate.rate_type in ('monthly', 'event'):
            return round(rate.price, 2)

        return 0.0

    def _get_discount(self):
        """Retorna el % de descuento segun categoria del cliente"""
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
            t.discount_applied = disc
            t.amount_total = round(base * (1 - disc / 100), 2)

    @api.depends('rate_id', 'duration_hours', 'duration_display', 'amount_total',
                 'vehicle_id', 'discount_applied')
    def _compute_tariff_info(self):
        """Genera texto legible del cobro actual para mostrar en el formulario"""
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

    # =========================================================================
    # ORM: create — genera numero, crea vehiculo nuevo si aplica, bloquea espacio
    # =========================================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Generar numero de ticket
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('parking2.ticket') or 'Nuevo'

            # Si el cajero registro un vehiculo nuevo desde el ticket, crearlo aqui
            if vals.get('is_new_vehicle') and vals.get('input_plate'):
                plate = vals['input_plate'].strip().upper()
                existing = self.env['parking2.vehicle'].search(
                    [('plate', '=ilike', plate)], limit=1
                )
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

            # Limpiar campos temporales que no existen en la tabla
            for f in ['is_new_vehicle', 'input_plate', 'new_owner_name', 'new_owner_phone',
                      'new_owner_id_number', 'new_vehicle_type', 'new_brand', 'new_color']:
                vals.pop(f, None)

        tickets = super().create(vals_list)

        # Bloquear el espacio al crear el ticket
        for ticket in tickets:
            ticket.spot_id.write({
                'state': 'occupied',
                'current_ticket_id': ticket.id,
            })
        return tickets

    # =========================================================================
    # ORM: write — proteger tickets cerrados
    # =========================================================================
    def write(self, vals):
        system_fields = {
            'exit_time', 'state', 'amount_total', 'amount_paid',
            'discount_applied', 'cashier_exit_id', 'duration_hours',
            'duration_display', 'message_ids', 'activity_ids',
            'message_follower_ids'
        }
        for ticket in self:
            if ticket.state == 'done':
                # Una vez cerrado, NADIE puede modificar nada
                # ni el monto pagado ni ningún otro campo
                user_editable = set(vals.keys()) - system_fields
                # Si el ticket ya tiene exit_time, significa que ya fue
                # cerrado correctamente — bloquear también system_fields
                if ticket.exit_time:
                    blocked = set(vals.keys()) - {
                        'message_ids', 'activity_ids', 'message_follower_ids'
                    }
                    if blocked:
                        raise UserError(
                            'El ticket %s ya esta cerrado. '
                            'No se puede modificar ningún campo.' % ticket.name
                        )
                elif user_editable:
                    raise UserError(
                        'El ticket %s ya esta cerrado y no puede modificarse.' % ticket.name
                    )
            if ticket.state == 'cancelled':
                user_editable = set(vals.keys()) - system_fields
                if user_editable:
                    raise UserError(
                        'El ticket %s esta anulado y no puede modificarse.' % ticket.name
                    )
        return super().write(vals)

    # =========================================================================
    # VALIDACIONES de negocio
    # =========================================================================
    @api.constrains('spot_id', 'vehicle_id', 'state')
    def _check_business_rules(self):
        for t in self:
            if t.state != 'open':
                continue

            # Un espacio no puede tener dos tickets abiertos
            other_spot = self.search([
                ('spot_id', '=', t.spot_id.id),
                ('state', '=', 'open'),
                ('id', '!=', t.id),
            ])
            if other_spot:
                raise ValidationError(
                    'El espacio "%s" ya esta ocupado por el ticket %s (Placa: %s).' % (
                        t.spot_id.name, other_spot[0].name, other_spot[0].plate
                    )
                )

            # Un vehiculo no puede estar dos veces adentro
            if t.vehicle_id:
                other_veh = self.search([
                    ('vehicle_id', '=', t.vehicle_id.id),
                    ('state', '=', 'open'),
                    ('id', '!=', t.id),
                ])
                if other_veh:
                    raise ValidationError(
                        'El vehiculo "%s" ya esta en el espacio "%s" (Ticket %s).' % (
                            t.vehicle_id.plate, other_veh[0].spot_id.name, other_veh[0].name
                        )
                    )

            # No se puede usar un espacio en mantenimiento
            if t.spot_id.state == 'maintenance':
                raise ValidationError(
                    'El espacio "%s" esta en mantenimiento.' % t.spot_id.name
                )

    @api.constrains('vehicle_id')
    def _check_vehicle_required(self):
        for t in self:
            if t.state == 'open' and not t.vehicle_id:
                raise ValidationError('Debe seleccionar o registrar un vehiculo.')

    # =========================================================================
    # ACCIONES
    # =========================================================================
    def action_checkout(self):
        """Abre el wizard de cobro y salida"""
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
        """Cierra el ticket, registra el pago y libera el espacio"""
        self.ensure_one()
        if self.state != 'open':
            raise UserError('Este ticket ya fue cerrado.')

        exit_now = fields.Datetime.now()

        # Recalcular monto final con la hora exacta de salida
        secs = (exit_now - self.entry_time).total_seconds()
        final_hours = round(secs / 3600, 4)
        base = self._calc_amount(self.rate_id, final_hours)
        disc = self._get_discount()
        final_total = round(base * (1 - disc / 100), 2)

        self.write({
            'exit_time': exit_now,
            'state': 'done',
            'amount_total': final_total,
            'amount_paid': amount_paid,
            'discount_applied': disc,
            'cashier_exit_id': self.env.user.id,
        })

        # Liberar el espacio
        self.spot_id.write({'state': 'available', 'current_ticket_id': False})

        self.message_post(body=(
            '<b>Salida registrada</b><br/>'
            'Hora: %s | Duracion: %dh %02dmin<br/>'
            'Total cobrado: %.2f | Pago recibido: %.2f | Vuelto: %.2f'
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