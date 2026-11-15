# 2026-11-16 01:23 +03: Odoo 20 removed ir.config_parameter get_param/set_param; calls renamed to get_str/set_str. Task int-backport
"""Tests for Phase 4 OTP models, services, and MFA hooks."""

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged

from odoo.addons.kwtsms_sms.tools.otp_service import (
    generate_otp, hash_otp, verify_otp,
    generate_device_token, hash_device_token, hash_user_agent,
)


# =====================================================================
# OTP Service (pure crypto utilities)
# =====================================================================

@tagged('post_install', '-at_install')
class TestOtpService(TransactionCase):
    """Test otp_service.py cryptographic utilities."""

    # -- generate_otp --------------------------------------------------

    def test_generate_otp_default_length(self):
        """Default OTP is 6 digits."""
        code, hashed = generate_otp()
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())
        self.assertTrue(len(hashed) > 0)

    def test_generate_otp_custom_length(self):
        """Custom length is respected."""
        code, _ = generate_otp(length=8)
        self.assertEqual(len(code), 8)

    def test_generate_otp_minimum_length(self):
        """Lengths below 6 are clamped to 6."""
        code, _ = generate_otp(length=3)
        self.assertEqual(len(code), 6)

    def test_generate_otp_returns_different_codes(self):
        """Consecutive calls produce different codes (probabilistic)."""
        codes = {generate_otp()[0] for _ in range(20)}
        self.assertGreater(len(codes), 1)

    def test_generate_otp_hash_matches(self):
        """Returned hash matches the code."""
        code, hashed = generate_otp()
        self.assertTrue(verify_otp(code, hashed))

    # -- hash_otp / verify_otp ----------------------------------------

    def test_hash_otp_deterministic(self):
        """Same input always produces the same hash."""
        h1 = hash_otp('123456')
        h2 = hash_otp('123456')
        self.assertEqual(h1, h2)

    def test_hash_otp_different_inputs(self):
        """Different inputs produce different hashes."""
        h1 = hash_otp('123456')
        h2 = hash_otp('654321')
        self.assertNotEqual(h1, h2)

    def test_verify_otp_correct(self):
        """Correct code verifies True."""
        hashed = hash_otp('999999')
        self.assertTrue(verify_otp('999999', hashed))

    def test_verify_otp_wrong(self):
        """Wrong code verifies False."""
        hashed = hash_otp('999999')
        self.assertFalse(verify_otp('000000', hashed))

    def test_verify_otp_empty_input(self):
        """Empty input does not match any hash."""
        hashed = hash_otp('123456')
        self.assertFalse(verify_otp('', hashed))

    # -- device tokens -------------------------------------------------

    def test_generate_device_token_format(self):
        """Device token is 64 hex chars (256 bits)."""
        token, hashed = generate_device_token()
        self.assertEqual(len(token), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in token))
        self.assertTrue(len(hashed) > 0)

    def test_generate_device_token_unique(self):
        """Consecutive tokens are unique."""
        tokens = {generate_device_token()[0] for _ in range(10)}
        self.assertEqual(len(tokens), 10)

    def test_hash_device_token_deterministic(self):
        """Same token always hashes the same."""
        t, _ = generate_device_token()
        h1 = hash_device_token(t)
        h2 = hash_device_token(t)
        self.assertEqual(h1, h2)

    # -- hash_user_agent -----------------------------------------------

    def test_hash_user_agent_deterministic(self):
        """Same UA string hashes the same."""
        ua = 'Mozilla/5.0 Test'
        self.assertEqual(hash_user_agent(ua), hash_user_agent(ua))

    def test_hash_user_agent_different(self):
        """Different UA strings produce different hashes."""
        self.assertNotEqual(
            hash_user_agent('Chrome/1'),
            hash_user_agent('Firefox/2'),
        )

    def test_hash_user_agent_none(self):
        """None user agent hashes without error."""
        h = hash_user_agent(None)
        self.assertTrue(len(h) > 0)

    def test_hash_user_agent_empty(self):
        """Empty string hashes without error."""
        h = hash_user_agent('')
        self.assertTrue(len(h) > 0)
        self.assertEqual(h, hash_user_agent(None))


# =====================================================================
# OTP Token model
# =====================================================================

@tagged('post_install', '-at_install')
class TestOtpToken(TransactionCase):
    """Test kwtsms.otp.token model and cron cleanup."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Token = cls.env['kwtsms.otp.token'].sudo()

    def _create_token(self, **kw):
        vals = {
            'phone': '96598765432',
            'otp_hash': hash_otp('123456'),
            'otp_type': 'portal_login',
            'state': 'pending',
            'expires_at': fields.Datetime.now() + timedelta(minutes=5),
        }
        vals.update(kw)
        return self.Token.create(vals)

    def test_create_token(self):
        """Token creation stores all fields."""
        token = self._create_token()
        self.assertTrue(token.id)
        self.assertEqual(token.phone, '96598765432')
        self.assertEqual(token.state, 'pending')
        self.assertEqual(token.attempt_count, 0)

    def test_token_states(self):
        """All token states are valid."""
        for state in ('pending', 'verified', 'expired', 'locked'):
            token = self._create_token(state=state)
            self.assertEqual(token.state, state)

    def test_token_otp_types(self):
        """All OTP types are valid."""
        for otype in ('portal_login', 'backend_login', 'passwordless',
                      'signup', 'password_reset'):
            token = self._create_token(otp_type=otype)
            self.assertEqual(token.otp_type, otype)

    def test_cron_cleanup_expired_pending(self):
        """Cron deletes pending tokens past expiry."""
        token = self._create_token(
            expires_at=fields.Datetime.now() - timedelta(minutes=1),
        )
        self.Token._cron_cleanup_expired_tokens()
        self.assertFalse(token.exists())

    def test_cron_cleanup_old_completed(self):
        """Cron deletes verified/expired/locked tokens older than 24h."""
        token = self._create_token(state='verified')
        # Simulate old create_date
        self.env.cr.execute(
            "UPDATE kwtsms_otp_token SET create_date = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(hours=25), token.id),
        )
        self.Token._cron_cleanup_expired_tokens()
        self.assertFalse(token.exists())

    def test_cron_keeps_fresh_pending(self):
        """Cron does not delete pending tokens that haven't expired."""
        token = self._create_token(
            expires_at=fields.Datetime.now() + timedelta(minutes=5),
        )
        self.Token._cron_cleanup_expired_tokens()
        self.assertTrue(token.exists())

    def test_cron_keeps_recent_completed(self):
        """Cron does not delete completed tokens under 24h old."""
        token = self._create_token(state='verified')
        self.Token._cron_cleanup_expired_tokens()
        self.assertTrue(token.exists())

    def test_attempt_count_increment(self):
        """Attempt count increments correctly."""
        token = self._create_token()
        token.write({'attempt_count': token.attempt_count + 1})
        self.assertEqual(token.attempt_count, 1)
        token.write({'attempt_count': token.attempt_count + 1})
        self.assertEqual(token.attempt_count, 2)


# =====================================================================
# OTP Device Trust model
# =====================================================================

@tagged('post_install', '-at_install')
class TestOtpDevice(TransactionCase):
    """Test kwtsms.otp.device model and cron cleanup."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Device = cls.env['kwtsms.otp.device'].sudo()
        cls.user = cls.env['res.users'].create({
            'name': 'OTP Test User',
            'login': 'otp_test@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

    def _create_device(self, **kw):
        _, hashed = generate_device_token()
        vals = {
            'user_id': self.user.id,
            'device_hash': hashed,
            'user_agent_hash': hash_user_agent('Test Agent'),
            'expires_at': fields.Datetime.now() + timedelta(days=30),
        }
        vals.update(kw)
        return self.Device.create(vals)

    def test_create_device(self):
        """Device trust record creation."""
        device = self._create_device()
        self.assertTrue(device.id)
        self.assertEqual(device.user_id, self.user)

    def test_cron_cleanup_expired_devices(self):
        """Cron deletes expired device records."""
        device = self._create_device(
            expires_at=fields.Datetime.now() - timedelta(days=1),
        )
        self.Device._cron_cleanup_expired_devices()
        self.assertFalse(device.exists())

    def test_cron_keeps_valid_devices(self):
        """Cron keeps non-expired device records."""
        device = self._create_device(
            expires_at=fields.Datetime.now() + timedelta(days=15),
        )
        self.Device._cron_cleanup_expired_devices()
        self.assertTrue(device.exists())

    def test_cascade_delete_on_user_unlink(self):
        """Device records are deleted when user is deleted."""
        user2 = self.env['res.users'].create({
            'name': 'Temp User',
            'login': 'temp_otp@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        device = self._create_device(user_id=user2.id)
        device_id = device.id
        user2.unlink()
        self.assertFalse(self.Device.browse(device_id).exists())


# =====================================================================
# OTP Log model
# =====================================================================

@tagged('post_install', '-at_install')
class TestOtpLog(TransactionCase):
    """Test kwtsms.otp.log model and cron cleanup."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Log = cls.env['kwtsms.otp.log'].sudo()

    def _create_log(self, **kw):
        vals = {
            'phone': '96598765432',
            'action': 'request',
            'otp_type': 'portal_login',
            'ip_address': '127.0.0.1',
        }
        vals.update(kw)
        return self.Log.create(vals)

    def test_create_log(self):
        """OTP log creation stores all fields."""
        log = self._create_log()
        self.assertTrue(log.id)
        self.assertEqual(log.action, 'request')

    def test_all_action_types(self):
        """All action types are valid."""
        actions = [
            'request', 'resend', 'verify_ok', 'verify_failed',
            'expired', 'locked_out', 'invalid_phone', 'user_not_found',
            'captcha_failed', 'ambiguous_phone', 'device_trusted',
            'device_skip', 'device_revoked', 'password_changed',
        ]
        for action in actions:
            log = self._create_log(action=action)
            self.assertEqual(log.action, action)

    def test_cron_cleanup_old_logs(self):
        """Cron deletes logs older than retention days."""
        log = self._create_log()
        # Simulate old create_date (100 days ago, default retention 90)
        self.env.cr.execute(
            "UPDATE kwtsms_otp_log SET create_date = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(days=100), log.id),
        )
        self.Log._cron_cleanup_old_otp_logs()
        self.assertFalse(log.exists())

    def test_cron_keeps_recent_logs(self):
        """Cron keeps logs within retention period."""
        log = self._create_log()
        self.Log._cron_cleanup_old_otp_logs()
        self.assertTrue(log.exists())

    def test_cron_respects_custom_retention(self):
        """Cron uses custom retention_days from ICP."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_str('kwtsms.log_retention_days', '10')

        log = self._create_log()
        self.env.cr.execute(
            "UPDATE kwtsms_otp_log SET create_date = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(days=15), log.id),
        )
        self.Log._cron_cleanup_old_otp_logs()
        self.assertFalse(log.exists())

        # Restore
        ICP.set_str('kwtsms.log_retention_days', '90')

    def test_cron_zero_retention_skips(self):
        """Cron does nothing when retention_days is 0."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_str('kwtsms.log_retention_days', '0')

        log = self._create_log()
        self.env.cr.execute(
            "UPDATE kwtsms_otp_log SET create_date = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(days=200), log.id),
        )
        self.Log._cron_cleanup_old_otp_logs()
        self.assertTrue(log.exists())

        # Restore
        ICP.set_str('kwtsms.log_retention_days', '90')


# =====================================================================
# res.users MFA hooks
# =====================================================================

@tagged('post_install', '-at_install')
class TestResUsersMfa(TransactionCase):
    """Test res.users MFA hooks for SMS OTP."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ICP = cls.env['ir.config_parameter'].sudo()
        cls.backend_user = cls.env['res.users'].create({
            'name': 'Backend MFA',
            'login': 'backend_mfa@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.portal_user = cls.env['res.users'].create({
            'name': 'Portal MFA',
            'login': 'portal_mfa@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })

    def setUp(self):
        super().setUp()
        # Default: gateway enabled, OTP toggles off
        self.ICP.set_str('kwtsms.enabled', 'True')
        self.ICP.set_str('kwtsms.otp_backend_login', 'False')
        self.ICP.set_str('kwtsms.otp_portal_login', 'False')

    def test_mfa_type_none_when_disabled(self):
        """No MFA type when both toggles are off."""
        result = self.backend_user._mfa_type()
        self.assertFalse(result)

    def test_mfa_type_backend_enabled(self):
        """Backend user gets sms_otp when backend toggle is on."""
        self.ICP.set_str('kwtsms.otp_backend_login', 'True')
        self.assertEqual(self.backend_user._mfa_type(), 'sms_otp')

    def test_mfa_type_portal_enabled(self):
        """Portal user gets sms_otp when portal toggle is on."""
        self.ICP.set_str('kwtsms.otp_portal_login', 'True')
        self.assertEqual(self.portal_user._mfa_type(), 'sms_otp')

    def test_mfa_type_backend_toggle_no_portal(self):
        """Backend toggle does not affect portal users."""
        self.ICP.set_str('kwtsms.otp_backend_login', 'True')
        self.assertFalse(self.portal_user._mfa_type())

    def test_mfa_type_portal_toggle_no_backend(self):
        """Portal toggle does not affect backend users."""
        self.ICP.set_str('kwtsms.otp_portal_login', 'True')
        self.assertFalse(self.backend_user._mfa_type())

    def test_mfa_type_gateway_disabled(self):
        """No MFA when gateway is disabled, even with toggle on."""
        self.ICP.set_str('kwtsms.enabled', 'False')
        self.ICP.set_str('kwtsms.otp_backend_login', 'True')
        self.assertFalse(self.backend_user._mfa_type())

    def test_mfa_url_returns_verify(self):
        """MFA URL points to OTP verify page when sms_otp is active."""
        self.ICP.set_str('kwtsms.otp_backend_login', 'True')
        self.assertEqual(
            self.backend_user._mfa_url(), '/kwtsms/otp/verify',
        )

    def test_mfa_url_none_when_disabled(self):
        """MFA URL is falsy when OTP is not active."""
        result = self.backend_user._mfa_url()
        self.assertFalse(result)


# =====================================================================
# res.partner normalized phone
# =====================================================================

@tagged('post_install', '-at_install')
class TestResPartnerNormalizedPhone(TransactionCase):
    """Test res.partner kwtsms_phone_normalized computed field."""

    def test_normalized_phone_basic(self):
        """Phone is normalized and stored."""
        partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'phone': '+96598765432',
        })
        self.assertEqual(partner.kwtsms_phone_normalized, '96598765432')

    def test_normalized_phone_without_plus(self):
        """Phone without + prefix is normalized."""
        partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'phone': '96598765432',
        })
        self.assertEqual(partner.kwtsms_phone_normalized, '96598765432')

    def test_normalized_phone_with_spaces(self):
        """Phone with spaces is normalized."""
        partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'phone': '+965 9876 5432',
        })
        self.assertEqual(partner.kwtsms_phone_normalized, '96598765432')

    def test_normalized_phone_empty(self):
        """Empty phone results in False."""
        partner = self.env['res.partner'].create({
            'name': 'No Phone Partner',
        })
        self.assertFalse(partner.kwtsms_phone_normalized)

    def test_normalized_phone_updates_on_change(self):
        """Changing phone field updates the normalized field."""
        partner = self.env['res.partner'].create({
            'name': 'Update Partner',
            'phone': '+96598765432',
        })
        self.assertEqual(partner.kwtsms_phone_normalized, '96598765432')
        partner.write({'phone': '+96599887766'})
        self.assertEqual(partner.kwtsms_phone_normalized, '96599887766')

    def test_normalized_phone_cleared(self):
        """Clearing phone sets normalized to False."""
        partner = self.env['res.partner'].create({
            'name': 'Clear Partner',
            'phone': '98765432',
        })
        partner.write({'phone': False})
        self.assertFalse(partner.kwtsms_phone_normalized)

    def test_normalized_phone_arabic_digits(self):
        """Arabic/Hindi digits are converted before normalization."""
        partner = self.env['res.partner'].create({
            'name': 'Arabic Digits',
            'phone': '+\u0669\u0666\u0665\u0669\u0668\u0667\u0666\u0665\u0664\u0663\u0662',
        })
        # Arabic digits +96598765432
        self.assertEqual(partner.kwtsms_phone_normalized, '96598765432')
