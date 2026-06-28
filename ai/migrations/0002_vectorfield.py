from django.db import migrations
from pgvector.django import VectorField


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0001_initial'),
        # Extension must exist before we use vector type
        ('documents', '0002_vectorfield'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                'ALTER TABLE embedding_cache DROP COLUMN IF EXISTS embedding_vector; '
                'ALTER TABLE embedding_cache ADD COLUMN embedding_vector vector(1536) NOT NULL DEFAULT array_fill(0, ARRAY[1536])::vector;'
            ),
            reverse_sql=(
                'ALTER TABLE embedding_cache DROP COLUMN IF EXISTS embedding_vector; '
                'ALTER TABLE embedding_cache ADD COLUMN embedding_vector jsonb NOT NULL DEFAULT \'[]\'::jsonb;'
            ),
        ),
        migrations.AlterField(
            model_name='embeddingcache',
            name='embedding_vector',
            field=VectorField(dimensions=1536),
        ),
    ]
