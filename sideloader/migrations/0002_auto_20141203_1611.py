# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sideloader', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='build_script',
            field=models.CharField(default=b'', max_length=255),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='project',
            name='package_name',
            field=models.CharField(default=b'', max_length=255),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='project',
            name='postinstall_script',
            field=models.CharField(default=b'', max_length=255),
            preserve_default=True,
        ),
    ]
