"""
emailotp/models.py
"""
from django.db import models


class EmailOTP(models.Model):
    """A single issued one-time code. The code itself is never stored."""
    email = models.EmailField(db_index=True)
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used = models.BooleanField(default=False)
    request_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['email', 'created_at']),
            models.Index(fields=['request_ip', 'created_at']),
        ]
        verbose_name = 'Email OTP'
        verbose_name_plural = 'Email OTPs'

    def __str__(self):
        return f"{self.email} @ {self.created_at:%Y-%m-%d %H:%M}"


class AuthEvent(models.Model):
    """Audit trail. Also backs the per-IP verification throttle."""
    CODE_REQUESTED = 'code_requested'
    CODE_SENT = 'code_sent'
    VERIFY_OK = 'verify_ok'
    VERIFY_FAIL = 'verify_fail'
    THROTTLED = 'throttled'

    KIND_CHOICES = [
        (CODE_REQUESTED, 'Code requested'),
        (CODE_SENT, 'Code sent'),
        (VERIFY_OK, 'Verify success'),
        (VERIFY_FAIL, 'Verify failure'),
        (THROTTLED, 'Throttled'),
    ]

    kind = models.CharField(max_length=20, choices=KIND_CHOICES, db_index=True)
    email = models.EmailField(db_index=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ip', 'created_at']),
            models.Index(fields=['email', 'created_at']),
            models.Index(fields=['kind', 'ip', 'created_at']),
        ]

    def __str__(self):
        return f"{self.kind} {self.email or self.ip} @ {self.created_at:%Y-%m-%d %H:%M}"
