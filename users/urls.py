from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    path('register/', views.register, name='auth-register'),
    path('token/', TokenObtainPairView.as_view(), name='auth-token-obtain'),
    path('token/refresh/', TokenRefreshView.as_view(), name='auth-token-refresh'),
    path('me/', views.me, name='auth-me'),
    path('password/change/', views.change_password, name='auth-password-change'),
]
