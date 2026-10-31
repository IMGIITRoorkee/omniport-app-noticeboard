from django.db import migrations

from noticeboard.utils.push_topics import ROOT_SLUG, send_directly


def mark_existing_categories(apps, schema_editor):
    Category = apps.get_model('categories', 'Category')
    for category in Category.objects.filter(slug__startswith=ROOT_SLUG):
        if send_directly(category):
            category.save(update_fields=['meta'])


class Migration(migrations.Migration):

    dependencies = [
        ('noticeboard', '0002_expirednotice_notice_created_on'),
        ('categories', '0002_category_meta'),
    ]

    operations = [
        migrations.RunPython(
            mark_existing_categories, migrations.RunPython.noop
        ),
    ]
