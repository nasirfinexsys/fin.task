# Migration to update halfvec function from 3072 to 768 dimensions
# Gemini embedding-001 returns 768 dimensions by default, not 3072

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0003_create_embedding_index'),
    ]

    operations = [
        # Update the function to use 768 dimensions instead of 3072
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
            reverse_sql="""
                -- Revert to 3072 (if needed)
                CREATE OR REPLACE FUNCTION jsonb_to_halfvec(jsonb_data jsonb)
                RETURNS halfvec(3072) AS $$
                DECLARE
                    result_array float4[];
                BEGIN
                    SELECT array_agg(value::float4 ORDER BY ordinality)
                    INTO result_array
                    FROM jsonb_array_elements_text(jsonb_data) WITH ORDINALITY AS t(value, ordinality);
                    RETURN result_array::halfvec(3072);
                END;
                $$ LANGUAGE plpgsql IMMUTABLE;
            """,
        ),
    ]

