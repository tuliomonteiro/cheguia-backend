from django.db import models
import uuid


class Document(models.Model):
    """Document model for storing Paraguay-specific knowledge base"""
    
    DOCUMENT_TYPES = [
        ('immigration', 'Immigration'),
        ('tax', 'Tax'),
        ('utilities', 'Utilities'),
        ('banking', 'Banking'),
        ('general', 'General'),
    ]
    
    LANGUAGE_CHOICES = [
        ('es', 'Spanish'),
        ('pt', 'Portuguese'),
        ('gu', 'Guarani'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=500)
    content = models.TextField()
    source_url = models.URLField(max_length=1000, blank=True, null=True)
    document_type = models.CharField(max_length=100, choices=DOCUMENT_TYPES)
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='es')
    embedding_vector = models.JSONField(null=True, blank=True)  # Store OpenAI embeddings
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'documents'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title


class DocumentTemplate(models.Model):
    """Template for generating official documents"""
    
    TEMPLATE_TYPES = [
        ('residency_application', 'Residency Application'),
        ('power_of_attorney', 'Power of Attorney'),
        ('rental_contract', 'Rental Contract'),
        ('bank_application', 'Bank Application'),
        ('ande_application', 'ANDE Application'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    template_type = models.CharField(max_length=100, choices=TEMPLATE_TYPES)
    template_content = models.TextField()  # HTML or markdown template
    fields = models.JSONField(default=list)  # List of required fields
    is_premium = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'document_templates'
        ordering = ['name']
    
    def __str__(self):
        return self.name