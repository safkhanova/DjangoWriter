"""
emailotp/admin.py — read-only views over the OTP table and audit log.
"""
from django.contrib import admin

from .models import AuthEvent, EmailOTP


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ('email', 'created_at', 'expires_at', 'attempts', 'used', 'request_ip')
    list_filter = ('used', 'created_at')
    search_fields = ('email', 'request_ip')
    readonly_fields = ('email', 'code_hash', 'created_at', 'expires_at',
                       'attempts', 'used', 'request_ip')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AuthEvent)
class AuthEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'kind', 'email', 'ip')
    list_filter = ('kind', 'created_at')
    search_fields = ('email', 'ip', 'user_agent')
    readonly_fields = ('kind', 'email', 'ip', 'user_agent', 'created_at')
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
