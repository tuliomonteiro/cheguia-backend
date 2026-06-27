from django.db import migrations
from pgvector.django import VectorField


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0001_initial'),
    ]

    operations = [
        # Enable pgvector extension (idempotent)
        migrations.RunSQL(
            sql='CREATE EXTENSION IF NOT EXISTS vector',
            reverse_sql='DROP EXTENSION IF EXISTS vector',
        ),
        # Create a HNSW index for fast approximate cosine similarity search
        migrations.RunSQL(
            sql=(
                'ALTER TABLE documents DROP COLUMN IF EXISTS embedding_vector; '
                'ALTER TABLE documents ADD COLUMN embedding_vector vector(1536);'
            ),
            reverse_sql=(
                'ALTER TABLE documents DROP COLUMN IF EXISTS embedding_vector; '
                'ALTER TABLE documents ADD COLUMN embedding_vector jsonb;'
            ),
        ),
        migrations.RunSQL(
            sql=(
                'CREATE INDEX IF NOT EXISTS documents_embedding_hnsw '
                'ON documents USING hnsw (embedding_vector vector_cosine_ops)'
            ),
            reverse_sql='DROP INDEX IF EXISTS documents_embedding_hnsw',
        ),
        migrations.AlterField(
            model_name='document',
            name='embedding_vector',
            field=VectorField(dimensions=1536, null=True, blank=True),
        ),
    ]
