# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ParkingCheckoutWizard(models.TransientModel):
    _name = 'parking2.checkout.wizard'
    _description = 'Asistente de Salida de Parqueo'

    ticket_id = fields.Many2one(
        'parking2.ticket', string='Ticket', required=True, readonly=True
    )
    plate = fields.Char(related='ticket_id.plate', string='Placa', readonly=True)
    owner_name = fields.Char(related='ticket_id.owner_name', string='Propietario', readonly=True)
    spot_name = fields.Char(related='ticket_id.spot_id.name', string='Espacio', readonly=True)
    entry_time = fields.Datetime(related='ticket_id.entry_time', string='Hora de Entrada', readonly=True)
    duration_display = fields.Char(related='ticket_id.duration_display', string='Tiempo', readonly=True)
    rate_name = fields.Char(related='ticket_id.rate_id.name', string='Tarifa', readonly=True)
    discount_applied = fields.Float(related='ticket_id.discount_applied', string='Descuento (%)', readonly=True)

    amount_total = fields.Float(
        related='ticket_id.amount_total',
        string='Total a Cobrar',
        readonly=True,
        digits=(10, 2)
    )
    amount_paid = fields.Float(
        string='Monto Recibido del Cliente',
        digits=(10, 2)
    )
    amount_change = fields.Float(
        string='Vuelto a Entregar',
        compute='_compute_change',
        digits=(10, 2)
    )

    @api.model
    def default_get(self, fields_list):
        """Pre-llena amount_paid con el total del ticket al abrir el wizard"""
        res = super().default_get(fields_list)
        ticket_id = self.env.context.get('default_ticket_id')
        if ticket_id:
            ticket = self.env['parking2.ticket'].browse(ticket_id)
            res['amount_paid'] = ticket.amount_total
        return res

    @api.depends('amount_paid', 'amount_total')
    def _compute_change(self):
        for wiz in self:
            wiz.amount_change = max(0.0, wiz.amount_paid - wiz.amount_total)

    @api.onchange('amount_paid')
    def _onchange_amount_paid(self):
        if self.amount_paid and self.amount_paid < self.amount_total:
            return {'warning': {
                'title': 'Monto insuficiente',
                'message': 'El monto recibido (%.2f) es menor al total (%.2f).' % (
                    self.amount_paid, self.amount_total
                )
            }}

    def action_confirm_checkout(self):
        self.ensure_one()
        if not self.amount_paid or self.amount_paid <= 0:
            raise ValidationError('Ingrese el monto recibido del cliente.')
        if self.amount_paid < self.amount_total:
            raise ValidationError(
                'El monto recibido (%.2f) es menor al total (%.2f).' % (
                    self.amount_paid, self.amount_total
                )
            )
        ticket_name = self.ticket_id.name
        plate = self.plate or ''
        total = self.amount_total
        paid = self.amount_paid
        change = self.amount_change
        self.ticket_id.action_do_checkout(amount_paid=paid)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Salida Registrada',
                'message': 'Ticket: %s | Placa: %s | Total: %.2f | Recibido: %.2f | Vuelto: %.2f' % (
                    ticket_name, plate, total, paid, change
                ),
                'type': 'success',
                'sticky': False,
            }
        }

