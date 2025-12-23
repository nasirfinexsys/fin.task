from django.contrib import admin
from .models import Document

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'status', 'page_count', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'text_content']
    readonly_fields = ['created_at', 'updated_at', 'text_content', 'search_vector', 'meta_data', 'page_count']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user')
