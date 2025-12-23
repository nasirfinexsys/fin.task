from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files.storage import default_storage
from apps.documents.models import Document
import os
import boto3


class Command(BaseCommand):
    help = 'Delete all documents and their PDF files (use with caution!)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion of all documents',
        )

    def handle(self, *args, **options):
        total = Document.objects.count()
        
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    f'This will delete ALL {total} documents AND their PDF files!\n'
                    'Run with --confirm to proceed.'
                )
            )
            return
        
        # Get all documents before deletion
        documents = Document.objects.all()
        files_deleted = 0
        files_failed = 0
        
        # Check if using S3 or local storage
        using_s3 = hasattr(settings, 'AWS_ACCESS_KEY_ID') and settings.AWS_ACCESS_KEY_ID
        
        if using_s3:
            # Delete from S3
            self.stdout.write('Deleting files from S3...')
            s3 = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            
            for doc in documents:
                if doc.file.name:
                    try:
                        s3.delete_object(
                            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                            Key=doc.file.name
                        )
                        files_deleted += 1
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'Failed to delete S3 file {doc.file.name}: {e}')
                        )
                        files_failed += 1
        else:
            # Delete from local filesystem using Django's storage API
            self.stdout.write('Deleting files from local storage...')
            for doc in documents:
                if doc.file and doc.file.name:
                    try:
                        # Use Django's storage API for consistency
                        if default_storage.exists(doc.file.name):
                            default_storage.delete(doc.file.name)
                            files_deleted += 1
                        else:
                            self.stdout.write(
                                self.style.WARNING(f'File not found: {doc.file.name}')
                            )
                            files_failed += 1
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'Failed to delete file {doc.file.name}: {e}')
                        )
                        files_failed += 1
        
        # Now delete the database records
        self.stdout.write('Deleting database records...')
        deleted_count = Document.objects.all().delete()[0]
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully deleted:\n'
                f'  - {deleted_count} database records\n'
                f'  - {files_deleted} PDF files\n'
                f'  - {files_failed} files failed to delete'
            )
        )

