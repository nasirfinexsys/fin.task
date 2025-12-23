# Generated migration for embeddings support

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('documents', '0001_initial'),
    ]

    operations = [
        # Install pgvector extension
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS vector;",
            reverse_sql="DROP EXTENSION IF EXISTS vector;",
        ),
        
        # Add embedding_status to Document
        migrations.AddField(
            model_name='document',
            name='embedding_status',
            field=models.CharField(
                choices=[('PENDING', 'Pending'), ('PROCESSING', 'Processing'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed')],
                default='PENDING',
                max_length=20
            ),
        ),
        
        # Create DocumentChunk model
        migrations.CreateModel(
            name='DocumentChunk',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chunk_text', models.TextField()),
                ('chunk_index', models.IntegerField()),
                ('embedding', models.JSONField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chunks', to='documents.document')),
            ],
            options={
                'ordering': ['document', 'chunk_index'],
            },
        ),
        
        # Add unique constraint
        migrations.AddConstraint(
            model_name='documentchunk',
            constraint=models.UniqueConstraint(fields=['document', 'chunk_index'], name='unique_document_chunk'),
        ),
        
        # Add index on document and chunk_index
        migrations.AddIndex(
            model_name='documentchunk',
            index=models.Index(fields=['document', 'chunk_index'], name='documents_d_documen_idx'),
        ),
        
        # Create a function to convert JSONB array to halfvec(768)
        # Note: Gemini embedding-001 returns 768 dimensions by default
        # This function converts the JSON array to PostgreSQL array, then to halfvec with dimensions
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE FUNCTION jsonb_to_halfvec(jsonb_data jsonb)
                RETURNS halfvec(768) AS $$
                DECLARE
                    result_array float4[];
                BEGIN
                    SELECT array_agg(value::float4 ORDER BY ordinality)
                    INTO result_array
                    FROM jsonb_array_elements_text(jsonb_data) WITH ORDINALITY AS t(value, ordinality);
                    
                    -- Ensure the array has exactly 768 elements
                    IF array_length(result_array, 1) != 768 THEN
                        RAISE EXCEPTION 'Array must have exactly 768 elements, got %', array_length(result_array, 1);
                    END IF;
                    
                    RETURN result_array::halfvec(768);
                END;
                $$ LANGUAGE plpgsql IMMUTABLE;
            """,
            reverse_sql="DROP FUNCTION IF EXISTS jsonb_to_halfvec(jsonb);",
        ),
        
    ]

