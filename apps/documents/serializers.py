from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from .models import Document

# Maximum file size: 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024  # 52,428,800 bytes

class DocumentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Document
        fields = ['id', 'title', 'file', 'text_content', 'status', 'status_display', 'page_count', 'created_at']
        read_only_fields = ['text_content', 'status', 'page_count', 'created_at']

    def validate_file(self, value):
        """
        Validate uploaded file:
        1. Check file size (max 50MB)
        2. Check file is not empty
        3. Check MIME type is PDF
        4. Check PDF magic bytes
        """
        # 1. Check file size
        if value.size > MAX_FILE_SIZE:
            raise ValidationError(f"File size exceeds 50MB limit. Your file is {value.size / (1024*1024):.2f}MB.")
        
        # 2. Check empty file
        if value.size == 0:
            raise ValidationError("File is empty. Please upload a valid PDF file.")
        
        # 3. Check MIME type
        if hasattr(value, 'content_type') and value.content_type:
            if value.content_type != 'application/pdf':
                raise ValidationError(f"Only PDF files are allowed. Received: {value.content_type}")
        
        # 4. Check PDF magic bytes (most reliable check)
        # Save current position
        current_position = value.tell()
        value.seek(0)
        header = value.read(4)
        value.seek(current_position)  # Restore position
        
        if header != b'%PDF':
            raise ValidationError("Invalid PDF file. The file does not appear to be a valid PDF.")
        
        return value

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
