from django.urls import path
from .views import (
    DocumentListCreateAPIView, DocumentDetailAPIView,
    DashboardView, DocumentUploadView, DocumentListView, DocumentDetailView,
    SemanticSearchView, QnAView, QnAAPIView
)

urlpatterns = [
    # UI URLs
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('upload/', DocumentUploadView.as_view(), name='upload_document'),
    path('documents/', DocumentListView.as_view(), name='document_list'),
    path('documents/<int:pk>/', DocumentDetailView.as_view(), name='document_detail'),
    path('search/', SemanticSearchView.as_view(), name='semantic_search'),
    path('qna/', QnAView.as_view(), name='qna'),

    # API URLs
    path('api/documents/', DocumentListCreateAPIView.as_view(), name='api_document_list'),
    path('api/documents/<int:pk>/', DocumentDetailAPIView.as_view(), name='api_document_detail'),
    path('api/qna/', QnAAPIView.as_view(), name='api_qna'),
]
