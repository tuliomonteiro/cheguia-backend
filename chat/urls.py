from django.urls import path
from . import views

urlpatterns = [
    path('sessions/', views.session_list_create, name='session-list-create'),
    path('sessions/<uuid:session_id>/', views.session_detail, name='session-detail'),
    path('sessions/<uuid:session_id>/messages/', views.message_list_create, name='message-list-create'),
]
