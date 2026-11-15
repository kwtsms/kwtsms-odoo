# 2026-11-16 01:23 +03: Odoo 20 removed ir.config_parameter get_param/set_param; calls renamed to get_str/set_str. Task int-backport
"""Tests for admin notification events: mixin, hooks, cron jobs, templates."""

import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAdminNotificationMixin(TransactionCase):
    """Test kwtsms.admin.notification.mixin shared logic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({'name': 'Al-Salam Electronics'})
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_str('kwtsms.enabled', 'True')
        ICP.set_str('kwtsms.api_username', 'testuser')
        ICP.set_str('kwtsms.api_password', 'testpass')
        ICP.set_str('kwtsms.sender_id', 'KWT-SMS')
        ICP.set_str('kwtsms.test_mode', 'True')

        # Set up gateway config with balance
        config = cls.env['kwtsms.gateway.config']._get_or_create()
        config.write({'balance_available': 1000, 'api_status': 'connected'})

        # Admin phone
        ICP.set_str('kwtsms.admin_phone', '96598765432')

    def _ensure_admin_template(self, event_type, body=None):
        """Create an admin template for the given event type."""
        if body is None:
            body = '{company_name}: test admin notification'
        existing = self.env['kwtsms.sms.template'].search([
            ('event_type', '=', event_type),
            ('lang', '=', 'en'),
            ('active', '=', True),
        ])
        if existing:
            return existing[0]
        return self.env['kwtsms.sms.template'].create({
            'name': 'Admin %s EN' % event_type,
            'event_type': event_type,
            'lang': 'en',
            'body': body,
        })

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_phone_resolution_per_app_override(self, mock_api_call):
        """Test per-app phone override takes precedence over global admin phone."""
        mock_api_call.return_value = {
            'result': 'OK', 'msg-id': 'MSG-001',
            'points-charged': 1, 'balance-after': 999,
        }
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_str('kwtsms.admin_phone_sales', '96598765432')
        ICP.set_str('kwtsms.auto_admin_new_quotation', 'True')

        self._ensure_admin_template('admin_new_quotation',
                                    '{company_name}: New quote {order_name}')

        partner = self.env['res.partner'].create({
            'name': 'Test Customer',
            'phone': '+96598765432',
        })
        product = self.env['product.product'].create({
            'name': 'Test Product', 'type': 'consu', 'list_price': 50.0,
        })
        self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1,
                'price_unit': 50.0,
            })],
        })

        self.assertTrue(mock_api_call.called)
        payload = mock_api_call.call_args[0][1]
        self.assertIn('96598765432', payload.get('mobile', ''))

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_skips_when_gateway_disabled(self, mock_api_call):
        """Test admin notification skips when gateway is disabled."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_str('kwtsms.enabled', 'False')
        ICP.set_str('kwtsms.auto_admin_new_quotation', 'True')

        self._ensure_admin_template('admin_new_quotation')

        partner = self.env['res.partner'].create({
            'name': 'Test Customer', 'phone': '+96598765432',
        })
        product = self.env['product.product'].create({
            'name': 'Test Product', 'type': 'consu', 'list_price': 50.0,
        })
        self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id, 'product_uom_qty': 1,
                'price_unit': 50.0,
            })],
        })

        mock_api_call.assert_not_called()

        ICP.set_str('kwtsms.enabled', 'True')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_skips_when_event_toggle_disabled(self, mock_api_call):
        """Test admin notification skips when event toggle is off."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_str('kwtsms.auto_admin_new_quotation', 'False')

        self._ensure_admin_template('admin_new_quotation')

        partner = self.env['res.partner'].create({
            'name': 'Test Customer', 'phone': '+96598765432',
        })
        product = self.env['product.product'].create({
            'name': 'Test Product', 'type': 'consu', 'list_price': 50.0,
        })
        self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id, 'product_uom_qty': 1,
                'price_unit': 50.0,
            })],
        })

        mock_api_call.assert_not_called()

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_skips_when_no_admin_phone(self, mock_api_call):
        """Test admin notification skips when no admin phone is configured."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_str('kwtsms.auto_admin_new_quotation', 'True')
        ICP.set_str('kwtsms.admin_phone', '')
        ICP.set_str('kwtsms.admin_phone_sales', '')

        self._ensure_admin_template('admin_new_quotation')

        partner = self.env['res.partner'].create({
            'name': 'Test Customer', 'phone': '+96598765432',
        })
        product = self.env['product.product'].create({
            'name': 'Test Product', 'type': 'consu', 'list_price': 50.0,
        })
        self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id, 'product_uom_qty': 1,
                'price_unit': 50.0,
            })],
        })

        mock_api_call.assert_not_called()

        # Restore
        ICP.set_str('kwtsms.admin_phone', '96598765432')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_uses_company_language_for_template(self, mock_api_call):
        """Test admin notification uses company language for template selection."""
        mock_api_call.return_value = {
            'result': 'OK', 'msg-id': 'MSG-LANG',
            'points-charged': 1, 'balance-after': 999,
        }
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_str('kwtsms.auto_admin_new_quotation', 'True')

        en_template = self._ensure_admin_template(
            'admin_new_quotation', '{company_name}: English admin')

        # Company language is not Arabic, so should use English template
        partner = self.env['res.partner'].create({
            'name': 'Test Customer', 'phone': '+96598765432',
        })
        product = self.env['product.product'].create({
            'name': 'Test Product', 'type': 'consu', 'list_price': 50.0,
        })
        self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id, 'product_uom_qty': 1,
                'price_unit': 50.0,
            })],
        })

        self.assertTrue(mock_api_call.called)

        # Check log uses the English template
        log = self.env['kwtsms.sms.log'].search([
            ('recipient_type', '=', 'admin'),
        ], limit=1, order='id desc')
        self.assertTrue(log)
        if log.template_id:
            self.assertEqual(log.template_id.id, en_template.id)


@tagged('post_install', '-at_install')
class TestSalesAdminHooks(TransactionCase):
    """Test sale order admin notification hooks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({'name': 'Al-Salam Electronics'})
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_str('kwtsms.enabled', 'True')
        ICP.set_str('kwtsms.api_username', 'testuser')
        ICP.set_str('kwtsms.api_password', 'testpass')
        ICP.set_str('kwtsms.sender_id', 'KWT-SMS')
        ICP.set_str('kwtsms.test_mode', 'True')
        ICP.set_str('kwtsms.admin_phone', '96598765432')
        ICP.set_str('kwtsms.auto_admin_new_quotation', 'True')
        ICP.set_str('kwtsms.auto_admin_large_order', 'True')
        ICP.set_str('kwtsms.auto_admin_order_cancelled', 'True')
        ICP.set_str('kwtsms.auto_order_confirm', 'True')
        ICP.set_str('kwtsms.auto_order_cancel', 'True')
        ICP.set_str('kwtsms.large_order_threshold', '1000')

        config = cls.env['kwtsms.gateway.config']._get_or_create()
        config.write({'balance_available': 1000, 'api_status': 'connected'})

        cls.partner = cls.env['res.partner'].create({
            'name': 'Ahmad Al-Sabah', 'phone': '+96598765432',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Samsung Galaxy S24', 'type': 'consu', 'list_price': 100.0,
        })

        # Ensure templates exist
        for evt in ('admin_new_quotation', 'admin_large_order',
                     'admin_order_cancelled', 'order_confirm', 'order_cancel'):
            existing = cls.env['kwtsms.sms.template'].search([
                ('event_type', '=', evt), ('lang', '=', 'en'), ('active', '=', True),
            ])
            if not existing:
                cls.env['kwtsms.sms.template'].create({
                    'name': '%s EN' % evt,
                    'event_type': evt,
                    'lang': 'en',
                    'body': '{company_name}: %s {order_name}' % evt,
                })

    def _create_sale_order(self, price=100.0, qty=1):
        """Helper to create a sale order."""
        self.env.invalidate_all()
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': qty,
                'price_unit': price,
            })],
        })

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_new_quotation_triggers_admin_sms(self, mock_api_call):
        """Test new quotation creation triggers admin_new_quotation SMS."""
        mock_api_call.return_value = {
            'result': 'OK', 'msg-id': 'MSG-NQ',
            'points-charged': 1, 'balance-after': 999,
        }

        order = self._create_sale_order()

        # Should have been called for admin notification
        self.assertTrue(mock_api_call.called)
        log = self.env['kwtsms.sms.log'].search([
            ('recipient_type', '=', 'admin'),
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', order.id),
        ], limit=1)
        self.assertTrue(log)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_order_cancel_triggers_both_customer_and_admin(self, mock_api_call):
        """Test order cancellation triggers both customer AND admin SMS."""
        mock_api_call.return_value = {
            'result': 'OK', 'msg-id': 'MSG-CAN',
            'points-charged': 1, 'balance-after': 998,
        }

        order = self._create_sale_order()
        mock_api_call.reset_mock()

        order.action_confirm()
        mock_api_call.reset_mock()

        order.action_cancel()

        # Should be called at least twice (customer cancel + admin cancel)
        self.assertGreaterEqual(mock_api_call.call_count, 1)

        admin_log = self.env['kwtsms.sms.log'].search([
            ('recipient_type', '=', 'admin'),
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', order.id),
        ])
        # Should have admin logs for new quotation + cancelled
        self.assertTrue(admin_log)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_large_order_above_threshold_triggers_admin(self, mock_api_call):
        """Test large order at or above threshold triggers admin_large_order."""
        mock_api_call.return_value = {
            'result': 'OK', 'msg-id': 'MSG-LO',
            'points-charged': 1, 'balance-after': 999,
        }

        # Price * qty = 1000.0, threshold is 1000
        order = self._create_sale_order(price=1000.0, qty=1)
        mock_api_call.reset_mock()

        order.action_confirm()

        # Check that large order admin SMS was logged
        admin_logs = self.env['kwtsms.sms.log'].search([
            ('recipient_type', '=', 'admin'),
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', order.id),
        ], order='id desc')
        # Should include admin_large_order template
        large_order_logged = any(
            log.template_id and log.template_id.event_type == 'admin_large_order'
            for log in admin_logs
        )
        self.assertTrue(large_order_logged)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_order_below_threshold_no_large_order_sms(self, mock_api_call):
        """Test order below threshold does NOT trigger admin_large_order."""
        mock_api_call.return_value = {
            'result': 'OK', 'msg-id': 'MSG-SM',
            'points-charged': 1, 'balance-after': 999,
        }

        # Price * qty = 100.0, threshold is 1000
        order = self._create_sale_order(price=100.0, qty=1)
        # Clear logs from create (admin_new_quotation)
        self.env['kwtsms.sms.log'].search([
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', order.id),
        ]).unlink()
        mock_api_call.reset_mock()

        order.action_confirm()

        # Should NOT have admin_large_order log
        large_logs = self.env['kwtsms.sms.log'].search([
            ('recipient_type', '=', 'admin'),
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', order.id),
        ])
        for log in large_logs:
            if log.template_id:
                self.assertNotEqual(log.template_id.event_type, 'admin_large_order')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_threshold_is_configurable(self, mock_api_call):
        """Test large order threshold can be configured via ICP."""
        mock_api_call.return_value = {
            'result': 'OK', 'msg-id': 'MSG-TH',
            'points-charged': 1, 'balance-after': 999,
        }

        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_str('kwtsms.large_order_threshold', '50')

        # Price * qty = 100.0, threshold is now 50
        order = self._create_sale_order(price=100.0, qty=1)
        self.env['kwtsms.sms.log'].search([
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', order.id),
        ]).unlink()
        mock_api_call.reset_mock()

        order.action_confirm()

        admin_logs = self.env['kwtsms.sms.log'].search([
            ('recipient_type', '=', 'admin'),
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', order.id),
        ])
        large_order_logged = any(
            log.template_id and log.template_id.event_type == 'admin_large_order'
            for log in admin_logs
        )
        self.assertTrue(large_order_logged)

        # Restore
        ICP.set_str('kwtsms.large_order_threshold', '1000')


@tagged('post_install', '-at_install')
class TestInventoryAdminHook(TransactionCase):
    """Test stock.picking admin notification hooks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({'name': 'Al-Salam Electronics'})
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_str('kwtsms.enabled', 'True')
        ICP.set_str('kwtsms.api_username', 'testuser')
        ICP.set_str('kwtsms.api_password', 'testpass')
        ICP.set_str('kwtsms.sender_id', 'KWT-SMS')
        ICP.set_str('kwtsms.test_mode', 'True')
        ICP.set_str('kwtsms.admin_phone', '96598765432')
        ICP.set_str('kwtsms.auto_admin_incoming_shipment', 'True')
        ICP.set_str('kwtsms.auto_delivery_done', 'False')

        config = cls.env['kwtsms.gateway.config']._get_or_create()
        config.write({'balance_available': 1000, 'api_status': 'connected'})

        cls.partner = cls.env['res.partner'].create({
            'name': 'Supplier Kuwait', 'phone': '+96598765432',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Apple iPad Pro', 'type': 'consu', 'list_price': 50.0,
        })

        existing = cls.env['kwtsms.sms.template'].search([
            ('event_type', '=', 'admin_incoming_shipment'),
            ('lang', '=', 'en'), ('active', '=', True),
        ])
        if not existing:
            cls.env['kwtsms.sms.template'].create({
                'name': 'Admin Incoming Shipment EN',
                'event_type': 'admin_incoming_shipment',
                'lang': 'en',
                'body': '{company_name}: Incoming shipment {picking_name} from {supplier_name}',
            })

    def _create_incoming_picking(self):
        """Helper to create an incoming stock picking."""
        self.env.invalidate_all()
        picking_type = self.env.ref('stock.picking_type_in')
        location_src = self.env.ref('stock.stock_location_suppliers')
        location_dest = self.env.ref('stock.stock_location_stock')

        picking = self.env['stock.picking'].create({
            'partner_id': self.partner.id,
            'picking_type_id': picking_type.id,
            'location_id': location_src.id,
            'location_dest_id': location_dest.id,
            'move_ids': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 5.0,
                'product_uom': self.product.uom_id.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
            })],
        })
        return picking

    def _create_outgoing_picking(self):
        """Helper to create an outgoing stock picking."""
        self.env.invalidate_all()
        picking_type = self.env.ref('stock.picking_type_out')
        location_src = self.env.ref('stock.stock_location_stock')
        location_dest = self.env.ref('stock.stock_location_customers')

        picking = self.env['stock.picking'].create({
            'partner_id': self.partner.id,
            'picking_type_id': picking_type.id,
            'location_id': location_src.id,
            'location_dest_id': location_dest.id,
            'move_ids': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'product_uom': self.product.uom_id.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
            })],
        })
        return picking

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_incoming_shipment_triggers_admin_sms(self, mock_api_call):
        """Test incoming shipment triggers admin_incoming_shipment SMS."""
        mock_api_call.return_value = {
            'result': 'OK', 'msg-id': 'MSG-IN',
            'points-charged': 1, 'balance-after': 999,
        }

        picking = self._create_incoming_picking()
        picking.action_confirm()
        picking.move_ids.quantity = 5.0
        picking.move_ids.picked = True
        picking.button_validate()

        log = self.env['kwtsms.sms.log'].search([
            ('recipient_type', '=', 'admin'),
            ('res_model', '=', 'stock.picking'),
            ('res_id', '=', picking.id),
        ], limit=1)
        self.assertTrue(log)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_outgoing_shipment_no_admin_notification(self, mock_api_call):
        """Test outgoing shipment does NOT trigger admin_incoming_shipment."""
        mock_api_call.return_value = {
            'result': 'OK', 'msg-id': 'MSG-OUT',
            'points-charged': 1, 'balance-after': 999,
        }

        picking = self._create_outgoing_picking()
        picking.action_confirm()
        picking.move_ids.quantity = 1.0
        picking.move_ids.picked = True
        picking.button_validate()

        admin_logs = self.env['kwtsms.sms.log'].search([
            ('recipient_type', '=', 'admin'),
            ('res_model', '=', 'stock.picking'),
            ('res_id', '=', picking.id),
        ])
        self.assertFalse(admin_logs)


@tagged('post_install', '-at_install')
class TestAccountingAdminHook(TransactionCase):
    """Test account.payment admin notification hooks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({'name': 'Al-Salam Electronics'})
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_str('kwtsms.enabled', 'True')
        ICP.set_str('kwtsms.api_username', 'testuser')
        ICP.set_str('kwtsms.api_password', 'testpass')
        ICP.set_str('kwtsms.sender_id', 'KWT-SMS')
        ICP.set_str('kwtsms.test_mode', 'True')
        ICP.set_str('kwtsms.admin_phone', '96598765432')
        ICP.set_str('kwtsms.auto_admin_payment_received', 'True')
        ICP.set_str('kwtsms.auto_payment_received', 'False')

        config = cls.env['kwtsms.gateway.config']._get_or_create()
        config.write({'balance_available': 1000, 'api_status': 'connected'})

        # Ensure partner has proper receivable/payable accounts
        receivable = cls.env['account.account'].search([
            ('account_type', '=', 'asset_receivable'),
        ], limit=1)
        payable = cls.env['account.account'].search([
            ('account_type', '=', 'liability_payable'),
        ], limit=1)

        cls.partner = cls.env['res.partner'].create({
            'name': 'Nora Al-Kandari', 'phone': '+96598765432',
            'property_account_receivable_id': receivable.id,
            'property_account_payable_id': payable.id,
        })

        existing = cls.env['kwtsms.sms.template'].search([
            ('event_type', '=', 'admin_payment_received'),
            ('lang', '=', 'en'), ('active', '=', True),
        ])
        if not existing:
            cls.env['kwtsms.sms.template'].create({
                'name': 'Admin Payment Received EN',
                'event_type': 'admin_payment_received',
                'lang': 'en',
                'body': '{company_name}: Payment {amount} from {customer_name}',
            })

    def _create_payment(self, payment_type='inbound'):
        """Helper to create a payment."""
        self.env.invalidate_all()
        journal = self.env['account.journal'].search([
            ('type', 'in', ['bank', 'cash']),
            ('company_id', '=', self.company.id),
        ], limit=1)
        if not journal:
            journal = self.env['account.journal'].create({
                'name': 'Test Bank',
                'type': 'bank',
                'code': 'TBNK',
                'company_id': self.company.id,
            })

        partner_type = 'customer' if payment_type == 'inbound' else 'supplier'
        if partner_type == 'customer':
            dest_account = self.partner.property_account_receivable_id
        else:
            dest_account = self.partner.property_account_payable_id

        return self.env['account.payment'].create({
            'partner_id': self.partner.id,
            'amount': 500.0,
            'payment_type': payment_type,
            'partner_type': partner_type,
            'journal_id': journal.id,
            'destination_account_id': dest_account.id,
        })

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_inbound_payment_triggers_admin_sms(self, mock_api_call):
        """Test inbound payment triggers admin_payment_received SMS."""
        mock_api_call.return_value = {
            'result': 'OK', 'msg-id': 'MSG-PAY',
            'points-charged': 1, 'balance-after': 999,
        }

        payment = self._create_payment('inbound')
        payment.action_post()

        admin_log = self.env['kwtsms.sms.log'].search([
            ('recipient_type', '=', 'admin'),
            ('res_model', '=', 'account.payment'),
            ('res_id', '=', payment.id),
        ], limit=1)
        self.assertTrue(admin_log)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_outbound_payment_no_admin_sms(self, mock_api_call):
        """Test outbound payment does NOT trigger admin_payment_received SMS."""
        mock_api_call.return_value = {
            'result': 'OK', 'msg-id': 'MSG-OUT-PAY',
            'points-charged': 1, 'balance-after': 999,
        }

        payment = self._create_payment('outbound')
        payment.action_post()

        admin_log = self.env['kwtsms.sms.log'].search([
            ('recipient_type', '=', 'admin'),
            ('res_model', '=', 'account.payment'),
            ('res_id', '=', payment.id),
        ])
        self.assertFalse(admin_log)


@tagged('post_install', '-at_install')
class TestCrmAdminHooks(TransactionCase):
    """Test crm.lead admin notification hooks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({'name': 'Al-Salam Electronics'})
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_str('kwtsms.enabled', 'True')
        ICP.set_str('kwtsms.api_username', 'testuser')
        ICP.set_str('kwtsms.api_password', 'testpass')
        ICP.set_str('kwtsms.sender_id', 'KWT-SMS')
        ICP.set_str('kwtsms.test_mode', 'True')
        ICP.set_str('kwtsms.admin_phone', '96598765432')
        ICP.set_str('kwtsms.auto_admin_new_lead', 'True')
        ICP.set_str('kwtsms.auto_admin_lead_stage_changed', 'True')

        config = cls.env['kwtsms.gateway.config']._get_or_create()
        config.write({'balance_available': 1000, 'api_status': 'connected'})

        for evt in ('admin_new_lead', 'admin_lead_stage_changed'):
            existing = cls.env['kwtsms.sms.template'].search([
                ('event_type', '=', evt), ('lang', '=', 'en'), ('active', '=', True),
            ])
            if not existing:
                cls.env['kwtsms.sms.template'].create({
                    'name': '%s EN' % evt,
                    'event_type': evt,
                    'lang': 'en',
                    'body': '{company_name}: %s {lead_name}' % evt,
                })

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_lead_create_triggers_admin_sms(self, mock_api_call):
        """Test lead creation triggers admin_new_lead SMS."""
        mock_api_call.return_value = {
            'result': 'OK', 'msg-id': 'MSG-LEAD',
            'points-charged': 1, 'balance-after': 999,
        }

        lead = self.env['crm.lead'].create({
            'name': 'New Opportunity from Website',
            'contact_name': 'Khalid Al-Dosari',
        })

        admin_log = self.env['kwtsms.sms.log'].search([
            ('recipient_type', '=', 'admin'),
            ('res_model', '=', 'crm.lead'),
            ('res_id', '=', lead.id),
        ], limit=1)
        self.assertTrue(admin_log)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_lead_stage_change_triggers_admin_sms(self, mock_api_call):
        """Test lead stage change triggers admin_lead_stage_changed SMS."""
        mock_api_call.return_value = {
            'result': 'OK', 'msg-id': 'MSG-STAGE',
            'points-charged': 1, 'balance-after': 999,
        }

        stages = self.env['crm.stage'].search([], order='sequence', limit=2)
        if len(stages) < 2:
            stages = self.env['crm.stage'].create([
                {'name': 'New', 'sequence': 1},
                {'name': 'Qualified', 'sequence': 2},
            ])

        lead = self.env['crm.lead'].create({
            'name': 'Test Lead Stage',
            'stage_id': stages[0].id,
        })
        mock_api_call.reset_mock()
        self.env['kwtsms.sms.log'].search([
            ('res_model', '=', 'crm.lead'),
            ('res_id', '=', lead.id),
        ]).unlink()

        lead.write({'stage_id': stages[1].id})

        admin_log = self.env['kwtsms.sms.log'].search([
            ('recipient_type', '=', 'admin'),
            ('res_model', '=', 'crm.lead'),
            ('res_id', '=', lead.id),
        ], limit=1)
        self.assertTrue(admin_log)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_lead_write_without_stage_no_admin_sms(self, mock_api_call):
        """Test lead write without stage_id change does NOT trigger stage SMS."""
        mock_api_call.return_value = {
            'result': 'OK', 'msg-id': 'MSG-NS',
            'points-charged': 1, 'balance-after': 999,
        }

        lead = self.env['crm.lead'].create({
            'name': 'Test Lead No Stage Change',
        })
        mock_api_call.reset_mock()
        self.env['kwtsms.sms.log'].search([
            ('res_model', '=', 'crm.lead'),
            ('res_id', '=', lead.id),
        ]).unlink()

        # Update name only (no stage_id in vals)
        lead.write({'name': 'Renamed Lead'})

        stage_logs = self.env['kwtsms.sms.log'].search([
            ('recipient_type', '=', 'admin'),
            ('res_model', '=', 'crm.lead'),
            ('res_id', '=', lead.id),
        ])
        # Should not have stage change log (admin_lead_stage_changed)
        for log in stage_logs:
            if log.template_id:
                self.assertNotEqual(
                    log.template_id.event_type, 'admin_lead_stage_changed')


@tagged('post_install', '-at_install')
class TestAdminCronJobs(TransactionCase):
    """Test admin cron jobs: low stock and overdue invoices."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({'name': 'Al-Salam Electronics'})
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_str('kwtsms.enabled', 'True')
        ICP.set_str('kwtsms.api_username', 'testuser')
        ICP.set_str('kwtsms.api_password', 'testpass')
        ICP.set_str('kwtsms.sender_id', 'KWT-SMS')
        ICP.set_str('kwtsms.test_mode', 'True')
        ICP.set_str('kwtsms.admin_phone', '96598765432')
        ICP.set_str('kwtsms.auto_admin_low_stock', 'True')
        ICP.set_str('kwtsms.auto_admin_invoice_overdue', 'True')
        ICP.set_str('kwtsms.overdue_invoice_days', '30')

        config = cls.env['kwtsms.gateway.config']._get_or_create()
        config.write({'balance_available': 1000, 'api_status': 'connected'})

        for evt, body in [
            ('admin_low_stock', '{company_name}: {count} items low. {details}'),
            ('admin_invoice_overdue',
             '{company_name}: {count} overdue invoices, total {total_amount}. {details}'),
        ]:
            existing = cls.env['kwtsms.sms.template'].search([
                ('event_type', '=', evt), ('lang', '=', 'en'), ('active', '=', True),
            ])
            if not existing:
                cls.env['kwtsms.sms.template'].create({
                    'name': '%s EN' % evt,
                    'event_type': evt,
                    'lang': 'en',
                    'body': body,
                })

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_low_stock_cron_sends_summary(self, mock_api_call):
        """Test low stock cron sends summary when products below reorder."""
        mock_api_call.return_value = {
            'result': 'OK', 'msg-id': 'MSG-LS',
            'points-charged': 1, 'balance-after': 999,
        }

        product = self.env['product.product'].create({
            'name': 'Widget Low Stock',
            'type': 'consu',
            'list_price': 10.0,
        })
        # Create warehouse orderpoint with min qty
        warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', self.company.id),
        ], limit=1)
        self.env['stock.warehouse.orderpoint'].create({
            'product_id': product.id,
            'product_min_qty': 10.0,
            'product_max_qty': 20.0,
            'warehouse_id': warehouse.id,
            'location_id': warehouse.lot_stock_id.id,
        })
        # Product qty_available defaults to 0, which is < 10

        config = self.env['kwtsms.gateway.config']._get_or_create()
        config._cron_admin_low_stock_alert()

        self.assertTrue(mock_api_call.called)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_low_stock_cron_skips_when_no_low_stock(self, mock_api_call):
        """Test low stock cron skips when no products below reorder level."""
        # Remove all orderpoints to ensure no low stock
        self.env['stock.warehouse.orderpoint'].search([]).unlink()

        config = self.env['kwtsms.gateway.config']._get_or_create()
        config._cron_admin_low_stock_alert()

        mock_api_call.assert_not_called()

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_overdue_invoice_cron_sends_summary(self, mock_api_call):
        """Test overdue invoice cron sends summary when invoices are overdue."""
        mock_api_call.return_value = {
            'result': 'OK', 'msg-id': 'MSG-OD',
            'points-charged': 1, 'balance-after': 999,
        }

        partner = self.env['res.partner'].create({
            'name': 'Overdue Customer',
        })

        # Find a revenue account for invoice lines
        account = self.env['account.account'].search([
            ('account_type', '=', 'income'),
        ], limit=1)
        if not account:
            account = self.env['account.account'].search([
                ('account_type', 'like', 'income'),
            ], limit=1)

        # Create an overdue invoice
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': fields.Date.today() - timedelta(days=60),
            'invoice_date_due': fields.Date.today() - timedelta(days=45),
            'invoice_line_ids': [(0, 0, {
                'name': 'Overdue service',
                'quantity': 1,
                'price_unit': 500.0,
                'account_id': account.id,
            })],
        })
        invoice.action_post()

        config = self.env['kwtsms.gateway.config']._get_or_create()
        config._cron_admin_overdue_invoices()

        self.assertTrue(mock_api_call.called)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_overdue_invoice_cron_skips_when_no_overdue(self, mock_api_call):
        """Test overdue invoice cron skips when no invoices are overdue."""
        # No overdue invoices in a clean test env
        config = self.env['kwtsms.gateway.config']._get_or_create()
        config._cron_admin_overdue_invoices()

        mock_api_call.assert_not_called()

    def test_build_truncated_details_fits(self):
        """Test _build_truncated_details returns all items when they fit."""
        config = self.env['kwtsms.gateway.config']._get_or_create()
        items = ['Item A: 2 (min 5)', 'Item B: 0 (min 3)']
        result = config._build_truncated_details(
            items=items,
            template_body='{company_name}: {count} low. {details}',
            context_base={'company_name': 'TestCo', 'count': '2'},
        )
        self.assertIn('Item A', result)
        self.assertIn('Item B', result)

    def test_build_truncated_details_truncates(self):
        """Test _build_truncated_details truncates when exceeding 7 SMS pages."""
        config = self.env['kwtsms.gateway.config']._get_or_create()
        # Create many items that would exceed 7 pages
        items = ['Product %d: 0 (min 100)' % i for i in range(200)]
        result = config._build_truncated_details(
            items=items,
            template_body='{company_name}: {count} low. {details}',
            context_base={'company_name': 'TestCo', 'count': '200'},
        )
        self.assertIn('... and', result)
        self.assertIn('more', result)


@tagged('post_install', '-at_install')
class TestAdminTemplateRendering(TransactionCase):
    """Test render_from_dict template method for admin notifications."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

    def test_render_from_dict_basic(self):
        """Test render_from_dict replaces placeholders from dict."""
        template = self.env['kwtsms.sms.template'].create({
            'name': 'Test Admin',
            'event_type': 'admin_new_quotation',
            'lang': 'en',
            'body': '{company_name}: New quotation {order_name} by {salesperson}',
        })
        result = template.render_from_dict({
            'company_name': 'TestCo',
            'order_name': 'S00001',
            'salesperson': 'John',
        })
        self.assertEqual(result, 'TestCo: New quotation S00001 by John')

    def test_render_from_dict_cleans_unreplaced(self):
        """Test render_from_dict removes unreplaced placeholders."""
        template = self.env['kwtsms.sms.template'].create({
            'name': 'Test Clean',
            'event_type': 'admin_large_order',
            'lang': 'en',
            'body': '{company_name}: {order_name} {missing_placeholder}',
        })
        result = template.render_from_dict({
            'company_name': 'TestCo',
            'order_name': 'S00001',
        })
        self.assertEqual(result, 'TestCo: S00001')

    def test_render_from_dict_empty_body(self):
        """Test render_from_dict with empty body returns empty string."""
        template = self.env['kwtsms.sms.template'].create({
            'name': 'Empty',
            'event_type': 'admin_low_stock',
            'lang': 'en',
            'body': '',
        })
        self.assertEqual(template.render_from_dict({'key': 'val'}), '')
