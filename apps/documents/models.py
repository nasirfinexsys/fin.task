from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex

User = get_user_model()

class Document(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED_DIGITAL = 'FAILED_DIGITAL', 'Failed Digital Extraction'
        FAILED_OCR = 'FAILED_OCR', 'Failed OCR'
        FAILED = 'FAILED', 'Failed'
    
    class EmbeddingStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='pdfs/') # S3 storage handles the backend
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    
    # Extraction results
    text_content = models.TextField(blank=True, default='')
    search_vector = SearchVectorField(null=True, blank=True) # For full text search
    
    # Metadata
    meta_data = models.JSONField(default=dict, blank=True)
    page_count = models.IntegerField(null=True, blank=True)
    
    # Processing state
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    embedding_status = models.CharField(
        max_length=20,
        choices=EmbeddingStatus.choices,
        default=EmbeddingStatus.PENDING
    )
    error_message = models.TextField(blank=True, default='')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            GinIndex(fields=['search_vector']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class DocumentChunk(models.Model):
    """
    Stores text chunks from PDFs with their embeddings.
    Embeddings are stored as JSONField and will be cast to halfvec(3072) in SQL queries.
    """
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    chunk_text = models.TextField()
    chunk_index = models.IntegerField()  # Order of chunk in document
    # Embedding stored as JSON array (list of 3072 float values)
    # Will be cast to halfvec(3072) in SQL queries for similarity search
    embedding = models.JSONField(null=True, blank=True)  # List of 3072 floats
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['document', 'chunk_index']),
        ]
        ordering = ['document', 'chunk_index']
        unique_together = [['document', 'chunk_index']]
    
    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.document.title}"
