from django.contrib import admin, messages
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html
from reversion.admin import VersionAdmin
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action, display
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from emailotp.admin import AuthEventAdmin, EmailOTPAdmin
from emailotp.models import AuthEvent, EmailOTP

from .admin_confirm import confirm_then
from .models import ContactMessage, ContactTopic, Hero, HeroTag, SiteSettings, SocialLink, UserSession
from .sessions import purge_stale, revoke_sessions, revoke_user_sessions

# --- Auth: Unfold look; usernames must be e-mail addresses (emailotp lookup) ----

admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    actions = ["revoke_all_sessions"]
    actions_detail = ["revoke_sessions_detail"]

    @admin.action(description="Bütün cihazlardan çıxış et (sessiyaları ləğv et)")
    def revoke_all_sessions(self, request, queryset):
        total = sum(revoke_user_sessions(u, except_key=request.session.session_key) for u in queryset)
        messages.success(request, f"{total} sessiya ləğv edildi.")

    @action(description="Bütün cihazlardan çıxış et", icon="logout", permissions=["change"])
    def revoke_sessions_detail(self, request, object_id):
        user = User.objects.get(pk=object_id)
        back = reverse("admin:auth_user_change", args=[object_id])

        def run():
            count = revoke_user_sessions(user, except_key=request.session.session_key)
            messages.success(request, f"{user}: {count} sessiya ləğv edildi. Kompromis şübhəsi varsa, şifrəni də dəyişin.")
            return redirect(back)

        return confirm_then(
            request, self, title="Bütün cihazlardan çıxış", button="Bəli, çıxış et", back_url=back, run=run,
            message=f"{user} bütün cihazlardan dərhal çıxarılacaq (sizin hazırkı sessiyanız saxlanılır).",
        )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "username" in form.base_fields:
            form.base_fields["username"].help_text = (
                "Mütləq e-poçt ünvanı olmalıdır: giriş kodu bu ünvana göndərilir."
            )
        return form

    def save_model(self, request, obj, form, change):
        obj.username = obj.username.strip().lower()
        if "@" in obj.username and not obj.email:
            obj.email = obj.username
        super().save_model(request, obj, form, change)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass


admin.site.unregister(EmailOTP)
admin.site.unregister(AuthEvent)


@admin.register(EmailOTP)
class UnfoldEmailOTPAdmin(EmailOTPAdmin, ModelAdmin):
    pass


@admin.register(AuthEvent)
class UnfoldAuthEventAdmin(AuthEventAdmin, ModelAdmin):
    pass


# --- Singleton ------------------------------------------------------------------

class SingletonAdmin(ModelAdmin):
    """Opens the single row's edit form directly instead of a list."""

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = self.model.load()
        return redirect(reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk]))


@admin.register(SiteSettings)
class SiteSettingsAdmin(SingletonAdmin, VersionAdmin):
    warn_unsaved_form = True
    fieldsets = (
        ("Ümumi", {"fields": ("site_name", "logo", "favicon", "nav_cta_label", "footer_text")}),
        ("Dizayn", {
            "fields": ("font_preset", "color_preset"),
            "description": "Şrift və rəng hazır dəstlərdən seçilir ki, dizayn həmişə səliqəli qalsın.",
        }),
        ("Əlaqə bölməsi", {
            "fields": ("show_contact_section", "contact_title", "contact_text", "contact_email", "notification_email"),
        }),
        ("Abunə formu", {"fields": ("show_subscribe_box", "subscribe_title", "subscribe_text")}),
        ("Google və sosial şəbəkələr (SEO)", {
            "fields": ("seo_title", "seo_description", "og_image"),
            "classes": ("collapse",),
        }),
        ("Texniki", {"fields": ("analytics_snippet",), "classes": ("collapse",)}),
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if not request.user.is_superuser:
            fieldsets = [fs for fs in fieldsets if fs[0] != "Texniki"]
        return fieldsets


# --- Hero -----------------------------------------------------------------------

class HeroTagInline(TabularInline):
    model = HeroTag
    extra = 0
    fields = ("label", "is_visible", "order")
    ordering_field = "order"
    hide_ordering_field = True


@admin.register(Hero)
class HeroAdmin(VersionAdmin, ModelAdmin):
    inlines = [HeroTagInline]
    warn_unsaved_form = True
    list_display = ("name", "status_badge", "title_line_1", "updated_at")
    list_display_links = ("name",)
    actions = ["duplicate"]
    actions_detail = ["activate_detail", "preview_detail"]
    actions_row = ["activate_row", "preview_row"]
    fieldsets = (
        (None, {"fields": ("name", "is_active")}),
        ("Mətn", {"fields": ("title_line_1", "title_line_2", "intro_text", "font_preset")}),
        ("Şəkil", {"fields": ("portrait", "portrait_alt", "portrait_position")}),
        ("Görünüş", {"fields": ("show_section_cards",)}),
    )

    @display(description="Status", label={"Aktiv": "success", "Qaralama": "warning"})
    def status_badge(self, obj):
        return "Aktiv" if obj.is_active else "Qaralama"

    def _activate(self, request, pk):
        hero = Hero.objects.get(pk=pk)
        back = reverse("admin:core_hero_changelist")

        def run():
            hero.activate()
            messages.success(request, f"«{hero}» indi saytda göstərilir. Digər versiyalar qaralamadır.")
            return redirect(back)

        return confirm_then(
            request, self, title="Hero versiyasını aktiv et", button="Bəli, aktiv et", back_url=back, run=run,
            message=f"«{hero}» saytda göstəriləcək, hazırkı aktiv versiya qaralamaya keçəcək.",
        )

    def _preview(self, request, pk):
        return redirect(f"{reverse('core:home')}?hero={pk}")

    @action(description="Aktiv et", icon="check_circle", permissions=["change"])
    def activate_detail(self, request, object_id):
        return self._activate(request, object_id)

    @action(description="Aktiv et", icon="check_circle", permissions=["change"])
    def activate_row(self, request, object_id):
        return self._activate(request, object_id)

    @action(description="Saytda önizlə", icon="visibility", attrs={"target": "_blank"})
    def preview_detail(self, request, object_id):
        return self._preview(request, object_id)

    @action(description="Önizlə", icon="visibility", attrs={"target": "_blank"})
    def preview_row(self, request, object_id):
        return self._preview(request, object_id)

    @admin.action(description="Seçilmiş versiyaların surətini çıxar (qaralama kimi)")
    def duplicate(self, request, queryset):
        for hero in queryset:
            tags = list(hero.tags.all())
            hero.pk, hero.is_active = None, False
            hero.name = f"{hero.name} (surət)"
            hero.save()
            HeroTag.objects.bulk_create(
                HeroTag(hero=hero, label=t.label, is_visible=t.is_visible, order=t.order) for t in tags
            )
        messages.success(request, "Surət yaradıldı.")


# --- Lists ----------------------------------------------------------------------

@admin.register(SocialLink)
class SocialLinkAdmin(ModelAdmin):
    list_display = ("name", "icon", "url", "is_visible", "order")
    list_editable = ("is_visible",)
    ordering_field = "order"
    hide_ordering_field = True


@admin.register(ContactTopic)
class ContactTopicAdmin(ModelAdmin):
    list_display = ("name", "is_visible", "order")
    list_editable = ("is_visible",)
    ordering_field = "order"
    hide_ordering_field = True


@admin.register(ContactMessage)
class ContactMessageAdmin(ModelAdmin):
    list_display = ("read_badge", "name", "email", "topic", "created_at")
    list_display_links = ("name",)
    list_filter = ("is_read", "is_archived", "topic", "created_at")
    search_fields = ("name", "email", "message")
    readonly_fields = ("name", "email", "phone", "topic", "message", "created_at", "reply_link", "ip_address")
    fields = ("reply_link", "name", "email", "phone", "topic", "created_at", "message", "is_read", "is_archived")
    actions = ["mark_read", "mark_unread", "archive"]
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Archived messages are hidden unless the archive filter is used.
        if "is_archived__exact" not in request.GET:
            qs = qs.filter(is_archived=False)
        return qs

    def change_view(self, request, object_id, form_url="", extra_context=None):
        ContactMessage.objects.filter(pk=object_id, is_read=False).update(is_read=True)
        return super().change_view(request, object_id, form_url, extra_context)

    @display(description="", label={"Yeni": "info", "Oxunub": "success"})
    def read_badge(self, obj):
        return "Oxunub" if obj.is_read else "Yeni"

    @display(description="Cavab ver")
    def reply_link(self, obj):
        subject = f"Re: {obj.topic or 'Mesajınız'}"
        return format_html('<a class="text-primary-600 font-semibold" href="mailto:{}?subject={}">✉ {} ünvanına cavab yaz</a>', obj.email, subject, obj.email)

    @admin.action(description="Oxunmuş kimi qeyd et")
    def mark_read(self, request, queryset):
        queryset.update(is_read=True)

    @admin.action(description="Oxunmamış kimi qeyd et")
    def mark_unread(self, request, queryset):
        queryset.update(is_read=False)

    @admin.action(description="Arxivə göndər")
    def archive(self, request, queryset):
        queryset.update(is_archived=True, is_read=True)


# --- Active sessions (every staff member sees and revokes their own) -----------------

@admin.register(UserSession)
class UserSessionAdmin(ModelAdmin):
    list_display = ("device", "current_badge", "ip_address", "created_at", "last_seen_at")
    list_display_links = None
    actions = ["revoke_selected"]
    actions_list = ["revoke_other_devices"]
    _current_key = None  # set per request in get_changelist_instance, read by current_badge

    def get_list_display(self, request):
        if request.user.is_superuser:
            return ("user", *self.list_display)
        return self.list_display

    def get_list_filter(self, request):
        return ("user",) if request.user.is_superuser else ()

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("user")
        return qs if request.user.is_superuser else qs.filter(user=request.user)

    def changelist_view(self, request, extra_context=None):
        purge_stale()
        return super().changelist_view(request, extra_context)

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    # Permissions: any staff member may view/revoke their own sessions (queryset is scoped).
    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request) and (obj is None or request.user.is_superuser or obj.user_id == request.user.pk)

    def has_delete_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)

    def has_revoke_permission(self, request):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @display(description="Cihaz")
    def device(self, obj):
        return obj.device

    @display(description="", label={"Bu cihaz": "success"})
    def current_badge(self, obj):
        return "Bu cihaz" if obj.session_key == self._current_key else ""

    def get_changelist_instance(self, request):
        self._current_key = request.session.session_key
        return super().get_changelist_instance(request)

    @admin.action(description="Seçilmiş sessiyaları ləğv et (həmin cihazlardan çıxış)", permissions=["revoke"])
    def revoke_selected(self, request, queryset):
        count = revoke_sessions(queryset.exclude(session_key=request.session.session_key))
        messages.success(request, f"{count} sessiya ləğv edildi. (Hazırkı cihazınız saxlanıldı.)")

    @action(description="Digər bütün cihazlardan çıx", icon="logout", permissions=["revoke"])
    def revoke_other_devices(self, request):
        back = reverse("admin:core_usersession_changelist")

        def run():
            count = revoke_user_sessions(request.user, except_key=request.session.session_key)
            messages.success(request, f"{count} digər cihazdan çıxış edildi.")
            return redirect(back)

        return confirm_then(
            request, self, title="Digər cihazlardan çıxış", button="Bəli, çıxış et", back_url=back, run=run,
            message="Bu cihazdan başqa bütün cihazlarda hesabınızdan dərhal çıxış ediləcək.",
        )
