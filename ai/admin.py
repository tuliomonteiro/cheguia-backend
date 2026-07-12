from django.contrib import admin

from .models import EmbeddingCache


@admin.register(EmbeddingCache)
class EmbeddingCacheAdmin(admin.ModelAdmin):
    """
    View/delete-only. The cache is keyed by text hash alone (model_used is
    informational), so after an embedding-model change the sanctioned fix is
    deleting entries — never editing them. The vector itself is not shown
    (1536 floats).
    """

    list_display = ['text_hash', 'model_used', 'created_at']
    list_filter = ['model_used']
    search_fields = ['text_hash']
    fields = ['text_hash', 'model_used', 'created_at']
    readonly_fields = ['text_hash', 'model_used', 'created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
