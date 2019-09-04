# Generated by Django 2.2.3 on 2019-09-04 00:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('noticeboard', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='expirednotice',
            name='is_important',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='notice',
            name='is_important',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='permissions',
            name='is_super_uploader',
            field=models.BooleanField(default=False),
        ),
    ]
