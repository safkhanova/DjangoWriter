from django.contrib.sitemaps import Sitemap
from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from core.utils import is_preview_user

from .models import Article, ArticleBlock, Section, visible_sections


def section_detail(request, section_slug):
    section = get_object_or_404(visible_sections(request.user), slug=section_slug)
    articles = (
        Article.objects.visible_for(request.user)
        .filter(section=section)
        .select_related("category", "section")
        .listing_order()
    )
    active_category = None
    category_slug = request.GET.get("nov")
    if category_slug:
        active_category = section.categories.filter(slug=category_slug).first()
        if active_category:
            articles = articles.filter(category=active_category)

    # «Kim yazıb» filter, offered only when the section mixes own writing and writing about her.
    labels = {Article.Authorship.OWN: "Mənim yazılarım", Article.Authorship.INTERVIEW: "Müsahibələr",
              Article.Authorship.ABOUT: "Haqqımda", Article.Authorship.MENTION: "Adımın çəkildiyi yazılar"}
    present = set(articles.values_list("authorship", flat=True))
    authorship_choices = [(value, label) for value, label in labels.items() if value in present]
    active_authorship = request.GET.get("kim") if request.GET.get("kim") in labels else None
    if active_authorship:
        articles = articles.filter(authorship=active_authorship)

    page = Paginator(articles, 12).get_page(request.GET.get("page"))
    return render(
        request,
        "site/section_detail.html",
        {
            "section": section,
            "page_obj": page,
            "articles": page.object_list,
            "categories": section.categories.all(),
            "active_category": active_category,
            "authorship_choices": authorship_choices,
            "active_authorship": active_authorship,
        },
    )


def article_detail(request, section_slug, article_slug):
    preview = is_preview_user(request.user)
    blocks = ArticleBlock.objects.all() if preview else ArticleBlock.objects.filter(is_visible=True)
    article = (
        Article.objects.visible_for(request.user)
        .select_related("section", "category")
        .prefetch_related(Prefetch("blocks", queryset=blocks), "gallery", "tags")
        .filter(section__slug=section_slug, slug=article_slug)
        .first()
    )
    if article is None:
        raise Http404("Yazı tapılmadı")

    related = (
        Article.objects.visible_for(request.user)
        .filter(section=article.section)
        .exclude(pk=article.pk)
        .select_related("section", "category")
        .listing_order()[:3]
    )
    return render(
        request,
        "site/article_detail.html",
        {"article": article, "section": article.section, "related": related},
    )


class ArticleSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return Article.objects.public().filter(link_mode=Article.LinkMode.PAGE).select_related("section")

    def lastmod(self, obj):
        return obj.updated_at


class SectionSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Section.objects.filter(is_visible=True)
