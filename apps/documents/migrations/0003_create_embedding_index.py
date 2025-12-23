# Migration to create HNSW index on embeddings
# NOTE: Index creation is skipped due to PostgreSQL limitations with functional indexes on halfvec
# Create the index manually using the SQL command below

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0002_add_embeddings'),
    ]

    operations = [
        # Skip index creation - create manually
        # PostgreSQL has issues creating HNSW indexes on functional expressions with halfvec
        # Run this SQL manually after migration:
        # CREATE INDEX documents_documentchunk_embedding_hnsw_idx 
        # ON documents_documentchunk 
        # USING hnsw (jsonb_to_halfvec(embedding) halfvec_l2_ops)
        # WITH (m = 16, ef_construction = 64)
        # WHERE embedding IS NOT NULL;
        migrations.RunSQL(
            sql="SELECT 1;",  # No-op
            reverse_sql="SELECT 1;",
        ),
    ]

