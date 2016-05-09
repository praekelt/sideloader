# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sideloader', '0007_auto_20151107_0831'),
    ]

    operations = [
        migrations.CreateModel(
            name='WebHook',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.CharField(max_length=255)),
                ('url', models.CharField(max_length=255)),
                ('method', models.CharField(max_length=4)),
                ('content_type', models.CharField(max_length=255)),
                ('payload', models.TextField(blank=True)),
                ('after', models.ForeignKey(blank=True, to='sideloader.WebHook', null=True)),
                ('flow', models.ForeignKey(to='sideloader.ReleaseFlow')),
            ],
        ),
    ]
