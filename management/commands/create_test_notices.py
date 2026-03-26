from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import swapper

from noticeboard.models import Notice, Banner


class Command(BaseCommand):
    help = 'Create test notices for testing the search feature'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=30,
            help='Number of notices to create (default: 30)',
        )

    def handle(self, *args, **options):
        count = options['count']
        
        # Get the first available banner, or create one if needed
        try:
            banner = Banner.objects.first()
            if not banner:
                self.stdout.write(self.style.ERROR('No banners found in the system.'))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error getting banner: {e}'))
            return

        # Get or create a test user
        Person = swapper.get_model_name('kernel', 'Person')
        try:
            # Try to get the first person (usually admin)
            from kernel.models import Person as PersonModel
            uploader = PersonModel.objects.first()
            if not uploader:
                self.stdout.write(self.style.ERROR('No users found in the system.'))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error getting user: {e}'))
            return

        created_count = 0
        expiry_date = (timezone.now() + timedelta(days=30)).date()

        # Create 30 notices with unique titles
        test_titles = [
            "Academic Calendar Update",
            "Library Reopens After Renovation",
            "New Scholarship Opportunities",
            "Campus Wi-Fi Maintenance Schedule",
            "Examination Hall Allocation",
            "Hostel Room Allocation Process",
            "Sports Day Registration Open",
            "Workshop on Machine Learning",
            "Cultural Festival Planning Committee",
            "Internship Fair Announcement",
            "Student Council Elections",
            "Class Representative Meeting",
            "University Convocation Dates",
            "Research Paper Submission Deadline",
            "Placement Drive Schedule",
            "Department Seminar Series",
            "Alumni Meet Planning",
            "Environmental Awareness Campaign",
            "Health Insurance Renewal",
            "Library Book Issue Limit Change",
            "Campus Security Notice",
            "Parking Lot Reservation",
            "Cafeteria Menu Update",
            "IT Support New Helpdesk",
            "Building Maintenance Work",
            "Guest Lecturer Series",
            "Field Trip Announcement",
            "Exam Result Publication",
            "Fee Submission Deadline",
            "Academic Performance Awards",
        ]

        for i, title in enumerate(test_titles[:count]):
            try:
                notice = Notice.objects.create(
                    title=title,
                    content=f"<p>This is test notice #{i+1}: {title}</p><p>Content for testing search functionality.</p>",
                    banner=banner,
                    uploader=uploader,
                    expiry_date=expiry_date,
                    is_draft=False,
                    is_public=True,
                )
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created notice {created_count}: "{title}"')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Failed to create notice: {e}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\n✓ Successfully created {created_count} test notices!')
        )
