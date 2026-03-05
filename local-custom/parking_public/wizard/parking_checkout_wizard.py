# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ParkingCheckoutWizard(models.TransientModel):
    _name = 'parking.checkout.wizard'
    _description = 'Asistente de Salida de Parqueo'

    ticket_id = fields.Many2one('parking.ticket', string='Ticket', required=True, readonly=True)
    plate = fields.Char(related='ticket_id.plate', string='Placa', readonly=True)
    owner_name = fields.Char(related='ticket_id.owner_name', string='Propietario', readonly=True)
    spot_name = fields.Char(related='ticket_id.spot_id.name', string='Espacio', readonly=True)
    entry_time = fields.Datetime(related='ticket_id.entry_time', string='Hora de Entrada', readonly=True)
    duration_display = fields.Char(related='ticket_id.duration_display', string='Tiempo en Parqueo', readonly=True)
    rate_name = fields.Char(related='ticket_id.rate_id.name', string='Tarifa', readonly=True)

    amount_total = fields.Float(string='Total Calculado', readonly=True, digits=(10, 2))
    amount_paid = fields.Float(string='Monto Recibido', digits=(10, 2))
    amount_change = fields.Float(string='Vuelto', compute='_compute_change', digits=(10, 2))

    @api.depends('amount_paid', 'amount_total')
    def _compute_change(self):
        for wiz in self:
            wiz.amount_change = max(0, wiz.amount_paid - wiz.amount_total)

    @api.onchange('ticket_id')
    def _onchange_ticket(self):
        if self.ticket_id:
            self.amount_total = self.ticket_id.amount_total
            self.amount_paid = self.ticket_id.amount_total  # Pre-llenar con el total

    @api.constrains('amount_paid')
    def _check_amount_paid(self):
        for wiz in self:
            if wiz.amount_paid < 0:
                raise ValidationError(_('El monto recibido no puede ser negativo.'))

    def action_confirm_checkout(self):
        self.ensure_one()
        if self.amount_paid < self.amount_total:
            raise ValidationError(_(
                'El monto recibido (%.2f) es menor al total a pagar (%.2f).\n'
                'No puede cerrar el ticket sin cobro completo.'
            ) % (self.amount_paid, self.amount_total))

        self.ticket_id.action_do_checkout(amount_paid=self.amount_paid)

        # Mostrar mensaje de confirmación
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('¡Salida Registrada!'),
                'message': _(
                    'Ticket %s cerrado.\nVehículo: %s\nTotal cobrado: %.2f\nVuelto: %.2f'
                ) % (
                    self.ticket_id.name,
                    self.plate,
                    self.amount_paid,
                    self.amount_change
                ),
                'type': 'success',
                'sticky': False,
            }
        }
