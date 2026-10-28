from django.urls import path

from . import views

app_name = "newsletter"

urlpatterns = [
    path("", views.subscribe, name="subscribe"),
    path("tesdiq/<uuid:token>/", views.confirm, name="confirm"),
    path("<uuid:token>/", views.manage, name="manage"),
    path("<uuid:token>/imtina/", views.one_click_unsubscribe, name="one_click_unsubscribe"),
]
