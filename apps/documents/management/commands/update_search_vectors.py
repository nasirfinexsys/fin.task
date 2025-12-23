from django.core.management.base import BaseCommand
from django.contrib.postgres.search import SearchVector
from apps.documents.models import Document


class Command(BaseCommand):
    help = 'Update search_vector field for all documents that have text_content but NULL search_vector'

    def handle(self, *args, **options):
        # Get documents with text_content but NULL or empty search_vector
        documents = Document.objects.filter(
            text_content__isnull=False
        ).exclude(text_content='')
        
        total = documents.count()
        updated = 0
        
        self.stdout.write(f'Found {total} documents to update...')
        
        for doc in documents:
            # Include both title and text_content with higher weight on title
            Document.objects.filter(id=doc.id).update(
                search_vector=SearchVector('title', weight='A', config='english') + SearchVector('text_content', weight='B', config='english')
            )
            updated += 1
            if updated % 10 == 0:
                self.stdout.write(f'Updated {updated}/{total} documents...')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated {updated} documents')
        )

