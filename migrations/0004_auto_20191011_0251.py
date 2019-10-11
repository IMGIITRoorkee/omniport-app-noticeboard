# Generated by Django 2.2.3 on 2019-10-10 21:21

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.KERNEL_PERSON_MODEL),
        ('noticeboard', '0003_auto_20191005_1127'),
    ]

    operations = [
        migrations.AddField(
            model_name='expirednotice',
            name='uploader',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='uploaded_notices_expired', to=settings.KERNEL_PERSON_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='notice',
            name='uploader',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='uploaded_notices', to=settings.KERNEL_PERSON_MODEL),
            preserve_default=False,
        ),
    ]
