from django.urls import path

from . import views

app_name = "content"

urlpatterns = [
    path("<slug:section_slug>/", views.section_detail, name="section"),
    path("<slug:section_slug>/<slug:article_slug>/", views.article_detail, name="article"),
]
