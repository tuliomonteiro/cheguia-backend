from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """
    Knowledge-base browser. Title and content are read-only here on purpose:
    embeddings are computed from "title + content" at ingest time, so hand
    edits would silently desync the stored vector from the text — updating
    content goes through `manage.py ingest_documents --update` (the only
    sanctioned write path). Metadata that does not participate in the
    embedding (type, language, source URL) stays editable, and deleting
    orphaned documents is allowed.
    """

    list_display = ['title', 'document_type', 'language', 'has_embedding',
                    'source_url', 'updated_at']
    list_filter = ['document_type', 'language']
    search_fields = ['title', 'content']
    readonly_fields = ['id', 'title', 'content', 'has_embedding',
                       'created_at', 'updated_at']
    exclude = ['embedding_vector']

    @admin.display(boolean=True, description='embedded')
    def has_embedding(self, obj):
        return obj.embedding_vector is not None

    def has_add_permission(self, request):
        return False
