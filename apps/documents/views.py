from rest_framework import generics, permissions, filters, status
from rest_framework.response import Response
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.views.generic import TemplateView, CreateView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import F
from django.core.exceptions import ValidationError
from django.views import View
from django.http import JsonResponse
import google.generativeai as genai
from django.conf import settings
from .models import Document
from .serializers import DocumentSerializer
from .tasks import process_document
from .services import generate_query_embedding, find_similar_chunks

# Maximum file size: 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024  # 52,428,800 bytes

# --- API Views ---
class DocumentListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'text_content']

    def get_queryset(self):
        queryset = Document.objects.filter(user=self.request.user)
        search_query = self.request.query_params.get('search', None)
        
        if search_query:
            # Use Full Text Search - case-insensitive
            # Use stored search_vector field (uses GIN index for performance)
            query = SearchQuery(search_query, config='english')
            queryset = queryset.annotate(
                rank=SearchRank(F('search_vector'), query)
            ).filter(rank__gt=0).order_by('-rank')
            
        return queryset

    def perform_create(self, serializer):
        doc = serializer.save()
        # Trigger Celery Task
        process_document.delay(doc.id)

class DocumentDetailAPIView(generics.RetrieveDestroyAPIView):
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Document.objects.filter(user=self.request.user)

# --- UI Views ---

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'

class DocumentUploadView(LoginRequiredMixin, CreateView):
    model = Document
    fields = ['title', 'file']
    template_name = 'upload.html'
    success_url = reverse_lazy('dashboard')

    def validate_file(self, file):
        """
        Validate uploaded file before saving:
        1. Check file size (max 50MB)
        2. Check file is not empty
        3. Check MIME type is PDF
        4. Check PDF magic bytes
        """
        errors = []
        
        # 1. Check file size
        if file.size > MAX_FILE_SIZE:
            errors.append(f"File size exceeds 50MB limit. Your file is {file.size / (1024*1024):.2f}MB.")
        
        # 2. Check empty file
        if file.size == 0:
            errors.append("File is empty. Please upload a valid PDF file.")
        
        # 3. Check MIME type
        if hasattr(file, 'content_type') and file.content_type:
            if file.content_type != 'application/pdf':
                errors.append(f"Only PDF files are allowed. Received: {file.content_type}")
        
        # 4. Check PDF magic bytes (most reliable check)
        if file.size > 0:
            current_position = file.tell()
            file.seek(0)
            header = file.read(4)
            file.seek(current_position)  # Restore position
            
            if header != b'%PDF':
                errors.append("Invalid PDF file. The file does not appear to be a valid PDF.")
        
        if errors:
            raise ValidationError(errors)
        
        return True

    def form_valid(self, form):
        # Validate file before saving
        uploaded_file = form.cleaned_data.get('file')
        if uploaded_file:
            try:
                self.validate_file(uploaded_file)
            except ValidationError as e:
                # Add error messages to form
                for error in e.messages if hasattr(e, 'messages') else [str(e)]:
                    messages.error(self.request, error)
                return self.form_invalid(form)
        
        form.instance.user = self.request.user
        response = super().form_valid(form)
        # Trigger Celery Task
        process_document.delay(self.object.id)
        return response

class DocumentListView(LoginRequiredMixin, ListView):
    model = Document
    template_name = 'list.html'
    context_object_name = 'documents'
    paginate_by = 10

    def get_queryset(self):
        queryset = Document.objects.filter(user=self.request.user)
        search_query = self.request.GET.get('q')
        
        if search_query:
            # Use Full Text Search - case-insensitive
            # Use stored search_vector field (uses GIN index for performance)
            query = SearchQuery(search_query, config='english')
            queryset = queryset.annotate(
                rank=SearchRank(F('search_vector'), query)
            ).filter(rank__gt=0).order_by('-rank')
            
        return queryset

class DocumentDetailView(LoginRequiredMixin, DetailView):
    model = Document
    template_name = 'detail.html'
    context_object_name = 'document'

    def get_queryset(self):
        return Document.objects.filter(user=self.request.user)


class SemanticSearchView(LoginRequiredMixin, TemplateView):
    template_name = 'semantic_search.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '')
        results = []
        
        if query:
            try:
                # Generate query embedding
                query_embedding = generate_query_embedding(query)
                
                # Find similar chunks
                similar_chunks = find_similar_chunks(query_embedding, self.request.user, limit=20)
                
                # Group by document and get unique documents
                documents_dict = {}
                for chunk in similar_chunks:
                    doc = chunk.document
                    if doc.id not in documents_dict:
                        documents_dict[doc.id] = {
                            'document': doc,
                            'chunks': [],
                            'max_similarity': 0
                        }
                    documents_dict[doc.id]['chunks'].append(chunk)
                    # Update max similarity
                    similarity = getattr(chunk, 'similarity_score', 0)
                    if similarity > documents_dict[doc.id]['max_similarity']:
                        documents_dict[doc.id]['max_similarity'] = similarity
                
                # Convert to list and sort by similarity
                results = list(documents_dict.values())
                results.sort(key=lambda x: x['max_similarity'], reverse=True)
                
            except Exception as e:
                messages.error(self.request, f"Search error: {str(e)}")
        
        context['query'] = query
        context['results'] = results
        return context


class QnAView(LoginRequiredMixin, TemplateView):
    template_name = 'qna.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        question = self.request.GET.get('q', '')
        answer = None
        source_documents = []
        source_texts = []
        
        if question:
            try:
                # Generate query embedding
                query_embedding = generate_query_embedding(question)
                
                # Find top-k similar chunks
                similar_chunks = find_similar_chunks(query_embedding, self.request.user, limit=5)
                
                if not similar_chunks:
                    context['error'] = "No relevant information found in your documents."
                    return context
                
                # Prepare context for Gemini
                context_texts = []
                source_docs_set = set()
                
                for chunk in similar_chunks:
                    context_texts.append(chunk.chunk_text)
                    source_docs_set.add(chunk.document)
                    source_texts.append({
                        'document': chunk.document,
                        'text': chunk.chunk_text[:500] + '...' if len(chunk.chunk_text) > 500 else chunk.chunk_text,
                        'similarity': getattr(chunk, 'similarity_score', 0)
                    })
                
                # Combine context
                combined_context = "\n\n".join([f"Document excerpt {i+1}:\n{text}" for i, text in enumerate(context_texts)])
                
                # Generate answer using Gemini
                if settings.GEMINI_API_KEY:
                    genai.configure(api_key=settings.GEMINI_API_KEY)
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    prompt = f"""Based on the following document excerpts, please answer the question. 
If the answer cannot be found in the excerpts, say so.

Question: {question}

Document excerpts:
{combined_context}

Answer:"""
                    
                    response = model.generate_content(prompt)
                    answer = response.text
                    
                    # Get source documents
                    source_documents = list(source_docs_set)
                else:
                    context['error'] = "Gemini API key not configured."
                    return context
                
            except Exception as e:
                context['error'] = f"Error generating answer: {str(e)}"
                return context
        
        context['question'] = question
        context['answer'] = answer
        context['source_documents'] = source_documents
        context['source_texts'] = source_texts
        return context


class QnAAPIView(LoginRequiredMixin, View):
    """API endpoint for QnA (for AJAX requests)"""
    
    def post(self, request):
        question = request.POST.get('question', '')
        
        if not question:
            return JsonResponse({'error': 'Question is required'}, status=400)
        
        try:
            # Generate query embedding
            query_embedding = generate_query_embedding(question)
            
            # Find top-k similar chunks
            similar_chunks = find_similar_chunks(query_embedding, request.user, limit=5)
            
            if not similar_chunks:
                return JsonResponse({
                    'answer': 'No relevant information found in your documents.',
                    'sources': []
                })
            
            # Prepare context
            context_texts = []
            source_docs = []
            source_texts = []
            
            for chunk in similar_chunks:
                context_texts.append(chunk.chunk_text)
                if chunk.document not in source_docs:
                    source_docs.append(chunk.document)
                source_texts.append({
                    'document_id': chunk.document.id,
                    'document_title': chunk.document.title,
                    'text': chunk.chunk_text[:500] + '...' if len(chunk.chunk_text) > 500 else chunk.chunk_text,
                    'similarity': getattr(chunk, 'similarity_score', 0)
                })
            
            # Generate answer
            combined_context = "\n\n".join([f"Document excerpt {i+1}:\n{text}" for i, text in enumerate(context_texts)])
            
            if settings.GEMINI_API_KEY:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                prompt = f"""Based on the following document excerpts, please answer the question. 
If the answer cannot be found in the excerpts, say so.

Question: {question}

Document excerpts:
{combined_context}

Answer:"""
                
                response = model.generate_content(prompt)
                answer = response.text
                
                return JsonResponse({
                    'answer': answer,
                    'sources': [
                        {
                            'id': doc.id,
                            'title': doc.title,
                            'url': f'/documents/{doc.id}/'
                        }
                        for doc in source_docs
                    ],
                    'source_texts': source_texts
                })
            else:
                return JsonResponse({'error': 'Gemini API key not configured'}, status=500)
                
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
