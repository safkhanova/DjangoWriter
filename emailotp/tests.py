from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from . import services


User = get_user_model()


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='noreply@example.com',
)
class OtpEmailPresentationTests(TestCase):
    @patch('emailotp.services.secrets.randbelow', return_value=12345)
    def test_otp_email_has_plain_text_and_large_bold_html_code(self, _random):
        mail.outbox.clear()

        sent = services.issue_otp('recipient@example.com', '127.0.0.1')

        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn('012345', message.body)
        self.assertEqual(len(message.alternatives), 1)
        html = message.alternatives[0][0]
        self.assertIn('font-size:32px', html)
        self.assertIn('font-weight:700', html)
        self.assertIn('>012345</strong>', html)


@override_settings(
    EMAILOTP_USE_CAPTCHA=False,
    EMAILOTP_REGISTER_COLLECT_NAME=True,
    EMAILOTP_REGISTER_COLLECT_PASSWORD=False,
    EMAILOTP_ACTIVATE_EXISTING_INACTIVE=False,
)
class BlockedUserFlowTests(TestCase):
    def setUp(self):
        self.email = 'blocked@example.com'
        self.user = User.objects.create_user(
            username=self.email,
            email=self.email,
            is_active=False,
        )

    @patch('emailotp.conf.USE_CAPTCHA', False)
    @patch('emailotp.views.services.issue_otp')
    @patch('emailotp.views.services.notify_existing_account')
    def test_blocked_email_cannot_request_registration_code(
        self, notify_existing, issue_otp
    ):
        response = self.client.post(reverse('emailotp:register'), {
            'name': 'Blocked person',
            'email': self.email,
        })

        self.assertRedirects(
            response,
            reverse('emailotp:register_verify'),
            fetch_redirect_response=False,
        )
        issue_otp.assert_not_called()
        notify_existing.assert_not_called()

    @patch('emailotp.conf.USE_CAPTCHA', False)
    @patch('emailotp.views.services.issue_otp')
    def test_blocked_email_cannot_request_login_code(self, issue_otp):
        response = self.client.post(reverse('emailotp:login'), {
            'email': self.email,
            'remember': False,
        })

        self.assertRedirects(
            response,
            reverse('emailotp:login_verify'),
            fetch_redirect_response=False,
        )
        issue_otp.assert_not_called()

    @patch('emailotp.views.services.consume_otp', return_value=(True, None))
    def test_blocked_email_is_not_reactivated_after_verification(self, _consume):
        session = self.client.session
        session['emailotp_email'] = self.email
        session['emailotp_flow'] = 'register'
        session['emailotp_stage'] = 'code'
        session['emailotp_pending'] = {'name': 'Blocked person'}
        session.save()

        response = self.client.post(
            reverse('emailotp:register_verify'), {'code': '123456'}
        )

        self.assertRedirects(
            response,
            reverse('emailotp:register'),
            fetch_redirect_response=False,
        )
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertNotIn('_auth_user_id', self.client.session)


@override_settings(
    EMAILOTP_USE_CAPTCHA=False,
    EMAILOTP_REGISTER_COLLECT_NAME=True,
    EMAILOTP_REGISTER_COLLECT_PASSWORD=False,
)
class ExistingOtpFlowRegressionTests(TestCase):
    @patch('emailotp.conf.ACTIVATE_EXISTING_INACTIVE', True)
    @patch('emailotp.conf.USE_CAPTCHA', False)
    @patch('emailotp.views.services.issue_otp', return_value=True)
    def test_configured_inactive_account_reactivation_is_preserved(
        self, issue_otp
    ):
        email = 'reactivatable@example.com'
        User.objects.create_user(
            username=email, email=email, is_active=False
        )

        response = self.client.post(reverse('emailotp:register'), {
            'name': 'Returning person',
            'email': email,
        })

        self.assertRedirects(
            response,
            reverse('emailotp:register_verify'),
            fetch_redirect_response=False,
        )
        issue_otp.assert_called_once()

    @patch('emailotp.conf.USE_CAPTCHA', False)
    @patch('emailotp.views.services.issue_otp', return_value=True)
    def test_new_registration_still_requests_an_otp(self, issue_otp):
        response = self.client.post(reverse('emailotp:register'), {
            'name': 'New person',
            'email': 'new-person@example.com',
        })

        self.assertRedirects(
            response,
            reverse('emailotp:register_verify'),
            fetch_redirect_response=False,
        )
        issue_otp.assert_called_once()

    @patch('emailotp.conf.USE_CAPTCHA', False)
    @patch('emailotp.views.services.issue_otp')
    @patch('emailotp.views.services.notify_existing_account')
    def test_active_account_registration_keeps_existing_account_flow(
        self, notify_existing, issue_otp
    ):
        email = 'existing@example.com'
        User.objects.create_user(username=email, email=email)

        response = self.client.post(reverse('emailotp:register'), {
            'name': 'Existing person',
            'email': email,
        })

        self.assertRedirects(
            response,
            reverse('emailotp:register_verify'),
            fetch_redirect_response=False,
        )
        notify_existing.assert_called_once_with(email)
        issue_otp.assert_not_called()

    @patch('emailotp.conf.USE_CAPTCHA', False)
    @patch('emailotp.views.services.issue_otp', return_value=True)
    def test_active_account_login_still_requests_an_otp(self, issue_otp):
        email = 'login-user@example.com'
        User.objects.create_user(username=email, email=email)

        response = self.client.post(reverse('emailotp:login'), {
            'email': email,
            'remember': False,
        })

        self.assertRedirects(
            response,
            reverse('emailotp:login_verify'),
            fetch_redirect_response=False,
        )
        issue_otp.assert_called_once()

    @patch('emailotp.views.services.consume_otp', return_value=(True, None))
    def test_active_account_can_still_finish_login(self, _consume):
        email = 'verify-login@example.com'
        user = User.objects.create_user(username=email, email=email)
        session = self.client.session
        session['emailotp_email'] = email
        session['emailotp_flow'] = 'login'
        session['emailotp_stage'] = 'code'
        session['emailotp_remember'] = False
        session.save()

        response = self.client.post(
            reverse('emailotp:login_verify'), {'code': '123456'}
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            int(self.client.session['_auth_user_id']), user.pk
        )
