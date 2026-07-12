from django.contrib import admin

from .models import ChatSession, Message


class MessageInline(admin.TabularInline):
    """Conversation transcript inside the session page — view-only."""

    model = Message
    extra = 0
    can_delete = False
    readonly_fields = ['role', 'content', 'sources', 'created_at']

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'platform', 'created_at', 'updated_at']
    list_filter = ['platform']
    search_fields = ['title', 'user__email']
    list_select_related = ['user']
    date_hierarchy = 'created_at'
    readonly_fields = ['id', 'user', 'created_at', 'updated_at']
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """View-only: messages are conversation history, never edited by hand."""

    list_display = ['session', 'role', 'short_content', 'created_at']
    list_filter = ['role']
    search_fields = ['content', 'session__user__email']
    list_select_related = ['session', 'session__user']
    date_hierarchy = 'created_at'

    @admin.display(description='content')
    def short_content(self, obj):
        return obj.content[:80]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
