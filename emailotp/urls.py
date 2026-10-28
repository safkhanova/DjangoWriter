"""
emailotp/urls.py

Include in the project's root urls.py:

    path('', include('emailotp.urls')),

Reverse names are namespaced: emailotp:login, emailotp:register, etc.
"""
from django.urls import path

from . import views

app_name = 'emailotp'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('register/verify/', views.register_verify, name='register_verify'),
    path('register/resend/', views.register_resend, name='register_resend'),
    path('login/', views.login_start, name='login'),
    path('login/password/', views.login_password, name='login_password'),
    path('login/verify/', views.login_verify, name='login_verify'),
    path('login/resend/', views.login_resend, name='login_resend'),
]
