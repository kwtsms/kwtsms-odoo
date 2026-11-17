# Changelog

All notable changes to the kwtSMS Gateway for Odoo module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
with Odoo version prefix (e.g., 19.0.1.0.0).

## [Unreleased]

## [0.4.2] - 2026-11-18

### Fixed
- Signing in to Odoo failed (error 403) once the module was installed on current Odoo releases; sign-in works again.

### Upgrade notice
- If you cannot sign in after installing 19.0.4.0.1, upgrade the module from the server: `odoo -u kwtsms_sms -d <your database>`, then restart Odoo. Or remove the kwtsms_sms folder from your addons path and restart, then install 19.0.4.0.2.
- After Login or Logout on the Gateway page, Odoo showed "Missing Action"; the page now reloads normally.
- Arabic: Sender ID now reads "اسم المرسل", the wording used in the kwtSMS account.

## [0.4.1] - 2026-11-16

### Fixed
- A fresh install failed with "External ID not found"; the module now installs on a new database.

### Changed
- Phone examples show 965XXXXXXXX.
- Clearer help on test mode.

## [0.4.0] - 2026-03-17

### Added
- SMS OTP for portal and backend login, signup and password reset.
- Passwordless phone login.
- Remember this device.
- Odoo 19 two-factor login support.
- New Settings page.
- OTP SMS template in English and Arabic.
- CAPTCHA support.

## [0.3.0] - 2026-03-16

### Added
- Admin SMS alerts for Sales, Inventory, Accounting and CRM.
- Daily low stock and overdue invoice summaries.
- Admin templates in English and Arabic.

## [0.2.2] - 2026-03-13

### Added
- Order cancelled, invoice posted and payment received SMS.
- Dashboard and Help pages.
- Test SMS on the Gateway page.
- Full Arabic translation.

### Fixed
- Bug fixes.

## [0.2.1] - 2026-03-11

### Changed
- One send method for single and bulk SMS, duplicates removed.

## [0.2.0] - 2026-03-10

### Added
- Bulk SMS to many numbers at once.

### Fixed
- Bug fixes.

## [0.1.0] - 2026-03-09

### Added
- First release: kwtSMS gateway for Odoo with order and delivery SMS, English and Arabic templates, bulk sending, test
  mode, SMS log, dashboard and help page.
