import csv

from django.contrib import admin, messages
from django.http import HttpResponse
from unfold.admin import ModelAdmin
from unfold.decorators import display

from .models import NewsletterIssue, OutgoingEmail, Subscriber


def csv_safe(value) -> str:
    """Neutralise spreadsheet formulas (CSV injection): names come from a public form."""
    text = str(value)
    return f"'{text}" if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@admin.register(Subscriber)
class SubscriberAdmin(ModelAdmin):
    list_display = ("email", "name", "status_badge", "sections_list", "created_at")
    list_filter = ("is_confirmed", "sections", ("unsubscribed_at", admin.EmptyFieldListFilter))
    search_fields = ("email", "name")
    filter_horizontal = ("sections",)
    readonly_fields = ("created_at", "confirmed_at", "unsubscribed_at")
    fields = ("email", "name", "sections", "is_confirmed", "created_at", "confirmed_at", "unsubscribed_at")
    actions = ["export_csv", "unsubscribe"]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("sections")

    @display(description="Status", label={"Aktiv": "success", "Təsdiq gözləyir": "warning", "İmtina edib": "danger"})
    def status_badge(self, obj):
        if obj.unsubscribed_at:
            return "İmtina edib"
        return "Aktiv" if obj.is_confirmed else "Təsdiq gözləyir"

    @display(description="Bölmələr")
    def sections_list(self, obj):
        return ", ".join(s.title for s in obj.sections.all()) or "Hamısı"

    @admin.action(description="CSV faylına çıxar")
    def export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="abuneciler.csv"'
        response.write("﻿")  # Excel opens UTF-8 correctly with a BOM
        writer = csv.writer(response)
        writer.writerow(["E-poçt", "Ad", "Status", "Bölmələr", "Tarix"])
        for s in queryset:
            row = [s.email, s.name, self.status_badge(s), self.sections_list(s), f"{s.created_at:%d.%m.%Y}"]
            writer.writerow([csv_safe(cell) for cell in row])
        return response

    @admin.action(description="Abunəlikdən çıxar")
    def unsubscribe(self, request, queryset):
        from django.utils import timezone

        queryset.update(unsubscribed_at=timezone.now())


class ReadOnlyAdmin(ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(NewsletterIssue)
class NewsletterIssueAdmin(ReadOnlyAdmin):
    list_display = ("subject", "article", "created_at", "created_by", "recipients_count", "sent")
    readonly_fields = ("subject", "article", "created_at", "created_by", "recipients_count")

    @display(description="Çatdırılıb")
    def sent(self, obj):
        return f"{obj.sent_count} / {obj.recipients_count}"


@admin.register(OutgoingEmail)
class OutgoingEmailAdmin(ReadOnlyAdmin):
    list_display = ("to_email", "subject", "status", "attempts", "created_at", "sent_at")
    list_filter = ("status", "issue")
    search_fields = ("to_email", "subject")
    actions = ["retry"]

    def has_module_permission(self, request):
        return request.user.is_superuser

    @admin.action(description="Xətalıları yenidən növbəyə qoy")
    def retry(self, request, queryset):
        n = queryset.filter(status=OutgoingEmail.Status.FAILED).update(status=OutgoingEmail.Status.PENDING, attempts=0)
        messages.success(request, f"{n} e-poçt yenidən növbədədir.")
