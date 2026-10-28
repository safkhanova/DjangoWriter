from django import forms
from django.contrib import admin, messages
from django.db import models
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from reversion.admin import VersionAdmin
from unfold.admin import ModelAdmin, StackedInline, TabularInline
from unfold.contrib.forms.widgets import WysiwygWidget
from unfold.decorators import action, display
from unfold.widgets import UnfoldAdminIntegerFieldWidget, UnfoldAdminTextareaWidget

from newsletter.models import NewsletterIssue, Subscriber
from newsletter.services import queue_article_newsletter

from .models import Article, ArticleBlock, ArticleImage, Category, Section, Tag


# --- Sections -------------------------------------------------------------------

class CategoryInline(TabularInline):
    model = Category
    extra = 0
    fields = ("name", "order")
    ordering_field = "order"
    hide_ordering_field = True
    verbose_name_plural = "Növlər (bu bölmənin daxilində yazı növləri: Hekayə, Şeir, Qəzet ...)"


@admin.register(Section)
class SectionAdmin(VersionAdmin, ModelAdmin):
    inlines = [CategoryInline]
    warn_unsaved_form = True
    list_display = ("title", "layout", "visible_badge", "is_visible", "show_in_nav", "article_count")
    list_display_links = ("title",)
    list_editable = ("is_visible", "show_in_nav")
    ordering_field = "order"
    hide_ordering_field = True
    actions_row = ["open_on_site"]
    fieldsets = (
        (None, {"fields": ("title", "is_visible", "layout", "theme", "intro_text")}),
        ("Hero altındakı kart", {"fields": ("show_in_hero_cards", "number_label", "card_subtitle", "highlight_card")}),
        ("Ana səhifədə", {"fields": ("show_in_nav", "items_on_homepage", "see_all_label", "show_category_filter")}),
        ("Əlavə düymə", {
            "fields": ("cta_label", "cta_topic", "cta_url"),
            "description": "Məsələn «Seansı təyin et» və ya «Kitabı sifariş et». Düymə əlaqə formunu seçilmiş mövzu ilə açır.",
        }),
        ("Ünvan və SEO", {"fields": ("slug", "seo_title", "seo_description"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_articles=models.Count("articles"))

    @display(description="Görünürlük", label={"Görünür": "success", "Gizli": "danger"})
    def visible_badge(self, obj):
        return "Görünür" if obj.is_visible else "Gizli"

    @display(description="Yazı sayı", ordering="_articles")
    def article_count(self, obj):
        return obj._articles

    @action(description="Saytda bax", icon="open_in_new", attrs={"target": "_blank"})
    def open_on_site(self, request, object_id):
        return redirect(Section.objects.get(pk=object_id).get_absolute_url())


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ("name", "section", "order")
    list_filter = ("section",)
    search_fields = ("name",)
    fields = ("section", "name", "slug", "order")


@admin.register(Tag)
class TagAdmin(ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    fields = ("name", "slug")


# --- Articles -------------------------------------------------------------------

class ArticleBlockForm(forms.ModelForm):
    class Meta:
        model = ArticleBlock
        fields = "__all__"
        widgets = {
            "text": WysiwygWidget,
            "image_width": UnfoldAdminIntegerFieldWidget(attrs={"min": 20, "max": 100, "step": 5}),
        }


class ArticleBlockInline(StackedInline):
    model = ArticleBlock
    form = ArticleBlockForm
    extra = 0
    min_num = 0
    ordering_field = "order"
    hide_ordering_field = True
    show_count = True
    template_before = "admin/content/blocks_help.html"
    fields = (
        ("type", "is_visible"),
        "heading",
        "text",
        "image",
        "image_alt",
        ("image_position", "image_width"),
        "text_wrap",
        "caption",
        "youtube_url",
        "quote_author",
        "file",
        ("button_label", "button_url"),
    )


class ArticleImageInline(TabularInline):
    model = ArticleImage
    extra = 0
    fields = ("image", "alt", "caption", "order")
    ordering_field = "order"
    hide_ordering_field = True
    tab = True
    verbose_name_plural = "Qalereya"


class ArticleAdminForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = "__all__"
        widgets = {"excerpt": UnfoldAdminTextareaWidget(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields.get("category")
        if field is None:
            return
        # Only the chosen section's types are valid choices (also enforced on POST).
        # admin/content/article_form.js swaps the options live when the section changes.
        section_id = self.data.get("section") if self.is_bound else (
            self.instance.section_id or self.initial.get("section")
        )
        section_id = section_id if str(section_id or "").isdigit() else None
        field.queryset = Category.objects.filter(section_id=section_id) if section_id else Category.objects.none()
        field.label_from_instance = lambda category: category.name
        field.empty_label = "Seçin" if section_id else "Əvvəlcə bölməni seçin"
        field.help_text = "Yalnız seçilmiş bölməyə aid növlər göstərilir. Yeni növ «Növlər» menyusundan əlavə olunur."


class ScheduledFilter(admin.SimpleListFilter):
    title = "Vəziyyət"
    parameter_name = "veziyyet"

    def lookups(self, request, model_admin):
        return [("live", "Saytda görünür"), ("scheduled", "Planlaşdırılıb"), ("draft", "Qaralama")]

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == "live":
            return queryset.filter(status=Article.Status.PUBLISHED, publish_at__lte=now)
        if self.value() == "scheduled":
            return queryset.filter(status=Article.Status.PUBLISHED, publish_at__gt=now)
        if self.value() == "draft":
            return queryset.filter(status=Article.Status.DRAFT)
        return queryset


@admin.register(Article)
class ArticleAdmin(VersionAdmin, ModelAdmin):
    form = ArticleAdminForm

    class Media:
        js = ("admin/content/article_form.js",)

    inlines = [ArticleBlockInline, ArticleImageInline]
    warn_unsaved_form = True
    list_display = (
        "title", "section", "category", "authorship_badge", "state_badge", "is_featured", "is_pinned", "publish_at",
        "newsletter_badge",
    )
    list_display_links = ("title",)
    list_editable = ("is_featured", "is_pinned")
    list_filter = (ScheduledFilter, "authorship", "section", "category", "is_featured", "is_pinned", "tags")
    list_filter_submit = True
    search_fields = ("title", "excerpt", "source_name", "original_author", "blocks__text")
    date_hierarchy = "publish_at"
    autocomplete_fields = ("tags",)
    readonly_fields = ("state_info",)
    change_form_before_template = "admin/content/article_form_data.html"
    actions = ["publish", "unpublish", "duplicate"]
    actions_row = ["preview_row"]
    actions_detail = ["preview_detail", "send_newsletter"]
    list_per_page = 30

    fieldsets = (
        (None, {"fields": ("state_info", "section", "category", "authorship", "title", "excerpt", "tags")}),
        ("Dərc", {"fields": ("status", "publish_at", ("is_featured", "is_pinned"))}),
        ("Üz şəkli", {"fields": ("cover_image", "cover_alt", "show_cover")}),
        ("Link, PDF və mənbə", {
            "fields": ("link_mode", "external_url", "pdf_file", "source_name", "source_year", "original_author"),
            "classes": ("tab",),
            "description": "Media arxivi üçün: qəzet adı, il, müəllif və yazının harada açılacağı (sayt səhifəsi, xarici link və ya PDF skan).",
        }),
        ("Audio və video", {
            "fields": ("audio_file", "video_url", "video_duration"),
            "classes": ("tab",),
        }),
        ("SEO və ünvan", {"fields": ("slug", "seo_title", "seo_description"), "classes": ("tab",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("section", "category", "newsletter_issue")

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["block_fields_map"] = {k.value: v for k, v in ArticleBlock.FIELDS_BY_TYPE.items()}
        extra_context["categories_by_section"] = {
            section_id: [[c.pk, c.name] for c in Category.objects.filter(section_id=section_id)]
            for section_id in Section.objects.values_list("pk", flat=True)
        }
        return super().changeform_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        if not obj.author_id:
            obj.author = request.user
        super().save_model(request, obj, form, change)

    # --- display ---

    @display(
        description="Vəziyyət",
        label={"Saytda": "success", "Planlaşdırılıb": "info", "Qaralama": "warning", "Bölmə gizlidir": "danger"},
    )
    def state_badge(self, obj):
        if obj.status == Article.Status.DRAFT:
            return "Qaralama"
        if obj.is_scheduled:
            return "Planlaşdırılıb"
        if not obj.section.is_visible:
            return "Bölmə gizlidir"
        return "Saytda"

    @display(
        description="Kim yazıb",
        label={"Mənim yazım": "success", "Müsahibə": "info", "Haqqımda": "warning", "Adım çəkilir": "default"},
    )
    def authorship_badge(self, obj):
        return obj.authorship_label or "Mənim yazım"

    @display(description="Bülleten", label={"Göndərilib": "success", "—": "default"})
    def newsletter_badge(self, obj):
        return "Göndərilib" if hasattr(obj, "newsletter_issue") else "—"

    @display(description="Hazırkı vəziyyət")
    def state_info(self, obj):
        if not obj.pk:
            return "Yeni yazı. Yadda saxladıqdan sonra «Saytda önizlə» ilə necə görünəcəyinə baxa bilərsiniz."
        texts = {
            "Qaralama": "Qaralama — yalnız siz (daxil olduqda) görürsünüz.",
            "Planlaşdırılıb": f"Planlaşdırılıb — {timezone.localtime(obj.publish_at):%d.%m.%Y %H:%M} tarixində avtomatik görünəcək.",
            "Bölmə gizlidir": "Dərc olunub, amma bölmə gizli olduğu üçün ziyarətçilər görmür.",
            "Saytda": "Saytda — hamı görür.",
        }
        return format_html(
            '{} &nbsp; <a href="{}" target="_blank" class="text-primary-600 font-semibold">Saytda önizlə ↗</a>',
            texts[self.state_badge(obj)], obj.get_absolute_url(),
        )

    # --- actions ---

    @action(description="Önizlə", icon="visibility", attrs={"target": "_blank"})
    def preview_row(self, request, object_id):
        return redirect(Article.objects.get(pk=object_id).get_absolute_url())

    @action(description="Saytda önizlə", icon="visibility", attrs={"target": "_blank"})
    def preview_detail(self, request, object_id):
        return redirect(Article.objects.get(pk=object_id).get_absolute_url())

    @action(description="Abunəçilərə göndər", icon="send", permissions=["send_newsletter"])
    def send_newsletter(self, request, object_id):
        article = Article.objects.select_related("section").get(pk=object_id)
        change_url = reverse("admin:content_article_change", args=[object_id])
        if request.method == "POST":
            try:
                issue = queue_article_newsletter(article, request.user)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    f"Bülleten {issue.recipients_count} abunəçiyə göndərilmək üçün növbəyə qoyuldu. "
                    "Bir neçə dəqiqə ərzində çatdırılacaq.",
                )
            return redirect(change_url)
        context = {
            **self.admin_site.each_context(request),
            "title": "Abunəçilərə göndər",
            "article": article,
            "already_sent": NewsletterIssue.objects.filter(article=article).first(),
            "recipients": Subscriber.objects.interested_in(article.section).count(),
            "change_url": change_url,
            "opts": self.model._meta,
        }
        return render(request, "admin/content/send_newsletter.html", context)

    def has_send_newsletter_permission(self, request, object_id=None):
        return request.user.has_perm("newsletter.add_newsletterissue")

    @admin.action(description="Seçilmişləri dərc et")
    def publish(self, request, queryset):
        updated = queryset.update(status=Article.Status.PUBLISHED)
        messages.success(request, f"{updated} yazı dərc olundu.")

    @admin.action(description="Seçilmişləri qaralamaya qaytar")
    def unpublish(self, request, queryset):
        updated = queryset.update(status=Article.Status.DRAFT)
        messages.success(request, f"{updated} yazı qaralamaya qaytarıldı.")

    @admin.action(description="Seçilmişlərin surətini çıxar (qaralama kimi)")
    def duplicate(self, request, queryset):
        for article in queryset:
            blocks, gallery, tags = list(article.blocks.all()), list(article.gallery.all()), list(article.tags.all())
            article.pk, article.slug = None, ""
            article.title = f"{article.title} (surət)"
            article.status, article.is_featured, article.is_pinned = Article.Status.DRAFT, False, False
            article.author = request.user
            article.save()
            article.tags.set(tags)
            for item in blocks + gallery:
                item.pk, item.article = None, article
                item.save()
        messages.success(request, "Surət(lər) qaralama kimi yaradıldı.")
