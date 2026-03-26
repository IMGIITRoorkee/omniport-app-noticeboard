from django.core.management.base import BaseCommand, CommandError
from noticeboard.models import Notice
from noticeboard.documents import NoticeDocument


class Command(BaseCommand):
    help = 'Rebuild the Elasticsearch search index for notices'

    def add_arguments(self, parser):
        parser.add_argument(
            '--rebuild',
            action='store_true',
            help='Rebuild the index (delete and recreate)',
        )
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='Skip confirmation prompts',
        )

    def handle(self, *args, **options):
        try:
            if options['rebuild']:
                self.stdout.write(self.style.WARNING('Deleting existing notice index...'))
                try:
                    if not options['no_input']:
                        response = input("Are you sure you want to delete the 'notice' indices? [y/N]: ")
                        if response.lower() != 'y':
                            self.stdout.write(self.style.WARNING('Aborted'))
                            return
                    
                    NoticeDocument._index.delete()
                    self.stdout.write(self.style.SUCCESS('Index deleted successfully'))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'Index did not exist or error: {e}'))

            # Create/initialize the index
            self.stdout.write(self.style.WARNING('Initializing notice index...'))
            NoticeDocument.init()
            self.stdout.write(self.style.SUCCESS('Index initialized successfully'))

            # Index all non-draft notices
            self.stdout.write(self.style.WARNING('Indexing all notices...'))
            notices = Notice.objects.filter(is_draft=False)
            indexed_count = 0

            for notice in notices:
                doc = NoticeDocument(
                    meta={'id': notice.id},
                    title=notice.title,
                    is_draft=notice.is_draft,
                    id=notice.id,
                )
                doc.save()
                indexed_count += 1

            self.stdout.write(self.style.SUCCESS(f'Successfully indexed {indexed_count} notices'))

        except Exception as e:
            raise CommandError(f'Failed to rebuild search index: {e}')
