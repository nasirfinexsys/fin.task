import io
import boto3
import pypdf
import pytesseract
from pdf2image import convert_from_bytes
from celery import shared_task
from django.conf import settings
from django.contrib.postgres.search import SearchVector
from .models import Document, DocumentChunk
from .services import chunk_text, generate_embedding
import os
import tempfile
import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Configure Gemini
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)

@shared_task
def process_document(doc_id):
    try:
        doc = Document.objects.get(id=doc_id)
        doc.status = Document.Status.PROCESSING
        doc.save(update_fields=['status'])

        # Download file from S3 (or local storage if dev)
        file_content = None
        
        # Check if using S3 or FileSystem
        if hasattr(settings, 'AWS_ACCESS_KEY_ID') and settings.AWS_ACCESS_KEY_ID:
            try:
                s3 = boto3.client('s3', 
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_S3_REGION_NAME
                )
                # We need to get the bucket key. 
                # If doc.file.name is the full path/key? Yes usually.
                obj = s3.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=doc.file.name)
                file_content = obj['Body'].read()
            except Exception as e:
                error_msg = f"Failed to download file from S3: {str(e)}"
                logger.error(error_msg)
                doc.status = Document.Status.FAILED
                doc.error_message = error_msg
                doc.save()
                return
        else:
            # Local Dev
            try:
                with doc.file.open('rb') as f:
                    file_content = f.read()
            except Exception as e:
                error_msg = f"Failed to read local file: {str(e)}"
                logger.error(error_msg)
                doc.status = Document.Status.FAILED
                doc.error_message = error_msg
                doc.save()
                return

        text = ""
        page_count = 0
        extraction_method = "unknown"
        
        # METHOD 1: Try Gemini API for PDF extraction (Best quality, handles scanned PDFs)
        try:
            if settings.GEMINI_API_KEY:
                logger.info(f"Attempting Gemini API extraction for document {doc_id}")
                
                # Save file temporarily for Gemini API
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                    tmp_file.write(file_content)
                    tmp_file_path = tmp_file.name
                
                try:
                    # Upload file to Gemini
                    uploaded_file = genai.upload_file(tmp_file_path)
                    
                    # Use Gemini 2.0 Flash for PDF processing
                    model = genai.GenerativeModel('gemini-2.0-flash-exp')
                    
                    # Extract text with prompt
                    prompt = """Extract all text from this PDF document. 
                    Include all text content, maintaining the original structure and formatting as much as possible.
                    If this is a scanned document, use OCR to extract the text.
                    Return only the extracted text without any additional commentary."""
                    
                    response = model.generate_content([uploaded_file, prompt])
                    text = response.text
                    
                    # Try to get page count from pypdf (faster than Gemini)
                    try:
                        pdf_file = io.BytesIO(file_content)
                        reader = pypdf.PdfReader(pdf_file)
                        page_count = len(reader.pages)
                        
                        # Extract metadata while we have pypdf open
                        if reader.metadata:
                            doc.meta_data = {k: str(v) for k, v in reader.metadata.items()}
                    except:
                        page_count = 0  # Will estimate from text
                    
                    extraction_method = "gemini"
                    logger.info(f"Gemini extraction successful for document {doc_id}")
                    
                finally:
                    # Cleanup temp file
                    if os.path.exists(tmp_file_path):
                        os.unlink(tmp_file_path)
                    
                    # Delete uploaded file from Gemini
                    try:
                        genai.delete_file(uploaded_file.name)
                    except:
                        pass
                        
        except Exception as e:
            logger.warning(f"Gemini extraction failed: {e}. Falling back to pypdf/OCR")
        
        # METHOD 2: Fallback to pypdf (if Gemini failed or no API key)
        if not text.strip() or len(text.strip()) < 50:
            try:
                logger.info("Attempting pypdf extraction")
                pdf_file = io.BytesIO(file_content)
                reader = pypdf.PdfReader(pdf_file)
                page_count = len(reader.pages)
                
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                
                # Extract Metadata
                if reader.metadata:
                    doc.meta_data = {k: str(v) for k, v in reader.metadata.items()}
                
                extraction_method = "pypdf"
                logger.info(f"pypdf extraction successful for document {doc_id}")
            except Exception as e:
                logger.warning(f"pypdf failed: {e}")
            
        # METHOD 3: Final fallback to OCR (if both Gemini and pypdf failed)
        if not text.strip() or len(text.strip()) < 50:
            logger.info("Text sparse. Attempting OCR with Tesseract.")
            try:
                images = convert_from_bytes(file_content)
                text = ""
                page_count = len(images)
                for image in images:
                    text += pytesseract.image_to_string(image) + "\n"
                
                extraction_method = "ocr"
                logger.info(f"OCR extraction successful for document {doc_id}")
            except Exception as e:
                logger.error(f"All extraction methods failed: {e}")
                doc.status = Document.Status.FAILED
                doc.error_message = f"Text extraction failed: {str(e)}"
                doc.save()
                return
        
        # Add extraction method to metadata
        if not doc.meta_data:
            doc.meta_data = {}
        doc.meta_data['extraction_method'] = extraction_method

        doc.text_content = text
        doc.page_count = page_count
        doc.status = Document.Status.COMPLETED
        # Save all fields (meta_data may have been set during pypdf extraction)
        doc.save(update_fields=['text_content', 'page_count', 'status', 'meta_data'])
        
        # Update search vector for full-text search using database query
        # Include both title and text_content with higher weight on title
        # This is non-critical - if it fails, document still works, just not searchable
        try:
            Document.objects.filter(id=doc.id).update(
                search_vector=SearchVector('title', weight='A', config='english') + SearchVector('text_content', weight='B', config='english')
            )
        except Exception as e:
            # Log warning but don't fail document processing
            logger.warning(f"Failed to update search vector for document {doc_id}: {str(e)}")
            # Document is still marked as COMPLETED and will work, just won't be searchable
        
        # Generate embeddings for semantic search
        try:
            generate_document_embeddings.delay(doc_id)
        except Exception as e:
            logger.warning(f"Failed to trigger embedding generation for document {doc_id}: {str(e)}")
            # Don't fail document processing if embedding generation fails

    except Document.DoesNotExist:
        logger.error(f"Document {doc_id} not found.")
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        if 'doc' in locals():
            doc.status = Document.Status.FAILED
            doc.error_message = str(e)
            doc.save()


@shared_task
def generate_document_embeddings(doc_id):
    """
    Generate embeddings for a document's text chunks.
    This is called after text extraction is complete.
    """
    try:
        doc = Document.objects.get(id=doc_id)
        
        # Check if document has text content
        if not doc.text_content or not doc.text_content.strip():
            logger.warning(f"Document {doc_id} has no text content, skipping embedding generation")
            doc.embedding_status = Document.EmbeddingStatus.FAILED
            doc.save(update_fields=['embedding_status'])
            return
        
        # Update status
        doc.embedding_status = Document.EmbeddingStatus.PROCESSING
        doc.save(update_fields=['embedding_status'])
        
        # Delete existing chunks if any
        DocumentChunk.objects.filter(document=doc).delete()
        
        # Chunk the text
        chunks = chunk_text(doc.text_content)
        
        if not chunks:
            logger.warning(f"No chunks generated for document {doc_id}")
            doc.embedding_status = Document.EmbeddingStatus.FAILED
            doc.save(update_fields=['embedding_status'])
            return
        
        # Generate embeddings for each chunk
        chunk_objects = []
        for idx, chunk_text_content in enumerate(chunks):
            try:
                # Generate embedding
                embedding = generate_embedding(chunk_text_content)
                
                # Create chunk object
                chunk = DocumentChunk(
                    document=doc,
                    chunk_text=chunk_text_content,
                    chunk_index=idx,
                    embedding=embedding
                )
                chunk_objects.append(chunk)
                
            except Exception as e:
                logger.error(f"Error generating embedding for chunk {idx} of document {doc_id}: {str(e)}")
                # Continue with other chunks even if one fails
                continue
        
        # Bulk create chunks
        if chunk_objects:
            DocumentChunk.objects.bulk_create(chunk_objects)
            doc.embedding_status = Document.EmbeddingStatus.COMPLETED
            logger.info(f"Successfully generated {len(chunk_objects)} embeddings for document {doc_id}")
        else:
            doc.embedding_status = Document.EmbeddingStatus.FAILED
            logger.error(f"Failed to generate any embeddings for document {doc_id}")
        
        doc.save(update_fields=['embedding_status'])
    
    except Document.DoesNotExist:
        logger.error(f"Document {doc_id} not found for embedding generation.")
    except Exception as e:
        logger.error(f"Embedding generation failed for document {doc_id}: {e}")
        if 'doc' in locals():
            doc.embedding_status = Document.EmbeddingStatus.FAILED
            doc.save(update_fields=['embedding_status'])
