from django.db import models
from pgvector.django import VectorField
import uuid


class AIInteraction(models.Model):
    """Track AI interactions for analytics and improvement"""
    
    INTERACTION_TYPES = [
        ('chat', 'Chat'),
        ('document_generation', 'Document Generation'),
        ('translation', 'Translation'),
        ('question_answering', 'Question Answering'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interaction_type = models.CharField(max_length=50, choices=INTERACTION_TYPES)
    user_input = models.TextField()
    ai_response = models.TextField()
    tokens_used = models.IntegerField(default=0)
    processing_time = models.FloatField(default=0.0)  # in seconds
    sources_used = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ai_interactions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.interaction_type}: {self.user_input[:50]}..."


class EmbeddingCache(models.Model):
    """Cache for document embeddings to avoid recomputation"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    text_hash = models.CharField(max_length=64, unique=True)  # Hash of the text
    embedding_vector = VectorField(dimensions=1536)
    model_used = models.CharField(max_length=100, default='text-embedding-3-small')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'embedding_cache'
    
    def __str__(self):
        return f"Embedding for hash: {self.text_hash[:16]}..."