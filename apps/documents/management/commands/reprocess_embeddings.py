"""
Management command to reprocess embeddings for documents that failed or are pending.
"""
from django.core.management.base import BaseCommand
from apps.documents.models import Document
from apps.documents.tasks import generate_document_embeddings


class Command(BaseCommand):
    help = 'Reprocess embeddings for documents with PENDING or FAILED embedding status'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Reprocess all documents regardless of status',
        )
        parser.add_argument(
            '--doc-id',
            type=int,
            help='Reprocess a specific document by ID',
        )

    def handle(self, *args, **options):
        if options['doc_id']:
            try:
                doc = Document.objects.get(id=options['doc_id'])
                self.stdout.write(f'Reprocessing document {doc.id}: {doc.title}')
                generate_document_embeddings.delay(doc.id)
                self.stdout.write(self.style.SUCCESS(f'Queued document {doc.id} for embedding generation'))
            except Document.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Document {options["doc_id"]} not found'))
        elif options['all']:
            docs = Document.objects.filter(status=Document.Status.COMPLETED)
            count = docs.count()
            self.stdout.write(f'Reprocessing {count} documents...')
            for doc in docs:
                generate_document_embeddings.delay(doc.id)
            self.stdout.write(self.style.SUCCESS(f'Queued {count} documents for embedding generation'))
        else:
            # Default: reprocess PENDING and FAILED
            docs = Document.objects.filter(
                status=Document.Status.COMPLETED,
                embedding_status__in=[Document.EmbeddingStatus.PENDING, Document.EmbeddingStatus.FAILED]
            )
            count = docs.count()
            self.stdout.write(f'Found {count} documents with PENDING or FAILED embedding status')
            
            if count == 0:
                self.stdout.write(self.style.WARNING('No documents to reprocess'))
                return
            
            for doc in docs:
                self.stdout.write(f'  - Document {doc.id}: {doc.title[:50]}')
                generate_document_embeddings.delay(doc.id)
            
            self.stdout.write(self.style.SUCCESS(f'Queued {count} documents for embedding generation'))

