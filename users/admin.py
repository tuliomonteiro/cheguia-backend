from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """
    Backoffice for accounts. Email is the login identity (USERNAME_FIELD),
    so ordering, search, and the add form are keyed on it. Inherits the
    stock UserAdmin so password hashing and the change-password form keep
    working with the custom model.
    """

    ordering = ['email']
    list_display = ['email', 'username', 'language_preference', 'is_premium',
                    'is_staff', 'created_at']
    list_filter = ['is_premium', 'is_staff', 'is_superuser', 'is_active',
                   'language_preference']
    search_fields = ['email', 'username']
    readonly_fields = ['id', 'last_login', 'date_joined', 'created_at', 'updated_at']
    fieldsets = (
        (None, {'fields': ('id', 'email', 'username', 'password')}),
        ('Profile', {'fields': ('language_preference', 'is_premium',
                                'first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser',
                                    'groups', 'user_permissions')}),
        ('Dates', {'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2'),
        }),
    )
