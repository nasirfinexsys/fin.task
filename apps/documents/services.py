"""
Service functions for Gemini API interactions, text chunking, and embedding operations.
"""
import logging
import google.generativeai as genai
import numpy as np
from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)

# Initialize Gemini client
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)

# Embedding model configuration
EMBEDDING_MODEL = 'models/embedding-001'
# Note: embedding-001 returns 768 dimensions by default
# output_dimensionality parameter only REDUCES dimensions, not increases
EMBEDDING_DIMENSIONS = 768
CHUNK_SIZE = 1000  # Approximate tokens per chunk
CHUNK_OVERLAP = 200  # Overlap tokens between chunks


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """
    Split text into chunks with overlap.
    
    Args:
        text: The text to chunk
        chunk_size: Approximate number of tokens per chunk (using word count as proxy)
        overlap: Number of tokens to overlap between chunks
    
    Returns:
        List of text chunks
    """
    if not text or not text.strip():
        return []
    
    # Simple word-based chunking (can be improved with tokenizer)
    words = text.split()
    chunks = []
    
    if len(words) <= chunk_size:
        return [text]
    
    i = 0
    while i < len(words):
        chunk_words = words[i:i + chunk_size]
        chunk_text = ' '.join(chunk_words)
        chunks.append(chunk_text)
        
        # Move forward by chunk_size - overlap to create overlap
        i += chunk_size - overlap
        
        # Prevent infinite loop
        if i >= len(words):
            break
    
    return chunks


def generate_embedding(text):
    """
    Generate embedding for text using Gemini Embedding API.
    
    Args:
        text: Text to generate embedding for
    
    Returns:
        List of 768 float values (embedding vector)
    """
    try:
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not configured")
        
        # Generate embedding
        # Note: embedding-001 returns 768 dimensions by default
        # output_dimensionality parameter only reduces dimensions, not increases
        result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=text,
            task_type="retrieval_document"
        )
        
        embedding = result['embedding']
        
        # Ensure it's the right dimensions
        if len(embedding) != EMBEDDING_DIMENSIONS:
            logger.warning(f"Expected {EMBEDDING_DIMENSIONS} dimensions, got {len(embedding)}")
            # If wrong dimensions, raise error to prevent issues
            raise ValueError(f"Embedding has {len(embedding)} dimensions, expected {EMBEDDING_DIMENSIONS}")
        
        # Convert to half precision (float16) for storage
        embedding_array = np.array(embedding, dtype=np.float16)
        return embedding_array.tolist()
    
    except Exception as e:
        logger.error(f"Error generating embedding: {str(e)}")
        raise


def generate_query_embedding(query_text):
    """
    Generate embedding for a search query using Gemini Embedding API.
    
    Args:
        query_text: Query text to generate embedding for
    
    Returns:
        List of 768 float values (embedding vector)
    """
    try:
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not configured")
        
        # Generate embedding for query (use retrieval_query task type)
        # Note: embedding-001 returns 768 dimensions by default
        result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=query_text,
            task_type="retrieval_query"
        )
        
        embedding = result['embedding']
        
        # Ensure it's the right dimensions
        if len(embedding) != EMBEDDING_DIMENSIONS:
            logger.warning(f"Expected {EMBEDDING_DIMENSIONS} dimensions, got {len(embedding)}")
            raise ValueError(f"Query embedding has {len(embedding)} dimensions, expected {EMBEDDING_DIMENSIONS}")
        
        # Convert to half precision
        embedding_array = np.array(embedding, dtype=np.float16)
        return embedding_array.tolist()
    
    except Exception as e:
        logger.error(f"Error generating query embedding: {str(e)}")
        raise


def find_similar_chunks(query_embedding, user, limit=10):
    """
    Find similar chunks using pgvector similarity search on halfvec.
    
    Args:
        query_embedding: List of 768 float values (query embedding)
        user: User object to filter by user's documents
        limit: Maximum number of results to return
    
    Returns:
        List of DocumentChunk objects with similarity scores
    """
    from .models import DocumentChunk
    
    try:
        with connection.cursor() as cursor:
            # Convert embedding list to string format for PostgreSQL
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
            
            # SQL query using pgvector's <-> operator for cosine distance on halfvec(768)
            # Use the jsonb_to_halfvec function to convert JSON to halfvec(768)
            query = """
                SELECT 
                    dc.id,
                    dc.document_id,
                    dc.chunk_text,
                    dc.chunk_index,
                    jsonb_to_halfvec(dc.embedding) <-> %s::halfvec(768) AS distance
                FROM documents_documentchunk dc
                INNER JOIN documents_document d ON dc.document_id = d.id
                WHERE d.user_id = %s
                  AND dc.embedding IS NOT NULL
                ORDER BY jsonb_to_halfvec(dc.embedding) <-> %s::halfvec(768)
                LIMIT %s
            """
            
            cursor.execute(query, [embedding_str, user.id, embedding_str, limit])
            results = cursor.fetchall()
            
            # Get chunk objects
            chunk_ids = [row[0] for row in results]
            chunks = DocumentChunk.objects.filter(id__in=chunk_ids).select_related('document')
            
            # Create a dict for quick lookup
            chunk_dict = {chunk.id: chunk for chunk in chunks}
            
            # Return chunks with distance scores
            similar_chunks = []
            for row in results:
                chunk_id, doc_id, chunk_text, chunk_index, distance = row
                chunk = chunk_dict.get(chunk_id)
                if chunk:
                    chunk.similarity_score = 1.0 - distance  # Convert distance to similarity
                    similar_chunks.append(chunk)
            
            return similar_chunks
    
    except Exception as e:
        logger.error(f"Error finding similar chunks: {str(e)}")
        # Fallback: return empty list
        return []

